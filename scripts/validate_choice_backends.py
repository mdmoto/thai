#!/usr/bin/env python3
"""Reproducible native-versus-Choice-Learn holdout validation."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from model_artifacts.base import ArtifactWriteRequest
from model_artifacts.local import LocalArtifactStore
from simulation_core.choice_backends.base import ChoiceFitRequest
from simulation_core.choice_backends.choice_learn import (
    ChoiceLearnModelBackend,
)
from simulation_core.choice_backends.native import (
    NativeChoiceModelBackend,
)


FEATURES = ("price_log_ratio", "quality_fit", "brand_trust")
TRUE_COEFFICIENTS = np.array([-1.35, 1.05, 0.55])


def generate_choices(seed: int, choice_sets: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows: list[dict[str, Any]] = []
    for choice_set_id in range(choice_sets):
        focal = np.array(
            [
                rng.uniform(0.55, 1.55),
                rng.uniform(0.15, 1.0),
                rng.uniform(0.1, 0.95),
            ]
        )
        competitor = np.array(
            [
                rng.uniform(0.55, 1.55),
                rng.uniform(0.15, 1.0),
                rng.uniform(0.1, 0.95),
            ]
        )
        feature_matrix = np.vstack(
            [np.zeros(len(FEATURES)), focal, competitor]
        )
        utilities = feature_matrix @ TRUE_COEFFICIENTS
        numerator = np.exp(utilities - utilities.max())
        probabilities = numerator / numerator.sum()
        chosen = int(rng.choice(3, p=probabilities))
        for index, (label, values) in enumerate(
            (
                ("outside", feature_matrix[0]),
                ("focal", feature_matrix[1]),
                ("competitor", feature_matrix[2]),
            )
        ):
            rows.append(
                {
                    "choice_set_id": choice_set_id,
                    "alternative": label,
                    "is_outside_option": label == "outside",
                    "chosen": int(chosen == index),
                    **{
                        feature: float(value)
                        for feature, value in zip(FEATURES, values)
                    },
                }
            )
    return pd.DataFrame(rows)


def holdout_metrics(
    backend: Any,
    fit_result: Any,
    holdout: pd.DataFrame,
) -> dict[str, float]:
    prediction = backend.predict(
        fit_result,
        holdout,
        FEATURES,
    )
    negative_log_likelihood: list[float] = []
    accurate: list[float] = []
    for (_, group), probabilities in zip(
        holdout.groupby("choice_set_id", sort=False),
        prediction.probabilities,
    ):
        chosen = int(np.flatnonzero(group["chosen"].to_numpy())[0])
        negative_log_likelihood.append(
            -float(np.log(max(probabilities[chosen], 1e-15)))
        )
        accurate.append(float(int(np.argmax(probabilities)) == chosen))
    return {
        "log_loss": float(np.mean(negative_log_likelihood)),
        "accuracy": float(np.mean(accurate)),
        "probability_sum_max_error": float(
            prediction.diagnostics[
                "choice_set_probability_sum_max_error"
            ]
        ),
    }


def fit_and_evaluate(
    backend: Any,
    train: pd.DataFrame,
    holdout: pd.DataFrame,
    seed: int,
    artifact_store: LocalArtifactStore,
) -> dict[str, Any]:
    started = time.perf_counter()
    result = backend.fit(
        ChoiceFitRequest(
            frame=train,
            feature_columns=FEATURES,
            study_type="PRODUCT_VALIDATION",
            seed=seed,
            validation_policy="synthetic_holdout_validation",
        )
    )
    fit_seconds = time.perf_counter() - started
    if result.artifact_payload is None:
        raise RuntimeError("Choice backend did not produce a fit artifact")
    descriptor = artifact_store.put(
        ArtifactWriteRequest(
            component_run_id=f"choice_validation_{seed}_{backend.backend_id}",
            artifact_type="choice_coefficients",
            payload=result.artifact_payload,
            media_type="application/json",
            schema_version="choice-fit-v1",
            suffix=".json",
            metadata=result.artifact_metadata,
        )
    )
    artifact_reference = descriptor.to_dict()
    artifact_reference["uri"] = descriptor.object_path
    artifact_reference["uri_type"] = "relative_to_artifact_directory"
    return {
        "backend": backend.backend_id,
        "backend_version": backend.backend_version,
        "fit_seconds": fit_seconds,
        "converged": result.fit.converged,
        "coefficients": result.fit.coefficients,
        "standard_errors": result.fit.standard_errors,
        "log_likelihood": result.fit.log_likelihood,
        "fit_diagnostics": dict(result.diagnostics),
        "holdout": holdout_metrics(
            backend,
            result,
            holdout,
        ),
        "artifact": artifact_reference,
    }


def run_validation(
    *,
    choice_sets: int,
    seeds: list[int],
    artifact_directory: Path,
) -> dict[str, Any]:
    artifact_store = LocalArtifactStore(artifact_directory)
    comparisons = []
    for seed in seeds:
        frame = generate_choices(seed, choice_sets)
        training_sets = int(choice_sets * 0.8)
        train = frame[frame["choice_set_id"] < training_sets].copy()
        holdout = frame[frame["choice_set_id"] >= training_sets].copy()
        native = fit_and_evaluate(
            NativeChoiceModelBackend(),
            train,
            holdout,
            seed,
            artifact_store,
        )
        choice_learn = fit_and_evaluate(
            ChoiceLearnModelBackend(),
            train,
            holdout,
            seed,
            artifact_store,
        )
        improvement = (
            native["holdout"]["log_loss"]
            - choice_learn["holdout"]["log_loss"]
        )
        comparisons.append(
            {
                "seed": seed,
                "training_choice_sets": training_sets,
                "holdout_choice_sets": choice_sets - training_sets,
                "native": native,
                "choice_learn": choice_learn,
                "choice_learn_log_loss_improvement": improvement,
            }
        )

    functional_pass = all(
        comparison["choice_learn"]["converged"]
        and comparison["choice_learn"]["coefficients"]["price_log_ratio"] < 0
        and comparison["choice_learn"]["coefficients"]["quality_fit"] > 0
        and comparison["choice_learn"]["holdout"][
            "probability_sum_max_error"
        ]
        < 1e-6
        and comparison["choice_learn"]["fit_diagnostics"][
            "outside_option_status"
        ]
        == "present_in_every_choice_set"
        for comparison in comparisons
    )
    improvements = [
        comparison["choice_learn_log_loss_improvement"]
        for comparison in comparisons
    ]
    materially_better = bool(
        functional_pass
        and np.mean(improvements) >= 0.002
        and sum(value > 0 for value in improvements)
        >= (len(improvements) // 2 + 1)
    )
    return {
        "schema_version": "choice-backend-validation-v1",
        "dataset": {
            "status": "synthetic_recovery_test_not_customer_evidence",
            "choice_sets_per_seed": choice_sets,
            "alternatives_per_set": 3,
            "features": list(FEATURES),
            "true_coefficients": {
                feature: float(value)
                for feature, value in zip(
                    FEATURES,
                    TRUE_COEFFICIENTS,
                )
            },
        },
        "comparisons": comparisons,
        "gate": {
            "functional_validation_passed": functional_pass,
            "choice_learn_materially_better": materially_better,
            "mean_holdout_log_loss_improvement": float(
                np.mean(improvements)
            ),
            "production_recommendation": (
                "candidate_for_real_observed_data_validation"
                if materially_better
                else "retain_native_default"
            ),
            "limitation": (
                "Synthetic recovery proves implementation behavior only. "
                "Production promotion requires customer observed-choice "
                "holdout and time-based validation."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--artifact-directory",
        type=Path,
        default=Path("/tmp/choice-validation-artifacts"),
    )
    parser.add_argument("--choice-sets", type=int, default=600)
    parser.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=[20260730, 20260731, 20260732],
    )
    arguments = parser.parse_args()
    report = run_validation(
        choice_sets=arguments.choice_sets,
        seeds=arguments.seeds,
        artifact_directory=arguments.artifact_directory,
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        "utf-8",
    )
    print(
        json.dumps(
            report["gate"],
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if report["gate"]["functional_validation_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
