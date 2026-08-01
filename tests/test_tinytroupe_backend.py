"""Safety and contract tests for optional TinyTroupe qualitative research."""

from __future__ import annotations

import os
import time
import unittest
from unittest.mock import patch

from agents.backends.base import RepresentativeResearchRequest
from agents.backends.gemini import get_representative_research_backend
from agents.backends.tinytroupe import (
    ATTRIBUTE_NAMES,
    TinyTroupeRepresentativeResearchBackend,
)


def _persona(identifier: str = "TH_1") -> dict:
    return {
        "representative_id": identifier,
        "age_group": "25-34",
        "gender": "Female",
        "region": "North",
        "province": "Chiang Mai",
        "income_tier": "MID_HIGH",
        "household_size": 2,
        "online_affinity": 0.8,
        "category_engagement": 0.7,
        "price_sensitivity": 0.4,
        "local_brand_trust": 0.6,
        "promptpay_preference": 0.9,
        "cod_preference": 0.2,
        "expansion_weight": 3_125.0,
        "email": "must-not-leave-system@example.com",
        "payment_reference": "must-not-leave-system",
    }


def _valid_response(identifier: str = "TH_1") -> dict:
    return {
        "representative_id": identifier,
        "awareness_probability": 0.4,
        "consideration_probability": 0.6,
        "purchase_barriers": ["price", "trust"],
        "preferred_competitor": None,
        "attribute_importance": {
            name: 0.5 for name in ATTRIBUTE_NAMES
        },
        "qualitative_reason": "The value is plausible but warranty proof matters.",
        "confidence": 0.8,
        "sentiment": "neutral",
        "preferred_channel": "TikTok Shop",
    }


class TinyTroupeBackendTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.request = RepresentativeResearchRequest(
            product_info={
                "product_name": "Pet fountain",
                "price": 1290,
                "scenarios": [
                    {"scenario_id": "A", "name": "A"},
                    {"scenario_id": "B", "name": "B"},
                    {"scenario_id": "C", "name": "C"},
                ],
                "private_customer_token": "must-not-leave-system",
            },
            business_questions=["Would you buy this?"],
            representatives=[_persona()],
            plan_code="PROFESSIONAL",
            seed=73,
        )

    async def test_disabled_or_missing_credential_returns_no_fake_signal(self):
        runner_calls = []

        def runner(*args):
            runner_calls.append(args)
            return [_valid_response()]

        with patch.dict(os.environ, {}, clear=True):
            result = await TinyTroupeRepresentativeResearchBackend(
                runner=runner
            ).research(self.request)
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.payload["sample_size_completed"], 0)
        self.assertEqual(result.payload["responses"], [])
        self.assertEqual(result.payload["agent_signal_weight"], 0.0)
        self.assertEqual(runner_calls, [])

    async def test_valid_result_is_qualitative_and_inputs_are_whitelisted(self):
        captured = {}

        def runner(personas, product, questions, provider, seed):
            captured["personas"] = personas
            captured["product"] = product
            captured["seed"] = seed
            return [_valid_response()]

        environment = {
            "ENABLE_TINYTROUPE": "true",
            "TINY_TROUPE_PROVIDER": "gemini_openai",
            "GEMINI_API_KEY": "test-only-key",
        }
        with patch.dict(os.environ, environment, clear=True):
            result = await TinyTroupeRepresentativeResearchBackend(
                runner=runner
            ).research(self.request)
        self.assertEqual(result.status, "available")
        self.assertEqual(result.payload["sample_size_completed"], 1)
        self.assertEqual(result.payload["agent_signal_weight"], 0.0)
        self.assertEqual(
            result.payload["aggregate"]["confidence"],
            0.0,
        )
        self.assertNotIn("email", captured["personas"][0])
        self.assertNotIn("payment_reference", captured["personas"][0])
        self.assertNotIn("private_customer_token", captured["product"])
        self.assertTrue(result.diagnostics["persona_fields_immutable"])
        self.assertEqual(
            result.payload["budget"]["maximum_total_tokens"],
            1_200_000,
        )
        self.assertEqual(
            result.payload["budget"]["paid_list_price_estimate_usd"],
            None,
        )

    async def test_runner_usage_and_budget_stop_are_reported(self):
        environment = {
            "ENABLE_TINYTROUPE": "true",
            "GEMINI_API_KEY": "test-only-key",
            "TINY_TROUPE_MAX_TOTAL_TOKENS": "1234",
            "TINY_TROUPE_MAX_MODEL_CALLS": "7",
        }

        def runner(*args):
            return {
                "responses": [_valid_response()],
                "usage": {
                    "input_tokens": 800,
                    "output_tokens": 300,
                    "total_tokens": 1100,
                    "model_calls": 3,
                    "cached_calls": 0,
                },
                "budget_stop": "token_or_model_call_budget_exceeded",
            }

        with patch.dict(os.environ, environment, clear=True):
            result = await TinyTroupeRepresentativeResearchBackend(
                runner=runner
            ).research(self.request)
        self.assertEqual(result.status, "available")
        self.assertEqual(
            result.payload["budget"]["observed_usage"]["total_tokens"],
            1100,
        )
        self.assertEqual(
            result.payload["budget"]["stop_reason"],
            "token_or_model_call_budget_exceeded",
        )
        self.assertAlmostEqual(
            result.payload["budget"]["paid_list_price_estimate_usd"],
            0.00345,
        )

    async def test_invalid_json_shape_is_rejected_as_partial_failure(self):
        environment = {
            "ENABLE_TINYTROUPE": "true",
            "GEMINI_API_KEY": "test-only-key",
        }
        with patch.dict(os.environ, environment, clear=True):
            result = await TinyTroupeRepresentativeResearchBackend(
                runner=lambda *args: [{"representative_id": "TH_1"}],
            ).research(self.request)
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.payload["sample_size_completed"], 0)
        self.assertIn("invalid_schema", result.payload["errors"][0])

    async def test_duplicate_persona_response_is_rejected(self):
        environment = {
            "ENABLE_TINYTROUPE": "true",
            "GEMINI_API_KEY": "test-only-key",
        }
        with patch.dict(os.environ, environment, clear=True):
            result = await TinyTroupeRepresentativeResearchBackend(
                runner=lambda *args: [
                    _valid_response(),
                    _valid_response(),
                ],
            ).research(self.request)
        self.assertEqual(result.status, "available")
        self.assertEqual(result.payload["sample_size_completed"], 1)
        self.assertIn("duplicate_persona", result.payload["errors"][0])

    async def test_wall_time_budget_fails_closed(self):
        def slow_runner(*args):
            time.sleep(0.03)
            return [_valid_response()]

        environment = {
            "ENABLE_TINYTROUPE": "true",
            "GEMINI_API_KEY": "test-only-key",
        }
        with patch.dict(os.environ, environment, clear=True):
            result = await TinyTroupeRepresentativeResearchBackend(
                runner=slow_runner,
                timeout_seconds=0.001,
            ).research(self.request)
        self.assertEqual(result.status, "unavailable")
        self.assertIn("wall_time_budget_exceeded", result.payload["errors"])

    async def test_ab_order_is_seeded_and_reproducible(self):
        captured_orders = []

        def runner(personas, product, questions, provider, seed):
            captured_orders.append(
                [item["scenario_id"] for item in product["scenarios"]]
            )
            return [_valid_response()]

        environment = {
            "ENABLE_TINYTROUPE": "true",
            "GEMINI_API_KEY": "test-only-key",
        }
        backend = TinyTroupeRepresentativeResearchBackend(runner=runner)
        with patch.dict(os.environ, environment, clear=True):
            first = await backend.research(self.request)
            second = await backend.research(self.request)
        self.assertEqual(captured_orders[0], captured_orders[1])
        self.assertEqual(
            first.payload["experiment"]["randomization"],
            second.payload["experiment"]["randomization"],
        )

    def test_factory_supports_off_and_tinytroupe(self):
        self.assertEqual(
            get_representative_research_backend("off").backend_id,
            "off",
        )
        self.assertEqual(
            get_representative_research_backend("tinytroupe").backend_id,
            "tinytroupe",
        )

    def test_provider_keeps_secondary_key_as_failover(self):
        environment = {
            "ENABLE_TINYTROUPE": "true",
            "GEMINI_API_KEY_PRIMARY": "primary-test-key",
            "GEMINI_API_KEY_SECONDARY": "secondary-test-key",
        }
        with patch.dict(os.environ, environment, clear=True):
            provider = TinyTroupeRepresentativeResearchBackend._provider()
        self.assertIsNotNone(provider)
        self.assertEqual(
            provider.api_keys,
            ("primary-test-key", "secondary-test-key"),
        )

    def test_provider_can_use_vertex_without_api_key(self):
        environment = {
            "ENABLE_TINYTROUPE": "true",
            "GEMINI_VERTEX_FALLBACK": "true",
            "GOOGLE_CLOUD_PROJECT": "test-project",
            "GOOGLE_CLOUD_LOCATION": "global",
        }
        with patch.dict(os.environ, environment, clear=True):
            provider = TinyTroupeRepresentativeResearchBackend._provider()
        self.assertIsNotNone(provider)
        self.assertEqual(provider.api_keys, ())
        self.assertTrue(provider.vertex_configured)
        self.assertEqual(
            provider.vertex_model,
            "google/gemini-3.6-flash",
        )


if __name__ == "__main__":
    unittest.main()
