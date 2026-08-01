"""Contracts for prior and optional agent-based social simulations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol, Sequence


@dataclass(frozen=True)
class SocialSimulationRequest:
    seed: int
    plan_code: str
    frozen_inputs: Mapping[str, Any]
    native_runner: Callable[[], Sequence[Mapping[str, Any]]]


@dataclass(frozen=True)
class SocialSimulationResult:
    events: Sequence[Mapping[str, Any]]
    backend_id: str
    backend_version: str
    status: str

    def lineage(self) -> dict[str, Any]:
        return {
            "component": "social_simulation",
            "backend": self.backend_id,
            "backend_version": self.backend_version,
            "status": self.status,
        }


class SocialSimulationBackend(Protocol):
    backend_id: str
    backend_version: str

    def simulate(
        self,
        request: SocialSimulationRequest,
    ) -> SocialSimulationResult:
        ...
