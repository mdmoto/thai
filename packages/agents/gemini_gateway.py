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

    async def generate_diverse_voices(
        self,
        product_info: Dict[str, Any],
        business_questions: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Generates 6-10 rich representative consumer persona reactions using Gemini LLM.
        """
        if not self.api_key:
            return self._mock_diverse_voices(product_info)

        prompt = f"""You are an expert market research analyst simulating Thai consumer panels.
Product: {json.dumps(product_info, ensure_ascii=False)}
Business Questions: {json.dumps(business_questions, ensure_ascii=False)}

Generate 6 realistic Thai consumer responses representing 3 groups:
1. Supporters (High intent)
2. Fence-sitters (Hesitant/Conditional)
3. Skeptics/Rejectors (Low intent)

Return a JSON array of objects with fields:
- persona: string (e.g. "28岁清迈白领女性，月收入4.5万泰铢")
- segment: string (e.g. "都市白领消费人群")
- sentiment: "positive" | "neutral" | "negative"
- quote: string (authentic first-person quote in Chinese or Thai)
- reasoning: string (detailed 2-sentence breakdown of purchase motivation and barriers)
- price_reaction: string (reaction to product price)
- preferred_channel: string (e.g. "Lazada", "Shopee", "TikTok Shop", "实体店")

Return ONLY valid JSON array."""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.4
            }
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    text_out = data["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = json.loads(text_out)
                    if isinstance(parsed, list) and len(parsed) > 0:
                        return parsed
        except Exception as e:
            print(f"[GeminiAgentGateway] Error generating voices: {e}")

        return self._mock_diverse_voices(product_info)

    def _mock_diverse_voices(self, product_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        name = product_info.get("product_name") or product_info.get("name") or "产品"
        price = product_info.get("price") or 299
        return [
            {
                "persona": "28岁曼谷金融外企白领，月收入6.5万铢",
                "segment": "都市白领消费人群",
                "sentiment": "positive",
                "quote": f"对{name}的包装和定位很感兴趣，如果品质确实好，THB {price} 的价格完全在我的预算范围内。",
                "reasoning": "注重个人生活品质与品牌美誉度，价格敏感度较低，优先看重产品功效与用户口碑。",
                "price_reaction": "价格合理，符合高品质定位",
                "preferred_channel": "Lazada Flagship Store"
            },
            {
                "persona": "25岁清迈大学研究助理，月收入2.8万铢",
                "segment": "年轻单身潮流受众",
                "sentiment": "neutral",
                "quote": f"外观很吸引人，但THB {price} 对我来说稍微贵了一点，我会等优惠活动或先看看 TikTok 上 KOL 的评测。",
                "reasoning": "社群驱动型消费者，对新颖创意感兴趣，但收入中等，容易受到促销折扣与社群推荐影响。",
                "price_reaction": "略高于预期，需折扣拉动",
                "preferred_channel": "TikTok Shop"
            },
            {
                "persona": "35岁曼谷主妇，养有2只宠物，月收入4.2万铢",
                "segment": "宠物专属主妇",
                "sentiment": "positive",
                "quote": f"成分表看起来很安全专业，如果狗狗喜欢吃，我会选择按月长期订购。",
                "reasoning": "高粘性买家，最关注成分安全性与方便程度，一旦形成信任将带来极高复购价值。",
                "price_reaction": "若效果好愿意支付溢价",
                "preferred_channel": "Shopee Mall"
            },
            {
                "persona": "42岁暖武里公务员，家庭月收入8万铢",
                "segment": "区域外省家庭人口",
                "sentiment": "negative",
                "quote": f"对新品牌缺乏信任，本地实体店有大品牌替代品，暂时不会考虑在线购买未知品牌。",
                "reasoning": "传统保守型买家，品牌信任门槛高，高度依赖线下线下实体渠道或熟人推荐。",
                "price_reaction": "偏高，替代品丰富",
                "preferred_channel": "Big C / 线下连锁"
            },
            {
                "persona": "23岁清迈自由职业设计师，月收入3.2万铢",
                "segment": "年轻单身潮流受众",
                "sentiment": "positive",
                "quote": f"设计非常有视觉冲击力！在 Instagram 看到一定会点进去了解，试用装如果合适会立马下单。",
                "reasoning": "视觉审美导向，极易产生冲动型试用购买，是品牌早期小红书/IG 传播的关键种子用户。",
                "price_reaction": "试用装门槛低即可接受",
                "preferred_channel": "品牌自营官网 / IG"
            },
            {
                "persona": "31岁普吉岛酒店经理，月收入5.5万铢",
                "segment": "都市白领消费人群",
                "sentiment": "neutral",
                "quote": f"产品概念不错，但普吉配送物流费和时间需要明确，希望能有方便的售后保障。",
                "reasoning": "重视履约体验与服务保障，对物流时效与退换货政策敏感。",
                "price_reaction": "包邮前提下价格可接受",
                "preferred_channel": "Lazada"
            }
        ]
