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
    product_name: Optional[str] = Field(default=None, max_length=200)
    category: Optional[str] = Field(default=None, max_length=120)
    price: Optional[float] = Field(default=None, gt=0, le=1_000_000_000)
    url: Optional[str] = Field(default=None, max_length=2048)
    description: Optional[str] = Field(default=None, max_length=5000)
    selling_points: List[str] = Field(default_factory=list, max_length=20)
    competitors: List[str] = Field(default_factory=list, max_length=20)
    competitor_data: List[Dict[str, Any]] = Field(
        default_factory=list,
        max_length=20,
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

    @field_validator("study_type")
    @classmethod
    def validate_study_type(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"PRODUCT_VALIDATION", "PRICING_STUDY"}:
            raise ValueError("当前自助产品仅支持消费品验证与消费品定价")
        return normalized

    @field_validator("selling_points", "competitors", "business_questions")
    @classmethod
    def clean_text_lists(cls, values: List[str]) -> List[str]:
        return [str(value).strip()[:500] for value in values if str(value).strip()]

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
    model_lineage: Dict[str, Any]
    warnings: List[str]
