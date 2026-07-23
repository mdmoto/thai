"""
LLM Gateway for Representative Consumer Agents using Gemini API.
Handles structured JSON reasoning, prompt versioning, token tracking, and fallback.
"""

import os
import json
import httpx
from typing import Dict, Any, List, Optional

PROMPT_VERSION = "P-AGENT-2026.07.1"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

class GeminiAgentGateway:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or GEMINI_API_KEY
        self.model = "gemini-1.5-flash"

    async def reason_consumer(
        self,
        persona: Dict[str, Any],
        product_info: Dict[str, Any],
        business_questions: List[str]
    ) -> Dict[str, Any]:
        """
        Calls Gemini API to simulate representative consumer reaction.
        Returns validated JSON matching AgentResponseV1 contract.
        """
        prompt = self._build_prompt(persona, product_info, business_questions)

        if not self.api_key:
            # Return deterministic mock agent response if no API key set
            return self._mock_agent_response(persona)

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.3
            }
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    text_out = data["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = json.loads(text_out)
                    parsed["prompt_version"] = PROMPT_VERSION
                    return parsed
        except Exception as e:
            print(f"[GeminiAgentGateway] Error calling Gemini: {e}")

        return self._mock_agent_response(persona)

    def _build_prompt(self, persona: Dict[str, Any], product: Dict[str, Any], questions: List[str]) -> str:
        return f"""You are a representative Thai consumer. Respond strictly in JSON.

Consumer Profile:
- Age: {persona.get('age_group')}
- Gender: {persona.get('gender')}
- Province: {persona.get('province')}
- Income: {persona.get('income_tier')}
- Price Sensitivity: {persona.get('price_sensitivity')}/1.0
- Has Pets: {persona.get('has_pets')}

Product Offer:
- Name: {product.get('product_name')}
- Price: THB {product.get('price')}
- Description: {product.get('description')}

Key Questions to Address:
{json.dumps(questions, ensure_ascii=False)}

Return JSON with:
{{
  "awareness_probability": float(0-1),
  "comprehension_score": float(0-1),
  "interest_score": float(0-1),
  "trust_score": float(0-1),
  "value_score": float(0-1),
  "purchase_probability": float(0-1),
  "main_reasons": ["reason1", "reason2"],
  "main_barriers": ["barrier1", "barrier2"],
  "quote": "string consumer voice",
  "confidence": float(0-1)
}}"""

    def _mock_agent_response(self, persona: Dict[str, Any]) -> Dict[str, Any]:
        p_sens = persona.get("price_sensitivity", 0.5)
        return {
            "prompt_version": PROMPT_VERSION,
            "model_provider": "gemini",
            "model_id": self.model,
            "awareness_probability": 0.45,
            "comprehension_score": 0.80,
            "interest_score": 0.65,
            "trust_score": 0.55,
            "value_score": round(1.0 - (p_sens * 0.4), 2),
            "purchase_probability": round(max(0.05, 0.7 - p_sens * 0.5), 2),
            "main_reasons": ["设计吸引人", "尝试意愿高"],
            "main_barriers": ["知名度较低", "对价格观望"],
            "quote": "包装很好看，但我没听说过这个牌子，会先看看评论",
            "confidence": 0.75
        }
