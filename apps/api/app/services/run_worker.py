"""Durable execution of one paid simulation job."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.db.billing_service import refund_run_reservation
from app.db.database import SessionLocal
from app.db.models import (
    ReportRecord,
    SimulationRunRecord,
    StudyRecord,
)
from app.services.platform_calibration import (
    platform_calibration_override,
    record_platform_contribution,
)
from app.services.study_service import StudyService


LOGGER = logging.getLogger("market_twin.worker")


def _reservation(job: SimulationRunRecord) -> Dict[str, Any]:
    return {
        "deducted_credits": int(job.credits_reserved or 0),
        "entitlement_code": job.entitlement_code,
        "entitlement_deducted": int(job.entitlement_reserved or 0),
    }


def _hydrate(
    service: StudyService,
    record: StudyRecord,
) -> Dict[str, Any]:
    return service.hydrate_study(
        study_id=record.id,
        name=record.name,
        study_type=record.study_type,
        status=record.status,
        plan_code=record.plan_code,
        inputs=record.inputs_json,
        facts=record.facts_json,
        created_at=record.created_at.isoformat() if record.created_at else None,
        updated_at=record.updated_at.isoformat() if record.updated_at else None,
    )


def _update_progress(
    run_job_id: str,
    stage: str,
    percent: int,
) -> None:
    db = SessionLocal()
    try:
        job = (
            db.query(SimulationRunRecord)
            .filter(SimulationRunRecord.id == run_job_id)
            .first()
        )
        if not job or job.status == "COMPLETED":
            return
        job.progress_stage = stage
        job.progress_percent = max(0, min(100, int(percent)))
        study = (
            db.query(StudyRecord)
            .filter(StudyRecord.id == job.study_id)
            .first()
        )
        if study:
            study.status = stage
        db.commit()
    finally:
        db.close()


def _prepare_job(
    db: Session,
    run_job_id: str,
) -> tuple[
    SimulationRunRecord,
    StudyRecord,
    Optional[Dict[str, Any]],
]:
    job = (
        db.query(SimulationRunRecord)
        .filter(SimulationRunRecord.id == run_job_id)
        .with_for_update()
        .first()
    )
    if not job:
        raise RuntimeError("Simulation run job does not exist")
    if job.status == "COMPLETED":
        return job, db.query(StudyRecord).filter(
            StudyRecord.id == job.study_id
        ).one(), None
    if job.status not in {"QUEUED", "RUNNING"}:
        raise RuntimeError(f"Simulation run is not executable: {job.status}")
    if int(job.attempt_count or 0) >= 2:
        raise RuntimeError("Simulation run retry limit reached")

    study = (
        db.query(StudyRecord)
        .filter(StudyRecord.id == job.study_id)
        .one()
    )
    job.status = "RUNNING"
    job.progress_stage = "PREPARING_POPULATION"
    job.progress_percent = 5
    job.attempt_count = int(job.attempt_count or 0) + 1
    job.started_at = job.started_at or datetime.utcnow()
    study.status = "PREPARING_POPULATION"

    model_study_type = study.study_type
    if model_study_type in {"VENUE_STUDY", "OPERATING_SCENARIO"}:
        venue_type = str(
            (study.facts_json or {}).get("venue_type")
            or (study.inputs_json or {}).get("venue_type")
            or ""
        ).strip().upper()
        if venue_type in {"RESTAURANT", "CAFE", "BAR", "RETAIL"}:
            model_study_type = venue_type
    platform_override = platform_calibration_override(
        db,
        (study.facts_json or {}).get("category"),
        model_study_type,
    )
    if (study.inputs_json or {}).get("observed_choice_data"):
        job.calibration_tier = "CUSTOMER_OBSERVED_CHOICE"
    elif platform_override:
        job.calibration_tier = "PLATFORM_CATEGORY_BENCHMARK"
    else:
        job.calibration_tier = "PUBLIC_EVIDENCE"
    db.commit()
    db.refresh(job)
    return job, study, platform_override


async def execute_run_job(run_job_id: str) -> Optional[str]:
    db = SessionLocal()
    try:
        job, study_record, platform_override = _prepare_job(
            db,
            run_job_id,
        )
        if job.status == "COMPLETED":
            return job.report_id
        job_data = {
            "id": job.id,
            "user_id": job.user_id,
            "study_id": job.study_id,
            "request_key": job.request_key,
            "plan_code": job.plan_code,
            "requested_population": job.requested_population,
            "requested_mc_rounds": job.requested_mc_rounds,
            "seed": int(job.seed or 42),
        }
        study_data = {
            "id": study_record.id,
            "name": study_record.name,
            "study_type": study_record.study_type,
            "status": study_record.status,
            "plan_code": study_record.plan_code,
            "inputs_json": dict(study_record.inputs_json or {}),
            "facts_json": dict(study_record.facts_json or {}),
            "created_at": study_record.created_at,
            "updated_at": study_record.updated_at,
        }
    finally:
        db.close()

    service = StudyService()
    service.hydrate_study(
        study_id=study_data["id"],
        name=study_data["name"],
        study_type=study_data["study_type"],
        status=study_data["status"],
        plan_code=study_data["plan_code"],
        inputs=study_data["inputs_json"],
        facts=study_data["facts_json"],
        created_at=(
            study_data["created_at"].isoformat()
            if study_data["created_at"]
            else None
        ),
        updated_at=(
            study_data["updated_at"].isoformat()
            if study_data["updated_at"]
            else None
        ),
    )

    try:
        report = await service.execute_run(
            study_id=job_data["study_id"],
            pop_size=job_data["requested_population"],
            mc_rounds=job_data["requested_mc_rounds"],
            seed=job_data["seed"],
            plan_code=job_data["plan_code"],
            platform_calibration_override=platform_override,
            progress_callback=lambda stage, percent: _update_progress(
                run_job_id,
                stage,
                percent,
            ),
        )
        db = SessionLocal()
        try:
            existing = (
                db.query(ReportRecord)
                .filter(
                    ReportRecord.user_id == job_data["user_id"],
                    ReportRecord.request_key == job_data["request_key"],
                )
                .first()
            )
            if existing:
                report_record = existing
            else:
                report_record = ReportRecord(
                    id=report["report_id"],
                    user_id=job_data["user_id"],
                    run_id=report["run_id"],
                    study_id=job_data["study_id"],
                    request_key=job_data["request_key"],
                    population_size=report["population_size"],
                    mc_rounds=report["mc_rounds"],
                    report_data=report,
                )
                db.add(report_record)
                db.flush()
            record_platform_contribution(db, report)
            job = (
                db.query(SimulationRunRecord)
                .filter(SimulationRunRecord.id == run_job_id)
                .with_for_update()
                .one()
            )
            study = (
                db.query(StudyRecord)
                .filter(StudyRecord.id == job.study_id)
                .one()
            )
            job.status = "COMPLETED"
            job.progress_stage = "COMPLETED"
            job.progress_percent = 100
            job.report_id = report_record.id
            job.completed_at = datetime.utcnow()
            study.status = "COMPLETED"
            study.plan_code = job.plan_code
            db.commit()
            return report_record.id
        finally:
            db.close()
    except Exception as error:
        LOGGER.exception("Simulation worker failed for %s", run_job_id)
        db = SessionLocal()
        try:
            job = (
                db.query(SimulationRunRecord)
                .filter(SimulationRunRecord.id == run_job_id)
                .with_for_update()
                .first()
            )
            if job and job.status != "COMPLETED":
                reservation = _reservation(job)
                billing_reference = f"{job.user_id}:{job.request_key}"
                job.status = "FAILED"
                job.progress_stage = "FAILED_RECOVERABLE"
                job.progress_percent = 100
                job.error_code = type(error).__name__[:120]
                job.completed_at = datetime.utcnow()
                study = (
                    db.query(StudyRecord)
                    .filter(StudyRecord.id == job.study_id)
                    .first()
                )
                if study:
                    study.status = "FAILED_RECOVERABLE"
                refund_run_reservation(
                    db,
                    job.user_id,
                    reservation,
                    billing_reference,
                )
                db.commit()
        finally:
            db.close()
        return None


def run_worker(run_job_id: str) -> Optional[str]:
    return asyncio.run(execute_run_job(run_job_id))
