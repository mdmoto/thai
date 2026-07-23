"""
Thailand Digital Market Twin Platform — FastAPI Service Entrypoint
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, Optional

from app.schemas.study import (
    CreateStudyRequest, StudyConfirmRequest, RunSimulationRequest
)
from app.services.study_service import StudyService

app = FastAPI(
    title="Thailand Digital Market Twin API",
    version="1.0.0",
    description="Backend API for Thailand Digital Market Twin Platform"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

service = StudyService()

@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "Thailand Digital Market Twin Platform API",
        "version": "1.0.0"
    }

@app.get("/healthz")
def healthz():
    return {"status": "healthy"}

@app.post("/v1/studies")
def create_study(req: CreateStudyRequest):
    study = service.create_study(req.model_dump())
    return study

@app.get("/v1/studies/{study_id}")
def get_study(study_id: str):
    if study_id not in service.studies_db:
        raise HTTPException(status_code=404, detail="Study not found")
    return service.studies_db[study_id]

@app.post("/v1/studies/{study_id}/confirm")
def confirm_study(study_id: str, req: StudyConfirmRequest):
    try:
        study = service.confirm_study(study_id, req.overrides)
        return study
    except KeyError:
        raise HTTPException(status_code=404, detail="Study not found")

@app.post("/v1/studies/{study_id}/runs")
async def run_simulation(study_id: str, req: RunSimulationRequest):
    try:
        report = await service.execute_run(
            study_id=study_id,
            pop_size=req.population_size,
            mc_rounds=req.mc_rounds,
            seed=req.seed
        )
        return report
    except KeyError:
        raise HTTPException(status_code=404, detail="Study not found")

@app.get("/v1/reports/{report_id}")
def get_report(report_id: str):
    if report_id not in service.reports_db:
        raise HTTPException(status_code=404, detail="Report not found")
    return service.reports_db[report_id]
