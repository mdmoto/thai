"""Run one bounded, synthetic Thai OASIS propagation experiment.

This is an isolated Phase 5 research command. It deliberately excludes
customer data, observed-platform credentials, purchase outcomes, sales and
revenue. Only aggregate simulated social diagnostics are persisted.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import io
import json
import logging
import os
import random
import sqlite3
import tempfile
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

os.environ.setdefault("CAMEL_MODEL_LOG_ENABLED", "False")
os.environ.setdefault("LANGFUSE_ENABLED", "False")
os.environ.setdefault("TRACEROOT_ENABLED", "False")

import oasis
from camel.models.openai_compatible_model import OpenAICompatibleModel
from oasis import ActionType, LLMAction, ManualAction, generate_reddit_agent_graph

from simulation_core.social_backends.base import (
    OasisExperimentLimits,
    SocialSimulationRequest,
)
from simulation_core.social_backends.oasis import (
    OASIS_BACKEND_VERSION,
    OASIS_COMMIT,
    OASIS_VERSION,
    OasisSocialSimulationBackend,
)
from simulation_core.social_backends.oasis_budget import OasisUsageBudget
from simulation_core.social_backends.oasis_metrics import aggregate_oasis_sqlite
from simulation_core.social_backends.prior import PriorSocialSimulationBackend


MODEL_ID = "gemini-2.5-flash"
MODEL_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
MAXIMUM_CALL_OUTPUT_TOKENS = 384
PRICE_SOURCE = "https://ai.google.dev/gemini-api/docs/pricing"
SCENARIO_ID = "synthetic-thai-social-seed-v1"


def _quiet_dependency_logs() -> None:
    logging.basicConfig(level=logging.WARNING)
    for name in (
        "camel",
        "oasis",
        "oasis.env",
        "social",
        "social.agent",
        "social.rec",
        "social.twitter",
        "openai",
        "httpx",
        "httpcore",
    ):
        logger = logging.getLogger(name)
        logger.setLevel(logging.WARNING)
        logger.handlers.clear()
        logger.propagate = False
        logger.addHandler(logging.NullHandler())


class _BudgetedGeminiModel(OpenAICompatibleModel):
    """CAMEL model backend with pre-call reservation and actual accounting."""

    def __init__(self, limits: OasisExperimentLimits) -> None:
        self.usage_budget = OasisUsageBudget(limits)
        super().__init__(
            model_type=MODEL_ID,
            model_config_dict={
                "temperature": 0,
                "max_tokens": MAXIMUM_CALL_OUTPUT_TOKENS,
            },
            api_key=os.environ["GEMINI_API_KEY"],
            url=MODEL_URL,
            timeout=30,
            max_retries=0,
        )

    def _authorize(self, messages: list[dict[str, Any]]) -> None:
        # GPT-4o tokenization is only an approximation for the compatible
        # Gemini endpoint, so reserve twice the local estimate before calling.
        estimated = max(1, self.count_tokens_from_messages(messages))
        self.usage_budget.authorize_call(
            estimated_input_tokens=estimated * 2,
            maximum_call_output_tokens=MAXIMUM_CALL_OUTPUT_TOKENS,
        )

    def _account(self, response: Any) -> None:
        usage = getattr(response, "usage", None)
        if usage is None:
            raise RuntimeError("OASIS provider response omitted token usage")
        self.usage_budget.record_response(
            prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            completion_tokens=int(
                getattr(usage, "completion_tokens", 0) or 0
            ),
            total_tokens=int(getattr(usage, "total_tokens", 0) or 0),
        )

    def _run(
        self,
        messages: list[dict[str, Any]],
        response_format: Any = None,
        tools: Any = None,
    ) -> Any:
        self._authorize(messages)
        response = super()._run(messages, response_format, tools)
        self._account(response)
        return response

    async def _arun(
        self,
        messages: list[dict[str, Any]],
        response_format: Any = None,
        tools: Any = None,
    ) -> Any:
        self._authorize(messages)
        response = await super()._arun(messages, response_format, tools)
        self._account(response)
        return response


def _synthetic_profiles(agent_count: int) -> list[dict[str, Any]]:
    segments = [
        (24, "female", "ENFP", "Bangkok early-career social shopper"),
        (31, "male", "ISTJ", "Chiang Mai value-conscious office worker"),
        (38, "female", "ESFJ", "Khon Kaen parent managing household spend"),
        (27, "unspecified", "INTP", "Phuket mobile-first service worker"),
        (45, "male", "ESTJ", "Chonburi small business owner"),
        (34, "female", "ISFP", "Nakhon Ratchasima convenience shopper"),
        (29, "male", "ENTP", "Bangkok creator-economy freelancer"),
        (52, "female", "ISFJ", "Songkhla cautious family purchaser"),
    ]
    profiles = []
    for index in range(agent_count):
        age, gender, mbti, persona = segments[index % len(segments)]
        profiles.append(
            {
                "realname": f"Synthetic Thai Persona {index + 1}",
                "username": f"th_oasis_synthetic_{index + 1}",
                "bio": "Synthetic Thai consumer research persona; not real.",
                "persona": persona,
                "age": age,
                "gender": gender,
                "mbti": mbti,
                "country": "Thailand",
            }
        )
    return profiles


async def _oasis_protocol(
    limits: OasisExperimentLimits,
    seed: int,
) -> tuple[dict[str, int], dict[str, Any]]:
    randomizer = random.Random(seed)
    model = _BudgetedGeminiModel(limits)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="oasis-phase5-") as directory:
        root = Path(directory)
        profile_path = root / "synthetic-thai-profiles.json"
        database_path = root / "oasis-experiment.db"
        profile_path.write_text(
            json.dumps(_synthetic_profiles(limits.agent_count), ensure_ascii=False),
            encoding="utf-8",
        )
        with contextlib.redirect_stdout(io.StringIO()):
            agent_graph = await generate_reddit_agent_graph(
                profile_path=str(profile_path),
                model=model,
                available_actions=[
                    ActionType.LIKE_POST,
                    ActionType.DISLIKE_POST,
                    ActionType.CREATE_COMMENT,
                    ActionType.DO_NOTHING,
                ],
            )
            environment = oasis.make(
                agent_graph=agent_graph,
                platform=oasis.DefaultPlatformType.REDDIT,
                database_path=str(database_path),
            )
            await environment.reset()
            try:
                await environment.step(
                    {
                        environment.agent_graph.get_agent(0): ManualAction(
                            action_type=ActionType.CREATE_POST,
                            action_args={
                                "content": (
                                    "Synthetic research scenario: a fictional "
                                    "zero-sugar lychee drink is introduced in "
                                    "Thailand. React only as your synthetic persona."
                                )
                            },
                        )
                    }
                )
                eligible = list(range(1, limits.agent_count))
                active_count = max(
                    1,
                    min(
                        len(eligible),
                        round(limits.agent_count * limits.activation_probability),
                    ),
                )
                for _ in range(limits.time_steps):
                    active_ids = randomizer.sample(eligible, active_count)
                    # One active agent per step in this initial experiment.
                    # Sequential steps make the token reservation deterministic.
                    for agent_id in active_ids:
                        await environment.step(
                            {
                                environment.agent_graph.get_agent(
                                    agent_id
                                ): LLMAction()
                            }
                        )
            finally:
                await environment.close()

        with sqlite3.connect(database_path) as connection:
            counts = aggregate_oasis_sqlite(connection)
    usage = asdict(model.usage_budget.snapshot())
    usage["wall_time_seconds"] = round(time.monotonic() - started, 3)
    return counts, usage


def _oasis_events(counts: dict[str, int]) -> Sequence[dict[str, Any]]:
    interactions = counts["interactions"]
    sentiment = (
        (counts["likes"] - counts["dislikes"]) / interactions
        if interactions
        else 0.0
    )
    return [
        {
            "time_step": 1,
            "metric": "simulated_social_exposure",
            "value": float(counts["recommendation_records"]),
            "scenario_id": SCENARIO_ID,
        },
        {
            "time_step": 1,
            "metric": "simulated_interaction",
            "value": float(interactions),
            "scenario_id": SCENARIO_ID,
        },
        {
            "time_step": 1,
            "metric": "simulated_diffusion",
            "value": float(counts["participants"]),
            "scenario_id": SCENARIO_ID,
        },
        {
            "time_step": 1,
            "metric": "simulated_sentiment",
            "value": float(sentiment),
            "scenario_id": SCENARIO_ID,
        },
    ]


def _prior_events(limits: OasisExperimentLimits) -> Sequence[dict[str, Any]]:
    interactions = max(1, round(limits.agent_count * limits.activation_probability))
    return [
        {
            "time_step": 1,
            "metric": "simulated_social_exposure",
            "value": float(limits.agent_count - 1),
            "scenario_id": SCENARIO_ID,
        },
        {
            "time_step": 1,
            "metric": "simulated_interaction",
            "value": float(interactions),
            "scenario_id": SCENARIO_ID,
        },
        {
            "time_step": 1,
            "metric": "simulated_diffusion",
            "value": float(1 + interactions),
            "scenario_id": SCENARIO_ID,
        },
        {
            "time_step": 1,
            "metric": "simulated_sentiment",
            "value": 0.0,
            "scenario_id": SCENARIO_ID,
        },
    ]


async def _run_experiment(agent_count: int, seed: int) -> dict[str, Any]:
    limits = OasisExperimentLimits(
        agent_count=agent_count,
        activation_probability=0.125,
        time_steps=1,
        maximum_input_tokens=40_000,
        maximum_output_tokens=1_000,
        maximum_cost_minor=10,
        maximum_wall_time_seconds=180,
        cost_currency="USD",
    )
    request = SocialSimulationRequest(
        seed=seed,
        plan_code="PHASE5_RESEARCH",
        frozen_inputs={"oasis_experiment": asdict(limits)},
        native_runner=lambda: _prior_events(limits),
    )
    counts, usage = await asyncio.wait_for(
        _oasis_protocol(limits, seed),
        timeout=limits.maximum_wall_time_seconds,
    )
    oasis_result = OasisSocialSimulationBackend(
        runner=lambda _limits, _request: _oasis_events(counts)
    ).simulate(request)
    prior_result = PriorSocialSimulationBackend().simulate(request)
    oasis_values = {event["metric"]: event["value"] for event in oasis_result.events}
    prior_values = {event["metric"]: event["value"] for event in prior_result.events}
    return {
        "schema_version": "oasis-phase5-experiment-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "isolated_research_completed",
        "production_enabled": False,
        "synthetic_personas_only": True,
        "customer_data_used": False,
        "external_social_platform_calls": 0,
        "raw_model_content_persisted": False,
        "purchase_or_sales_fields": False,
        "seed": seed,
        "scenario_id": SCENARIO_ID,
        "oasis": {
            "version": OASIS_VERSION,
            "commit": OASIS_COMMIT,
            "backend_version": OASIS_BACKEND_VERSION,
        },
        "provider": {
            "model": MODEL_ID,
            "interface": "openai_compatible",
            "max_retries": 0,
            "price_source": PRICE_SOURCE,
        },
        "limits": asdict(limits),
        "usage": usage,
        "oasis_events": list(oasis_result.events),
        "prior_events": list(prior_result.events),
        "comparison_delta": {
            metric: float(oasis_values[metric] - prior_values[metric])
            for metric in oasis_values
        },
        "disclosure": (
            "A small synthetic OASIS social-propagation experiment. Values "
            "are simulated diagnostics, not observed reach, purchase "
            "probability, sales, revenue, or forecast accuracy."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--agent-count", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20260801)
    arguments = parser.parse_args()
    if not 4 <= arguments.agent_count <= 8:
        parser.error("initial Phase 5 experiment supports 4 to 8 agents")
    _quiet_dependency_logs()
    output = asyncio.run(_run_experiment(arguments.agent_count, arguments.seed))
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "schema_version": output["schema_version"],
                "status": output["status"],
                "production_enabled": False,
                "usage": output["usage"],
                "oasis_events": output["oasis_events"],
                "prior_events": output["prior_events"],
                "comparison_delta": output["comparison_delta"],
                "raw_model_content_persisted": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
