"""Gemini gateway for structured, bounded representative-consumer signals.

The gateway produces weak labels and qualitative evidence.  It never returns a
purchase rate for direct aggregation, and it never silently substitutes fixed
mock personas when the provider is unavailable.
"""

import json
import os
from typing import Any, Dict, List, Mapping, Optional, Sequence

import numpy as np
from google import genai
from google.genai import types

from simulation_core.config import get_plan_config


PROMPT_VERSION = "P-AGENT-STRUCTURED-2026.07.2"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL_STANDARD = os.environ.get(
    "GEMINI_MODEL_STANDARD",
    "gemini-3.5-flash-lite",
)
GEMINI_MODEL_DEEP = os.environ.get(
    "GEMINI_MODEL_DEEP",
    "gemini-3.6-flash",
)

ATTRIBUTE_NAMES = (
    "price",
    "quality",
    "trust",
    "warranty",
    "design",
    "convenience",
    "social_proof",
)

RESPONSE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "responses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "representative_id": {"type": "string"},
                    "awareness_probability": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                    },
                    "consideration_probability": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                    },
                    "purchase_barriers": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "price",
                                "brand_trust",
                                "reviews",
                                "localization",
                                "warranty",
                                "delivery",
                                "product_fit",
                                "location",
                                "competition",
                                "none",
                            ],
                        },
                    },
                    "preferred_competitor": {
                        "type": ["string", "null"],
                    },
                    "attribute_importance": {
                        "type": "object",
                        "properties": {
                            name: {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1,
                            }
                            for name in ATTRIBUTE_NAMES
                        },
                        "required": list(ATTRIBUTE_NAMES),
                        "additionalProperties": False,
                    },
                    "qualitative_reason": {"type": "string"},
                    "confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                    },
                    "sentiment": {
                        "type": "string",
                        "enum": ["positive", "neutral", "negative"],
                    },
                    "preferred_channel": {"type": "string"},
                },
                "required": [
                    "representative_id",
                    "awareness_probability",
                    "consideration_probability",
                    "purchase_barriers",
                    "preferred_competitor",
                    "attribute_importance",
                    "qualitative_reason",
                    "confidence",
                    "sentiment",
                    "preferred_channel",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["responses"],
    "additionalProperties": False,
}


def _clamp(value: Any, low: float = 0.0, high: float = 1.0) -> float:
    return float(np.clip(float(value), low, high))


