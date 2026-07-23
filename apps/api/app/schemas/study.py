"""
Pydantic Schemas for Study, Run, and Report API matching Data Contracts (v1)
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class CreateStudyRequest(BaseModel):
    name: str
    study_type: str
    language: str = "zh"
    plan_code: str = "PROFESSIONAL"
    product_name: Optional[str] = None
    price: Optional[float] = None
    url: Optional[str] = None
    description: Optional[str] = None
    selling_points: List[str] = []
    competitors: List[str] = []
    business_questions: List[str] = []

class StudyConfirmRequest(BaseModel):
    overrides: Dict[str, Any] = {}

class RunSimulationRequest(BaseModel):
    study_id: str
    plan_code: str = "PROFESSIONAL"
    population_size: int = 30000
    mc_rounds: int = 50
    seed: int = 42

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
    report_id: str
    run_id: str
    study_id: str
    world_model_version: str
    simulation_model_version: str
    population_size: int
    mc_rounds: int
    executive_summary: Dict[str, Any]
    funnel: List[Dict[str, Any]]
    segments: List[Dict[str, Any]]
    scenarios: List[Dict[str, Any]]
    consumer_voices: List[Dict[str, Any]]
