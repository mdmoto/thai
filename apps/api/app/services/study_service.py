"""Study orchestration for calibrated population and choice simulation."""

import os
import sys
import uuid
import json
import re
import math
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

# Add repository packages to sys.path for Cloud Run and local execution.
sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../../../packages")
    )
)

from agents.gemini_gateway import GeminiAgentGateway
from data_pipeline.market_research import PublicMarketResearch
from app.services.geospatial_research import GoogleGeospatialResearch
from simulation_core.calibration import (
    get_study_model,
    load_calibration_profile,
)
from simulation_core.config import (
    get_plan_config,
    normalize_plan_code,
    resolve_execution_config,
)
from simulation_core.engine import SIMULATION_MODEL_VERSION, SimulationEngine
from simulation_core.estimation import ConditionalLogitEstimator
from simulation_core.geo import build_geo_analysis
from world_model.generator import PopulationGenerator, WORLD_MODEL_VERSION
from world_model.category_profiles import load_category_profile
from world_model.thailand_geo import sample_point_in_province


def _data_catalog_root() -> Path:
    configured = os.environ.get("DATA_CATALOG_ROOT")
    if configured:
        return Path(configured)
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "data_catalog"
        if candidate.exists():
            return candidate
    return Path("/data_catalog")


PET_WATER_PANEL_PATH = (
    _data_catalog_root() / "categories" / "pet_water_fountain_th_v1.json"
)
SOCIAL_ACCESS_PATH = (
    _data_catalog_root() / "social" / "platform_access_v1.json"
)


SEGMENT_COPY = {
    "AFFLUENT_DIGITAL": {
        "drivers": ["品质与保障", "品牌可信度", "线上购买便利"],
        "barriers": ["本地售后证据不足"],
        "preferred_channel": "Lazada / 品牌旗舰店",
    },
    "TREND_EXPLORER": {
        "drivers": ["设计新颖", "社交推荐", "尝鲜动机"],
        "barriers": ["口碑不足", "预算波动"],
        "preferred_channel": "TikTok Shop / 社交电商",
    },
    "VALUE_SEEKER": {
        "drivers": ["折扣", "包邮", "明确性价比"],
        "barriers": ["价格", "替代品丰富"],
        "preferred_channel": "Shopee Thailand",
    },
    "EVIDENCE_SEEKER": {
        "drivers": ["可验证评价", "保修与退货保障", "详细对比信息"],
        "barriers": ["信息不完整", "品牌可信度不足", "售后不确定"],
        "preferred_channel": "品牌官网 / Lazada 官方店",
    },
    "SOCIAL_COMMERCE": {
        "drivers": ["创作者演示", "真实使用场景", "社交口碑"],
        "barriers": ["广告感过强", "缺少长期评价", "冲动购买顾虑"],
        "preferred_channel": "TikTok Shop / Facebook 内容",
    },
    "FAMILY_PRAGMATIST": {
        "drivers": ["家庭适用性", "耐用与安全", "配送售后便利"],
        "barriers": ["家庭成员意见不一致", "维护成本", "退换货麻烦"],
        "preferred_channel": "Shopee / Lazada 官方店",
    },
    "LOCAL_TRUST_OFFLINE": {
        "drivers": ["本地认证", "线下体验", "熟人推荐"],
        "barriers": ["新品牌信任", "售后与物流"],
        "preferred_channel": "线下零售 / 门店",
    },
    "MAINSTREAM": {
        "drivers": ["评价证据", "稳定品质", "购买便利"],
        "barriers": ["品牌认知", "决策惯性"],
        "preferred_channel": "Shopee / Lazada",
    },
}

AGE_GROUP_RANGES = {
    "18-24": (18, 24),
    "25-34": (25, 34),
    "35-44": (35, 44),
    "45-54": (45, 54),
    "55-64": (55, 64),
    "65+": (65, 78),
}

OBSERVED_CHOICE_FEATURES = (
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
MARKETPLACE_PLATFORMS = {"Shopee", "Lazada"}
CALIBRATED_CHOICE_STATUSES = {
    "applied_unvalidated",
    "platform_benchmark_applied_unvalidated",
}
ProgressCallback = Callable[[str, int], None]


def _utc_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _json_value(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value


def _canonical_source_url(value: Any) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw.startswith(("http://", "https://")):
        return None
    parsed = urllib.parse.urlsplit(raw)
    if not parsed.hostname:
        return None
    return urllib.parse.urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/") or "/",
            parsed.query,
            "",
        )
    )


def _signal_numbers(values: Sequence[Any]) -> List[float]:
    numbers: List[float] = []
    for value in values:
        for match in re.findall(r"\d[\d,]*(?:\.\d+)?", str(value or "")):
            try:
                number = float(match.replace(",", ""))
            except ValueError:
                continue
            if np.isfinite(number):
                numbers.append(number)
    return numbers


def _normalized_name(value: Any) -> str:
    return re.sub(
        r"[^a-z0-9ก-๙\u3400-\u9fff]+",
        "",
        str(value or "").lower(),
    )


