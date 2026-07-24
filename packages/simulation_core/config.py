"""Versioned execution plans for the market simulation engine.

Plans change the amount of evidence, model family, uncertainty work, and
scenario depth.  They do not merely select a more expensive language model.
"""

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


PLAN_CONFIG_VERSION = "PLAN-CONFIG-2026.07.1"


@dataclass(frozen=True)
class PlanConfig:
    code: str
    default_population: int
    maximum_population: int
    default_mc_rounds: int
    maximum_mc_rounds: int
    model_family: str
    model_sample_size: int
    representative_agents: int
    agent_signal_weight: float
    competitor_limit: int
    elasticity_points: int
    dynamic_periods: int
    customer_calibration: bool
    data_depth: str
    execution_backend: str

    def public_dict(self) -> Dict[str, Any]:
        return asdict(self)


PLAN_CONFIGS: Dict[str, PlanConfig] = {
    "PREVIEW": PlanConfig(
        code="PREVIEW",
        default_population=100,
        maximum_population=100,
        default_mc_rounds=40,
        maximum_mc_rounds=60,
        model_family="mnl_prior",
        model_sample_size=100,
        representative_agents=0,
        agent_signal_weight=0.0,
        competitor_limit=1,
        elasticity_points=3,
        dynamic_periods=3,
        customer_calibration=False,
        data_depth="versioned_public_prior",
        execution_backend="inline",
    ),
    "STANDARD": PlanConfig(
        code="STANDARD",
        default_population=10_000,
        maximum_population=10_000,
        default_mc_rounds=80,
        maximum_mc_rounds=120,
        model_family="mnl_prior",
        model_sample_size=10_000,
        representative_agents=12,
        agent_signal_weight=0.03,
        competitor_limit=3,
        elasticity_points=5,
        dynamic_periods=6,
        customer_calibration=False,
        data_depth="versioned_public_prior_plus_structured_agent_signals",
        execution_backend="inline",
    ),
    "PROFESSIONAL": PlanConfig(
        code="PROFESSIONAL",
        default_population=30_000,
        maximum_population=30_000,
        default_mc_rounds=150,
        maximum_mc_rounds=220,
        model_family="mnl_with_observed_heterogeneity",
        model_sample_size=30_000,
        representative_agents=32,
        agent_signal_weight=0.05,
        competitor_limit=5,
        elasticity_points=7,
        dynamic_periods=12,
        customer_calibration=False,
        data_depth="category_prior_competitors_and_structured_agent_signals",
        execution_backend="inline",
    ),
    "DEEP": PlanConfig(
        code="DEEP",
        default_population=100_000,
        maximum_population=100_000,
        default_mc_rounds=250,
        maximum_mc_rounds=350,
        model_family="mixed_logit_prior",
        model_sample_size=50_000,
        representative_agents=96,
        agent_signal_weight=0.08,
        competitor_limit=10,
        elasticity_points=9,
        dynamic_periods=18,
        customer_calibration=True,
        data_depth="mixed_logit_conjoint_ready_and_dynamic_diffusion",
        execution_backend="cloud_batch",
    ),
    "ENTERPRISE": PlanConfig(
        code="ENTERPRISE",
        default_population=300_000,
        maximum_population=300_000,
        default_mc_rounds=400,
        maximum_mc_rounds=600,
        model_family="mixed_logit_customer_calibratable",
        model_sample_size=75_000,
        representative_agents=192,
        agent_signal_weight=0.10,
        competitor_limit=20,
        elasticity_points=11,
        dynamic_periods=24,
        customer_calibration=True,
        data_depth="customer_data_calibration_backtesting_and_regional_model",
        execution_backend="cloud_batch",
    ),
}

PLAN_ALIASES = {
    "FREE": "PREVIEW",
    "BASIC": "STANDARD",
}


def normalize_plan_code(plan_code: Optional[str]) -> str:
    normalized = (plan_code or "PREVIEW").strip().upper()
    normalized = PLAN_ALIASES.get(normalized, normalized)
    if normalized not in PLAN_CONFIGS:
        raise ValueError(f"Unsupported plan_code: {plan_code}")
    return normalized


def get_plan_config(plan_code: Optional[str]) -> PlanConfig:
    return PLAN_CONFIGS[normalize_plan_code(plan_code)]


def resolve_execution_config(
    plan_code: Optional[str],
    requested_population: Optional[int] = None,
    requested_mc_rounds: Optional[int] = None,
) -> Dict[str, Any]:
    plan = get_plan_config(plan_code)
    population = plan.default_population
    if requested_population is not None:
        population = min(max(100, int(requested_population)), plan.maximum_population)

    rounds = plan.default_mc_rounds
    if requested_mc_rounds is not None:
        rounds = min(max(20, int(requested_mc_rounds)), plan.maximum_mc_rounds)

    return {
        "plan": plan,
        "population_size": population,
        "mc_rounds": rounds,
        "plan_config_version": PLAN_CONFIG_VERSION,
    }
