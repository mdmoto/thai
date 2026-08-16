"""Bounded visual-product evidence extraction for uploaded customer images."""

from __future__ import annotations

import base64
import json
import os
import re
from typing import Any, Dict, Mapping

import numpy as np
from google import genai
from google.genai import types


_DATA_URL = re.compile(r"^data:(image/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=]+)$")
_SCORE_FIELDS = (
    "quality_score",
    "design_score",
    "clarity_score",
    "localization_score",
    "brand_strength",
)
_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "appearance_summary": {"type": "string"},
        "visible_claims": {"type": "array", "items": {"type": "string"}},
        "visual_differentiators": {"type": "array", "items": {"type": "string"}},
        "trust_risks": {"type": "array", "items": {"type": "string"}},
        "scores": {
            "type": "object",
            "properties": {name: {"type": "number", "minimum": 0, "maximum": 1} for name in _SCORE_FIELDS},
            "required": list(_SCORE_FIELDS),
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["appearance_summary", "visible_claims", "visual_differentiators", "trust_risks", "scores", "confidence"],
}


def _keys() -> list[str]:
    values = [
        os.environ.get("GEMINI_API_KEY_PRIMARY", ""),
        os.environ.get("GEMINI_API_KEY_SECONDARY", ""),
        os.environ.get("GEMINI_API_KEY", ""),
    ]
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))


def _unavailable(status: str, reason: str) -> Dict[str, Any]:
    return {
        "status": status,
        "source_type": "customer_uploaded_image",
        "reason": reason,
        "scores": {},
        "attribute_overrides": {},
        "coefficient_effect": "none",
    }


async def analyze_product_image(
    data_url: str | None,
    product_name: str,
    category: str,
    plan_code: str,
) -> Dict[str, Any]:
    """Extract bounded attributes from an upload using a configured Gemini vision model."""

    if not data_url:
        return _unavailable("not_supplied", "未上传产品或素材图片。")
    match = _DATA_URL.match(data_url)
    if not match:
        return _unavailable("invalid_image", "上传图片格式无效。")
    keys = _keys()
    if not keys:
        return _unavailable("unavailable", "未配置 Gemini 视觉模型密钥。")
    try:
        image_bytes = base64.b64decode(match.group(2), validate=True)
    except ValueError:
        return _unavailable("invalid_image", "上传图片无法解码。")
    if not image_bytes or len(image_bytes) > 600_000:
        return _unavailable("invalid_image", "图片超过视觉分析安全大小限制。")

    prompt = (
        "You are a Thailand consumer-market visual evidence analyst. Analyze only "
        "what is visible in the customer-uploaded image. Do not infer sales, price, "
        "ratings, certifications, safety, or market share. Return concise Chinese JSON. "
        "Scores are weak visual impressions only, not measured consumer outcomes.\n\n"
        f"Product: {product_name[:200]}\nCategory: {category[:120]}\nPlan: {plan_code}\n"
        "Assess visible packaging, form factor, legibility, design differentiation, "
        "Thai-localization cues, and trust risks such as unreadable copy or unsupported claims."
    )
    model = os.environ.get("GEMINI_VISION_MODEL", "gemini-3.6-flash").strip()
    try:
        client = genai.Client(api_key=keys[0])
        async with client.aio as async_client:
            response = await async_client.models.generate_content(
                model=model,
                contents=[
                    prompt,
                    types.Part.from_bytes(data=image_bytes, mime_type=match.group(1)),
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_json_schema=_SCHEMA,
                    temperature=0.0,
                    max_output_tokens=1_500,
                ),
            )
        parsed = json.loads(response.text or "{}")
        raw_scores = parsed.get("scores") or {}
        scores = {
            name: float(np.clip(float(raw_scores.get(name, 0.5)), 0.0, 1.0))
            for name in _SCORE_FIELDS
        }
        # Vision is a weak, bounded input: no image can move an attribute by >0.15.
        overrides = {
            name: float(np.clip(0.5 + np.clip(value - 0.5, -0.15, 0.15), 0.0, 1.0))
            for name, value in scores.items()
        }
        return {
            "status": "analyzed",
            "source_type": "customer_uploaded_image",
            "model_id": model,
            "appearance_summary": str(parsed.get("appearance_summary") or "")[:1_200],
            "visible_claims": [str(item)[:240] for item in parsed.get("visible_claims", [])[:8]],
            "visual_differentiators": [str(item)[:240] for item in parsed.get("visual_differentiators", [])[:8]],
            "trust_risks": [str(item)[:240] for item in parsed.get("trust_risks", [])[:8]],
            "scores": scores,
            "attribute_overrides": overrides,
            "confidence": float(np.clip(float(parsed.get("confidence", 0.0)), 0.0, 1.0)),
            "coefficient_effect": "bounded_offer_attribute_update_only",
            "limitation": "图片视觉信号不等同于真实购买、销量、评分或安全认证。",
        }
    except Exception as error:  # Provider failures must not break a paid run.
        return _unavailable("failed", f"视觉模型调用失败：{str(error)[:240]}")
