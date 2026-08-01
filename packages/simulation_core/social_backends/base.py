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


@dataclass(frozen=True)
class OasisExperimentLimits:
    """Hard ceilings for an optional, isolated OASIS experiment."""

    agent_count: int
    activation_probability: float
    time_steps: int
    maximum_input_tokens: int
    maximum_output_tokens: int
    maximum_cost_minor: int
    maximum_wall_time_seconds: int


class SocialSimulationBackend(Protocol):
    backend_id: str
    backend_version: str

    def simulate(
        self,
        request: SocialSimulationRequest,
    ) -> SocialSimulationResult:
        ...
