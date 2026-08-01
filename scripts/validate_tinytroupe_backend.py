#!/usr/bin/env python3
"""Validate the bounded TinyTroupe qualitative-research adapter."""

from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

from agents.backends.base import RepresentativeResearchRequest
from agents.backends.tinytroupe import (
    ATTRIBUTE_NAMES,
    PERSONA_FIELDS,
    PRODUCT_FIELDS,
    TINY_TROUPE_BACKEND_VERSION,
    TINY_TROUPE_COMMIT,
    TinyTroupeRepresentativeResearchBackend,
)


def _personas(count: int) -> list[dict[str, Any]]:
    profiles = [
        ("25-34", "Female", "North", "Chiang Mai", "MID_HIGH", 2, 0.82),
        ("35-44", "Male", "Bangkok", "Bangkok", "HIGH", 3, 0.91),
        ("18-24", "Female", "Northeast", "Khon Kaen", "MID", 4, 0.94),
        ("45-54", "Male", "Central", "Nonthaburi", "MID", 3, 0.63),
        ("25-34", "Male", "South", "Phuket", "MID_HIGH", 2, 0.87),
        ("55-64", "Female", "North", "Chiang Rai", "LOW_MID", 2, 0.42),
        ("35-44", "Female", "East", "Chon Buri", "MID_HIGH", 4, 0.78),
        ("18-24", "Male", "South", "Songkhla", "LOW_MID", 5, 0.89),
    ]
    personas = []
    for index in range(max(1, count)):
        (
            age,
            gender,
            region,
            province,
            income,
            household,
            online_affinity,
        ) = profiles[index % len(profiles)]
        personas.append(
            {
                "representative_id": f"TH_VALIDATION_{index + 1}",
                "age_group": age,
                "gender": gender,
                "region": region,
                "province": province,
                "income_tier": income,
                "household_size": household,
                "online_affinity": online_affinity,
                "category_engagement": round(0.55 + (index % 4) * 0.1, 2),
                "price_sensitivity": round(0.35 + (index % 5) * 0.1, 2),
                "local_brand_trust": round(0.45 + (index % 4) * 0.1, 2),
                "promptpay_preference": round(0.58 + (index % 4) * 0.1, 2),
                "cod_preference": round(0.18 + (index % 3) * 0.12, 2),
                "expansion_weight": 3_125.0,
                "email": "must-never-be-forwarded@example.com",
            }
        )
    return personas


def _request(persona_count: int = 1) -> RepresentativeResearchRequest:
    return RepresentativeResearchRequest(
        product_info={
            "product_name": "เครื่องให้น้ำสัตว์เลี้ยงอัจฉริยะ",
            "category": "pet water fountain",
            "price": 1_290,
            "reference_price": 1_590,
            "brand_awareness": 0.12,
            "selling_points": [
                "quiet pump",
                "replaceable filter",
                "local warranty",
            ],
            "scenarios": [
                {"scenario_id": "A", "price": 1_290},
                {"scenario_id": "B", "price": 1_090},
            ],
            "private_customer_token": "must-never-be-forwarded",
        },
        business_questions=[
            "Which proof would reduce purchase hesitation?",
            "Which buying channel feels most trustworthy?",
        ],
        representatives=_personas(persona_count),
        plan_code="PROFESSIONAL",
        seed=20260730,
    )


def _valid_response() -> dict[str, Any]:
    return {
        "representative_id": "TH_VALIDATION_1",
        "awareness_probability": 0.31,
        "consideration_probability": 0.58,
        "purchase_barriers": ["price", "filter replacement proof"],
        "preferred_competitor": None,
        "attribute_importance": {
            name: 0.5 for name in ATTRIBUTE_NAMES
        },
        "qualitative_reason": (
            "A clear local warranty and filter cost would reduce uncertainty."
        ),
        "confidence": 0.7,
        "sentiment": "neutral",
        "preferred_channel": "Lazada official store",
    }


async def _technical_validation() -> dict[str, Any]:
    captured: dict[str, Any] = {}

    def runner(personas, product, questions, provider, seed):
        captured["personas"] = personas
        captured["product"] = product
        return {
            "responses": [_valid_response()],
            "usage": {
                "input_tokens": 500,
                "output_tokens": 250,
                "total_tokens": 750,
                "model_calls": 2,
                "cached_calls": 0,
            },
            "budget_stop": None,
        }

    environment = {
        "ENABLE_TINYTROUPE": "true",
        "TINY_TROUPE_PROVIDER": "gemini_openai",
        "GEMINI_API_KEY": "validation-placeholder-not-sent",
    }
    with patch.dict(os.environ, environment, clear=True):
        result = await TinyTroupeRepresentativeResearchBackend(
            runner=runner,
            maximum_agents=1,
        ).research(_request())
    persona_fields = set(captured["personas"][0])
    product_fields = set(captured["product"])
    checks = {
        "official_package_imported": (
            importlib.metadata.version("tinytroupe") == "0.7.0"
        ),
        "structured_output_accepted": result.status == "available",
        "persona_input_whitelisted": persona_fields <= set(PERSONA_FIELDS),
        "product_input_whitelisted": product_fields <= set(PRODUCT_FIELDS),
        "sensitive_persona_field_removed": (
            "email" not in captured["personas"][0]
        ),
        "sensitive_product_field_removed": (
            "private_customer_token" not in captured["product"]
        ),
        "quantitative_signal_disabled": (
            result.payload["agent_signal_weight"] == 0.0
            and result.payload["aggregate"]["confidence"] == 0.0
        ),
        "usage_accounting_present": (
            result.payload["budget"]["observed_usage"]["total_tokens"] == 750
        ),
        "seeded_randomization_recorded": bool(
            result.payload["experiment"]["randomization"]
        ),
    }
    return {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "backend_version": TINY_TROUPE_BACKEND_VERSION,
        "tinytroupe_commit": TINY_TROUPE_COMMIT,
        "tinytroupe_package_version": importlib.metadata.version(
            "tinytroupe"
        ),
        "result_lineage": result.lineage(),
    }


