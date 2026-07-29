"""Privacy-preserving pooled calibration from observed-choice fits.

Raw customer rows, customer identifiers, study identifiers, and report
contents never enter this table.  A contribution contains only a category,
study type, sample counts, fitted coefficients, and standard errors.
"""

from __future__ import annotations

import hashlib
import math
import os
from typing import Any, Dict, Mapping, Optional, Sequence

import numpy as np
from sqlalchemy.orm import Session

from app.db.models import CalibrationContribution


COEFFICIENT_BOUNDS = {
    "price_log_ratio": (-5.0, -0.02),
    "distance_friction": (-5.0, 0.25),
    "affordability": (-1.0, 5.0),
    "quality_fit": (-1.0, 5.0),
    "brand_trust": (-1.0, 5.0),
    "review_proof": (-1.0, 5.0),
    "novelty": (-2.0, 5.0),
    "convenience": (-1.0, 5.0),
    "social_influence": (-1.0, 5.0),
    "category_engagement": (-1.0, 5.0),
    "localization": (-1.0, 5.0),
}


def _finite_mapping(value: Any) -> Dict[str, float]:
    if not isinstance(value, Mapping):
        return {}
    output: Dict[str, float] = {}
    for key, raw in value.items():
        try:
            number = float(raw)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            output[str(key)] = number
    return output


def _weighted_median(
    values: Sequence[float],
    weights: Sequence[float],
) -> float:
    order = np.argsort(np.asarray(values, dtype=float))
    sorted_values = np.asarray(values, dtype=float)[order]
    sorted_weights = np.asarray(weights, dtype=float)[order]
    cutoff = float(sorted_weights.sum()) / 2.0
    position = int(np.searchsorted(np.cumsum(sorted_weights), cutoff))
    return float(sorted_values[min(position, len(sorted_values) - 1)])


def record_platform_contribution(
    db: Session,
    report: Mapping[str, Any],
) -> Optional[CalibrationContribution]:
    """Add one de-identified contribution for a genuine observed-choice fit."""
    lineage = report.get("model_lineage") or {}
    estimation = lineage.get("choice_estimation") or {}
    diagnostics = estimation.get("diagnostics") or {}
    if estimation.get("status") != "applied_unvalidated":
        return None
    if not diagnostics.get("converged"):
        return None

    coefficients = _finite_mapping(diagnostics.get("coefficients"))
    standard_errors = _finite_mapping(diagnostics.get("standard_errors"))
    coefficients = {
        name: float(np.clip(value, *COEFFICIENT_BOUNDS[name]))
        for name, value in coefficients.items()
        if name in COEFFICIENT_BOUNDS
    }
    standard_errors = {
        name: max(1e-6, value)
        for name, value in standard_errors.items()
        if name in coefficients
    }
    choice_sets = int(diagnostics.get("choice_sets") or 0)
    observations = int(diagnostics.get("observations") or 0)
    category_key = str(report.get("category_key") or "").strip().upper()
    study_type = str(
        estimation.get("study_type")
        or report.get("study_type")
        or ""
    ).strip().upper()
    report_id = str(report.get("report_id") or "")
    if (
        not coefficients
        or choice_sets < 20
        or observations < choice_sets * 2
        or not category_key
        or not study_type
        or not report_id
    ):
        return None

    source_digest = hashlib.sha256(
        f"platform-calibration:{report_id}".encode("utf-8")
    ).hexdigest()
    existing = (
        db.query(CalibrationContribution)
        .filter(CalibrationContribution.source_digest == source_digest)
        .first()
    )
    if existing:
        return existing
    contribution = CalibrationContribution(
        source_digest=source_digest,
        category_key=category_key,
        study_type=study_type,
        choice_set_count=choice_sets,
        observation_count=observations,
        coefficients_json=coefficients,
        standard_errors_json=standard_errors,
    )
    db.add(contribution)
    return contribution


