"""Create deterministic Phase 0 report baselines.

The reports deliberately use the PREVIEW execution plan, disabled external
research, fixed inputs, and a fixed seed. Volatile identifiers and timestamps
are replaced before the JSON is written so later adapter changes can be
compared without network or provider noise.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from app.services.study_service import StudyService


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = REPO_ROOT / "docs" / "baselines" / "phase0"
SEED = 42
POPULATION_SIZE = 100
MC_ROUNDS = 40

CASES: dict[str, dict[str, Any]] = {
    "pet_water_product_validation": {
        "name": "Phase 0 · 宠物智能饮水机产品验证",
        "study_type": "PRODUCT_VALIDATION",
        "plan_code": "PREVIEW",
        "product_name": "QuietFlow",
        "category": "PET_WATER_FOUNTAIN",
        "price": 1290,
        "selling_points": ["静音", "本地保修"],
    },
    "generic_pricing_study": {
        "name": "Phase 0 · 通用消费品定价研究",
        "study_type": "PRICING_STUDY",
        "plan_code": "PREVIEW",
        "product_name": "Everyday Product",
        "category": "GENERIC_CONSUMER_PRODUCT",
        "price": 499,
        "reference_price": 499,
        "competitor_data": [
            {
                "name": "Reference Competitor",
                "price": 459,
                "awareness": 0.55,
                "quality_score": 0.6,
            }
        ],
    },
    "nimman_cafe_venue": {
        "name": "Phase 0 · 宁曼路咖啡馆研究",
        "study_type": "VENUE_STUDY",
        "plan_code": "PREVIEW",
        "product_name": "CMAI Cafe",
        "category": "GENERIC_CONSUMER_PRODUCT",
        "venue_type": "CAFE",
        "average_check": 220,
        "capacity": 48,
        "location": {
            "label": "Chiang Mai, Nimman Road",
            "latitude": 18.7966,
            "longitude": 98.9677,
        },
    },
}


def _canonicalize(report: dict[str, Any]) -> dict[str, Any]:
    def normalize(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: (
                    f"BASELINE_{key.upper()}"
                    if key
                    in {
                        "generated_at",
                        "started_at",
                        "completed_at",
                        "collected_at",
                    }
                    else normalize(item)
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [normalize(item) for item in value]
        return value

    canonical = normalize(report)
    canonical["report_id"] = "BASELINE_REPORT_ID"
    canonical["run_id"] = "BASELINE_RUN_ID"
    canonical["study_id"] = "BASELINE_STUDY_ID"
    canonical["generated_at"] = "BASELINE_GENERATED_AT"
    return canonical


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


async def _run_case(case: dict[str, Any]) -> dict[str, Any]:
    service = StudyService()
    study = service.create_study(case)
    service.confirm_study(study["id"], {})
    report = await service.execute_run(
        study["id"],
        pop_size=POPULATION_SIZE,
        mc_rounds=MC_ROUNDS,
        seed=SEED,
        plan_code="PREVIEW",
    )
    return _canonicalize(report)


async def main() -> None:
    os.environ["MARKET_RESEARCH_ENABLED"] = "false"
    os.environ["GEO_RESEARCH_ENABLED"] = "false"
    os.environ["GEMINI_API_KEY_PRIMARY"] = ""
    os.environ["GEMINI_API_KEY_SECONDARY"] = ""
    os.environ["GEMINI_API_KEY"] = ""
    os.environ["GEMINI_VERTEX_FALLBACK"] = "false"
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    manifest_cases: list[dict[str, Any]] = []
    for case_id, case in CASES.items():
        report = await _run_case(case)
        payload = (
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
        report_path = OUTPUT_ROOT / f"{case_id}.report.json"
        report_path.write_bytes(payload)
        manifest_cases.append(
            {
                "case_id": case_id,
                "input": case,
                "seed": SEED,
                "population_size": POPULATION_SIZE,
                "mc_rounds": MC_ROUNDS,
                "report_path": str(report_path.relative_to(REPO_ROOT)),
                "report_sha256": _sha256(payload),
                "key_metrics": {
                    "purchase_rate": report["metric_intervals"][
                        "purchase_rate"
                    ]["mean"],
                    "purchase_p10": report["metric_intervals"][
                        "purchase_rate"
                    ]["p10"],
                    "purchase_p90": report["metric_intervals"][
                        "purchase_rate"
                    ]["p90"],
                    "best_scenario": report["executive_summary"][
                        "best_scenario"
                    ],
                },
            }
        )

    manifest = {
        "schema_version": "1",
        "baseline_id": "PHASE0-2026-07-30",
        "world_model_version": manifest_cases[0] and report[
            "world_model_version"
        ],
        "simulation_model_version": manifest_cases[0] and report[
            "simulation_model_version"
        ],
        "plan_config_version": report["model_lineage"][
            "plan_config_version"
        ],
        "external_research": "disabled",
        "llm_research": "disabled",
        "cases": manifest_cases,
    }
    manifest_payload = (
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    (OUTPUT_ROOT / "manifest.json").write_bytes(manifest_payload)


if __name__ == "__main__":
    asyncio.run(main())