def _read_gcp_secret(secret_name: str, project: str | None) -> str:
    command = [
        "gcloud",
        "secrets",
        "versions",
        "access",
        "latest",
        f"--secret={secret_name}",
    ]
    if project:
        command.append(f"--project={project}")
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return completed.stdout.strip()


async def _live_validation(
    secret_name: str | None,
    project: str | None,
    persona_count: int,
    vertex_fallback: bool,
) -> dict[str, Any]:
    api_key = os.environ.get("GEMINI_API_KEY_PRIMARY", "").strip()
    credential_source = "environment"
    if not api_key and secret_name:
        api_key = _read_gcp_secret(secret_name, project)
        credential_source = "gcp_secret_manager"
    if not api_key:
        return {
            "status": "skipped",
            "reason": "no_gemini_credential",
        }
    vertex_access_token = None
    if vertex_fallback:
        vertex_access_token = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout.strip()
    environment = {
        "ENABLE_TINYTROUPE": "true",
        "TINY_TROUPE_PROVIDER": "gemini_openai",
        "GEMINI_API_KEY_PRIMARY": api_key,
        "TINY_TROUPE_MODEL": os.environ.get(
            "TINY_TROUPE_MODEL",
            "gemini-3.6-flash",
        ),
        "TINY_TROUPE_MAX_AGENTS": str(persona_count),
        "TINY_TROUPE_MAX_TOTAL_TOKENS": str(
            max(25_000, persona_count * 15_000)
        ),
        "TINY_TROUPE_MAX_MODEL_CALLS": str(
            max(8, persona_count * 3)
        ),
        "TINY_TROUPE_MAX_COST_USD": str(
            max(1.0, persona_count * 0.10)
        ),
        "TINY_TROUPE_MAX_WALL_SECONDS": "1800",
    }
    if vertex_fallback and project and vertex_access_token:
        environment.update(
            {
                "GEMINI_VERTEX_FALLBACK": "true",
                "GOOGLE_CLOUD_PROJECT": project,
                "GOOGLE_CLOUD_LOCATION": "global",
                "TINY_TROUPE_VERTEX_MODEL": (
                    "google/gemini-3.6-flash"
                ),
                "TINY_TROUPE_VERTEX_ACCESS_TOKEN": (
                    vertex_access_token
                ),
            }
        )
    started = time.perf_counter()
    with patch.dict(os.environ, environment, clear=True):
        result = await TinyTroupeRepresentativeResearchBackend(
            maximum_agents=persona_count,
            timeout_seconds=1800,
        ).research(_request(persona_count))
    response = (
        result.payload.get("responses", [{}])[0]
        if result.payload.get("responses")
        else {}
    )
    return {
        "status": result.status,
        "credential_source": credential_source,
        "credential_value_recorded": False,
        "wall_time_seconds": time.perf_counter() - started,
        "provider": result.payload.get("provider"),
        "sample_size_completed": result.payload.get(
            "sample_size_completed",
            0,
        ),
        "sample_size_requested": persona_count,
        "usage": result.payload.get("budget", {}).get(
            "observed_usage",
            {},
        ),
        "paid_list_price_estimate_usd": result.payload.get(
            "budget",
            {},
        ).get("paid_list_price_estimate_usd"),
        "billable_output_tokens_for_cost_estimate": result.payload.get(
            "budget",
            {},
        ).get("billable_output_tokens_for_cost_estimate"),
        "errors": result.payload.get("errors", []),
        "structured_response_fields": sorted(response),
        "quantitative_signal_weight": result.payload.get(
            "agent_signal_weight"
        ),
        "quality_diagnostics": result.payload.get(
            "quality_diagnostics",
            {},
        ),
    }


async def run_validation(
    *,
    live: bool,
    secret_name: str | None,
    project: str | None,
    live_personas: int,
    vertex_fallback: bool,
) -> dict[str, Any]:
    technical = await _technical_validation()
    live_result = (
        await _live_validation(
            secret_name,
            project,
            live_personas,
            vertex_fallback,
        )
        if live
        else {"status": "not_requested"}
    )
    live_passed = live_result["status"] == "available"
    return {
        "schema_version": "tinytroupe-backend-validation-v1",
        "technical_validation": technical,
        "live_provider_validation": live_result,
        "gate": {
            "technical_validation_passed": technical["status"] == "passed",
            "live_provider_validation_passed": live_passed,
            "production_enabled": False,
            "production_recommendation": (
                "retain_gemini_default_pending_quality_holdout"
                if live_passed
                else "retain_gemini_default_pending_live_compatibility"
            ),
            "limitation": (
                "TinyTroupe responses remain qualitative hypotheses with "
                "zero quantitative signal weight. Promotion requires a "
                "blinded quality comparison and repeated live reliability."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--gcp-secret-name")
    parser.add_argument("--gcp-project")
    parser.add_argument("--live-personas", type=int, default=1)
    parser.add_argument("--vertex-fallback", action="store_true")
    arguments = parser.parse_args()
    report = asyncio.run(
        run_validation(
            live=arguments.live,
            secret_name=arguments.gcp_secret_name,
            project=arguments.gcp_project,
            live_personas=max(1, arguments.live_personas),
            vertex_fallback=arguments.vertex_fallback,
        )
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["gate"], ensure_ascii=False, indent=2))
    return 0 if report["gate"]["technical_validation_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
