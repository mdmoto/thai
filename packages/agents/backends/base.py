"""Contracts for bounded representative-consumer qualitative research."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence


@dataclass(frozen=True)
class RepresentativeResearchRequest:
    product_info: Mapping[str, Any]
    business_questions: Sequence[str]
    representatives: Sequence[Mapping[str, Any]]
    plan_code: str
    seed: int


@dataclass(frozen=True)
class RepresentativeResearchResult:
    payload: Mapping[str, Any]
    backend_id: str
    backend_version: str
    status: str
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def lineage(self) -> dict[str, Any]:
        return {
            "component": "representative_research",
            "backend": self.backend_id,
            "backend_version": self.backend_version,
            "status": self.status,
            "diagnostics": dict(self.diagnostics),
        }


class RepresentativeResearchBackend(Protocol):
    backend_id: str
    backend_version: str

    async def research(
        self,
        request: RepresentativeResearchRequest,
    ) -> RepresentativeResearchResult:
        ...
