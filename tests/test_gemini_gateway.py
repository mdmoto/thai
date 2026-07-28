"""Gemini credential-priority and Vertex fallback tests."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from agents.gemini_gateway import ATTRIBUTE_NAMES, GeminiAgentGateway


def _response(representative_id: str):
    return {
        "responses": [
            {
                "representative_id": representative_id,
                "awareness_probability": 0.4,
                "consideration_probability": 0.3,
                "purchase_barriers": ["price"],
                "preferred_competitor": None,
                "attribute_importance": {
                    name: 0.5 for name in ATTRIBUTE_NAMES
                },
                "qualitative_reason": "价格与可信度需要进一步比较。",
                "confidence": 0.7,
                "sentiment": "neutral",
                "preferred_channel": "marketplace",
            }
        ]
    }


class GeminiGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def test_api_keys_are_prioritized_before_vertex_adc(self):
        gateway = GeminiAgentGateway(
            api_keys=["AQ.primary-test", "AIza-secondary-test"],
            vertex_fallback=True,
        )
        gateway.vertex_project = "test-project"
        representatives = [
            {
                "representative_id": "rep_1",
                "expansion_weight": 1.0,
            }
        ]

        with patch.object(
            gateway,
            "_call_provider",
            new=AsyncMock(
                side_effect=[
                    RuntimeError("primary unavailable"),
                    _response("rep_1"),
                ]
            ),
        ) as call:
            result = await gateway.generate_research_signals(
                product_info={"brand_awareness": 0.1},
                business_questions=["是否值得购买？"],
                representatives=representatives,
                plan_code="BASIC_DECISION",
            )

        self.assertEqual(result["status"], "available")
        self.assertEqual(call.await_count, 2)
        self.assertEqual(
            [item["mode"] for item in result["provider_chain"]],
            ["vertex_express", "gemini_developer", "vertex_adc"],
        )
        self.assertEqual(
            result["providers_used"],
            [{"id": "api_key_2", "mode": "gemini_developer"}],
        )
        self.assertEqual(
            result["provider_failures"][0]["id"],
            "api_key_1",
        )

    async def test_no_credentials_returns_honest_unavailable_status(self):
        gateway = GeminiAgentGateway(
            api_keys=[],
            vertex_fallback=False,
        )
        result = await gateway.generate_research_signals(
            product_info={},
            business_questions=[],
            representatives=[{"representative_id": "rep_1"}],
            plan_code="BASIC_DECISION",
        )
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["sample_size_completed"], 0)
        self.assertEqual(result["responses"], [])


if __name__ == "__main__":
    unittest.main()
