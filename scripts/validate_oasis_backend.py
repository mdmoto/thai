"""Technical verification for the isolated CAMEL OASIS research runtime.

This command intentionally uses only synthetic Thai personas and manually
specified platform actions.  It proves that the pinned OASIS environment can
create its event trace and recommendation records without making any LLM or
external-platform call.  It is not a customer study and cannot be used as a
sales, purchase-rate, reach, or forecast claim.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import io
import json
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import oasis
from camel.models.base_model import BaseModelBackend
from camel.models.stub_model import StubTokenCounter
from oasis import ActionType, ManualAction, generate_reddit_agent_graph

from simulation_core.social_backends.base import (
    OasisExperimentLimits,
    SocialSimulationRequest,
)
from simulation_core.social_backends.oasis import (
    OASIS_BACKEND_VERSION,
    OASIS_COMMIT,
    OASIS_STATUS,
    OASIS_VERSION,
    OasisSocialSimulationBackend,
)
from simulation_core.social_backends.oasis_metrics import aggregate_oasis_sqlite


class _ManualOnlyBackend(BaseModelBackend):
    """Satisfy OASIS agent construction while rejecting every LLM call."""

    def __init__(self) -> None:
        super().__init__(
            "manual-only-validation",
            model_config_dict={"max_tokens": 4_096},
        )

    @property
    def token_counter(self) -> StubTokenCounter:
        return StubTokenCounter()

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("technical validation must not call an LLM")

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("technical validation must not call an LLM")


def _synthetic_profiles(agent_count: int) -> list[dict[str, Any]]:
    return [
        {
            "realname": f"Thailand Synthetic Persona {index + 1}",
            "username": f"th_synthetic_validation_{index + 1}",
            "bio": (
                "Synthetic Thai market-research persona for isolated "
                "technical validation only."
            ),
            "persona": (
                "Synthetic consumer persona for isolated technical platform "
                "verification. It is not a real person."
            ),
            "age": 25 + index,
            "gender": "unspecified",
            "mbti": "ISTJ",
            "country": "Thailand",
            "profession": "Synthetic research profile",
            "interested_topics": ["consumer products"],
        }
        for index in range(agent_count)
    ]


async def _manual_protocol(agent_count: int) -> dict[str, int]:
    """Run one manual post/response sequence and read only aggregate counts."""

    with tempfile.TemporaryDirectory(prefix="oasis-validation-") as directory:
        root = Path(directory)
        profile_path = root / "synthetic-thai-profiles.json"
        database_path = root / "oasis-validation.db"
        profile_path.write_text(
            json.dumps(_synthetic_profiles(agent_count), ensure_ascii=False),
            encoding="utf-8",
        )
        # OASIS emits profile details to stdout while it creates agents.  The
        # validation stores no individual profile or transcript and exposes
        # only aggregate, synthetic diagnostics below.
        with contextlib.redirect_stdout(io.StringIO()):
            agent_graph = await generate_reddit_agent_graph(
                profile_path=str(profile_path),
                model=_ManualOnlyBackend(),
                available_actions=[
                    ActionType.CREATE_POST,
                    ActionType.LIKE_POST,
                    ActionType.DISLIKE_POST,
                ],
            )
            environment = oasis.make(
                agent_graph=agent_graph,
                platform=oasis.DefaultPlatformType.REDDIT,
                database_path=str(database_path),
            )
            await environment.reset()
            await environment.step(
                {
                    environment.agent_graph.get_agent(0): ManualAction(
                        action_type=ActionType.CREATE_POST,
                        action_args={
                            "content": (
                                "Technical validation only: synthetic "
                                "market-research scenario."
                            )
                        },
                    )
                }
            )
            response_actions = {
                environment.agent_graph.get_agent(index): ManualAction(
                    action_type=(
                        ActionType.LIKE_POST
                        if index % 2
                        else ActionType.DISLIKE_POST
                    ),
                    action_args={"post_id": 1},
                )
                for index in range(1, agent_count)
            }
            if response_actions:
                await environment.step(response_actions)
            await environment.close()

        with sqlite3.connect(database_path) as connection:
            aggregate = aggregate_oasis_sqlite(connection)
            return {
                "post_count": aggregate["posts"],
                "recommendation_records": aggregate[
                    "recommendation_records"
                ],
                "interaction_records": aggregate["interactions"],
                "participating_agents": aggregate["participants"],
                "like_records": aggregate["likes"],
                "dislike_records": aggregate["dislikes"],
                "trace_records": aggregate["trace_records"],
            }


def _events_from_protocol(
    limits: OasisExperimentLimits,
    request: SocialSimulationRequest,
) -> Sequence[dict[str, Any]]:
    """Adapt OASIS trace counts to the strictly simulated social contract."""

    counts = asyncio.run(_manual_protocol(limits.agent_count))
    interactions = counts["interaction_records"]
    sentiment = (
        (counts["like_records"] - counts["dislike_records"]) / interactions
        if interactions
        else 0.0
    )
    return [
        {
            "time_step": 1,
            "metric": "simulated_social_exposure",
            "value": float(counts["recommendation_records"]),
            "scenario_id": "manual-action-technical-validation",
        },
        {
            "time_step": 1,
            "metric": "simulated_interaction",
            "value": float(interactions),
            "scenario_id": "manual-action-technical-validation",
        },
        {
            "time_step": 1,
            "metric": "simulated_diffusion",
            "value": float(counts["participating_agents"]),
            "scenario_id": "manual-action-technical-validation",
        },
        {
            "time_step": 1,
            "metric": "simulated_sentiment",
            "value": sentiment,
            "scenario_id": "manual-action-technical-validation",
        },
    ]


def _run(agent_count: int) -> dict[str, Any]:
    limits = OasisExperimentLimits(
        agent_count=agent_count,
        activation_probability=0.1,
        time_steps=1,
        maximum_input_tokens=1_000,
        maximum_output_tokens=1,
        maximum_cost_minor=0,
        maximum_wall_time_seconds=120,
        cost_currency="USD",
    )
    request = SocialSimulationRequest(
        seed=42,
        plan_code="TECHNICAL_VALIDATION",
        frozen_inputs={"oasis_experiment": limits.__dict__},
        native_runner=lambda: [],
    )
    backend = OasisSocialSimulationBackend(runner=_events_from_protocol)
    result = backend.simulate(request)
    return {
        "schema_version": "oasis-technical-validation-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "manual_action_technical_validation",
        "status": "technical_validation_only",
        "production_enabled": False,
        "llm_calls": 0,
        "external_platform_calls": 0,
        "synthetic_personas_only": True,
        "oasis": {
            "version": OASIS_VERSION,
            "commit": OASIS_COMMIT,
            "backend_version": OASIS_BACKEND_VERSION,
            "result_status": result.status,
        },
        "limits": OasisSocialSimulationBackend.lineage_limits(limits),
        "events": list(result.events),
        "disclosure": (
            "The values are OASIS technical validation trace counts from "
            "manual actions over synthetic personas. They are simulated "
            "social-platform diagnostics, not observed reach, customer "
            "behaviour, purchase probability, sales, revenue, or forecast "
            "accuracy."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--agent-count", type=int, default=8)
    arguments = parser.parse_args()
    if not 3 <= arguments.agent_count <= 96:
        parser.error("--agent-count must be between 3 and 96")
    output = _run(arguments.agent_count)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(
        f"OASIS technical validation completed: {arguments.output} "
        f"({OASIS_STATUS})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
