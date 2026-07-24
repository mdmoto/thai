"""Versioned category eligibility and engagement profiles."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


DATA_CATALOG_ROOT = Path(
    os.environ.get(
        "DATA_CATALOG_ROOT",
        str(Path(__file__).resolve().parents[2] / "data_catalog"),
    )
)
CATEGORY_PROFILE_DIR = DATA_CATALOG_ROOT / "category_profiles"


def _normalize(value: Optional[str]) -> str:
    return " ".join(str(value or "").strip().upper().replace("-", " ").split())


def load_category_profile(category: Optional[str]) -> Dict[str, Any]:
    normalized = _normalize(category)
    for path in sorted(CATEGORY_PROFILE_DIR.glob("*.json")):
        profile = json.loads(path.read_text(encoding="utf-8"))
        aliases = {
            _normalize(profile.get("category_key")),
            *(_normalize(alias) for alias in profile.get("aliases", [])),
        }
        if normalized and normalized in aliases:
            return profile
    return {
        "schema_version": "1",
        "version": "GENERIC-CATEGORY-2026.07.1",
        "category_key": normalized.replace(" ", "_") or "GENERIC_CONSUMER_PRODUCT",
        "aliases": [],
        "eligibility": {
            "field": None,
            "status": "universal_population_assumption",
        },
        "engagement": {
            "online_purchase_weight": 1.0,
            "pet_spend_weight": 0.0,
            "status": "engineering_prior_not_choice_calibrated",
        },
        "limitations": [
            "No versioned category-specific eligibility profile was matched."
        ],
    }
