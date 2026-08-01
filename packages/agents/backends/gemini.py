"""Adapter for the current structured Gemini weak-signal gateway."""

from __future__ import annotations

import os

from agents.backends.base import (
    RepresentativeResearchBackend,
    RepresentativeResearchRequest,
    RepresentativeResearchResult,
)
from agents.gemini_gateway import GeminiAgentGateway, PROMPT_VERSION


class GeminiRepresentativeResearchBackend:
    backend_id = "gemini"
    backend_version = PROMPT_VERSION

    def __init__(self, gateway: GeminiAgentGateway | None = None):
        self.gateway = gateway or GeminiAgentGateway()

    async def research(
        self,
        request: RepresentativeResearchRequest,
    ) -> RepresentativeResearchResult:
        payload = await self.gateway.generate_research_signals(
            product_info=request.product_info,
            business_questions=request.business_questions,
            representatives=request.representatives,
            plan_code=request.plan_code,
        )
        return RepresentativeResearchResult(
            payload=payload,
            backend_id=self.backend_id,
            backend_version=self.backend_version,
            status=str(payload.get("status") or "unavailable"),
        )


def get_representative_research_backend(
    backend_id: str | None = None,
) -> RepresentativeResearchBackend:
    selected = (
        backend_id
        or os.environ.get("REPRESENTATIVE_AGENT_BACKEND", "gemini")
    ).strip().lower()
    if selected in {"gemini", "gemini_structured"}:
        return GeminiRepresentativeResearchBackend()
    if selected in {"tinytroupe", "tiny_troupe"}:
        from agents.backends.tinytroupe import (
            TinyTroupeRepresentativeResearchBackend,
        )

        return TinyTroupeRepresentativeResearchBackend()
    if selected in {"off", "disabled", "none"}:
        from agents.backends.tinytroupe import (
            DisabledRepresentativeResearchBackend,
        )

        return DisabledRepresentativeResearchBackend()
    raise ValueError(
        f"Unsupported representative research backend: {selected}"
    )
