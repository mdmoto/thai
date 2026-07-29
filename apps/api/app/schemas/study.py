"""
Pydantic Schemas for Study, Run, and Report API matching Data Contracts (v1)
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any, Optional

class CreateStudyRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    study_type: str = Field(min_length=2, max_length=40)
    language: str = Field(default="zh", max_length=10)
    plan_code: str = Field(default="PROFESSIONAL", max_length=32)
    template_key: Optional[str] = Field(default=None, max_length=80)
    product_name: Optional[str] = Field(default=None, max_length=200)
    category: Optional[str] = Field(default=None, max_length=120)
    price: Optional[float] = Field(default=None, gt=0, le=1_000_000_000)
    url: Optional[str] = Field(default=None, max_length=2048)
    research_urls: List[str] = Field(default_factory=list, max_length=20)
    description: Optional[str] = Field(default=None, max_length=5000)
    selling_points: List[str] = Field(default_factory=list, max_length=20)
    competitors: List[str] = Field(default_factory=list, max_length=20)
    competitor_data: List[Dict[str, Any]] = Field(
        default_factory=list,
        max_length=20,
    )
    observed_choice_data: List[Dict[str, Any]] = Field(
        default_factory=list,
        max_length=5000,
    )
    venue_history: List[Dict[str, Any]] = Field(
        default_factory=list,
        max_length=5000,
        description=(
            "Optional historical venue rows. Supported fields include "
            "location_label, date, hour, visits, average_daily_visits, "
            "average_daily_revenue, and service_minutes."
        ),
    )
    business_questions: List[str] = Field(default_factory=list, max_length=20)
    scenarios: List[Dict[str, Any]] = Field(default_factory=list, max_length=20)
    product_attributes: Dict[str, float] = Field(default_factory=dict)
    brand_awareness: Optional[float] = Field(default=None, ge=0, le=1)
    reference_price: Optional[float] = Field(default=None, gt=0)
    variable_cost: Optional[float] = Field(default=None, ge=0)
    average_check: Optional[float] = Field(default=None, gt=0)
    capacity: Optional[int] = Field(default=None, gt=0)
    location: Optional[Dict[str, Any]] = None
    venue_type: Optional[str] = Field(default=None, max_length=40)
    opening_hours: Optional[str] = Field(default=None, max_length=200)
    parking: Optional[str] = Field(default=None, max_length=500)
    distance_km: Optional[float] = Field(default=None, ge=0, le=500)
    creative_format: Optional[str] = Field(default=None, max_length=80)
    channel: Optional[str] = Field(default=None, max_length=120)
    campaign_budget: Optional[float] = Field(default=None, ge=0)
    marketplaces: List[str] = Field(default_factory=list, max_length=10)
    shipping_fee: Optional[float] = Field(default=None, ge=0)
    delivery_days: Optional[float] = Field(default=None, gt=0, le=90)
    cod_available: Optional[bool] = None
    official_store: Optional[bool] = None
    candidate_locations: List[Dict[str, Any]] = Field(
        default_factory=list,
        max_length=10,
    )

    @field_validator("study_type")
    @classmethod
    def validate_study_type(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {
            "PRODUCT_VALIDATION",
            "PRICING_STUDY",
            "VENUE_STUDY",
            "SITE_COMPARISON",
            "CREATIVE_TEST",
            "OPERATING_SCENARIO",
        }:
            raise ValueError("不支持的研究类型")
        return normalized

    @field_validator("selling_points", "competitors", "business_questions")
    @classmethod
    def clean_text_lists(cls, values: List[str]) -> List[str]:
        return [str(value).strip()[:500] for value in values if str(value).strip()]

    @field_validator("research_urls")
    @classmethod
    def clean_research_urls(cls, values: List[str]) -> List[str]:
        return [str(value).strip()[:2048] for value in values if str(value).strip()]

    @field_validator("observed_choice_data")
    @classmethod
    def validate_observed_choice_data(
        cls,
        rows: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        allowed = {
            "choice_set_id",
            "alternative",
            "chosen",
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
        }
        group_ids: Dict[str, str] = {}
        alternative_counts: Dict[str, int] = {}
        cleaned: List[Dict[str, Any]] = []
        for row in rows:
            raw_group = str(row.get("choice_set_id") or "").strip()
            if not raw_group:
                raise ValueError("真实选择数据的每一行都需要 choice_set_id")
            if raw_group not in group_ids:
                group_ids[raw_group] = f"set-{len(group_ids) + 1:05d}"
            group_id = group_ids[raw_group]
            alternative_counts[group_id] = (
                alternative_counts.get(group_id, 0) + 1
            )
            item = {
                key: value
                for key, value in row.items()
                if key in allowed
            }
            item["choice_set_id"] = group_id
            if "alternative" in item:
                item["alternative"] = (
                    f"option-{alternative_counts[group_id]}"
                )
            cleaned.append(item)
        return cleaned

    @field_validator("venue_history")
    @classmethod
    def validate_venue_history(
        cls,
        rows: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        allowed = {
            "location_label",
            "date",
            "hour",
            "visits",
            "average_daily_visits",
            "average_daily_revenue",
            "service_minutes",
        }
        cleaned: List[Dict[str, Any]] = []
        for row in rows:
            item = {key: value for key, value in row.items() if key in allowed}
            if not item:
                continue
            if "location_label" in item:
                item["location_label"] = str(item["location_label"]).strip()[:200]
            cleaned.append(item)
        return cleaned

class StudyConfirmRequest(BaseModel):
    overrides: Dict[str, Any] = Field(default_factory=dict)

class RunSimulationRequest(BaseModel):
    study_id: Optional[str] = None
    plan_code: Optional[str] = None
    population_size: Optional[int] = Field(default=None, ge=100)
    mc_rounds: Optional[int] = Field(default=None, ge=20)
    seed: int = Field(default=42, ge=0)
    idempotency_key: Optional[str] = Field(
        default=None,
        min_length=8,
        max_length=128,
    )

class MetricResultSchema(BaseModel):
    metric_code: str
    label: str
    value_mean: float
    value_median: float
    ci_p10: float
    ci_p90: float
    unit: str = "%"

class StudyResponse(BaseModel):
    id: str
    name: str
    study_type: str
    status: str
    plan_code: str
    created_at: str
    updated_at: str

class ReportResponse(BaseModel):
    schema_version: str = "2"
    report_id: str
    run_id: str
    study_id: str
    world_model_version: str
    simulation_model_version: str
    population_size: int
    model_sample_size: int
    mc_rounds: int
    executive_summary: Dict[str, Any]
    funnel: List[Dict[str, Any]]
    segments: List[Dict[str, Any]]
    scenarios: List[Dict[str, Any]]
    consumer_voices: List[Dict[str, Any]]
    sample_profile: Optional[Dict[str, Any]] = None
    social_dynamics: List[Dict[str, Any]] = Field(default_factory=list)
    social_evidence: Optional[Dict[str, Any]] = None
    evidence_estimates: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_acquisition: Optional[Dict[str, Any]] = None
    market_research: Optional[Dict[str, Any]] = None
    geo_analysis: Optional[Dict[str, Any]] = None
    commerce_analysis: Optional[Dict[str, Any]] = None
    model_lineage: Dict[str, Any]
    warnings: List[str]
