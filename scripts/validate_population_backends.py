#!/usr/bin/env python3
"""Reproducible native-versus-PopulationSim population validation."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import time
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from model_artifacts.local import LocalArtifactStore
from simulation_core.calibration import load_calibration_profile
from world_model.backends.base import PopulationSynthesisRequest
from world_model.backends.native import NativePopulationSynthesisBackend
from world_model.backends.population_sim import (
    PopulationSimSynthesisBackend,
)


CONTROL_DIMENSIONS = ("region", "gender", "income_tier")
JOINT_DIMENSIONS = ("region", "gender", "income_tier")


def _margin_metrics(
    population: pd.DataFrame,
    profile: Mapping[str, Any],
) -> dict[str, Any]:
    weights = population.get(
        "sample_weight",
        pd.Series(np.ones(len(population)), index=population.index),
    ).to_numpy(dtype=float)
    total_weight = float(weights.sum())
    rows: list[dict[str, Any]] = []
    for dimension in CONTROL_DIMENSIONS:
        targets = profile["population"][dimension]
        labels = population[dimension].astype(str)
        for value, target_share in targets.items():
            generated_share = float(weights[labels == str(value)].sum())
            generated_share /= max(total_weight, 1.0)
            rows.append(
                {
                    "dimension": dimension,
                    "value": str(value),
                    "target_share": float(target_share),
                    "generated_share": generated_share,
                    "absolute_percentage_point_error": (
                        abs(generated_share - float(target_share)) * 100.0
                    ),
                }
            )
    errors = [
        row["absolute_percentage_point_error"]
        for row in rows
    ]
    return {
        "total_weight": total_weight,
        "maximum_absolute_percentage_point_error": float(max(errors)),
        "mean_absolute_percentage_point_error": float(np.mean(errors)),
        "controls": rows,
    }


def _joint_distribution(
    population: pd.DataFrame,
) -> dict[tuple[str, ...], float]:
    weights = population.get(
        "sample_weight",
        pd.Series(np.ones(len(population)), index=population.index),
    ).to_numpy(dtype=float)
    working = population.loc[:, JOINT_DIMENSIONS].astype(str).copy()
    working["_weight"] = weights
    grouped = working.groupby(
        list(JOINT_DIMENSIONS),
        observed=True,
    )["_weight"].sum()
    denominator = max(float(grouped.sum()), 1.0)
    return {
        tuple(str(part) for part in index): float(value / denominator)
        for index, value in grouped.items()
    }


def _joint_comparison(
    reference: Mapping[tuple[str, ...], float],
    candidate: Mapping[tuple[str, ...], float],
) -> dict[str, Any]:
    cells = sorted(set(reference) | set(candidate))
    absolute_differences = [
        abs(float(reference.get(cell, 0.0)) - float(candidate.get(cell, 0.0)))
        for cell in cells
    ]
    return {
        "dimensions": list(JOINT_DIMENSIONS),
        "reference_status": (
            "native_synthetic_reference_not_observed_joint_truth"
        ),
        "cell_count": len(cells),
        "candidate_missing_reference_cells": sum(
            cell in reference and cell not in candidate for cell in cells
        ),
        "total_variation_distance": float(
            0.5 * sum(absolute_differences)
        ),
        "maximum_cell_percentage_point_difference": float(
            max(absolute_differences, default=0.0) * 100.0
        ),
    }


def _relative_artifacts(
    artifacts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    relative = []
    for descriptor in artifacts:
        item = dict(descriptor)
        item["uri"] = item["object_path"]
        item["uri_type"] = "relative_to_artifact_directory"
        relative.append(item)
    return relative


def _run_seed(
    *,
    seed: int,
    population_size: int,
    seed_sample_size: int,
    profile: Mapping[str, Any],
    artifact_store: LocalArtifactStore,
) -> dict[str, Any]:
    request = PopulationSynthesisRequest(
        population_size=population_size,
        study_type="PRODUCT_VALIDATION",
        category="GENERIC_CONSUMER_PRODUCT",
        seed=seed,
        calibration_profile=profile,
        control_totals_version=str(profile.get("version")),
        seed_sample_version="native_synthetic_seed_same_profile",
        geography_level="province",
        output_schema_version="population-v1",
    )

    native_started = time.perf_counter()
    native = NativePopulationSynthesisBackend().generate(request)
    native_seconds = time.perf_counter() - native_started
    native_margins = _margin_metrics(native.population, profile)
    native_joint = _joint_distribution(native.population)

    candidate_started = time.perf_counter()
    candidate = PopulationSimSynthesisBackend(
        artifact_store=artifact_store,
        seed_sample_size=seed_sample_size,
        max_iterations=1_000,
        use_numba=True,
    ).generate(request)
    candidate_seconds = time.perf_counter() - candidate_started
    candidate_margins = _margin_metrics(candidate.population, profile)
    candidate_joint = _joint_distribution(candidate.population)

    return {
        "seed": seed,
        "target_population": population_size,
        "native": {
            "backend": native.backend_id,
            "backend_version": native.backend_version,
            "runtime_seconds": native_seconds,
            "population_rows": len(native.population),
            "margins": native_margins,
        },
        "population_sim": {
            "backend": candidate.backend_id,
            "backend_version": candidate.backend_version,
            "runtime_seconds": candidate_seconds,
            "population_rows": len(candidate.population),
            "status": candidate.status,
            "diagnostics": candidate.diagnostics,
            "margins": candidate_margins,
            "joint_against_native_synthetic_reference": _joint_comparison(
                native_joint,
                candidate_joint,
            ),
            "limitations": candidate.limitations,
            "artifacts": _relative_artifacts(candidate.artifacts),
        },
    }


def run_validation(
    *,
    population_size: int,
    seed_sample_size: int,
    seeds: list[int],
    artifact_directory: Path,
) -> dict[str, Any]:
    profile = load_calibration_profile()
    artifact_store = LocalArtifactStore(artifact_directory)
    comparisons = [
        _run_seed(
            seed=seed,
            population_size=population_size,
            seed_sample_size=seed_sample_size,
            profile=profile,
            artifact_store=artifact_store,
        )
        for seed in seeds
    ]
    candidate_max_errors = [
        item["population_sim"]["margins"][
            "maximum_absolute_percentage_point_error"
        ]
        for item in comparisons
    ]
    native_max_errors = [
        item["native"]["margins"][
            "maximum_absolute_percentage_point_error"
        ]
        for item in comparisons
    ]
    functional_pass = all(
        item["population_sim"]["diagnostics"]["converged"]
        and item["population_sim"]["diagnostics"][
            "total_population_error_percent"
        ]
        <= 0.001
        and item["population_sim"]["margins"][
            "maximum_absolute_percentage_point_error"
        ]
        <= 0.05
        and item["population_sim"]["diagnostics"]["minimum_weight"] > 0
        and item["population_sim"]["diagnostics"]["zero_weight_rows"] == 0
        and item["population_sim"]["diagnostics"][
            "maximum_to_median_weight_ratio"
        ]
        <= 20.0
        and item["population_sim"]["diagnostics"][
            "effective_sample_share"
        ]
        >= 0.80
        for item in comparisons
    )
    margin_improvement = float(
        np.mean(native_max_errors) - np.mean(candidate_max_errors)
    )
    materially_better_margins = bool(
        functional_pass
        and np.mean(candidate_max_errors)
        <= max(np.mean(native_max_errors) * 0.25, 0.001)
    )
    joint_preservation = all(
        item["population_sim"][
            "joint_against_native_synthetic_reference"
        ]["total_variation_distance"]
        <= 0.03
        for item in comparisons
    )
    return {
        "schema_version": "population-backend-validation-v1",
        "dataset": {
            "status": (
                "synthetic_technical_validation_not_observed_thai_microdata"
            ),
            "calibration_profile_version": profile.get("version"),
            "calibration_profile_status": profile.get("status"),
            "target_population": population_size,
            "population_rows_per_candidate": seed_sample_size,
            "controls": list(CONTROL_DIMENSIONS),
            "joint_diagnostic": list(JOINT_DIMENSIONS),
            "seeds": seeds,
        },
        "dependency_versions": {
            "populationsim": importlib.metadata.version("populationsim"),
            "numpy": importlib.metadata.version("numpy"),
            "pandas": importlib.metadata.version("pandas"),
            "pyarrow": importlib.metadata.version("pyarrow"),
        },
        "comparisons": comparisons,
        "gate": {
            "functional_validation_passed": functional_pass,
            "marginal_calibration_materially_better": (
                materially_better_margins
            ),
            "joint_distribution_preserved_against_synthetic_reference": (
                joint_preservation
            ),
            "mean_max_margin_error_native_pp": float(
                np.mean(native_max_errors)
            ),
            "mean_max_margin_error_population_sim_pp": float(
                np.mean(candidate_max_errors)
            ),
            "mean_max_margin_error_improvement_pp": margin_improvement,
            "household_person_consistency_validated": False,
            "observed_microdata_validated": False,
            "production_ready": False,
            "production_recommendation": (
                "retain_native_default_until_authorized_microdata_validation"
            ),
            "decision_basis": (
                "Effect quality gates only; runtime and compute cost are "
                "reported but are not rejection criteria."
            ),
            "limitation": (
                "PopulationSim can force aggregate margins to match, but the "
                "available seed contains independent synthetic decision units. "
                "It cannot validate household-person relationships or recover "
                "real Thai joint distributions without authorized microdata."
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--population-size", type=int, default=300_000)
    parser.add_argument("--seed-sample-size", type=int, default=300_000)
    parser.add_argument(
        "--seeds",
        default="20260730,20260731,20260732",
    )
    parser.add_argument(
        "--artifact-directory",
        type=Path,
        default=Path("docs/validation/population-artifacts"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/validation/populationsim-phase2.json"),
    )
    args = parser.parse_args()
    seeds = [
        int(value.strip())
        for value in args.seeds.split(",")
        if value.strip()
    ]
    report = run_validation(
        population_size=args.population_size,
        seed_sample_size=args.seed_sample_size,
        seeds=seeds,
        artifact_directory=args.artifact_directory,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["gate"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
