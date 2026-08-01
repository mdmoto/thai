"""Fail-closed contract for optional CAMEL OASIS social experiments.

The actual OASIS package lives only in a Python-3.11 research job.  This
adapter is intentionally dependency-free so it can be imported by the
production API without pulling in CAMEL, torch, or an LLM provider.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable, Mapping, Sequence

from simulation_core.social_backends.base import (
    OasisExperimentLimits,
    SocialSimulationRequest,
    SocialSimulationResult,
)


OASIS_VERSION = "0.2.5"
OASIS_COMMIT = "e97a1d83761605a24a7dc91fa4d4e9defffa7e23"
OASIS_BACKEND_VERSION = f"camel-oasis-{OASIS_VERSION}+{OASIS_COMMIT[:12]}"
OASIS_STATUS = "simulated_social_propagation_oasis"

# This is a research gate, not a scale claim.  Each submitted experiment must
# additionally fit inside the component-level job wall time and cost budget.
MAX_AGENT_COUNT = 96
MAX_TIME_STEPS = 12
MAX_ACTIVATION_PROBABILITY = 0.35
MAX_INPUT_TOKENS = 250_000
MAX_OUTPUT_TOKENS = 50_000
MAX_COST_MINOR = 100_000
MAX_WALL_TIME_SECONDS = 1_200

OasisRunner = Callable[
    [OasisExperimentLimits, SocialSimulationRequest],
    Sequence[Mapping[str, Any]],
]


def oasis_limits_from_inputs(
    frozen_inputs: Mapping[str, Any],
) -> OasisExperimentLimits:
    """Parse and cap a frozen OASIS experiment before any model call."""

    raw = frozen_inputs.get("oasis_experiment")
    if not isinstance(raw, Mapping):
        raise RuntimeError(
            "OASIS requires a frozen oasis_experiment manifest from its "
            "dedicated asynchronous research job"
        )
    try:
        limits = OasisExperimentLimits(
            agent_count=int(raw["agent_count"]),
            activation_probability=float(raw["activation_probability"]),
            time_steps=int(raw["time_steps"]),
            maximum_input_tokens=int(raw["maximum_input_tokens"]),
            maximum_output_tokens=int(raw["maximum_output_tokens"]),
            maximum_cost_minor=int(raw["maximum_cost_minor"]),
            maximum_wall_time_seconds=int(raw["maximum_wall_time_seconds"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError(
            "OASIS experiment manifest has invalid resource limits"
        ) from error

    if not 1 <= limits.agent_count <= MAX_AGENT_COUNT:
        raise RuntimeError("OASIS agent_count exceeds the research ceiling")
    if not 0 < limits.activation_probability <= MAX_ACTIVATION_PROBABILITY:
        raise RuntimeError(
            "OASIS activation_probability exceeds the research ceiling"
        )
    if not 1 <= limits.time_steps <= MAX_TIME_STEPS:
        raise RuntimeError("OASIS time_steps exceeds the research ceiling")
    if not 1 <= limits.maximum_input_tokens <= MAX_INPUT_TOKENS:
        raise RuntimeError("OASIS input-token limit exceeds the research ceiling")
    if not 1 <= limits.maximum_output_tokens <= MAX_OUTPUT_TOKENS:
        raise RuntimeError("OASIS output-token limit exceeds the research ceiling")
    if not 0 <= limits.maximum_cost_minor <= MAX_COST_MINOR:
        raise RuntimeError("OASIS cost limit exceeds the research ceiling")
    if not 1 <= limits.maximum_wall_time_seconds <= MAX_WALL_TIME_SECONDS:
        raise RuntimeError("OASIS wall-time limit exceeds the research ceiling")
    return limits


def _validate_event(event: Mapping[str, Any]) -> dict[str, Any]:
    """Reject outputs that could be mistaken for sales or observed reach."""

    allowed_metrics = {
        "simulated_social_exposure",
        "simulated_social_interaction",
        "simulated_social_diffusion",
        "simulated_social_sentiment",
    }
    forbidden = {
        "purchase_rate",
        "sales",
        "revenue",
        "real_reach",
        "real_engagement",
        "forecast_accuracy",
    }
    metric = str(event.get("metric", ""))
    if metric not in allowed_metrics:
        raise RuntimeError("OASIS returned an unsupported social metric")
    if forbidden.intersection(event):
        raise RuntimeError("OASIS output includes a prohibited quantitative claim")
    normalized = {
        "time_step": int(event.get("time_step", 0)),
        "metric": metric,
        "value": float(event.get("value", 0.0)),
        "status": OASIS_STATUS,
    }
    if "scenario_id" in event:
        normalized["scenario_id"] = str(event["scenario_id"])
    return normalized


class OasisSocialSimulationBackend:
    """Adapter used only by a dedicated OASIS worker with an injected runner."""

    backend_id = "oasis"
    backend_version = OASIS_BACKEND_VERSION

    def __init__(self, runner: OasisRunner | None = None) -> None:
        self._runner = runner

    def simulate(
        self,
        request: SocialSimulationRequest,
    ) -> SocialSimulationResult:
        limits = oasis_limits_from_inputs(request.frozen_inputs)
        if self._runner is None:
            raise RuntimeError(
                "OASIS cannot run inside the API/native process; dispatch "
                "the frozen manifest to the isolated social research job"
            )
        events = [
            _validate_event(event)
            for event in self._runner(limits, request)
        ]
        if not events:
            raise RuntimeError("OASIS returned no simulated social events")
        return SocialSimulationResult(
            events=events,
            backend_id=self.backend_id,
            backend_version=self.backend_version,
            status=OASIS_STATUS,
        )

    @staticmethod
    def lineage_limits(limits: OasisExperimentLimits) -> dict[str, Any]:
        return asdict(limits)