def platform_calibration_override(
    db: Session,
    category_key: str,
    study_type: str,
) -> Optional[Dict[str, Any]]:
    """Build a pooled override only after the privacy and volume thresholds."""
    normalized_category = str(category_key or "").strip().upper()
    normalized_study_type = str(study_type or "").strip().upper()
    contributions = (
        db.query(CalibrationContribution)
        .filter(
            CalibrationContribution.category_key == normalized_category,
            CalibrationContribution.study_type == normalized_study_type,
        )
        .order_by(CalibrationContribution.created_at.desc())
        .limit(500)
        .all()
    )
    minimum_contributions = max(
        3,
        int(os.environ.get("PLATFORM_CALIBRATION_MIN_CONTRIBUTIONS", "5")),
    )
    minimum_choice_sets = max(
        100,
        int(os.environ.get("PLATFORM_CALIBRATION_MIN_CHOICE_SETS", "500")),
    )
    total_choice_sets = sum(item.choice_set_count for item in contributions)
    if (
        len(contributions) < minimum_contributions
        or total_choice_sets < minimum_choice_sets
    ):
        return None

    pooled: Dict[str, Dict[str, Any]] = {}
    for coefficient_name, bounds in COEFFICIENT_BOUNDS.items():
        values = []
        errors = []
        weights = []
        for item in contributions:
            coefficient = (item.coefficients_json or {}).get(
                coefficient_name
            )
            if coefficient is None:
                continue
            error = (item.standard_errors_json or {}).get(
                coefficient_name,
                0.1,
            )
            values.append(float(coefficient))
            errors.append(max(1e-6, float(error)))
            weights.append(float(max(1, item.choice_set_count)))
        if len(values) < minimum_contributions:
            continue
        center = float(np.clip(_weighted_median(values, weights), *bounds))
        absolute_deviation = [
            abs(value - center) for value in values
        ]
        robust_spread = 1.4826 * _weighted_median(
            absolute_deviation,
            weights,
        )
        pooled_error = _weighted_median(errors, weights)
        pooled[coefficient_name] = {
            "mean": round(center, 8),
            "sd": round(max(0.03, robust_spread, pooled_error), 8),
            "source": "pooled_platform_choice_benchmark_unvalidated",
        }
    if not pooled:
        return None

    return {
        "status": "platform_category_benchmark_unvalidated",
        "claim": (
            "Choice coefficients use a pooled, de-identified category "
            "benchmark derived from observed-choice fits. The pooled benchmark "
            "has not yet passed out-of-sample or time-based validation."
        ),
        "study_models": {
            normalized_study_type: {
                "coefficients": pooled,
            }
        },
        "platform_benchmark": {
            "category_key": normalized_category,
            "contribution_count": len(contributions),
            "choice_set_count": total_choice_sets,
            "minimum_contributions": minimum_contributions,
            "minimum_choice_sets": minimum_choice_sets,
            "privacy_status": (
                "deidentified_aggregate_coefficients_no_raw_customer_rows"
            ),
            "validation_status": "out_of_sample_validation_required",
        },
    }


def platform_calibration_summary(db: Session) -> Dict[str, Any]:
    rows = db.query(CalibrationContribution).all()
    cohorts: Dict[tuple[str, str], Dict[str, Any]] = {}
    for item in rows:
        key = (item.category_key, item.study_type)
        cohort = cohorts.setdefault(
            key,
            {
                "category_key": item.category_key,
                "study_type": item.study_type,
                "contribution_count": 0,
                "choice_set_count": 0,
            },
        )
        cohort["contribution_count"] += 1
        cohort["choice_set_count"] += int(item.choice_set_count)
    return {
        "total_contributions": len(rows),
        "cohorts": sorted(
            cohorts.values(),
            key=lambda item: (
                -int(item["contribution_count"]),
                str(item["category_key"]),
            ),
        ),
        "privacy_status": (
            "deidentified_aggregate_coefficients_no_raw_customer_rows"
        ),
    }
