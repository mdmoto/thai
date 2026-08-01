"""Adapter for the current disclosed prior-diffusion scenarios."""

from __future__ import annotations

import os

from simulation_core.social_backends.base import (
    SocialSimulationBackend,
    SocialSimulationRequest,
    SocialSimulationResult,
)


class PriorSocialSimulationBackend:
    backend_id = "prior"
    backend_version = "prior-diffusion-1"

    def simulate(
        self,
        request: SocialSimulationRequest,
    ) -> SocialSimulationResult:
        return SocialSimulationResult(
            events=list(request.native_runner()),
            backend_id=self.backend_id,
            backend_version=self.backend_version,
            status="uncalibrated_social_propagation_prior",
        )


def get_social_simulation_backend(
    backend_id: str | None = None,
) -> SocialSimulationBackend:
    selected = (
        backend_id
        or os.environ.get("SOCIAL_SIMULATION_BACKEND", "prior")
    ).strip().lower()
    if selected in {"prior", "prior_diffusion"}:
        return PriorSocialSimulationBackend()
    raise ValueError(f"Unsupported social simulation backend: {selected}")
