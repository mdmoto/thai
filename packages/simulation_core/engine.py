"""Calibratable discrete-choice and dynamic market simulation engine.

The engine uses a multinomial choice set (focal offer, competitors, and an
outside/no-purchase option), study-specific coefficient priors, observed
consumer heterogeneity, bounded LLM weak signals, and prior-predictive Monte
Carlo intervals.  It never treats LLM votes as observed purchase rates.
"""

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from simulation_core.calibration import (
    calibration_summary,
    get_study_model,
    load_calibration_profile,
)
from simulation_core.config import (
    PLAN_CONFIG_VERSION,
    PlanConfig,
    get_plan_config,
)


SIMULATION_MODEL_VERSION = "SIM-2.0.0"

FEATURE_NAMES = (
    "intercept",
    "price_log_ratio",
    "affordability",
    "quality_fit",
    "brand_trust",
    "review_proof",
    "novelty",
    "convenience",
    "social_influence",
    "category_engagement",
    "localization",
    "distance_friction",
)

VENUE_STUDY_TYPES = {
    "VENUE_STUDY",
    "SITE_COMPARISON",
    "OPERATING_SCENARIO",
    "RESTAURANT",
    "CAFE",
    "BAR",
}

SEGMENT_LABELS = {
    "AFFLUENT_DIGITAL": "高收入数字消费人群",
    "TREND_EXPLORER": "年轻潮流探索人群",
    "VALUE_SEEKER": "价格敏感价值人群",
    "LOCAL_TRUST_OFFLINE": "本地信任线下人群",
    "MAINSTREAM": "主流谨慎消费人群",
}


def _sigmoid(values: np.ndarray) -> np.ndarray:
    clipped = np.clip(values, -30.0, 30.0)
    return 1.0 / (1.0 + np.exp(-clipped))


def _weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    return float(np.average(values, weights=weights))


def _clamp(value: Any, low: float, high: float) -> float:
    return float(np.clip(float(value), low, high))


def _metric_summary(values: Sequence[float]) -> Dict[str, float]:
    array = np.asarray(values, dtype=float)
    return {
        "mean": round(float(np.mean(array)), 6),
        "median": round(float(np.median(array)), 6),
        "p10": round(float(np.percentile(array, 10)), 6),
        "p25": round(float(np.percentile(array, 25)), 6),
        "p75": round(float(np.percentile(array, 75)), 6),
        "p90": round(float(np.percentile(array, 90)), 6),
        "standard_deviation": round(float(np.std(array)), 6),
    }