class StudyService:
    def __init__(
        self,
        market_research: Optional[PublicMarketResearch] = None,
        geospatial_research: Optional[GoogleGeospatialResearch] = None,
    ):
        self.studies_db: Dict[str, Dict[str, Any]] = {}
        self.runs_db: Dict[str, Dict[str, Any]] = {}
        self.reports_db: Dict[str, Dict[str, Any]] = {}
        self.market_research = market_research or PublicMarketResearch()
        self.geospatial_research = (
            geospatial_research or GoogleGeospatialResearch()
        )

    def create_study(self, data: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(data)
        study_id = f"study_{uuid.uuid4().hex[:8]}"
        now = _utc_now()
        plan_code = normalize_plan_code(data.get("plan_code", "PROFESSIONAL"))
        category_profile = load_category_profile(data.get("category"))
        category_key = category_profile["category_key"]
        category_panel_version = None
        if category_key == "PET_WATER_FOUNTAIN" and PET_WATER_PANEL_PATH.exists():
            category_panel = json.loads(
                PET_WATER_PANEL_PATH.read_text(encoding="utf-8")
            )
            if not data.get("competitor_data"):
                data["competitor_data"] = category_panel[
                    "professional_choice_set"
                ]
            if data.get("reference_price") is None:
                data["reference_price"] = category_panel["price_summary"][
                    "median_thb"
                ]
            if data.get("price") is None:
                data["price"] = category_panel["price_summary"]["median_thb"]
            category_panel_version = category_panel["panel_version"]
        data["category"] = category_key
        price = data.get("price")
        if price is None:
            price = data.get("average_check")
        if price is None:
            price = 299.0

        fact_fields = (
            "url",
            "template_key",
            "description",
            "category",
            "brand_awareness",
            "reference_price",
            "variable_cost",
            "average_check",
            "capacity",
            "location",
            "venue_type",
            "opening_hours",
            "parking",
            "distance_km",
            "creative_format",
            "channel",
            "campaign_budget",
            "marketplaces",
            "shipping_fee",
            "delivery_days",
            "cod_available",
            "official_store",
            "candidate_locations",
            "product_attributes",
            "competitor_data",
            "scenarios",
            "category_panel_version",
            "research_urls",
        )
        facts = {
            "product_name": data.get("product_name") or data.get("name"),
            "price": float(price),
        }
        for field in fact_fields:
            if data.get(field) is not None:
                facts[field] = data[field]
        if category_panel_version:
            facts["category_panel_version"] = category_panel_version

        study = {
            "id": study_id,
            "name": data.get("name", "未命名研究项目"),
            "study_type": (
                data.get("study_type") or "PRODUCT_VALIDATION"
            ).upper(),
            "status": "NEEDS_CONFIRMATION",
            "plan_code": plan_code,
            "inputs": data,
            "facts": facts,
            "inferences": [
                {
                    "label": "模型选择",
                    "value": "将根据 study_type 使用行业专属选择模型",
                    "grade": "B",
                },
                {
                    "label": "数据校准状态",
                    "value": "人口与收入使用泰国 NSO 公开宏观数据；选择系数与品类渗透仍为先验",
                    "grade": "D",
                },
                {
                    "label": "品类数据",
                    "value": (
                        f"已加载公开竞品面板 {category_panel_version}"
                        if category_panel_version
                        else "未匹配专用品类面板，使用通用消费品先验"
                    ),
                    "grade": "B" if category_panel_version else "D",
                },
            ],
            "defaults": [
                {
                    "label": "品牌认知",
                    "value": "未提供时使用版本化先验，并进入不确定性计算",
                    "grade": "D",
                },
                {
                    "label": "竞品属性",
                    "value": "仅有名称时采用中性占位属性并明确披露",
                    "grade": "D",
                },
            ],
            "created_at": now,
            "updated_at": now,
        }
        self.studies_db[study_id] = study
        return study

    def hydrate_study(
        self,
        study_id: str,
        name: str,
        study_type: str,
        status: str,
        plan_code: str,
        inputs: Optional[Mapping[str, Any]],
        facts: Optional[Mapping[str, Any]],
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        study = {
            "id": study_id,
            "name": name,
            "study_type": study_type,
            "status": status,
            "plan_code": normalize_plan_code(plan_code),
            "inputs": dict(inputs or {}),
            "facts": dict(facts or {}),
            "inferences": [],
            "defaults": [],
            "created_at": created_at or _utc_now(),
            "updated_at": updated_at or _utc_now(),
        }
        self.studies_db[study_id] = study
        return study

    def confirm_study(
        self,
        study_id: str,
        overrides: Dict[str, Any],
    ) -> Dict[str, Any]:
        if study_id not in self.studies_db:
            raise KeyError("Study not found")
        study = self.studies_db[study_id]
        study["status"] = "READY"
        study["facts"].update(overrides)
        study["updated_at"] = _utc_now()
        return study

    def _competitors(self, study: Mapping[str, Any]) -> List[Dict[str, Any]]:
        inputs = study["inputs"]
        facts = study["facts"]
        competitors: List[Dict[str, Any]] = []
        supplied = facts.get("competitor_data") or inputs.get("competitor_data") or []
        for item in supplied:
            if isinstance(item, Mapping):
                competitors.append(dict(item))
        existing_names = {str(item.get("name")) for item in competitors}
        for name in inputs.get("competitors", []):
            normalized_name = str(name or "").strip()
            is_url = normalized_name.startswith(("http://", "https://"))
            if (
                normalized_name
                and not is_url
                and normalized_name not in existing_names
            ):
                competitors.append(
                    {
                        "name": normalized_name,
                        "data_quality": "name_only_assumption",
                    }
                )
        return competitors

    def _calibration_profile_for_run(
        self,
        study: Mapping[str, Any],
        plan: Any,
        model_study_type: str,
        platform_override: Optional[Mapping[str, Any]] = None,
    ) -> tuple[Dict[str, Any], Dict[str, Any], List[str]]:
        inputs = study.get("inputs") or {}
        observed_rows = list(inputs.get("observed_choice_data") or [])
        manual_overrides = inputs.get("calibration_overrides")
        warnings: List[str] = []

        if not observed_rows:
            use_overrides = manual_overrides if plan.customer_calibration else None
            if manual_overrides and not plan.customer_calibration:
                warnings.append(
                    f"{plan.code} 不支持客户校准覆盖，已使用平台基础模型。"
                )
            selected_override = use_overrides or platform_override
            profile = load_calibration_profile(overrides=selected_override)
            if platform_override and not use_overrides:
                benchmark = dict(
                    platform_override.get("platform_benchmark") or {}
                )
                profile.setdefault("sources", []).append(
                    {
                        "source_id": "POOLED_PLATFORM_CHOICE_BENCHMARK",
                        "source_type": (
                            "deidentified_observed_choice_fit_aggregate"
                        ),
                        "observed": True,
                        "record_count": benchmark.get(
                            "contribution_count",
                            0,
                        ),
                        "choice_set_count": benchmark.get(
                            "choice_set_count",
                            0,
                        ),
                        "note": (
                            "Only pooled coefficient summaries and sample "
                            "counts are used; no raw customer rows or customer "
                            "identifiers are included."
                        ),
                    }
                )
                profile.setdefault("limitations", []).append(
                    "The pooled category benchmark has not passed "
                    "out-of-sample or time-based validation."
                )
                return (
                    profile,
                    {
                        "status": (
                            "platform_benchmark_applied_unvalidated"
                        ),
                        "method": (
                            "privacy_thresholded_weighted_robust_pooling"
                        ),
                        "coefficient_effect": (
                            "pooled_platform_coefficients_replaced_priors"
                        ),
                        "study_type": model_study_type,
                        "diagnostics": benchmark,
                        "validation_status": (
                            "out_of_sample_validation_required"
                        ),
                    },
                    warnings,
                )
            return (
                profile,
                {
                    "status": "not_supplied",
                    "method": "conditional_multinomial_logit_newton",
                    "coefficient_effect": "none",
                    "reason": "未提供真实订单、选择实验或 A/B 选择数据。",
                },
                warnings,
            )

        if not plan.customer_calibration:
            raise ValueError(
                f"{plan.code} 不支持真实选择数据校准，请使用深度决策。"
            )
        if manual_overrides:
            raise ValueError(
                "真实选择数据与手工系数覆盖不能同时使用，请只保留一种校准来源。"
            )

        frame = pd.DataFrame(observed_rows)
        required = {"choice_set_id", "chosen"}
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(
                "真实选择数据缺少字段：" + ", ".join(sorted(missing))
            )
        feature_columns = [
            name
            for name in OBSERVED_CHOICE_FEATURES
            if name in frame.columns
            and frame[name].notna().all()
            and frame[name].nunique(dropna=True) > 1
        ]
        if not feature_columns:
            raise ValueError(
                "真实选择数据至少需要一个在备选方案之间发生变化的模型特征。"
            )
        for column in feature_columns:
            frame[column] = pd.to_numeric(frame[column], errors="raise")
            if not np.isfinite(frame[column].to_numpy(dtype=float)).all():
                raise ValueError(f"真实选择特征 {column} 包含无效数字。")

        choice_set_count = int(frame["choice_set_id"].nunique())
        minimum_choice_sets = max(20, len(feature_columns) * 5)
        if choice_set_count < minimum_choice_sets:
            raise ValueError(
                "真实选择数据量不足："
                f"当前 {choice_set_count} 个选择组，至少需要 "
                f"{minimum_choice_sets} 个。"
            )

        base_profile = load_calibration_profile()
        base_model = get_study_model(base_profile, model_study_type)
        initial_coefficients = {
            name: float(base_model["coefficients"][name]["mean"])
            for name in feature_columns
            if name in base_model["coefficients"]
        }
        fit = ConditionalLogitEstimator(
            l2_penalty=0.05,
            max_iterations=150,
            tolerance=1e-7,
        ).fit(
            frame,
            feature_columns,
            initial_coefficients=initial_coefficients,
        )
        if not fit.converged:
            raise ValueError(
                "真实选择模型未收敛，未替换生产系数；请检查选择组和特征尺度。"
            )
        override = fit.calibration_override(model_study_type)
        profile = load_calibration_profile(overrides=override)
        profile["limitations"] = [
            limitation
            for limitation in profile.get("limitations", [])
            if "Choice coefficients" not in str(limitation)
        ]
        profile["limitations"].append(
            "Choice coefficients were fitted from supplied observed choice "
            "sets but have not passed out-of-sample or time-based validation."
        )
        profile.setdefault("sources", []).append(
            {
                "source_id": "CUSTOMER_OBSERVED_CHOICE_DATA",
                "source_type": "observed_choice_data",
                "observed": True,
                "record_count": len(frame),
                "choice_set_count": choice_set_count,
                "note": (
                    "Customer-supplied grouped choices; raw rows are not "
                    "embedded in the report."
                ),
            }
        )
        diagnostics = {
            key: value
            for key, value in fit.to_dict().items()
            if key != "covariance"
        }
        return (
            profile,
            {
                "status": "applied_unvalidated",
                "method": "conditional_multinomial_logit_newton",
                "coefficient_effect": "fitted_coefficients_replaced_priors",
                "study_type": model_study_type,
                "feature_columns": feature_columns,
                "diagnostics": diagnostics,
                "validation_status": "out_of_sample_validation_required",
            },
            warnings,
        )

    def _research_enriched_choice_inputs(
        self,
        study: Mapping[str, Any],
        market_research: Mapping[str, Any],
        competitor_limit: int,
    ) -> Dict[str, Any]:
        product_attributes = self._product_attributes(study)
        competitors = self._competitors(study)
        inputs = study.get("inputs") or {}
        facts = study.get("facts") or {}
        focal_urls = {
            canonical
            for canonical in (
                _canonical_source_url(facts.get("url")),
                _canonical_source_url(inputs.get("url")),
            )
            if canonical
        }
        focal_name = _normalized_name(
            facts.get("product_name") or study.get("name")
        )
        used_sources: List[str] = []
        focal_fields: List[str] = []
        competitor_fields = 0

        def competitor_urls(item: Mapping[str, Any]) -> set[str]:
            return {
                canonical
                for canonical in (
                    _canonical_source_url(item.get("source_url")),
                    _canonical_source_url(item.get("url")),
                    _canonical_source_url(item.get("product_url")),
                )
                if canonical
            }

        for evidence in market_research.get("evidence") or []:
            if not isinstance(evidence, Mapping):
                continue
            signals = evidence.get("market_signals") or {}
            price_values = _signal_numbers(signals.get("prices") or [])
            rating_values = []
            for rating_signal in signals.get("ratings") or []:
                parsed_rating = _signal_numbers([rating_signal])
                if parsed_rating and 0 <= parsed_rating[0] <= 5:
                    rating_values.append(parsed_rating[0])
            review_values = _signal_numbers(
                signals.get("review_mentions") or []
            )
            if not price_values and not rating_values and not review_values:
                continue
            source_url = _canonical_source_url(evidence.get("url"))
            title = str(evidence.get("title") or "").strip()[:200]
            normalized_title = _normalized_name(title)
            source_id = str(evidence.get("source_id") or "")

            extracted: Dict[str, Any] = {}
            if price_values:
                plausible_prices = [
                    value for value in price_values if 1 <= value <= 10_000_000
                ]
                if plausible_prices:
                    extracted["price"] = float(np.median(plausible_prices))
            if rating_values:
                extracted["review_score"] = float(
                    np.clip(np.median(rating_values) / 5.0, 0.0, 1.0)
                )
            if review_values:
                review_count = max(review_values)
                if review_count >= 1:
                    extracted["social_proof_score"] = float(
                        np.clip(
                            np.log1p(review_count) / np.log1p(10_000),
                            0.0,
                            1.0,
                        )
                    )
            if not extracted:
                continue

            if source_url and source_url in focal_urls:
                focal_changed = False
                for field in ("review_score", "social_proof_score"):
                    if (
                        field in extracted
                        and field not in product_attributes
                    ):
                        product_attributes[field] = extracted[field]
                        focal_fields.append(field)
                        focal_changed = True
                if focal_changed and source_id:
                    used_sources.append(source_id)
                continue

            matched: Optional[Dict[str, Any]] = None
            for competitor in competitors:
                exact_url_match = bool(
                    source_url
                    and source_url in competitor_urls(competitor)
                )
                normalized_competitor = _normalized_name(
                    competitor.get("name")
                )
                name_match = bool(
                    normalized_competitor
                    and normalized_title
                    and (
                        normalized_competitor in normalized_title
                        or normalized_title in normalized_competitor
                    )
                )
                if exact_url_match or name_match:
                    matched = competitor
                    break

            is_focal_title = bool(
                focal_name
                and normalized_title
                and (
                    focal_name in normalized_title
                    or normalized_title in focal_name
                )
            )
            if (
                matched is None
                and str(evidence.get("platform")) in MARKETPLACE_PLATFORMS
                and "price" in extracted
                and title
                and not is_focal_title
                and len(competitors) < competitor_limit
            ):
                matched = {
                    "name": title,
                    "source_url": source_url,
                }
                competitors.append(matched)

            if matched is None:
                continue
            changed = False
            changed_fields = 0
            for field, value in extracted.items():
                if matched.get(field) is None:
                    matched[field] = value
                    changed = True
                    changed_fields += 1
            if changed:
                matched["data_quality"] = (
                    "public_price_rating_evidence_unvalidated"
                )
                matched["evidence_source_id"] = source_id or None
                competitor_fields += changed_fields
                if source_id:
                    used_sources.append(source_id)

        return {
            "product_attributes": product_attributes,
            "competitors": competitors[:competitor_limit],
            "lineage": {
                "status": (
                    "applied"
                    if used_sources
                    else "no_usable_quantitative_fields"
                ),
                "coefficient_effect": "none",
                "choice_set_effect": (
                    "public_price_rating_fields_update_offer_attributes"
                ),
                "source_ids": list(dict.fromkeys(used_sources)),
                "focal_fields_enriched": sorted(set(focal_fields)),
                "competitor_field_updates": competitor_fields,
                "limitation": (
                    "公开价格、评分和评论量只更新产品与竞品属性；"
                    "不会被当作真实成交选择，也不会重新拟合购买系数。"
                ),
            },
        }

    def _product_attributes(self, study: Mapping[str, Any]) -> Dict[str, Any]:
        attributes: Dict[str, Any] = {}
        for source in (study["inputs"], study["facts"]):
            nested = source.get("product_attributes")
            if isinstance(nested, Mapping):
                attributes.update(nested)
            for field in (
                "quality_score",
                "review_score",
                "design_score",
                "convenience_score",
                "localization_score",
                "clarity_score",
                "social_proof_score",
                "brand_strength",
                "warranty_score",
                "delivery_score",
                "return_policy_score",
                "payment_flexibility_score",
                "sustainability_score",
                "distance_km",
            ):
                if source.get(field) is not None:
                    attributes[field] = source[field]
        facts = study["facts"]
        inputs = study["inputs"]
        delivery_days = facts.get("delivery_days", inputs.get("delivery_days"))
        if delivery_days is not None and "delivery_score" not in attributes:
            attributes["delivery_score"] = max(
                0.15,
                min(0.95, 1.0 - (float(delivery_days) - 1.0) * 0.09),
            )
        cod_available = facts.get(
            "cod_available",
            inputs.get("cod_available"),
        )
        if (
            cod_available is not None
            and "payment_flexibility_score" not in attributes
        ):
            attributes["payment_flexibility_score"] = (
                0.82 if bool(cod_available) else 0.52
            )
        official_store = facts.get(
            "official_store",
            inputs.get("official_store"),
        )
        if official_store:
            attributes.setdefault("warranty_score", 0.78)
            attributes.setdefault("return_policy_score", 0.7)
            attributes.setdefault("brand_strength", 0.68)
        return attributes

    def _effective_model_type(self, study: Mapping[str, Any]) -> str:
        """Select a venue-specific prior while preserving the public study type."""
        study_type = str(study["study_type"]).upper()
        if study_type not in {"VENUE_STUDY", "OPERATING_SCENARIO"}:
            return study_type
        venue_type = str(
            study["facts"].get("venue_type")
            or study["inputs"].get("venue_type")
            or study["facts"].get("category")
            or ""
        ).upper()
        if venue_type in {"RESTAURANT", "CAFE", "BAR", "RETAIL"}:
            return venue_type
        return study_type

    def _commerce_analysis(
        self,
        study: Mapping[str, Any],
    ) -> Optional[Dict[str, Any]]:
        facts = study["facts"]
        if str(facts.get("template_key") or "").upper() != "ECOMMERCE":
            return None
        marketplaces = facts.get("marketplaces") or ["Shopee", "Lazada"]
        delivery_days = float(facts.get("delivery_days") or 4.0)
        shipping_fee = float(facts.get("shipping_fee") or 0.0)
        cod_available = bool(
            True if facts.get("cod_available") is None
            else facts.get("cod_available")
        )
        official_store = bool(facts.get("official_store") or False)
        trust_score = 45.0
        trust_score += 18.0 if official_store else 0.0
        trust_score += 10.0 if cod_available else 0.0
        trust_score += max(-18.0, 12.0 - delivery_days * 3.0)
        trust_score += max(-12.0, 8.0 - shipping_fee / 20.0)
        return {
            "marketplaces": marketplaces,
            "delivery_days": delivery_days,
            "shipping_fee_thb": shipping_fee,
            "cod_available": cod_available,
            "official_store": official_store,
            "checkout_trust_index": round(max(0.0, min(100.0, trust_score)), 1),
            "frictions": [
                message
                for condition, message in (
                    (delivery_days > 5, "配送时间超过 5 天"),
                    (shipping_fee > 60, "运费高于低客单商品常见容忍区间"),
                    (not cod_available, "未提供货到付款"),
                    (not official_store, "缺少官方店信任标记"),
                )
                if condition
            ],
            "status": "structured_ecommerce_prior_not_transaction_data",
        }

    def _representative_records(
        self,
        generator: PopulationGenerator,
        population_df: Any,
        sample_size: int,
        seed: int,
    ) -> List[Dict[str, Any]]:
        if sample_size <= 0:
            return []
        representative_population = population_df
        if (
            "category_eligible" in population_df
            and bool(population_df["category_eligible"].any())
        ):
            representative_population = population_df[
                population_df["category_eligible"]
            ].copy()
        sampled = generator.stratified_sample(
            representative_population,
            min(sample_size, len(representative_population)),
            seed=seed,
        )
        records = []
        for row in sampled.to_dict(orient="records"):
            record = _json_value(row)
            record["representative_id"] = record["person_id"]
            records.append(record)
        return records

    def _consumer_voices(
        self,
        agent_research: Mapping[str, Any],
        representatives: Sequence[Mapping[str, Any]],
    ) -> List[Dict[str, Any]]:
        lookup = {
            str(item["representative_id"]): item
            for item in representatives
        }
        voices = []
        for response in agent_research.get("responses", [])[:12]:
            profile = lookup.get(response["representative_id"], {})
            income = float(profile.get("monthly_income_thb", 0))
            persona = (
                f"{profile.get('age_group', '年龄未知')} · "
                f"{profile.get('province', profile.get('region', '地区未知'))} · "
                f"{profile.get('income_tier', '收入层未知')}"
            )
            barriers = response.get("purchase_barriers", [])
            voices.append(
                {
                    "persona": persona,
                    "segment": profile.get("segment_id", "UNCLASSIFIED"),
                    "sentiment": response.get("sentiment", "neutral"),
                    "quote": response.get("qualitative_reason", ""),
                    "reasoning": (
                        "结构化 LLM 弱标签，仅用于小权重调整属性先验；"
                        "未直接计入购买率。"
                    ),
                    "price_reaction": (
                        "价格是主要阻碍"
                        if "price" in barriers
                        else "价格不是首要阻碍"
                    ),
                    "preferred_channel": response.get(
                        "preferred_channel",
                        "unspecified",
                    ),
                    "representative_id": response["representative_id"],
                    "monthly_income_thb": round(income, 0),
                    "source_type": agent_research.get("source_type"),
                }
            )
        return voices

    def _sample_profile(
        self,
        generator: PopulationGenerator,
        population_df: Any,
        seed: int,
    ) -> Dict[str, Any]:
        """Build a bounded visualization sample without exposing real locations."""
        display_size = min(600, len(population_df))
        sampled = generator.stratified_sample(
            population_df,
            display_size,
            seed=seed + 1109,
        )
        rng = np.random.default_rng(seed + 2203)
        points = []
        for row in sampled.to_dict(orient="records"):
            age_group = str(row.get("age_group") or "35-44")
            low, high = AGE_GROUP_RANGES.get(age_group, (35, 44))
            age = int(rng.integers(low, high + 1))
            region = str(row.get("region") or "Central")
            province = str(row.get("province") or "Bangkok")
            # These are synthetic display points sampled inside the assigned
            # province polygon, not observed household addresses.
            latitude, longitude = sample_point_in_province(province, rng)
            points.append(
                {
                    "person_id": row.get("person_id"),
                    "age": age,
                    "age_group": age_group,
                    "household_income_thb": round(
                        float(row.get("household_monthly_income_thb") or 0),
                        0,
                    ),
                    "income_tier": row.get("income_tier"),
                    "region": region,
                    "province": province,
                    "latitude": round(latitude, 4),
                    "longitude": round(longitude, 4),
                    "category_eligible": bool(
                        row.get("category_eligible", True)
                    ),
                }
            )

        age_counts = (
            sampled["age_group"].value_counts(normalize=True).to_dict()
        )
        income_counts = (
            sampled["income_tier"].value_counts(normalize=True).to_dict()
        )
        region_counts = (
            sampled["region"].value_counts(normalize=True).to_dict()
        )
        return {
            "population_size": len(population_df),
            "display_sample_size": len(points),
            "points": points,
            "age_distribution": [
                {"label": key, "share": round(float(value), 6)}
                for key, value in age_counts.items()
            ],
            "income_distribution": [
                {"label": key, "share": round(float(value), 6)}
                for key, value in income_counts.items()
            ],
            "region_distribution": [
                {"label": key, "share": round(float(value), 6)}
                for key, value in region_counts.items()
            ],
            "location_status": "synthetic_province_polygon_sample",
            "location_disclosure": (
                "点位依据 AI 模拟消费人群所属府，在真实泰国府界多边形内确定性抽样，"
                "仅展示地域分布；不是个人住址、设备定位或实测客流。"
            ),
        }

    def _social_evidence_policy(self) -> Dict[str, Any]:
        with SOCIAL_ACCESS_PATH.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _enrich_segments(
        self,
        segments: Sequence[Mapping[str, Any]],
    ) -> List[Dict[str, Any]]:
        output = []
        for segment in segments:
            copy = dict(segment)
            text = SEGMENT_COPY.get(
                str(segment.get("segment_id")),
                SEGMENT_COPY["MAINSTREAM"],
            )
            copy.update(text)
            output.append(copy)
        return output

    def _main_barrier(
        self,
        sim_results: Mapping[str, Any],
        agent_research: Mapping[str, Any],
    ) -> str:
        barrier_share = (
            agent_research.get("aggregate", {}).get("barrier_share", {})
        )
        if barrier_share:
            top = next(iter(barrier_share))
            return f"代表样本最常见的结构化阻碍是 {top}；该信号尚需真实调研验证。"
        awareness = sim_results["metric_intervals"]["awareness_rate"]["mean"]
        if awareness < 0.2:
            return "当前基线的主要约束是品牌认知不足；此判断来自选择模型漏斗，不是 LLM 投票。"
        return "当前缺少可验证的竞品与历史转化数据，模型不确定性仍是首要决策约束。"

    def _evidence_estimates(
        self,
        sim_results: Mapping[str, Any],
        agent_research: Mapping[str, Any],
    ) -> List[Dict[str, Any]]:
        """Return provisional results even when stronger evidence is absent."""
        lineage = sim_results["model_lineage"]
        purchase = sim_results["metric_intervals"]["purchase_rate"]
        category = lineage.get("category", {})
        competitors = lineage.get("competitors", [])
        choice_estimation = lineage.get("choice_estimation", {})
        choice_status = choice_estimation.get("status")
        customer_fitted_choices = choice_status == "applied_unvalidated"
        calibrated_choices = (
            choice_status in CALIBRATED_CHOICE_STATUSES
        )
        social = sim_results.get("social_dynamics", [])
        final_period = max(
            (int(item["period"]) for item in social),
            default=0,
        )
        final_social = [
            item for item in social if int(item["period"]) == final_period
        ]
        social_low = min(
            (float(item["relative_sales_index"]) for item in final_social),
            default=100.0,
        )
        social_high = max(
            (float(item["relative_sales_index"]) for item in final_social),
            default=100.0,
        )
        agent_count = int(agent_research.get("sample_size_completed") or 0)
        return [
            {
                "topic": "购买 / 到店选择",
                "result": (
                    f"{float(purchase['mean']):.2%}，"
                    f"{'校准后模型预测区间' if calibrated_choices else '先验预测区间'} "
                    f"{float(purchase['p10']):.2%}–"
                    f"{float(purchase['p90']):.2%}"
                ),
                "grade": "B" if calibrated_choices else "C",
                "basis": (
                    "官方宏观校准人口 + 真实选择组条件多项 Logit 拟合 + "
                    "竞品与不选择选项"
                    if customer_fitted_choices
                    else (
                        "官方宏观校准人口 + 去标识化品类选择基准 + "
                        "竞品与不选择选项"
                        if calibrated_choices
                        else (
                            "官方宏观校准人口 + 行业选择模型 + "
                            "竞品与不选择选项"
                        )
                    )
                ),
                "limitation": (
                    "选择系数已经拟合，但尚未完成时间外或样本外回测。"
                    if customer_fitted_choices
                    else (
                        "品类基准来自多项目聚合，尚未完成当前项目的样本外回测。"
                        if calibrated_choices
                        else (
                            "选择系数尚未由真实订单、选择实验或 "
                            "A/B 数据拟合。"
                        )
                    )
                ),
            },
            {
                "topic": "品类目标人群",
                "result": (
                    f"{float(category.get('eligible_population_share', 1.0)):.1%}"
                    " 的 AI 模拟消费人群符合当前品类资格规则"
                ),
                "grade": "C",
                "basis": str(
                    category.get(
                        "eligibility_status",
                        "通用品类资格先验",
                    )
                ),
                "limitation": "没有官方品类渗透率时使用已披露的行为先验。",
            },
            {
                "topic": "消费者理由与阻碍",
                "result": (
                    f"获得 {agent_count} 份结构化 LLM 弱信号"
                    if agent_count
                    else "使用五类模型细分的驱动因素、阻碍与渠道偏好摘要"
                ),
                "grade": "D" if not agent_count else "C",
                "basis": (
                    "代表样本结构化解释"
                    if agent_count
                    else "选择模型细分摘要；未虚构访谈原话"
                ),
                "limitation": (
                    "LLM 或真人定性研究不可用时，仍输出模型摘要，"
                    "但不得称为消费者原话。"
                ),
            },
            {
                "topic": "竞品证据",
                "result": f"纳入 {len(competitors)} 个竞品选择项并记录缺失字段",
                "grade": "B" if competitors else "D",
                "basis": "公开报价、商家功能声明与显式字段先验",
                "limitation": "公开页面价格和评价不等于成交量或真实转化率。",
            },
            {
                "topic": "传播影响",
                "result": (
                    f"期末相对销售指数范围 {social_low:.1f}–"
                    f"{social_high:.1f}（自然传播 = 100）"
                ),
                "grade": "D",
                "basis": "晒单、好评、创作者推广与差评冲击的动态传播先验",
                "limitation": "未接入平台曝光—互动—归因成交前，只用于压力测试。",
            },
        ]

    def _evidence_acquisition(
        self,
        sim_results: Mapping[str, Any],
        agent_research: Mapping[str, Any],
        market_research: Mapping[str, Any],
    ) -> Dict[str, Any]:
        calibration_sources = sim_results["model_lineage"][
            "calibration"
        ].get("sources", [])
        observed_macro = sum(
            1 for source in calibration_sources if source.get("observed")
        )
        competitors = sim_results["model_lineage"].get("competitors", [])
        choice_estimation = sim_results["model_lineage"].get(
            "choice_estimation",
            {},
        )
        choice_status = choice_estimation.get("status")
        choice_fit_applied = choice_status == "applied_unvalidated"
        platform_benchmark_applied = (
            choice_status == "platform_benchmark_applied_unvalidated"
        )
        geo = sim_results.get("geo_analysis")
        public_collectors = list(market_research.get("collectors") or [])
        return {
            "execution_policy": "independent_collectors_fail_open",
            "collectors": [
                {
                    "collector": "Thailand NSO versioned snapshots",
                    "status": "succeeded" if observed_macro else "fallback",
                    "result_count": observed_macro,
                    "fallback_result": (
                        None if observed_macro else "versioned_population_prior"
                    ),
                },
                {
                    "collector": "Category competitor public evidence",
                    "status": "succeeded" if competitors else "fallback",
                    "result_count": len(competitors),
                    "fallback_result": (
                        None if competitors else "generic_competitor_prior"
                    ),
                },
                {
                    "collector": "Customer observed choice calibration",
                    "status": (
                        "succeeded"
                        if choice_fit_applied
                        else choice_estimation.get("status", "not_supplied")
                    ),
                    "result_count": int(
                        choice_estimation.get("diagnostics", {}).get(
                            "choice_sets"
                        )
                        or 0
                    ),
                    "fallback_result": (
                        None
                        if choice_fit_applied
                        else "disclosed_choice_coefficient_prior"
                    ),
                },
                {
                    "collector": "Pooled platform category calibration",
                    "status": (
                        "succeeded"
                        if platform_benchmark_applied
                        else "threshold_not_met_or_customer_fit_used"
                    ),
                    "result_count": int(
                        choice_estimation.get("diagnostics", {}).get(
                            "contribution_count"
                        )
                        or 0
                    ),
                    "fallback_result": (
                        None
                        if platform_benchmark_applied
                        else "customer_or_disclosed_choice_model"
                    ),
                },
                {
                    "collector": "Open geospatial / POI evidence",
                    "status": "succeeded" if geo else "not_applicable",
                    "result_count": (
                        len(geo.get("sources", [])) if geo else 0
                    ),
                    "fallback_result": (
                        None if geo else "synthetic_region_distribution"
                    ),
                },
                {
                    "collector": "Structured LLM research",
                    "status": agent_research.get("status", "unavailable"),
                    "result_count": int(
                        agent_research.get("sample_size_completed") or 0
                    ),
                    "fallback_result": "model_segment_summary",
                },
                {
                    "collector": "Social platform evidence",
                    "status": (
                        "succeeded"
                        if market_research.get("source_count")
                        else "public_only"
                    ),
                    "result_count": int(
                        market_research.get("source_count") or 0
                    ),
                    "fallback_result": (
                        None
                        if market_research.get("source_count")
                        else "disclosed_social_propagation_scenarios"
                    ),
                },
                *public_collectors,
            ],
        }

    def _report(
        self,
        study: Mapping[str, Any],
        run_id: str,
        sim_results: Mapping[str, Any],
        agent_research: Mapping[str, Any],
        representatives: Sequence[Mapping[str, Any]],
        sample_profile: Mapping[str, Any],
        market_research: Mapping[str, Any],
    ) -> Dict[str, Any]:
        report_id = f"rpt_{uuid.uuid4().hex[:8]}"
        scenarios = list(sim_results["scenarios"])
        best_scenario = max(scenarios, key=lambda item: item["revenue_idx"])
        segments = self._enrich_segments(sim_results["segments"])
        best_segment = segments[0] if segments else None
        metrics = sim_results["metric_intervals"]
        calibration_lineage = sim_results["model_lineage"]["calibration"]
        calibration_status = calibration_lineage["status"]
        interval_type = sim_results["model_lineage"].get(
            "uncertainty",
            {},
        ).get("interval_type", "prior_predictive_p10_p90")
        choice_estimation = sim_results["model_lineage"].get(
            "choice_estimation",
            {},
        )
        choice_status = choice_estimation.get("status")
        fitted_choices = choice_status == "applied_unvalidated"
        platform_calibrated = (
            choice_status == "platform_benchmark_applied_unvalidated"
        )
        calibrated_choices = (
            choice_status in CALIBRATED_CHOICE_STATUSES
        )
        has_official_macro = any(
            source.get("source_type") == "official_public_aggregate"
            and source.get("observed")
            for source in calibration_lineage.get("sources", [])
        )
        population_stage = (
            "official_macro_calibrated_population"
            if has_official_macro
            else "versioned_population_prior"
        )
        population_calibration_label = (
            "宏观人口已校准"
            if has_official_macro
            else "宏观人口仍为先验"
        )
        if calibration_status == "validated":
            choice_calibration_label = "选择系数已完成历史回测"
        elif calibration_status == "observed_choice_fit_unvalidated":
            choice_calibration_label = "选择系数已由观测选择拟合但尚未回测"
        elif calibration_status == "platform_category_benchmark_unvalidated":
            choice_calibration_label = "选择系数已采用平台品类基准但尚未回测"
        else:
            choice_calibration_label = "选择系数仍为先验"
        purchase = metrics["purchase_rate"]
        awareness = metrics["awareness_rate"]
        consideration = metrics["consideration_rate"]
        repeat = metrics["repeat_rate"]
        is_venue = study["study_type"] in {
            "VENUE_STUDY",
            "SITE_COMPARISON",
            "OPERATING_SCENARIO",
        }
        is_creative = study["study_type"] == "CREATIVE_TEST"
        if is_venue:
            metric_labels = (
                "总体到店概率",
                "门店认知概率",
                "进入到店考虑概率",
                "到店后复访倾向",
            )
            audience_rate_label = "模型到店率"
        elif is_creative:
            metric_labels = (
                "总体行动倾向",
                "广告触达认知概率",
                "进入考虑概率",
                "后续转化倾向",
            )
            audience_rate_label = "模型行动率"
        else:
            metric_labels = (
                "总体购买概率",
                "品牌认知概率",
                "进入考虑概率",
                "购买后复购倾向",
            )
            audience_rate_label = "模型购买率"

        validation_warning = (
            "在完成样本外或时间外回测前，"
            if calibrated_choices
            else "在接入真实订单、选择实验或 A/B 选择数据并完成回测前，"
        )
        recommendation = (
            f"当前{population_calibration_label}、{choice_calibration_label}的 "
            f"{sim_results['study_model_key']} 模型中，"
            f"“{best_scenario['name']}”的相对收入指数最高"
            f"（{best_scenario['revenue_idx']:.1f}）。"
            f"{validation_warning}"
            "该结果应作为方案筛选依据，而不是销量承诺。"
        )
        next_steps = [
            "补充至少一个可验证的竞品价格、评价、渠道和品牌认知基准。",
            (
                "扩大真实选择样本，并执行时间外或样本外回测。"
                if fitted_choices
                else (
                    "补充当前产品的真实选择数据，验证平台品类基准。"
                    if platform_calibrated
                    else "导入客户历史订单、选择实验或 A/B 选择数据，"
                    "拟合并替换当前系数先验。"
                )
            ),
            f"优先验证“{best_scenario['name']}”，同时保留基准方案作为对照组。",
            "上线前执行时间外回测，并记录预测误差、数据版本与模型版本。",
        ]
        report = {
            "schema_version": "2",
            "report_id": report_id,
            "run_id": run_id,
            "study_id": study["id"],
            "study_name": study["name"],
            "study_type": study["study_type"],
            "category_key": sim_results["category_key"],
            "plan_code": sim_results["plan_code"],
            "world_model_version": sim_results["world_model_version"],
            "simulation_model_version": sim_results[
                "simulation_model_version"
            ],
            "population_size": sim_results["population_size"],
            "category_eligible_population": sim_results[
                "category_eligible_population"
            ],
            "model_sample_size": sim_results["model_sample_size"],
            "mc_rounds": sim_results["mc_rounds"],
            "generated_at": _utc_now(),
            "calibration_status": calibration_status,
            "executive_summary": {
                "recommendation": recommendation,
                "best_audience": (
                    f"{best_segment['name']}（{audience_rate_label} "
                    f"{best_segment['purchase_rate']:.1%}）"
                    if best_segment
                    else "暂无可识别人群"
                ),
                "main_barrier": self._main_barrier(
                    sim_results,
                    agent_research,
                ),
                "best_scenario": best_scenario["name"],
                "key_metrics": [
                    {
                        "label": metric_labels[0],
                        "value": purchase["mean"],
                        "ci": [purchase["p10"], purchase["p90"]],
                        "interval_type": interval_type,
                    },
                    {
                        "label": metric_labels[1],
                        "value": awareness["mean"],
                        "ci": [awareness["p10"], awareness["p90"]],
                        "interval_type": interval_type,
                    },
                    {
                        "label": metric_labels[2],
                        "value": consideration["mean"],
                        "ci": [
                            consideration["p10"],
                            consideration["p90"],
                        ],
                        "interval_type": interval_type,
                    },
                    {
                        "label": metric_labels[3],
                        "value": repeat["mean"],
                        "ci": [repeat["p10"], repeat["p90"]],
                        "interval_type": interval_type,
                    },
                ],
                "next_steps": next_steps,
            },
            "funnel": sim_results["funnel"],
            "segments": segments,
            "price_elasticity": sim_results["price_elasticity"],
            "scenarios": scenarios,
            "regional_breakdown": sim_results["regional_breakdown"],
            "channels": sim_results["channels"],
            "consumer_voices": self._consumer_voices(
                agent_research,
                representatives,
            ),
            "sample_profile": sample_profile,
            "market_dynamics": sim_results["market_dynamics"],
            "social_dynamics": sim_results.get("social_dynamics", []),
            "social_evidence": self._social_evidence_policy(),
            "market_research": market_research,
            "evidence_estimates": self._evidence_estimates(
                sim_results,
                agent_research,
            ),
            "evidence_acquisition": self._evidence_acquisition(
                sim_results,
                agent_research,
                market_research,
            ),
            "geo_analysis": sim_results.get("geo_analysis"),
            "commerce_analysis": self._commerce_analysis(study),
            "implied_wtp": sim_results["implied_wtp"],
            "metric_intervals": sim_results["metric_intervals"],
            "model_lineage": sim_results["model_lineage"],
            "agent_research": {
                key: value
                for key, value in agent_research.items()
                if key != "responses"
            },
            "warnings": sim_results["warnings"],
            "methodology": {
                "quantitative_path": [
                    population_stage,
                    *(
                        ["observed_choice_conditional_logit_fit"]
                        if fitted_choices
                        else (
                            ["pooled_platform_category_choice_benchmark"]
                            if platform_calibrated
                            else ["disclosed_choice_coefficient_prior"]
                        )
                    ),
                    "study_specific_discrete_choice_model",
                    "public_evidence_choice_set_attribute_enrichment",
                    "competitor_and_outside_option_choice_set",
                    "bounded_llm_weak_signal",
                    "prior_predictive_monte_carlo",
                    "dynamic_diffusion_scenario",
                ],
                "llm_policy": (
                    "LLM responses are qualitative weak labels and cannot be "
                    "directly averaged into market size or purchase rate."
                ),
                "calibration_status": calibration_status,
            },
        }
        return _json_value(report)

    async def execute_run(
        self,
        study_id: str,
        pop_size: Optional[int] = None,
        mc_rounds: Optional[int] = None,
        seed: int = 42,
        plan_code: Optional[str] = None,
        platform_calibration_override: Optional[
            Mapping[str, Any]
        ] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        if study_id not in self.studies_db:
            raise KeyError("Study not found")

        study = self.studies_db[study_id]
        selected_plan = normalize_plan_code(plan_code or study["plan_code"])
        execution = resolve_execution_config(
            selected_plan,
            pop_size,
            mc_rounds,
        )
        plan = execution["plan"]
        if plan.execution_backend == "not_deployed":
            raise ValueError(
                f"{plan.code} execution backend is not deployed"
            )
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        self.runs_db[run_id] = {
            "status": "PREPARING_POPULATION",
            "study_id": study_id,
        }

        def update_progress(stage: str, percent: int) -> None:
            study["status"] = stage
            self.runs_db[run_id]["status"] = stage
            if progress_callback:
                try:
                    progress_callback(stage, percent)
                except Exception:
                    pass

        update_progress("PREPARING_POPULATION", 5)
        try:
            update_progress("COLLECTING_PUBLIC_EVIDENCE", 10)
            market_research = await self.market_research.collect(
                study,
                plan.code,
            )
            if study["study_type"] in {
                "VENUE_STUDY",
                "SITE_COMPARISON",
                "OPERATING_SCENARIO",
            }:
                update_progress("COLLECTING_GEOGRAPHIC_EVIDENCE", 25)
                geospatial_research = (
                    await self.geospatial_research.collect(study)
                )
            else:
                geospatial_research = {
                    "status": "not_applicable",
                    "locations": {},
                    "warnings": [],
                }
            model_study_type = self._effective_model_type(study)
            profile, choice_estimation, calibration_warnings = (
                self._calibration_profile_for_run(
                    study,
                    plan,
                    model_study_type,
                    platform_calibration_override,
                )
            )
            research_choice_inputs = self._research_enriched_choice_inputs(
                study,
                market_research,
                plan.competitor_limit,
            )
            update_progress("GENERATING_POPULATION", 35)
            generator = PopulationGenerator(
                seed=seed,
                calibration_profile=profile,
            )
            population_df = generator.generate(
                size=execution["population_size"],
                study_type=model_study_type,
                category=study["facts"].get("category"),
            )

            update_progress("RUNNING_AGENTS", 45)
            representatives = self._representative_records(
                generator,
                population_df,
                plan.representative_agents,
                seed,
            )
            sample_profile = self._sample_profile(
                generator,
                population_df,
                seed,
            )
            gateway = GeminiAgentGateway()
            product_context = {
                **study["facts"],
                "study_type": study["study_type"],
                "model_study_type": model_study_type,
                "brand_awareness": study["facts"].get(
                    "brand_awareness",
                    profile["defaults"]["brand_awareness"],
                ),
                "competitors": research_choice_inputs["competitors"],
                "public_market_evidence": [
                    {
                        "platform": item.get("platform"),
                        "title": item.get("title"),
                        "excerpt": str(item.get("excerpt") or "")[:500],
                        "evidence_grade": item.get("evidence_grade"),
                        "evidence_role": item.get("evidence_role"),
                    }
                    for item in market_research.get("evidence", [])[:24]
                ],
                "public_market_evidence_count": market_research.get(
                    "source_count",
                    0,
                ),
            }
            agent_research = await gateway.generate_research_signals(
                product_info=product_context,
                business_questions=study["inputs"].get(
                    "business_questions",
                    [],
                ),
                representatives=representatives,
                plan_code=plan.code,
            )

            update_progress("RUNNING_SIMULATION", 60)
            price = float(
                study["facts"].get("price")
                or study["facts"].get("average_check")
                or 299.0
            )
            engine = SimulationEngine(
                seed=seed,
                calibration_profile=profile,
            )
            sim_results = engine.run_simulation(
                population_df=population_df,
                study_type=model_study_type,
                price=price,
                ref_price=study["facts"].get("reference_price"),
                brand_awareness=study["facts"].get("brand_awareness"),
                mc_rounds=execution["mc_rounds"],
                scenarios=study["facts"].get("scenarios")
                or study["inputs"].get("scenarios"),
                product_attributes=research_choice_inputs[
                    "product_attributes"
                ],
                competitors=research_choice_inputs["competitors"],
                plan_code=plan.code,
                agent_signals=agent_research,
                variable_cost=study["facts"].get("variable_cost"),
            )
            geo_analysis = build_geo_analysis(
                study_type=study["study_type"],
                venue_type=study["facts"].get("venue_type") or model_study_type,
                inputs={**study["inputs"], **study["facts"]},
                capacity=study["facts"].get("capacity"),
                average_check=study["facts"].get("average_check") or price,
                external_evidence=geospatial_research,
            )
            if geo_analysis:
                sim_results["geo_analysis"] = geo_analysis
                sim_results["warnings"].extend(geo_analysis["warnings"])
                sim_results["model_lineage"]["geo"] = {
                    "dataset_id": geo_analysis["dataset_id"],
                    "observed_source_count": len(geo_analysis["sources"]),
                    "heatmap_status": "model_inference_not_measured_footfall",
                    "geospatial_status": geo_analysis["geospatial_status"],
                    "site_score_status": geo_analysis["score_method"],
                    "site_score_calibration": geo_analysis[
                        "score_calibration"
                    ],
                    "catchment_status": (
                        "walking_network_isochrone"
                        if geo_analysis["catchments"]
                        and all(
                            item["mode"] == "walking_network_isochrone"
                            for item in geo_analysis["catchments"]
                        )
                        else "partial_or_radial_proxy"
                    ),
                    "operations_status": geo_analysis["operations"][
                        "status"
                    ],
                }
                if study["study_type"] == "SITE_COMPARISON" and geo_analysis[
                    "locations"
                ]:
                    baseline_rate = float(sim_results["mean_purchase_rate"])
                    baseline_interval = sim_results["metric_intervals"][
                        "purchase_rate"
                    ]
                    top_score = max(
                        float(item["site_score"])
                        for item in geo_analysis["locations"]
                    )
                    median_score = float(
                        np.median(
                            [
                                float(item["site_score"])
                                for item in geo_analysis["locations"]
                            ]
                        )
                    )
                    site_scenarios = []
                    for item in geo_analysis["locations"]:
                        score = float(item["site_score"])
                        has_observed_geo = item["score_status"] != (
                            "insufficient_geospatial_evidence"
                        )
                        multiplier = (
                            min(
                                1.10,
                                max(
                                    0.90,
                                    math.exp((score - median_score) / 250.0),
                                ),
                            )
                            if has_observed_geo
                            else 1.0
                        )
                        rate = min(1.0, baseline_rate * multiplier)
                        geo_relative_index = (
                            score / max(1.0, top_score) * 100.0
                        )
                        conversion_index = (
                            rate / max(0.000001, baseline_rate) * 100.0
                        )
                        relative_index = (
                            conversion_index * 0.55
                            + geo_relative_index * 0.45
                        )
                        site_scenarios.append(
                            {
                                "scenario_id": item["id"],
                                "name": item["name"],
                                "price": price,
                                "purchase_rate": round(rate, 6),
                                "purchase_p10": round(
                                    min(1.0, float(baseline_interval["p10"]) * multiplier),
                                    6,
                                ),
                                "purchase_p90": round(
                                    min(1.0, float(baseline_interval["p90"]) * multiplier),
                                    6,
                                ),
                                "revenue_idx": round(relative_index, 2),
                                "margin_idx": round(relative_index, 2),
                                "geo_site_score": score,
                                "product_model_purchase_rate": round(
                                    baseline_rate,
                                    6,
                                ),
                                "bounded_location_multiplier": round(
                                    multiplier,
                                    4,
                                ),
                                "location_opportunity_index": round(
                                    geo_relative_index,
                                    2,
                                ),
                                "fusion_method": (
                                    "consumer_choice_55pct_plus_location_opportunity_45pct"
                                ),
                                "data_class": (
                                    "external_market_data_plus_model_inference"
                                    if has_observed_geo
                                    else "insufficient_geospatial_evidence"
                                ),
                            }
                        )
                    sim_results["scenarios"] = site_scenarios
            sim_results["warnings"].extend(calibration_warnings)
            sim_results["model_lineage"]["requested_study_type"] = study[
                "study_type"
            ]
            sim_results["model_lineage"]["effective_model_type"] = (
                model_study_type
            )
            sim_results["model_lineage"]["market_research"] = {
                "version": market_research.get("version"),
                "status": market_research.get("status"),
                "source_count": market_research.get("source_count", 0),
                "quantitative_effect": market_research.get(
                    "usage_policy",
                    {},
                ).get("quantitative_effect"),
                "choice_set_enrichment": research_choice_inputs["lineage"],
            }
            sim_results["model_lineage"]["choice_estimation"] = (
                choice_estimation
            )
            if research_choice_inputs["lineage"]["status"] == "applied":
                sim_results["warnings"].append(
                    research_choice_inputs["lineage"]["limitation"]
                )
            sim_results["warnings"].extend(
                market_research.get("warnings") or []
            )
            update_progress("GENERATING_REPORT", 92)
            report = self._report(
                study,
                run_id,
                sim_results,
                agent_research,
                representatives,
                sample_profile,
                market_research,
            )

            study["status"] = "COMPLETED"
            study["updated_at"] = _utc_now()
            self.reports_db[report["report_id"]] = report
            self.runs_db[run_id] = {
                "status": "COMPLETED",
                "report_id": report["report_id"],
                "study_id": study_id,
            }
            if progress_callback:
                try:
                    progress_callback("COMPLETED", 100)
                except Exception:
                    pass
            return report
        except Exception:
            study["status"] = "FAILED_RECOVERABLE"
            study["updated_at"] = _utc_now()
            self.runs_db[run_id]["status"] = "FAILED_RECOVERABLE"
            if progress_callback:
                try:
                    progress_callback("FAILED_RECOVERABLE", 100)
                except Exception:
                    pass
            raise
