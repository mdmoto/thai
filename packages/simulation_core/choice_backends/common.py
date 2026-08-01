"""Shared validation, prediction and artifact helpers for choice backends."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from simulation_core.estimation import ConditionalLogitFit


def validate_choice_frame(
    frame: pd.DataFrame,
    feature_columns: Sequence[str],
    choice_set_column: str,
    chosen_column: str,
) -> None:
    required = set(feature_columns) | {choice_set_column, chosen_column}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Choice data is missing columns: {sorted(missing)}")
    if frame.empty:
        raise ValueError("Choice data must not be empty")
    if frame[list(feature_columns)].isnull().any().any():
        raise ValueError("Choice features contain missing values")
    values = frame[list(feature_columns)].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Choice features contain invalid numbers")
    chosen = frame[chosen_column].astype(int)
    if not chosen.isin([0, 1]).all():
        raise ValueError("chosen must contain only 0 and 1")
    chosen_per_set = frame.assign(_chosen=chosen).groupby(
        choice_set_column,
        sort=False,
    )["_chosen"].sum()
    if not (chosen_per_set == 1).all():
        raise ValueError("Every choice set must contain exactly one chosen row")
    alternatives_per_set = frame.groupby(
        choice_set_column,
        sort=False,
    ).size()
    if (alternatives_per_set < 2).any():
        raise ValueError("Every choice set must contain at least two alternatives")


def grouped_probabilities(
    frame: pd.DataFrame,
    feature_columns: Sequence[str],
    coefficients: Mapping[str, float],
    choice_set_column: str,
) -> tuple[list[str], list[list[float]]]:
    beta = np.array(
        [float(coefficients[name]) for name in feature_columns],
        dtype=float,
    )
    choice_set_ids: list[str] = []
    probabilities: list[list[float]] = []
    for choice_set_id, group in frame.groupby(
        choice_set_column,
        sort=False,
    ):
        utilities = group[list(feature_columns)].to_numpy(dtype=float) @ beta
        shifted = utilities - np.max(utilities)
        numerator = np.exp(np.clip(shifted, -40.0, 40.0))
        probabilities.append((numerator / numerator.sum()).tolist())
        choice_set_ids.append(str(choice_set_id))
    return choice_set_ids, probabilities


def alternative_labels(
    frame: pd.DataFrame,
    choice_set_column: str,
    alternative_column: str,
) -> list[list[str]]:
    labels: list[list[str]] = []
    for _, group in frame.groupby(choice_set_column, sort=False):
        if alternative_column in group:
            labels.append(
                [str(value) for value in group[alternative_column].tolist()]
            )
        else:
            labels.append(
                [f"option-{index + 1}" for index in range(len(group))]
            )
    return labels


def outside_option_status(
    frame: pd.DataFrame,
    choice_set_column: str,
    outside_option_column: str,
) -> str:
    if outside_option_column not in frame:
        return "missing_or_unidentified"
    marked = frame[outside_option_column].fillna(False).astype(bool)
    counts = frame.assign(_outside=marked).groupby(
        choice_set_column,
        sort=False,
    )["_outside"].sum()
    if (counts == 1).all():
        return "present_in_every_choice_set"
    if (counts > 1).any():
        return "invalid_multiple_outside_options"
    return "missing_in_some_choice_sets"


def probability_diagnostics(
    probabilities: Sequence[Sequence[float]],
) -> dict[str, Any]:
    sums = np.array([sum(group) for group in probabilities], dtype=float)
    values = np.array(
        [value for group in probabilities for value in group],
        dtype=float,
    )
    return {
        "choice_set_probability_sum_max_error": float(
            np.max(np.abs(sums - 1.0)) if len(sums) else 0.0
        ),
        "minimum_probability": float(values.min() if len(values) else 0.0),
        "maximum_probability": float(values.max() if len(values) else 0.0),
    }


def conditional_logit_diagnostics(
    frame: pd.DataFrame,
    feature_columns: Sequence[str],
    coefficients: Mapping[str, float],
    l2_penalty: float,
    choice_set_column: str,
    chosen_column: str,
) -> tuple[float, float, list[list[float]], dict[str, float]]:
    working = frame.reset_index(drop=True)
    matrix = working[list(feature_columns)].to_numpy(dtype=float)
    chosen = working[chosen_column].to_numpy(dtype=float)
    beta = np.array(
        [float(coefficients[name]) for name in feature_columns],
        dtype=float,
    )
    gradient = -float(l2_penalty) * beta
    negative_hessian = float(l2_penalty) * np.eye(len(feature_columns))
    log_likelihood = -0.5 * float(l2_penalty) * float(beta @ beta)
    for _, group in working.groupby(choice_set_column, sort=False):
        positions = group.index.to_numpy()
        group_matrix = matrix[positions]
        group_chosen = chosen[positions]
        utilities = group_matrix @ beta
        shifted = utilities - np.max(utilities)
        numerator = np.exp(np.clip(shifted, -40.0, 40.0))
        probabilities = numerator / numerator.sum()
        log_likelihood += float(
            np.sum(
                group_chosen
                * np.log(np.clip(probabilities, 1e-15, 1.0))
            )
        )
        gradient += group_matrix.T @ (group_chosen - probabilities)
        covariance = np.diag(probabilities) - np.outer(
            probabilities,
            probabilities,
        )
        negative_hessian += group_matrix.T @ covariance @ group_matrix
    covariance_matrix = np.linalg.pinv(negative_hessian)
    standard_errors = np.sqrt(
        np.clip(np.diag(covariance_matrix), 0.0, None)
    )
    return (
        float(log_likelihood),
        float(np.max(np.abs(gradient))),
        covariance_matrix.tolist(),
        {
            name: round(float(value), 8)
            for name, value in zip(feature_columns, standard_errors)
        },
    )


def canonical_choice_records(
    frame: pd.DataFrame,
    columns: Sequence[str],
) -> list[dict[str, Any]]:
    return json.loads(
        frame[list(columns)].to_json(
            orient="records",
            double_precision=15,
        )
    )


def choice_fit_artifact(
    *,
    fit: ConditionalLogitFit,
    backend_id: str,
    backend_version: str,
    request_payload: Mapping[str, Any],
    feature_columns: Sequence[str],
    seed: int,
    diagnostics: Mapping[str, Any],
    validation_status: str,
) -> tuple[bytes, dict[str, Any]]:
    training_bytes = json.dumps(
        request_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    training_sha256 = hashlib.sha256(training_bytes).hexdigest()
    payload = {
        "artifact_type": "choice_coefficients",
        "schema_version": "choice-fit-v1",
        "backend": backend_id,
        "backend_version": backend_version,
        "training_data_sha256": training_sha256,
        "feature_mapping": list(feature_columns),
        "seed": int(seed),
        "fit": fit.to_dict(),
        "diagnostics": dict(diagnostics),
        "validation_status": validation_status,
    }
    artifact_bytes = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return artifact_bytes, {
        "artifact_type": "choice_coefficients",
        "schema_version": "choice-fit-v1",
        "media_type": "application/json",
        "sha256": hashlib.sha256(artifact_bytes).hexdigest(),
        "size_bytes": len(artifact_bytes),
        "training_data_sha256": training_sha256,
    }
