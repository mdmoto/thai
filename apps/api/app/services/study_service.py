"""Study orchestration for calibrated population and choice simulation."""

import os
import sys
import uuid
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

import numpy as np

# Add repository packages to sys.path for Cloud Run and local execution.
sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../../../packages")
    )
)

from agents.gemini_gateway import GeminiAgentGateway
from simulation_core.calibration import load_calibration_profile
from simulation_core.config import (
    get_plan_config,
    normalize_plan_code,
    resolve_execution_config,
)
from simulation_core.engine import SIMULATION_MODEL_VERSION, SimulationEngine
from world_model.generator import PopulationGenerator, WORLD_MODEL_VERSION
from world_model.category_profiles import load_category_profile


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


class StudyService:
    def __init__(self):
        self.studies_db: Dict[str, Dict[str, Any]] = {}
        self.runs_db: Dict[str, Dict[str, Any]] = {}
        self.reports_db: Dict[str, Dict[str, Any]] = {}

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
            "description",
            "category",
            "brand_awareness",
            "reference_price",
            "variable_cost",
            "average_check",
            "capacity",
            "location",
            "product_attributes",
            "competitor_data",
            "scenarios",
            "category_panel_version",
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
            if name and str(name) not in existing_names:
                competitors.append(
                    {
                        "name": str(name),
                        "data_quality": "name_only_assumption",
                    }
                )
        return competitors

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
                "distance_km",
            ):
                if source.get(field) is not None:
                    attributes[field] = source[field]
        return attributes

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

    def _report(
        self,
        study: Mapping[str, Any],
        run_id: str,
        sim_results: Mapping[str, Any],
        agent_research: Mapping[str, Any],
        representatives: Sequence[Mapping[str, Any]],
    ) -> Dict[str, Any]:
        report_id = f"rpt_{uuid.uuid4().hex[:8]}"
        scenarios = list(sim_results["scenarios"])
        best_scenario = max(scenarios, key=lambda item: item["revenue_idx"])
        segments = self._enrich_segments(sim_results["segments"])
        best_segment = segments[0] if segments else None
        metrics = sim_results["metric_intervals"]
        calibration_lineage = sim_results["model_lineage"]["calibration"]
        calibration_status = calibration_lineage["status"]
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
        else:
            choice_calibration_label = "选择系数仍为先验"
        purchase = metrics["purchase_rate"]
        awareness = metrics["awareness_rate"]
        consideration = metrics["consideration_rate"]
        repeat = metrics["repeat_rate"]

        recommendation = (
            f"当前{population_calibration_label}、{choice_calibration_label}的 "
            f"{sim_results['study_model_key']} 模型中，"
            f"“{best_scenario['name']}”的相对收入指数最高"
            f"（{best_scenario['revenue_idx']:.1f}）。"
            "在接入真实销量、问卷选择或 A/B 数据并完成回测前，"
            "该结果应作为方案筛选依据，而不是销量承诺。"
        )
        next_steps = [
            "补充至少一个可验证的竞品价格、评价、渠道和品牌认知基准。",
            "导入客户历史订单、投放或 A/B 测试数据，拟合并替换当前系数先验。",
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
                    f"{best_segment['name']}（模型购买率 "
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
                        "label": "总体购买概率",
                        "value": purchase["mean"],
                        "ci": [purchase["p10"], purchase["p90"]],
                        "interval_type": "prior_predictive",
                    },
                    {
                        "label": "品牌认知概率",
                        "value": awareness["mean"],
                        "ci": [awareness["p10"], awareness["p90"]],
                        "interval_type": "prior_predictive",
                    },
                    {
                        "label": "进入考虑概率",
                        "value": consideration["mean"],
                        "ci": [
                            consideration["p10"],
                            consideration["p90"],
                        ],
                        "interval_type": "prior_predictive",
                    },
                    {
                        "label": "购买后复购倾向",
                        "value": repeat["mean"],
                        "ci": [repeat["p10"], repeat["p90"]],
                        "interval_type": "prior_predictive",
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
            "market_dynamics": sim_results["market_dynamics"],
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
                    "study_specific_discrete_choice_model",
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
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        study["status"] = "PREPARING_POPULATION"
        self.runs_db[run_id] = {
            "status": "PREPARING_POPULATION",
            "study_id": study_id,
        }

        try:
            overrides = study["inputs"].get("calibration_overrides")
            use_overrides = overrides if plan.customer_calibration else None
            profile = load_calibration_profile(overrides=use_overrides)
            generator = PopulationGenerator(
                seed=seed,
                calibration_profile=profile,
            )
            population_df = generator.generate(
                size=execution["population_size"],
                study_type=study["study_type"],
                category=study["facts"].get("category"),
            )

            study["status"] = "RUNNING_AGENTS"
            self.runs_db[run_id]["status"] = "RUNNING_AGENTS"
            representatives = self._representative_records(
                generator,
                population_df,
                plan.representative_agents,
                seed,
            )
            gateway = GeminiAgentGateway()
            product_context = {
                **study["facts"],
                "study_type": study["study_type"],
                "brand_awareness": study["facts"].get(
                    "brand_awareness",
                    profile["defaults"]["brand_awareness"],
                ),
                "competitors": self._competitors(study),
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

            study["status"] = "RUNNING_SIMULATION"
            self.runs_db[run_id]["status"] = "RUNNING_SIMULATION"
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
                study_type=study["study_type"],
                price=price,
                ref_price=study["facts"].get("reference_price"),
                brand_awareness=study["facts"].get("brand_awareness"),
                mc_rounds=execution["mc_rounds"],
                scenarios=study["facts"].get("scenarios")
                or study["inputs"].get("scenarios"),
                product_attributes=self._product_attributes(study),
                competitors=self._competitors(study),
                plan_code=plan.code,
                agent_signals=agent_research,
                variable_cost=study["facts"].get("variable_cost"),
            )
            if overrides and not plan.customer_calibration:
                sim_results["warnings"].append(
                    f"{plan.code} does not apply customer calibration overrides; "
                    "the bundled prior profile was used."
                )
            study["status"] = "GENERATING_REPORT"
            self.runs_db[run_id]["status"] = "GENERATING_REPORT"
            report = self._report(
                study,
                run_id,
                sim_results,
                agent_research,
                representatives,
            )

            study["status"] = "COMPLETED"
            study["updated_at"] = _utc_now()
            self.reports_db[report["report_id"]] = report
            self.runs_db[run_id] = {
                "status": "COMPLETED",
                "report_id": report["report_id"],
                "study_id": study_id,
            }
            return report
        except Exception:
            study["status"] = "FAILED_RECOVERABLE"
            study["updated_at"] = _utc_now()
            self.runs_db[run_id]["status"] = "FAILED_RECOVERABLE"
            raise