class SimulationEngine:
    def __init__(
        self,
        seed: int = 42,
        calibration_profile: Optional[Mapping[str, Any]] = None,
    ):
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.profile = (
            dict(calibration_profile)
            if calibration_profile is not None
            else load_calibration_profile()
        )

    def _model_population(
        self,
        population_df: pd.DataFrame,
        plan: PlanConfig,
    ) -> Tuple[pd.DataFrame, int]:
        if population_df.empty:
            raise ValueError("population_df must not be empty")

        frame = population_df.copy()
        if "sample_weight" not in frame:
            frame["sample_weight"] = 1.0
        if len(frame) <= plan.model_sample_size:
            if "expansion_weight" in frame:
                frame["model_weight"] = frame["expansion_weight"].astype(float)
            else:
                frame["model_weight"] = frame["sample_weight"].astype(float)
            return frame.reset_index(drop=True), len(frame)

        sampled = frame.sample(
            n=plan.model_sample_size,
            replace=False,
            random_state=self.seed,
        ).copy()
        total_weight = float(frame["sample_weight"].sum())
        sampled["model_weight"] = total_weight / float(len(sampled))
        return sampled.reset_index(drop=True), len(sampled)

    def _normalize_product_attributes(
        self,
        product_attributes: Optional[Mapping[str, Any]],
        brand_awareness: Optional[float],
    ) -> Dict[str, float]:
        defaults = self.profile["defaults"]
        attributes = {
            "quality_score": float(defaults["quality_score"]),
            "review_score": float(defaults["review_score"]),
            "design_score": float(defaults["design_score"]),
            "convenience_score": float(defaults["convenience_score"]),
            "localization_score": float(defaults["localization_score"]),
            "clarity_score": float(defaults["clarity_score"]),
            "social_proof_score": 0.45,
            "brand_strength": 0.4,
            "distance_km": float(defaults["distance_km"]),
        }
        for key, value in (product_attributes or {}).items():
            if key in attributes and value is not None:
                attributes[key] = float(value)
        for score_name in (
            "quality_score",
            "review_score",
            "design_score",
            "convenience_score",
            "localization_score",
            "clarity_score",
            "social_proof_score",
            "brand_strength",
        ):
            attributes[score_name] = _clamp(attributes[score_name], 0.0, 1.0)
        attributes["distance_km"] = max(0.0, attributes["distance_km"])
        attributes["awareness"] = _clamp(
            brand_awareness
            if brand_awareness is not None
            else defaults["brand_awareness"],
            0.005,
            0.98,
        )
        return attributes

    def _normalize_competitors(
        self,
        competitors: Optional[Sequence[Mapping[str, Any]]],
        ref_price: float,
        focal_attributes: Mapping[str, float],
        plan: PlanConfig,
    ) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        for index, competitor in enumerate((competitors or [])[: plan.competitor_limit]):
            name = str(competitor.get("name") or f"competitor_{index + 1}")
            price = max(0.01, float(competitor.get("price") or ref_price))
            model_fields = (
                "price",
                "awareness",
                "quality_score",
                "review_score",
                "design_score",
                "convenience_score",
                "localization_score",
                "social_proof_score",
                "brand_strength",
                "distance_km",
            )
            provided_fields = sorted(
                field
                for field in model_fields
                if competitor.get(field) is not None
            )
            assumed_fields = sorted(set(model_fields) - set(provided_fields))
            has_observed_attributes = any(
                key in competitor
                for key in (
                    "price",
                    "quality_score",
                    "review_score",
                    "awareness",
                    "brand_strength",
                )
            )
            normalized.append(
                {
                    "name": name,
                    "price": price,
                    "awareness": _clamp(
                        competitor.get("awareness", 0.45),
                        0.005,
                        0.99,
                    ),
                    "quality_score": _clamp(
                        competitor.get(
                            "quality_score",
                            focal_attributes["quality_score"],
                        ),
                        0.0,
                        1.0,
                    ),
                    "review_score": _clamp(
                        competitor.get(
                            "review_score",
                            focal_attributes["review_score"],
                        ),
                        0.0,
                        1.0,
                    ),
                    "design_score": _clamp(
                        competitor.get(
                            "design_score",
                            focal_attributes["design_score"],
                        ),
                        0.0,
                        1.0,
                    ),
                    "convenience_score": _clamp(
                        competitor.get(
                            "convenience_score",
                            focal_attributes["convenience_score"],
                        ),
                        0.0,
                        1.0,
                    ),
                    "localization_score": _clamp(
                        competitor.get(
                            "localization_score",
                            focal_attributes["localization_score"],
                        ),
                        0.0,
                        1.0,
                    ),
                    "social_proof_score": _clamp(
                        competitor.get(
                            "social_proof_score",
                            focal_attributes["social_proof_score"],
                        ),
                        0.0,
                        1.0,
                    ),
                    "brand_strength": _clamp(
                        competitor.get("brand_strength", 0.6),
                        0.0,
                        1.0,
                    ),
                    "distance_km": max(
                        0.0,
                        float(
                            competitor.get(
                                "distance_km",
                                focal_attributes["distance_km"],
                            )
                        ),
                    ),
                    "data_quality": competitor.get(
                        "data_quality",
                        "provided"
                        if has_observed_attributes
                        else "name_only_assumption",
                    ),
                    "provided_fields": provided_fields,
                    "assumed_fields": assumed_fields,
                }
            )
        return normalized

    def _default_scenarios(
        self,
        price: float,
        attributes: Mapping[str, float],
        plan: PlanConfig,
    ) -> List[Dict[str, Any]]:
        scenarios = [
            {
                "scenario_id": "baseline",
                "name": "基准方案",
                "price": price,
            },
            {
                "scenario_id": "value_launch",
                "name": "首发降价 12%",
                "price": price * 0.88,
                "awareness": min(0.98, attributes["awareness"] * 1.08),
            },
            {
                "scenario_id": "premium_quality",
                "name": "品质增强与溢价 12%",
                "price": price * 1.12,
                "quality_score": min(1.0, attributes["quality_score"] + 0.12),
                "review_score": min(1.0, attributes["review_score"] + 0.08),
            },
            {
                "scenario_id": "social_launch",
                "name": "KOL 与口碑强化",
                "price": price,
                "awareness": min(0.98, attributes["awareness"] * 1.3),
                "social_proof_score": min(
                    1.0,
                    attributes["social_proof_score"] + 0.2,
                ),
            },
            {
                "scenario_id": "localized_trust",
                "name": "泰国本地化与信任增强",
                "price": price,
                "localization_score": min(
                    1.0,
                    attributes["localization_score"] + 0.22,
                ),
                "brand_strength": min(1.0, attributes["brand_strength"] + 0.12),
            },
        ]
        if plan.code == "PREVIEW":
            return scenarios[:2]
        if plan.code == "STANDARD":
            return scenarios[:3]
        return scenarios

    def _normalize_scenarios(
        self,
        scenarios: Optional[Sequence[Mapping[str, Any]]],
        price: float,
        attributes: Mapping[str, float],
        plan: PlanConfig,
    ) -> List[Dict[str, Any]]:
        source = scenarios or self._default_scenarios(price, attributes, plan)
        normalized: List[Dict[str, Any]] = []
        for index, scenario in enumerate(source):
            changes = scenario.get("changes", {})
            merged = dict(changes) if isinstance(changes, Mapping) else {}
            merged.update(
                {
                    key: value
                    for key, value in scenario.items()
                    if key not in {"changes"}
                }
            )
            normalized.append(
                {
                    "scenario_id": str(
                        merged.get("scenario_id") or f"scenario_{index + 1}"
                    ),
                    "name": str(merged.get("name") or f"方案 {index + 1}"),
                    "price": max(0.01, float(merged.get("price") or price)),
                    **{
                        key: merged[key]
                        for key in attributes
                        if key in merged and merged[key] is not None
                    },
                }
            )
        if not any(item["scenario_id"] == "baseline" for item in normalized):
            normalized.insert(
                0,
                {
                    "scenario_id": "baseline",
                    "name": "基准方案",
                    "price": price,
                },
            )
        return normalized

    def _agent_adjustments(
        self,
        agent_signals: Optional[Mapping[str, Any]],
        plan: PlanConfig,
    ) -> Dict[str, Any]:
        empty = {
            "status": "not_used",
            "effective_weight": 0.0,
            "coefficient_multiplier": {},
            "awareness_multiplier": 1.0,
            "sample_size": 0,
        }
        if not agent_signals:
            return empty
        status = str(agent_signals.get("status", "unavailable"))
        if status not in {"available", "partial"}:
            empty["status"] = status
            return empty

        aggregate = agent_signals.get("aggregate") or {}
        confidence = _clamp(aggregate.get("confidence", 0.0), 0.0, 1.0)
        effective_weight = plan.agent_signal_weight * confidence
        importance = aggregate.get("attribute_importance") or {}
        mapping = {
            "price": ("price_log_ratio",),
            "quality": ("quality_fit",),
            "trust": ("brand_trust", "localization"),
            "warranty": ("brand_trust",),
            "design": ("novelty",),
            "convenience": ("convenience",),
            "social_proof": ("review_proof", "social_influence"),
        }
        multipliers: Dict[str, float] = {}
        for source_name, coefficient_names in mapping.items():
            if source_name not in importance:
                continue
            centered = 2.0 * (_clamp(importance[source_name], 0.0, 1.0) - 0.5)
            multiplier = 1.0 + centered * effective_weight
            for coefficient_name in coefficient_names:
                multipliers[coefficient_name] = _clamp(multiplier, 0.85, 1.15)

        awareness_lift = _clamp(
            aggregate.get("awareness_lift", 0.0),
            -0.25,
            0.25,
        )
        return {
            "status": status,
            "effective_weight": round(effective_weight, 4),
            "coefficient_multiplier": multipliers,
            "awareness_multiplier": _clamp(
                1.0 + awareness_lift * effective_weight,
                0.95,
                1.05,
            ),
            "sample_size": int(agent_signals.get("sample_size_completed", 0)),
            "prompt_version": agent_signals.get("prompt_version"),
            "model_id": agent_signals.get("model_id"),
        }

    def _draw_coefficients(
        self,
        coefficient_priors: Mapping[str, Mapping[str, Any]],
        plan: PlanConfig,
        adjustments: Mapping[str, Any],
        rng: np.random.Generator,
    ) -> Dict[str, float]:
        uncertainty_scale = {
            "PREVIEW": 1.35,
            "STANDARD": 1.15,
            "PROFESSIONAL": 1.0,
            "DEEP": 0.9,
            "ENTERPRISE": 0.8,
        }[plan.code]
        multipliers = adjustments["coefficient_multiplier"]
        coefficients: Dict[str, float] = {}
        for name, prior in coefficient_priors.items():
            mean = float(prior["mean"]) * float(multipliers.get(name, 1.0))
            sd = float(prior["sd"]) * uncertainty_scale
            coefficients[name] = float(rng.normal(mean, sd)) if sd else mean
        return coefficients

    def _feature_matrix(
        self,
        frame: pd.DataFrame,
        offer: Mapping[str, Any],
        ref_price: float,
        study_type: str,
    ) -> Dict[str, np.ndarray]:
        price = max(0.01, float(offer["price"]))
        disposable = np.maximum(
            frame["disposable_income_thb"].to_numpy(dtype=float),
            1.0,
        )
        price_sensitivity = frame["price_sensitivity"].to_numpy(dtype=float)
        affordability = np.clip(
            np.log1p(disposable / price) / 5.5,
            0.0,
            1.5,
        )
        distance_feature = np.zeros(len(frame), dtype=float)
        if study_type in VENUE_STUDY_TYPES:
            distance = float(offer.get("distance_km", 0.0))
            if distance <= 0:
                distance = frame["distance_km"].to_numpy(dtype=float)
            else:
                distance = np.full(len(frame), distance, dtype=float)
            tolerance = np.maximum(
                frame["travel_tolerance_km"].to_numpy(dtype=float),
                0.5,
            )
            distance_feature = distance / tolerance

        return {
            "intercept": np.ones(len(frame), dtype=float),
            "price_log_ratio": (
                price_sensitivity
                * np.log(price / max(0.01, float(ref_price)))
            ),
            "affordability": affordability,
            "quality_fit": (
                frame["quality_sensitivity"].to_numpy(dtype=float)
                * float(offer["quality_score"])
            ),
            "brand_trust": (
                frame["brand_sensitivity"].to_numpy(dtype=float)
                * float(offer["brand_strength"])
            ),
            "review_proof": (
                frame["review_sensitivity"].to_numpy(dtype=float)
                * float(offer["review_score"])
            ),
            "novelty": (
                frame["novelty_seeking"].to_numpy(dtype=float)
                * float(offer["design_score"])
            ),
            "convenience": (
                frame["convenience_preference"].to_numpy(dtype=float)
                * float(offer["convenience_score"])
            ),
            "social_influence": (
                frame["social_influence"].to_numpy(dtype=float)
                * float(offer["social_proof_score"])
            ),
            "category_engagement": frame[
                "category_engagement"
            ].to_numpy(dtype=float),
            "localization": (
                frame["local_brand_trust"].to_numpy(dtype=float)
                * float(offer["localization_score"])
            ),
            "distance_friction": distance_feature,
        }

    def _awareness_vector(
        self,
        frame: pd.DataFrame,
        awareness: float,
        study_type: str,
    ) -> np.ndarray:
        if study_type in VENUE_STUDY_TYPES:
            modifier = (
                0.72
                + 0.42 * frame["category_engagement"].to_numpy(dtype=float)
                + 0.12 * frame["social_influence"].to_numpy(dtype=float)
            )
        else:
            modifier = (
                0.68
                + 0.48 * frame["online_affinity"].to_numpy(dtype=float)
                + 0.08 * frame["social_influence"].to_numpy(dtype=float)
            )
        return np.clip(float(awareness) * modifier, 0.001, 0.995)

    def _utility(
        self,
        features: Mapping[str, np.ndarray],
        coefficients: Mapping[str, float],
        mixed_taste: Optional[Mapping[str, np.ndarray]] = None,
    ) -> np.ndarray:
        utility = np.zeros_like(features["intercept"], dtype=float)
        for feature_name in FEATURE_NAMES:
            coefficient: Any = coefficients[feature_name]
            if mixed_taste and feature_name in mixed_taste:
                coefficient = coefficient * mixed_taste[feature_name]
            utility = utility + coefficient * features[feature_name]
        return np.clip(utility, -25.0, 25.0)

    def _choice_probabilities(
        self,
        frame: pd.DataFrame,
        focal_offer: Mapping[str, Any],
        competitor_offers: Sequence[Mapping[str, Any]],
        ref_price: float,
        study_type: str,
        coefficients: Mapping[str, float],
        mixed_taste: Optional[Mapping[str, np.ndarray]],
    ) -> Dict[str, np.ndarray]:
        focal_features = self._feature_matrix(
            frame,
            focal_offer,
            ref_price,
            study_type,
        )
        focal_utility = self._utility(focal_features, coefficients, mixed_taste)
        focal_awareness = self._awareness_vector(
            frame,
            float(focal_offer["awareness"]),
            study_type,
        )
        eligibility = (
            frame["category_eligible"].to_numpy(dtype=float)
            if "category_eligible" in frame
            else np.ones(len(frame), dtype=float)
        )
        focal_awareness = focal_awareness * eligibility
        focal_numerator = focal_awareness * np.exp(focal_utility)
        denominator = np.ones(len(frame), dtype=float) + focal_numerator

        competitor_probabilities: Dict[str, np.ndarray] = {}
        competitor_numerators: Dict[str, np.ndarray] = {}
        for competitor in competitor_offers:
            competitor_features = self._feature_matrix(
                frame,
                competitor,
                ref_price,
                study_type,
            )
            competitor_utility = self._utility(
                competitor_features,
                coefficients,
                mixed_taste,
            )
            competitor_awareness = self._awareness_vector(
                frame,
                float(competitor["awareness"]),
                study_type,
            ) * eligibility
            numerator = competitor_awareness * np.exp(competitor_utility)
            competitor_numerators[str(competitor["name"])] = numerator
            denominator = denominator + numerator

        focal_purchase = focal_numerator / denominator
        for name, numerator in competitor_numerators.items():
            competitor_probabilities[name] = numerator / denominator

        clarity = float(focal_offer["clarity_score"])
        understood = focal_awareness * (0.55 + 0.45 * clarity)
        focal_consideration = focal_numerator / (1.0 + focal_numerator)
        return {
            "awareness": focal_awareness,
            "understood": np.minimum(understood, focal_awareness),
            "consideration": np.minimum(focal_consideration, focal_awareness),
            "purchase": np.minimum(focal_purchase, focal_consideration),
            "competitors": competitor_probabilities,
        }

    def _offer_from_scenario(
        self,
        base_attributes: Mapping[str, float],
        scenario: Mapping[str, Any],
        awareness_multiplier: float,
    ) -> Dict[str, Any]:
        offer = dict(base_attributes)
        offer.update(
            {
                key: value
                for key, value in scenario.items()
                if key
                in {
                    "price",
                    "awareness",
                    "quality_score",
                    "review_score",
                    "design_score",
                    "convenience_score",
                    "localization_score",
                    "clarity_score",
                    "social_proof_score",
                    "brand_strength",
                    "distance_km",
                }
            }
        )
        offer["awareness"] = _clamp(
            float(offer["awareness"]) * awareness_multiplier,
            0.005,
            0.98,
        )
        offer["price"] = max(0.01, float(offer["price"]))
        return offer

    def _mixed_taste_draws(
        self,
        frame_size: int,
        plan: PlanConfig,
        rng: np.random.Generator,
    ) -> Optional[Dict[str, np.ndarray]]:
        if not plan.model_family.startswith("mixed_logit"):
            return None
        price_sigma = 0.22 if plan.code == "DEEP" else 0.18
        quality_sigma = 0.14 if plan.code == "DEEP" else 0.12
        return {
            "price_log_ratio": rng.lognormal(
                mean=-0.5 * price_sigma**2,
                sigma=price_sigma,
                size=frame_size,
            ),
            "quality_fit": np.clip(
                rng.normal(1.0, quality_sigma, frame_size),
                0.55,
                1.55,
            ),
            "social_influence": np.clip(
                rng.normal(1.0, 0.14, frame_size),
                0.55,
                1.55,
            ),
        }

    def _elasticity_ratios(self, point_count: int) -> np.ndarray:
        return np.linspace(0.7, 1.3, point_count)

    def _segment_results(
        self,
        frame: pd.DataFrame,
        purchase_probability: np.ndarray,
        total_population: int,
    ) -> List[Dict[str, Any]]:
        working = frame.copy()
        working["_purchase_probability"] = purchase_probability
        total_weight = float(working["model_weight"].sum())
        results: List[Dict[str, Any]] = []
        for segment_id, group in working.groupby("segment_id", sort=True):
            weights = group["model_weight"].to_numpy(dtype=float)
            share = float(weights.sum() / total_weight)
            results.append(
                {
                    "segment_id": segment_id,
                    "name": SEGMENT_LABELS.get(
                        segment_id,
                        segment_id.replace("_", " ").title(),
                    ),
                    "size": round(share, 4),
                    "population": int(round(total_population * share)),
                    "purchase_rate": round(
                        _weighted_mean(
                            group["_purchase_probability"].to_numpy(dtype=float),
                            weights,
                        ),
                        4,
                    ),
                    "price_sensitivity": round(
                        _weighted_mean(
                            group["price_sensitivity"].to_numpy(dtype=float),
                            weights,
                        ),
                        3,
                    ),
                    "category_engagement": round(
                        _weighted_mean(
                            group["category_engagement"].to_numpy(dtype=float),
                            weights,
                        ),
                        3,
                    ),
                }
            )
        return sorted(results, key=lambda item: item["purchase_rate"], reverse=True)

    def _regional_results(
        self,
        frame: pd.DataFrame,
        purchase_probability: np.ndarray,
    ) -> List[Dict[str, Any]]:
        working = frame.copy()
        working["_purchase_probability"] = purchase_probability
        total_weight = float(working["model_weight"].sum())
        results: List[Dict[str, Any]] = []
        for region, group in working.groupby("region", sort=True):
            weights = group["model_weight"].to_numpy(dtype=float)
            share = float(weights.sum() / total_weight)
            rate = _weighted_mean(
                group["_purchase_probability"].to_numpy(dtype=float),
                weights,
            )
            results.append(
                {
                    "region": region,
                    "share": f"{share:.1%}",
                    "purchase_rate": round(rate, 4),
                    "readiness": (
                        "高" if rate >= 0.08 else "中" if rate >= 0.035 else "低"
                    ),
                }
            )
        return sorted(results, key=lambda item: item["purchase_rate"], reverse=True)

    def _channel_results(
        self,
        frame: pd.DataFrame,
    ) -> List[Dict[str, Any]]:
        weights = frame["model_weight"].to_numpy(dtype=float)
        online = _weighted_mean(
            frame["online_affinity"].to_numpy(dtype=float),
            weights,
        )
        novelty = _weighted_mean(
            frame["novelty_seeking"].to_numpy(dtype=float),
            weights,
        )
        social = _weighted_mean(
            frame["social_influence"].to_numpy(dtype=float),
            weights,
        )
        trust = _weighted_mean(
            frame["local_brand_trust"].to_numpy(dtype=float),
            weights,
        )
        review = _weighted_mean(
            frame["review_sensitivity"].to_numpy(dtype=float),
            weights,
        )
        scores = {
            "Shopee Thailand": 0.45 * online + 0.35 * review + 0.2,
            "Lazada Thailand": 0.5 * online + 0.25 * trust + 0.2,
            "TikTok Shop Thailand": 0.42 * social + 0.38 * novelty + 0.15,
            "线下零售 / 门店": 0.48 * trust + 0.35 * (1.0 - online) + 0.15,
        }
        output = []
        for channel, raw_score in scores.items():
            score = _clamp(raw_score, 0.0, 1.0)
            output.append(
                {
                    "channel": channel,
                    "fit_score": int(round(score * 100)),
                    "relative_purchase_index": round(
                        (0.7 + 0.6 * score) * 100,
                        1,
                    ),
                    "recommendation": (
                        "进入渠道 A/B 测试优先级"
                        if score >= 0.68
                        else "作为补充测试渠道"
                    ),
                    "method": "population_affinity_index",
                }
            )
        return sorted(output, key=lambda item: item["fit_score"], reverse=True)

    def _market_dynamics(
        self,
        purchase_rate: float,
        awareness_rate: float,
        repeat_rate: float,
        frame: pd.DataFrame,
        plan: PlanConfig,
    ) -> List[Dict[str, Any]]:
        dynamics = self.profile["dynamics"]
        weights = frame["model_weight"].to_numpy(dtype=float)
        social = _weighted_mean(
            frame["social_influence"].to_numpy(dtype=float),
            weights,
        )
        innovation = float(dynamics["innovation_rate"]["mean"])
        imitation = float(dynamics["word_of_mouth_rate"]["mean"]) * social
        conditional_choice = purchase_rate / max(awareness_rate, 1e-6)

        awareness = awareness_rate
        cumulative_adoption = purchase_rate
        output = [
            {
                "period": 0,
                "awareness_rate": round(awareness, 5),
                "new_adoption_rate": round(purchase_rate, 5),
                "cumulative_adoption_rate": round(cumulative_adoption, 5),
                "repeat_rate": round(repeat_rate, 5),
            }
        ]
        for period in range(1, plan.dynamic_periods + 1):
            new_awareness = (1.0 - awareness) * (
                innovation + imitation * cumulative_adoption
            )
            awareness = min(0.995, awareness + new_awareness)
            new_adoption = min(
                1.0 - cumulative_adoption,
                new_awareness * conditional_choice
                + cumulative_adoption * repeat_rate * 0.08,
            )
            cumulative_adoption = min(1.0, cumulative_adoption + new_adoption)
            output.append(
                {
                    "period": period,
                    "awareness_rate": round(awareness, 5),
                    "new_adoption_rate": round(new_adoption, 5),
                    "cumulative_adoption_rate": round(
                        cumulative_adoption,
                        5,
                    ),
                    "repeat_rate": round(repeat_rate, 5),
                }
            )
        return output

    def _implied_wtp(
        self,
        coefficient_priors: Mapping[str, Mapping[str, Any]],
        frame: pd.DataFrame,
        price: float,
    ) -> List[Dict[str, Any]]:
        price_beta = float(coefficient_priors["price_log_ratio"]["mean"])
        weights = frame["model_weight"].to_numpy(dtype=float)
        mean_price_sensitivity = max(
            _weighted_mean(
                frame["price_sensitivity"].to_numpy(dtype=float),
                weights,
            ),
            0.05,
        )
        sensitivity_columns = {
            "quality_score": ("quality_fit", "quality_sensitivity"),
            "review_score": ("review_proof", "review_sensitivity"),
            "convenience_score": (
                "convenience",
                "convenience_preference",
            ),
            "localization_score": ("localization", "local_brand_trust"),
        }
        output = []
        for attribute, (coefficient_name, sensitivity_column) in sensitivity_columns.items():
            beta = float(coefficient_priors[coefficient_name]["mean"])
            mean_sensitivity = _weighted_mean(
                frame[sensitivity_column].to_numpy(dtype=float),
                weights,
            )
            delta_log_price = -(
                beta * mean_sensitivity * 0.1
            ) / (price_beta * mean_price_sensitivity)
            wtp = price * (np.exp(delta_log_price) - 1.0)
            output.append(
                {
                    "attribute": attribute,
                    "score_increase": 0.1,
                    "implied_wtp_thb": round(float(wtp), 2),
                    "status": "prior_implied_not_empirically_estimated",
                }
            )
        return output

    def run_simulation(
        self,
        population_df: pd.DataFrame,
        study_type: str,
        price: float = 299.0,
        ref_price: Optional[float] = None,
        brand_awareness: Optional[float] = None,
        mc_rounds: Optional[int] = None,
        scenarios: Optional[Sequence[Mapping[str, Any]]] = None,
        product_attributes: Optional[Mapping[str, Any]] = None,
        competitors: Optional[Sequence[Mapping[str, Any]]] = None,
        plan_code: str = "PROFESSIONAL",
        agent_signals: Optional[Mapping[str, Any]] = None,
        variable_cost: Optional[float] = None,
    ) -> Dict[str, Any]:
        normalized_study_type = (study_type or "PRODUCT_VALIDATION").upper()
        plan = get_plan_config(plan_code)
        rounds = int(mc_rounds or plan.default_mc_rounds)
        rounds = min(max(20, rounds), plan.maximum_mc_rounds)
        total_population = int(round(float(population_df["sample_weight"].sum())))
        model_frame, model_sample_size = self._model_population(population_df, plan)
        weights = model_frame["model_weight"].to_numpy(dtype=float)
        category_eligibility = (
            model_frame["category_eligible"].to_numpy(dtype=float)
            if "category_eligible" in model_frame
            else np.ones(len(model_frame), dtype=float)
        )
        eligibility_rate = _weighted_mean(category_eligibility, weights)
        category_key = str(
            model_frame["category_key"].iloc[0]
            if "category_key" in model_frame
            else "GENERIC_CONSUMER_PRODUCT"
        )
        category_profile_version = str(
            model_frame["category_profile_version"].iloc[0]
            if "category_profile_version" in model_frame
            else "unknown"
        )
        category_eligibility_status = str(
            model_frame["category_eligibility_status"].iloc[0]
            if "category_eligibility_status" in model_frame
            else "universal_population_assumption"
        )

        study_model = get_study_model(self.profile, normalized_study_type)
        coefficient_priors = study_model["coefficients"]
        attributes = self._normalize_product_attributes(
            product_attributes,
            brand_awareness,
        )
        reference_price = max(
            0.01,
            float(ref_price if ref_price is not None else price),
        )
        base_price = max(0.01, float(price))
        normalized_competitors = self._normalize_competitors(
            competitors,
            reference_price,
            attributes,
            plan,
        )
        normalized_scenarios = self._normalize_scenarios(
            scenarios,
            base_price,
            attributes,
            plan,
        )
        adjustments = self._agent_adjustments(agent_signals, plan)

        elasticity_scenarios = [
            {
                "scenario_id": f"elasticity_{index}",
                "name": f"价格 {ratio:.0%}",
                "price": base_price * float(ratio),
                "_elasticity_ratio": float(ratio),
            }
            for index, ratio in enumerate(
                self._elasticity_ratios(plan.elasticity_points)
            )
        ]
        all_variants = normalized_scenarios + elasticity_scenarios
        variant_metrics: Dict[str, Dict[str, List[float]]] = {
            variant["scenario_id"]: {
                "awareness": [],
                "understood": [],
                "consideration": [],
                "purchase": [],
                "repeat": [],
                "referral": [],
                "revenue_per_capita": [],
                "margin_per_capita": [],
            }
            for variant in all_variants
        }
        base_probability_sum = np.zeros(len(model_frame), dtype=float)
        base_awareness_sum = np.zeros(len(model_frame), dtype=float)

        cost = (
            max(0.0, float(variable_cost))
            if variable_cost is not None
            else base_price * float(self.profile["defaults"]["variable_cost_share"])
        )

        for round_index in range(rounds):
            round_rng = np.random.default_rng(self.seed + round_index * 10_007)
            coefficients = self._draw_coefficients(
                coefficient_priors,
                plan,
                adjustments,
                round_rng,
            )
            mixed_taste = self._mixed_taste_draws(
                len(model_frame),
                plan,
                round_rng,
            )

            for variant in all_variants:
                offer = self._offer_from_scenario(
                    attributes,
                    variant,
                    adjustments["awareness_multiplier"],
                )
                probabilities = self._choice_probabilities(
                    model_frame,
                    offer,
                    normalized_competitors,
                    reference_price,
                    normalized_study_type,
                    coefficients,
                    mixed_taste,
                )
                purchase = probabilities["purchase"]
                awareness = probabilities["awareness"]
                quality = float(offer["quality_score"])
                repeat_probability = _sigmoid(
                    float(study_model["repeat_intercept"])
                    + float(self.profile["dynamics"]["repeat_quality_effect"])
                    * quality
                    * model_frame["quality_sensitivity"].to_numpy(dtype=float)
                    + 0.45
                    * model_frame["category_engagement"].to_numpy(dtype=float)
                    - 0.28
                    * model_frame["price_sensitivity"].to_numpy(dtype=float)
                )
                referral_probability = _sigmoid(
                    float(study_model["referral_intercept"])
                    + float(self.profile["dynamics"]["referral_social_effect"])
                    * float(offer["social_proof_score"])
                    * model_frame["social_influence"].to_numpy(dtype=float)
                    + 0.45
                    * model_frame["novelty_seeking"].to_numpy(dtype=float)
                )

                metrics = variant_metrics[variant["scenario_id"]]
                metrics["awareness"].append(
                    _weighted_mean(awareness, weights)
                )
                metrics["understood"].append(
                    _weighted_mean(probabilities["understood"], weights)
                )
                metrics["consideration"].append(
                    _weighted_mean(probabilities["consideration"], weights)
                )
                purchase_rate = _weighted_mean(purchase, weights)
                metrics["purchase"].append(purchase_rate)
                purchaser_weights = weights * purchase
                metrics["repeat"].append(
                    _weighted_mean(
                        repeat_probability,
                        purchaser_weights
                        if purchaser_weights.sum() > 0
                        else weights,
                    )
                )
                metrics["referral"].append(
                    _weighted_mean(
                        referral_probability,
                        purchaser_weights
                        if purchaser_weights.sum() > 0
                        else weights,
                    )
                )
                metrics["revenue_per_capita"].append(
                    purchase_rate * float(offer["price"])
                )
                metrics["margin_per_capita"].append(
                    purchase_rate
                    * max(0.0, float(offer["price"]) - cost)
                )

                if variant["scenario_id"] == "baseline":
                    base_probability_sum += purchase
                    base_awareness_sum += awareness

        summaries = {
            variant_id: {
                metric_name: _metric_summary(metric_values)
                for metric_name, metric_values in metrics.items()
            }
            for variant_id, metrics in variant_metrics.items()
        }
        baseline = summaries["baseline"]
        baseline_revenue = max(
            baseline["revenue_per_capita"]["mean"],
            1e-9,
        )
        baseline_margin = max(
            baseline["margin_per_capita"]["mean"],
            1e-9,
        )

        scenario_results = []
        for scenario in normalized_scenarios:
            summary = summaries[scenario["scenario_id"]]
            scenario_results.append(
                {
                    "scenario_id": scenario["scenario_id"],
                    "name": scenario["name"],
                    "price": round(float(scenario["price"]), 2),
                    "purchase_rate": summary["purchase"]["mean"],
                    "purchase_p10": summary["purchase"]["p10"],
                    "purchase_p90": summary["purchase"]["p90"],
                    "revenue_idx": round(
                        summary["revenue_per_capita"]["mean"]
                        / baseline_revenue
                        * 100.0,
                        2,
                    ),
                    "margin_idx": round(
                        summary["margin_per_capita"]["mean"]
                        / baseline_margin
                        * 100.0,
                        2,
                    ),
                }
            )

        elasticity_results = []
        for elasticity in elasticity_scenarios:
            summary = summaries[elasticity["scenario_id"]]
            elasticity_results.append(
                {
                    "price": round(float(elasticity["price"]), 2),
                    "price_ratio": round(
                        float(elasticity["_elasticity_ratio"]),
                        4,
                    ),
                    "purchase_rate": summary["purchase"]["mean"],
                    "purchase_p10": summary["purchase"]["p10"],
                    "purchase_p90": summary["purchase"]["p90"],
                    "revenue_idx": round(
                        summary["revenue_per_capita"]["mean"]
                        / baseline_revenue
                        * 100.0,
                        2,
                    ),
                }
            )

        mean_purchase_probability = base_probability_sum / float(rounds)
        mean_awareness_probability = base_awareness_sum / float(rounds)
        purchase_rate = baseline["purchase"]["mean"]
        awareness_rate = baseline["awareness"]["mean"]
        repeat_rate = baseline["repeat"]["mean"]
        referral_rate = baseline["referral"]["mean"]
        funnel_rates = {
            "eligible": eligibility_rate,
            "aware": awareness_rate,
            "understood": baseline["understood"]["mean"],
            "considered": baseline["consideration"]["mean"],
            "purchased": purchase_rate,
            "repeated": purchase_rate * repeat_rate,
            "referred": purchase_rate * referral_rate,
        }
        if normalized_study_type in {
            "VENUE_STUDY",
            "SITE_COMPARISON",
            "RESTAURANT",
            "CAFE",
            "BAR",
            "RETAIL",
            "OPERATING_SCENARIO",
        }:
            funnel_labels = (
                ("eligible", "Target Audience"),
                ("aware", "Venue Aware"),
                ("understood", "Occasion Fit"),
                ("considered", "Visit Considered"),
                ("purchased", "Visited"),
                ("repeated", "Revisited"),
                ("referred", "Referred"),
            )
        elif normalized_study_type == "CREATIVE_TEST":
            funnel_labels = (
                ("eligible", "Target Audience"),
                ("aware", "Ad Reached"),
                ("understood", "Message Understood"),
                ("considered", "Offer Considered"),
                ("purchased", "Action Intended"),
                ("repeated", "Follow-up Intended"),
                ("referred", "Shared"),
            )
        else:
            funnel_labels = (
                ("eligible", "Eligible Population"),
                ("aware", "Aware"),
                ("understood", "Understood"),
                ("considered", "Considered"),
                ("purchased", "Purchased"),
                ("repeated", "Repeated"),
                ("referred", "Referred"),
            )
        funnel = [
            {
                "stage": stage,
                "label": label,
                "rate": round(funnel_rates[stage], 6),
                "value": int(round(total_population * funnel_rates[stage])),
            }
            for stage, label in funnel_labels
        ]

        coefficient_output = {
            name: {
                "mean": float(prior["mean"]),
                "sd": float(prior["sd"]),
                "source": "calibration_profile_prior",
            }
            for name, prior in coefficient_priors.items()
        }
        competitor_quality = [
            {
                "name": item["name"],
                "data_quality": item["data_quality"],
                "provided_fields": item["provided_fields"],
                "assumed_fields": item["assumed_fields"],
            }
            for item in normalized_competitors
        ]
        warnings = list(self.profile.get("limitations", []))
        if not normalized_competitors:
            warnings.append(
                "No competitor alternatives were supplied; the choice set contains only the focal offer and outside option."
            )
        elif any(
            item["data_quality"] == "name_only_assumption"
            for item in normalized_competitors
        ):
            warnings.append(
                "At least one competitor had only a name; neutral assumed attributes were used."
            )
        if any(item["assumed_fields"] for item in normalized_competitors):
            warnings.append(
                "Some competitor model fields were not observed and used disclosed priors; see model_lineage.competitors.assumed_fields."
            )
        if category_eligibility_status == "behavioral_prior_not_officially_calibrated":
            warnings.append(
                "Category eligibility uses an uncalibrated pet-ownership prior; purchase probability is not a validated category sales forecast."
            )
        if adjustments["effective_weight"] == 0:
            warnings.append(
                "LLM weak signals were unavailable or disabled and had zero effect on quantitative outputs."
            )
        if normalized_study_type in {
            "VENUE_STUDY",
            "SITE_COMPARISON",
            "RESTAURANT",
            "CAFE",
            "BAR",
            "RETAIL",
            "OPERATING_SCENARIO",
        }:
            warnings.append(
                "Offline results use geographic, travel-friction and venue-choice priors; no live footfall, mobility, queue or point-of-sale data were observed."
            )
        if normalized_study_type == "CREATIVE_TEST":
            warnings.append(
                "Creative-test action probability is a structured response prior, not an observed impression, click-through or conversion rate."
            )

        return {
            "simulation_model_version": SIMULATION_MODEL_VERSION,
            "world_model_version": str(
                population_df["world_model_version"].iloc[0]
                if "world_model_version" in population_df
                else "unknown"
            ),
            "study_type": normalized_study_type,
            "category_key": category_key,
            "category_eligible_population": int(
                round(total_population * eligibility_rate)
            ),
            "study_model_key": study_model["model_key"],
            "plan_code": plan.code,
            "population_size": total_population,
            "model_sample_size": model_sample_size,
            "mc_rounds": rounds,
            "mean_purchase_rate": purchase_rate,
            "ci_p10": baseline["purchase"]["p10"],
            "ci_p90": baseline["purchase"]["p90"],
            "metric_intervals": {
                "awareness_rate": baseline["awareness"],
                "consideration_rate": baseline["consideration"],
                "purchase_rate": baseline["purchase"],
                "repeat_rate": baseline["repeat"],
                "referral_rate": baseline["referral"],
            },
            "funnel": funnel,
            "segments": self._segment_results(
                model_frame,
                mean_purchase_probability,
                total_population,
            ),
            "regional_breakdown": self._regional_results(
                model_frame,
                mean_purchase_probability,
            ),
            "channels": self._channel_results(
                model_frame,
            ),
            "scenarios": scenario_results,
            "price_elasticity": elasticity_results,
            "market_dynamics": self._market_dynamics(
                purchase_rate,
                awareness_rate,
                repeat_rate,
                model_frame,
                plan,
            ),
            "implied_wtp": self._implied_wtp(
                coefficient_priors,
                model_frame,
                base_price,
            ),
            "model_lineage": {
                "calibration": calibration_summary(self.profile),
                "plan_config_version": PLAN_CONFIG_VERSION,
                "plan": plan.public_dict(),
                "model_family": plan.model_family,
                "study_model_key": study_model["model_key"],
                "category": {
                    "category_key": category_key,
                    "profile_version": category_profile_version,
                    "eligibility_status": category_eligibility_status,
                    "eligible_population_share": round(eligibility_rate, 6),
                },
                "coefficient_priors": coefficient_output,
                "agent_signal": adjustments,
                "competitors": competitor_quality,
                "uncertainty": {
                    "interval_type": "prior_predictive_p10_p90",
                    "components": [
                        "coefficient_prior_uncertainty",
                        "observed_population_heterogeneity",
                        "random_taste_heterogeneity"
                        if plan.model_family.startswith("mixed_logit")
                        else "fixed_taste_mnl",
                        "bounded_llm_weak_signal"
                        if adjustments["effective_weight"] > 0
                        else "no_llm_quantitative_effect",
                    ],
                    "validated_forecast_error": None,
                },
            },
            "warnings": warnings,
        }
