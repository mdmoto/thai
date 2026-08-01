"""Optional PopulationSim balancing backend for isolated technical validation."""

from __future__ import annotations

import io
import json
import os
import resource
import sys
import time
from typing import Any

import numpy as np
import pandas as pd

from data_pipeline.population_synthesis import (
    build_population_synthesis_inputs,
    control_comparison,
)
from model_artifacts.base import ArtifactWriteRequest, ModelArtifactStore
from world_model.backends.base import (
    PopulationSynthesisRequest,
    PopulationSynthesisResult,
)
from world_model.generator import PopulationGenerator


POPULATION_SIM_BACKEND_VERSION = "populationsim-adapter-1"


class PopulationBackendUnavailable(RuntimeError):
    """Raised before balancing when PopulationSim is not installed."""


def _load_list_balancer() -> Any:
    try:
        from populationsim.balancing import ListBalancer
    except ImportError as error:
        raise PopulationBackendUnavailable(
            "PopulationSim backend is unavailable in this image"
        ) from error
    return ListBalancer


class PopulationSimSynthesisBackend:
    backend_id = "population_sim"
    backend_version = POPULATION_SIM_BACKEND_VERSION

    def __init__(
        self,
        artifact_store: ModelArtifactStore | None = None,
        seed_sample_size: int | None = None,
        max_iterations: int = 1_000,
        use_numba: bool = True,
    ) -> None:
        self.artifact_store = artifact_store
        self.seed_sample_size = seed_sample_size
        self.max_iterations = int(max_iterations)
        self.use_numba = bool(use_numba)

    def generate(
        self,
        request: PopulationSynthesisRequest,
    ) -> PopulationSynthesisResult:
        started = time.perf_counter()
        list_balancer = _load_list_balancer()
        seed_size = self.seed_sample_size or int(
            os.environ.get(
                "POPULATION_SIM_SEED_SIZE",
                request.population_size,
            )
        )
        if seed_size <= 0:
            raise ValueError("PopulationSim seed sample size must be positive")
        generator = PopulationGenerator(
            seed=request.seed,
            calibration_profile=request.calibration_profile,
        )
        seed_population = generator.generate(
            size=seed_size,
            study_type=request.study_type,
            category=request.category,
        )
        inputs = build_population_synthesis_inputs(
            seed_population,
            request.calibration_profile,
            request.population_size,
            request.seed,
        )
        initial_weight = request.population_size / float(seed_size)
        balancer = list_balancer(
            incidence_table=inputs.incidence,
            initial_weights=np.full(seed_size, initial_weight),
            control_totals=inputs.controls,
            control_importance_weights=np.full(
                len(inputs.controls),
                100_000.0,
            ),
            lb_weights=np.full(seed_size, max(initial_weight * 0.01, 1e-6)),
            ub_weights=np.full(seed_size, initial_weight * 100.0),
            master_control_index=0,
            max_iterations=self.max_iterations,
            use_numba=self.use_numba,
            numba_precision="float64",
        )
        status, weights, _ = balancer.balance()
        final_weights = weights["final"].to_numpy(dtype=float)
        comparison = control_comparison(
            inputs.incidence,
            final_weights,
            inputs.controls,
        )
        population = seed_population.copy()
        population["sample_weight"] = final_weights
        population["calibration_status"] = (
            "synthetic_seed_joint_calibration"
        )
        population["population_backend"] = self.backend_id

        median_weight = float(np.median(final_weights))
        maximum_weight = float(final_weights.max())
        minimum_weight = float(final_weights.min())
        extreme_ratio = (
            maximum_weight / median_weight
            if median_weight > 0
            else float("inf")
        )
        effective_sample_size = float(
            final_weights.sum() ** 2
            / np.square(final_weights).sum()
        )
        non_total = comparison[
            comparison["control"] != "total_persons"
        ]
        regional_errors = comparison[
            comparison["control"].str.startswith("region__")
        ]
        peak_rss = int(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        )
        peak_rss_bytes = (
            peak_rss
            if sys.platform == "darwin"
            else peak_rss * 1_024
        )
        diagnostics = {
            "synthetic_population_rows": len(population),
            "represented_population_weight": float(final_weights.sum()),
            "target_population": int(request.population_size),
            "seed_sample_status": (
                "synthetic_seed_not_observed_microdata"
            ),
            "control_totals_version": request.control_totals_version,
            "seed_sample_version": inputs.manifest["dataset_id"],
            "geography_level": request.geography_level,
            "output_schema_version": request.output_schema_version,
            "seed": request.seed,
            "converged": bool(status["converged"]),
            "iterations": int(status["iter"]),
            "maximum_absolute_percentage_point_error": float(
                non_total["absolute_percentage_point_error"].max()
            ),
            "weighted_mean_absolute_percentage_point_error": float(
                np.average(
                    non_total["absolute_percentage_point_error"],
                    weights=non_total["target"].clip(lower=1.0),
                )
            ),
            "total_population_error_percent": float(
                comparison.loc[
                    comparison["control"] == "total_persons",
                    "absolute_percentage_point_error",
                ].iloc[0]
            ),
            "minimum_weight": minimum_weight,
            "median_weight": median_weight,
            "maximum_weight": maximum_weight,
            "maximum_to_median_weight_ratio": extreme_ratio,
            "effective_sample_size": effective_sample_size,
            "effective_sample_share": (
                effective_sample_size / len(population)
            ),
            "zero_weight_rows": int((final_weights <= 0).sum()),
            "zero_control_cells": int(
                (
                    (comparison["target"] > 0)
                    & (comparison["generated"] <= 0)
                ).sum()
            ),
            "regional_control_errors_pp": {
                str(row["control"]): float(
                    row["absolute_percentage_point_error"]
                )
                for _, row in regional_errors.iterrows()
            },
            "runtime_seconds_before_artifact_write": (
                time.perf_counter() - started
            ),
            "process_peak_rss_bytes": peak_rss_bytes,
            "households_rows": 0,
            "persons_rows": len(population),
            "persons_without_household": len(population),
            "household_person_consistency_status": (
                "not_available_synthetic_decision_unit_seed"
            ),
            "unmet_constraints": [
                "No household identifier or household-member relationship exists in the synthetic seed.",
                "No observed Thai joint microdistribution is available for validation.",
            ],
        }
        limitations = list(inputs.manifest["limitations"])
        if extreme_ratio > 20:
            limitations.append(
                "Extreme expansion weights exceed the 20x median warning threshold."
            )
        artifacts = self._write_artifacts(
            request,
            population,
            comparison,
            inputs.manifest,
            diagnostics,
        )
        return PopulationSynthesisResult(
            population=population,
            backend_id=self.backend_id,
            backend_version=self.backend_version,
            status="synthetic_seed_joint_calibration",
            diagnostics=diagnostics,
            artifacts=artifacts,
            limitations=limitations,
            runtime_context=generator,
        )

    def stratified_sample(
        self,
        result: PopulationSynthesisResult,
        sample_size: int,
        seed: int,
    ) -> pd.DataFrame:
        generator = result.runtime_context
        if not isinstance(generator, PopulationGenerator):
            raise RuntimeError(
                "PopulationSim result is missing its sampling context"
            )
        return generator.stratified_sample(
            result.population,
            sample_size,
            seed=seed,
        )

    def _write_artifacts(
        self,
        request: PopulationSynthesisRequest,
        population: pd.DataFrame,
        comparison: pd.DataFrame,
        manifest: dict[str, Any],
        diagnostics: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if self.artifact_store is None:
            return []
        run_id = (
            f"population_{request.seed}_"
            f"{manifest['manifest_sha256'][:16]}"
        )
        parquet_buffer = io.BytesIO()
        population.to_parquet(parquet_buffer, index=False)
        persons = population[
            [
                "person_id",
                "region",
                "province",
                "gender",
                "age_group",
                "income_tier",
                "household_size",
                "household_monthly_income_thb",
                "sample_weight",
            ]
        ].copy()
        persons["household_id"] = pd.Series(
            pd.NA,
            index=persons.index,
            dtype="string",
        )
        persons["consistency_status"] = (
            "unavailable_no_household_relationship"
        )
        persons_buffer = io.BytesIO()
        persons.to_parquet(persons_buffer, index=False)
        households = pd.DataFrame(
            {
                "household_id": pd.Series(dtype="string"),
                "household_size": pd.Series(dtype="int64"),
                "household_monthly_income_thb": pd.Series(dtype="float64"),
                "region": pd.Series(dtype="string"),
                "province": pd.Series(dtype="string"),
                "consistency_status": pd.Series(dtype="string"),
            }
        )
        households_buffer = io.BytesIO()
        households.to_parquet(households_buffer, index=False)
        run_manifest = {
            **manifest,
            "backend": self.backend_id,
            "backend_version": self.backend_version,
            "calibration_status": (
                "synthetic_seed_joint_calibration"
            ),
            "output_artifacts": [
                "population.parquet",
                "persons.parquet",
                "households.parquet",
                "control_comparison.csv",
                "calibration_diagnostics.json",
            ],
            "household_person_consistency_status": (
                "not_available_synthetic_decision_unit_seed"
            ),
        }
        payloads = (
            (
                "population",
                parquet_buffer.getvalue(),
                "application/vnd.apache.parquet",
                "population-v1",
                ".parquet",
            ),
            (
                "persons",
                persons_buffer.getvalue(),
                "application/vnd.apache.parquet",
                "persons-v1",
                ".parquet",
            ),
            (
                "households",
                households_buffer.getvalue(),
                "application/vnd.apache.parquet",
                "households-v1",
                ".parquet",
            ),
            (
                "control_comparison",
                comparison.to_csv(index=False).encode("utf-8"),
                "text/csv",
                "population-controls-v1",
                ".csv",
            ),
            (
                "calibration_diagnostics",
                json.dumps(
                    diagnostics,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8"),
                "application/json",
                "population-diagnostics-v1",
                ".json",
            ),
            (
                "population_run_manifest",
                json.dumps(
                    run_manifest,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8"),
                "application/json",
                "population-input-manifest-v1",
                ".json",
            ),
        )
        return [
            self.artifact_store.put(
                ArtifactWriteRequest(
                    component_run_id=run_id,
                    artifact_type=artifact_type,
                    payload=payload,
                    media_type=media_type,
                    schema_version=schema_version,
                    suffix=suffix,
                    metadata={
                        "backend": self.backend_id,
                        "backend_version": self.backend_version,
                    },
                )
            ).to_dict()
            for (
                artifact_type,
                payload,
                media_type,
                schema_version,
                suffix,
            ) in payloads
        ]
