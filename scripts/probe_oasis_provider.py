"""Bounded connectivity probe for the isolated OASIS model provider.

The probe logs only aggregate usage metadata. It never logs model content or
the API key, and it is not a social simulation or a customer-facing result.
"""

from __future__ import annotations

import json
import os
import time

from camel.agents import ChatAgent
from camel.models import ModelFactory
from camel.types import ModelPlatformType


def main() -> int:
    started = time.monotonic()
    model = ModelFactory.create(
        model_platform=ModelPlatformType.OPENAI_COMPATIBLE_MODEL,
        model_type="gemini-2.5-flash",
        model_config_dict={"temperature": 0, "max_tokens": 128},
        api_key=os.environ["GEMINI_API_KEY"],
        url="https://generativelanguage.googleapis.com/v1beta/openai/",
        timeout=30,
        max_retries=0,
    )
    response = ChatAgent(
        system_message="You are a connectivity probe. Reply briefly.",
        model=model,
    ).step("Reply with exactly one word: READY")
    usage = dict((response.info or {}).get("usage") or {})
    content = str(response.msg.content or "")
    total_tokens = int(usage.get("total_tokens") or 0)
    passed = bool(content.strip()) and 0 < total_tokens <= 512
    print(
        json.dumps(
            {
                "schema_version": "oasis-provider-probe-v1",
                "provider": "gemini-openai-compatible",
                "model": "gemini-2.5-flash",
                "passed": passed,
                "nonempty_response": bool(content.strip()),
                "content_length": len(content),
                "usage": {
                    "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                    "completion_tokens": int(
                        usage.get("completion_tokens") or 0
                    ),
                    "total_tokens": total_tokens,
                },
                "latency_seconds": round(time.monotonic() - started, 3),
                "max_retries": 0,
                "raw_content_logged": False,
            },
            sort_keys=True,
        )
    )
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