class GeminiAgentGateway:
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_keys: Optional[Sequence[str]] = None,
        vertex_fallback: Optional[bool] = None,
    ):
        configured_keys = list(api_keys) if api_keys is not None else []
        if api_key is not None:
            configured_keys.insert(0, api_key)
        if api_key is None and api_keys is None:
            configured_keys = [
                os.environ.get("GEMINI_API_KEY_PRIMARY", ""),
                os.environ.get("GEMINI_API_KEY_SECONDARY", ""),
                os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY),
            ]
        self.api_keys = []
        for key in configured_keys:
            normalized = str(key or "").strip()
            if normalized and normalized not in self.api_keys:
                self.api_keys.append(normalized)
        self.api_key = self.api_keys[0] if self.api_keys else ""
        configured_vertex = os.environ.get(
            "GEMINI_VERTEX_FALLBACK",
            "",
        ).lower()
        self.vertex_fallback = (
            vertex_fallback
            if vertex_fallback is not None
            else configured_vertex in {"1", "true", "yes", "on"}
        )
        self.vertex_project = os.environ.get(
            "GOOGLE_CLOUD_PROJECT",
            "",
        ).strip()
        self.vertex_location = os.environ.get(
            "GOOGLE_CLOUD_LOCATION",
            "global",
        ).strip()

    def select_model(self, plan_code: str = "PROFESSIONAL") -> str:
        plan = get_plan_config(plan_code)
        if plan.code in {
            "BASIC_DECISION",
            "PROFESSIONAL",
            "DEEP",
            "ENTERPRISE",
        }:
            return GEMINI_MODEL_DEEP
        return GEMINI_MODEL_STANDARD

    def _unavailable_result(
        self,
        plan_code: str,
        model: str,
        requested: int,
        reason: str,
    ) -> Dict[str, Any]:
        return {
            "status": "unavailable",
            "source_type": "none",
            "prompt_version": PROMPT_VERSION,
            "model_id": model,
            "plan_code": get_plan_config(plan_code).code,
            "sample_size_requested": requested,
            "sample_size_completed": 0,
            "responses": [],
            "aggregate": {},
            "errors": [reason],
            "quantitative_policy": (
                "No LLM output was used. The quantitative model remains driven "
                "by the calibration profile and discrete-choice engine."
            ),
        }

    def _profile_for_prompt(self, profile: Mapping[str, Any]) -> Dict[str, Any]:
        allowed = (
            "representative_id",
            "age_group",
            "gender",
            "region",
            "province",
            "income_tier",
            "disposable_income_thb",
            "is_tourist",
            "price_sensitivity",
            "brand_sensitivity",
            "novelty_seeking",
            "review_sensitivity",
            "convenience_preference",
            "social_influence",
            "local_brand_trust",
            "online_affinity",
            "promptpay_preference",
            "cod_preference",
            "category_engagement",
            "distance_km",
        )
        return {
            key: profile[key]
            for key in allowed
            if key in profile and profile[key] is not None
        }

    def _build_prompt(
        self,
        product_info: Mapping[str, Any],
        business_questions: Sequence[str],
        profiles: Sequence[Mapping[str, Any]],
    ) -> str:
        return (
            "You are producing structured weak labels for a Thailand market "
            "choice model. Evaluate each supplied representative independently. "
            "Do not invent a population purchase rate, sales forecast, sample "
            "count, or statistical confidence interval. Do not expose hidden "
            "chain-of-thought; provide only a concise observable reason. "
            "Probabilities describe awareness and consideration hypotheses and "
            "will be given low weight until validated against observed data.\n\n"
            f"Offer and context:\n{json.dumps(product_info, ensure_ascii=False)}\n\n"
            f"Business questions:\n{json.dumps(list(business_questions), ensure_ascii=False)}\n\n"
            "Representative profiles:\n"
            f"{json.dumps([self._profile_for_prompt(item) for item in profiles], ensure_ascii=False)}\n\n"
            "Return one response for every representative_id using the required "
            "JSON schema. Evaluate Thai payment habits, local-brand trust, "
            "delivery, location, and named competitors only when supported by "
            "the supplied context."
        )

    def _providers(self) -> List[Dict[str, Any]]:
        providers: List[Dict[str, Any]] = []
        for index, key in enumerate(self.api_keys, start=1):
            providers.append(
                {
                    "id": f"api_key_{index}",
                    "mode": (
                        "vertex_express"
                        if key.startswith("AQ.")
                        else "gemini_developer"
                    ),
                    "api_key": key,
                }
            )
        if self.vertex_fallback and self.vertex_project:
            providers.append(
                {
                    "id": "vertex_service_account",
                    "mode": "vertex_adc",
                }
            )
        return providers

    @staticmethod
    def _provider_public(provider: Mapping[str, Any]) -> Dict[str, str]:
        return {
            "id": str(provider["id"]),
            "mode": str(provider["mode"]),
        }

    async def _call_provider(
        self,
        provider: Mapping[str, Any],
        model: str,
        prompt: str,
    ) -> Dict[str, Any]:
        mode = str(provider["mode"])
        http_options = types.HttpOptions(api_version="v1")
        if mode == "vertex_express":
            client = genai.Client(
                vertexai=True,
                api_key=str(provider["api_key"]),
                http_options=http_options,
            )
        elif mode == "gemini_developer":
            client = genai.Client(api_key=str(provider["api_key"]))
        elif mode == "vertex_adc":
            client = genai.Client(
                vertexai=True,
                project=self.vertex_project,
                location=self.vertex_location,
                http_options=http_options,
            )
        else:
            raise ValueError("Unsupported Gemini provider mode")

        async with client.aio as async_client:
            response = await async_client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_json_schema=RESPONSE_SCHEMA,
                    max_output_tokens=16_384,
                    temperature=0.2,
                ),
            )
        text_output = response.text
        if not text_output:
            raise ValueError("Gemini response contained no text")
        parsed = json.loads(text_output)
        if not isinstance(parsed, dict) or not isinstance(
            parsed.get("responses"),
            list,
        ):
            raise ValueError("Gemini response did not match the response schema")
        return parsed

    def _validate_response(
        self,
        response: Mapping[str, Any],
        valid_ids: Sequence[str],
    ) -> Optional[Dict[str, Any]]:
        representative_id = str(response.get("representative_id") or "")
        if representative_id not in valid_ids:
            return None

        importance = response.get("attribute_importance") or {}
        if not all(name in importance for name in ATTRIBUTE_NAMES):
            return None

        barriers = [
            str(item)
            for item in response.get("purchase_barriers", [])
            if isinstance(item, str)
        ][:5]
        return {
            "representative_id": representative_id,
            "awareness_probability": _clamp(
                response.get("awareness_probability", 0.0)
            ),
            "consideration_probability": _clamp(
                response.get("consideration_probability", 0.0)
            ),
            "purchase_barriers": barriers,
            "preferred_competitor": response.get("preferred_competitor"),
            "attribute_importance": {
                name: _clamp(importance[name])
                for name in ATTRIBUTE_NAMES
            },
            "qualitative_reason": str(
                response.get("qualitative_reason") or ""
            )[:800],
            "confidence": _clamp(response.get("confidence", 0.0)),
            "sentiment": (
                response.get("sentiment")
                if response.get("sentiment")
                in {"positive", "neutral", "negative"}
                else "neutral"
            ),
            "preferred_channel": str(
                response.get("preferred_channel") or "unspecified"
            )[:120],
        }

    def _aggregate(
        self,
        responses: Sequence[Mapping[str, Any]],
        profile_lookup: Mapping[str, Mapping[str, Any]],
        baseline_awareness: float,
    ) -> Dict[str, Any]:
        if not responses:
            return {}

        weights = np.array(
            [
                float(
                    profile_lookup[item["representative_id"]].get(
                        "expansion_weight",
                        1.0,
                    )
                )
                for item in responses
            ],
            dtype=float,
        )
        if weights.sum() <= 0:
            weights = np.ones(len(responses), dtype=float)

        awareness = np.array(
            [float(item["awareness_probability"]) for item in responses]
        )
        consideration = np.array(
            [float(item["consideration_probability"]) for item in responses]
        )
        confidence = np.array(
            [float(item["confidence"]) for item in responses]
        )
        importance = {
            name: float(
                np.average(
                    [item["attribute_importance"][name] for item in responses],
                    weights=weights,
                )
            )
            for name in ATTRIBUTE_NAMES
        }
        barrier_weight: Dict[str, float] = {}
        for item, weight in zip(responses, weights):
            for barrier in item["purchase_barriers"]:
                barrier_weight[barrier] = barrier_weight.get(barrier, 0.0) + float(
                    weight
                )
        total_weight = float(weights.sum())
        barrier_share = {
            key: round(value / total_weight, 4)
            for key, value in sorted(
                barrier_weight.items(),
                key=lambda pair: pair[1],
                reverse=True,
            )
        }
        return {
            "awareness_lift": round(
                _clamp(
                    float(np.average(awareness, weights=weights))
                    - baseline_awareness,
                    -0.25,
                    0.25,
                ),
                4,
            ),
            "consideration_hypothesis": round(
                float(np.average(consideration, weights=weights)),
                4,
            ),
            "attribute_importance": {
                key: round(value, 4)
                for key, value in importance.items()
            },
            "barrier_share": barrier_share,
            "confidence": round(
                float(np.average(confidence, weights=weights)),
                4,
            ),
        }

    async def generate_research_signals(
        self,
        product_info: Mapping[str, Any],
        business_questions: Sequence[str],
        representatives: Sequence[Mapping[str, Any]],
        plan_code: str = "PROFESSIONAL",
    ) -> Dict[str, Any]:
        plan = get_plan_config(plan_code)
        model = self.select_model(plan.code)
        selected = list(representatives)[: plan.representative_agents]
        requested = len(selected)
        providers = self._providers()

        if plan.representative_agents == 0:
            result = self._unavailable_result(
                plan.code,
                model,
                requested,
                "Representative LLM research is disabled for this plan.",
            )
            result["status"] = "disabled"
            return result
        if not providers:
            return self._unavailable_result(
                plan.code,
                model,
                requested,
                (
                    "No Gemini API key or Vertex service-account fallback is "
                    "configured; no mock personas were substituted."
                ),
            )
        if not selected:
            return self._unavailable_result(
                plan.code,
                model,
                requested,
                "No representative profiles were supplied.",
            )

        profile_lookup = {
            str(item["representative_id"]): item
            for item in selected
            if item.get("representative_id")
        }
        valid_ids = list(profile_lookup)
        responses: List[Dict[str, Any]] = []
        errors: List[str] = []
        provider_failures: List[Dict[str, str]] = []
        providers_used: List[Dict[str, str]] = []
        batch_size = 12
        active_provider_index = 0

        for start in range(0, len(selected), batch_size):
            batch = selected[start : start + batch_size]
            parsed: Optional[Dict[str, Any]] = None
            for provider_index in range(
                active_provider_index,
                len(providers),
            ):
                provider = providers[provider_index]
                try:
                    parsed = await self._call_provider(
                        provider,
                        model,
                        self._build_prompt(
                            product_info,
                            business_questions,
                            batch,
                        ),
                    )
                    active_provider_index = provider_index
                    public_provider = self._provider_public(provider)
                    if public_provider not in providers_used:
                        providers_used.append(public_provider)
                    break
                except Exception as error:
                    provider_failures.append(
                        {
                            **self._provider_public(provider),
                            "error": type(error).__name__,
                        }
                    )
                    active_provider_index = provider_index + 1
            if parsed is None:
                errors.append(
                    f"batch_{start // batch_size + 1}: all providers unavailable"
                )
                continue
            for raw_response in parsed["responses"]:
                validated = self._validate_response(
                    raw_response,
                    valid_ids,
                )
                if validated is not None:
                    responses.append(validated)

        deduplicated = {
            item["representative_id"]: item
            for item in responses
        }
        completed = list(deduplicated.values())
        baseline_awareness = _clamp(
            product_info.get("brand_awareness", 0.12),
            0.005,
            0.98,
        )
        status = (
            "available"
            if len(completed) == requested
            else "partial"
            if completed
            else "unavailable"
        )
        return {
            "status": status,
            "source_type": "llm_weak_label_not_observed_data",
            "prompt_version": PROMPT_VERSION,
            "model_id": model,
            "plan_code": plan.code,
            "sample_size_requested": requested,
            "sample_size_completed": len(completed),
            "responses": completed,
            "aggregate": self._aggregate(
                completed,
                profile_lookup,
                baseline_awareness,
            ),
            "errors": errors,
            "provider_chain": [
                self._provider_public(provider)
                for provider in providers
            ],
            "providers_used": providers_used,
            "provider_failures": provider_failures,
            "quantitative_policy": (
                "Signals receive a bounded plan-specific prior weight. They are "
                "never averaged into the final purchase rate."
            ),
        }

    async def generate_diverse_voices(
        self,
        product_info: Dict[str, Any],
        business_questions: List[str],
        plan_code: str = "PROFESSIONAL",
    ) -> List[Dict[str, Any]]:
        """Backward-compatible method with honest unavailable behavior."""
        result = await self.generate_research_signals(
            product_info,
            business_questions,
            representatives=[],
            plan_code=plan_code,
        )
        return result["responses"]
