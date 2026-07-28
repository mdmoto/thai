"""Calibration profile loading and validation.

The bundled profile is deliberately marked ``prior_only``.  It provides a
versioned, replaceable starting point for the model, not a claim that the
current coefficients were estimated from Thailand microdata.
"""

import copy
import json
import os
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


DATA_CATALOG_ROOT = Path(
    os.environ.get(
        "DATA_CATALOG_ROOT",
        str(Path(__file__).resolve().parents[2] / "data_catalog"),
    )
)
BASE_PRIOR_PROFILE_PATH = DATA_CATALOG_ROOT / "thailand_market_priors_v1.json"
CONSUMER_PRODUCTS_PROFILE_PATH = (
    DATA_CATALOG_ROOT / "thailand_consumer_products_macro_v1.json"
)
DEFAULT_PROFILE_PATH = (
    CONSUMER_PRODUCTS_PROFILE_PATH
    if CONSUMER_PRODUCTS_PROFILE_PATH.exists()
    else BASE_PRIOR_PROFILE_PATH
)


class CalibrationError(ValueError):
    """Raised when a calibration profile cannot be used safely."""


def _deep_merge(base: Dict[str, Any], override: Mapping[str, Any]) -> Dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _validate_distribution(name: str, values: Mapping[str, Any]) -> None:
    probabilities = [float(value) for value in values.values()]
    if any(value < 0 for value in probabilities):
        raise CalibrationError(f"{name} contains a negative probability")
    if abs(sum(probabilities) - 1.0) > 1e-6:
        raise CalibrationError(f"{name} probabilities must sum to 1.0")


def validate_profile(profile: Mapping[str, Any]) -> None:
    for required in ("version", "status", "population", "study_models", "dynamics"):
        if required not in profile:
            raise CalibrationError(f"Calibration profile is missing '{required}'")

    population = profile["population"]
    for distribution_name in ("age_group", "gender", "region", "income_tier"):
        if distribution_name not in population:
            raise CalibrationError(
                f"Calibration profile is missing population.{distribution_name}"
            )
        _validate_distribution(
            f"population.{distribution_name}",
            population[distribution_name],
        )

    for study_type, model in profile["study_models"].items():
        coefficients = model.get("coefficients", {})
        if not coefficients:
            raise CalibrationError(f"{study_type} has no coefficient priors")
        for coefficient_name, prior in coefficients.items():
            if "mean" not in prior or "sd" not in prior:
                raise CalibrationError(
                    f"{study_type}.{coefficient_name} requires mean and sd"
                )
            if float(prior["sd"]) < 0:
                raise CalibrationError(
                    f"{study_type}.{coefficient_name} has a negative sd"
                )


def load_calibration_profile(
    path: Optional[str] = None,
    overrides: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    profile_path = Path(path) if path else DEFAULT_PROFILE_PATH
    with profile_path.open("r", encoding="utf-8") as handle:
        profile = json.load(handle)

    if overrides:
        override_status = str(
            overrides.get("status", "customer_override_unvalidated")
        )
        profile = _deep_merge(profile, overrides)
        profile["base_profile_version"] = profile.get("version")
        profile["version"] = f"{profile.get('version', 'unknown')}+override"
        profile["status"] = override_status

    validate_profile(profile)
    return profile


def get_study_model(profile: Mapping[str, Any], study_type: str) -> Dict[str, Any]:
    normalized = (study_type or "PRODUCT_VALIDATION").upper()
    models = profile["study_models"]
    if normalized in models:
        return copy.deepcopy(models[normalized])
    return copy.deepcopy(models["PRODUCT_VALIDATION"])


def calibration_summary(profile: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "profile_version": profile["version"],
        "status": profile["status"],
        "claim": profile.get("claim"),
        "sources": copy.deepcopy(profile.get("sources", [])),
        "limitations": copy.deepcopy(profile.get("limitations", [])),
    }
