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
    ModelComponentRunRecord,
    ReportRecord,
    SimulationRunRecord,
    StudyRecord,
)
from app.datetime_utils import utc_isoformat
from app.services.platform_calibration import (
    platform_calibration_override,
    record_platform_contribution,
)
from app.services.component_runs import (
    begin_native_component_run,
    cancel_component_run,
    complete_component_run,
    component_run_lineage,
    fail_component_run,
    update_run_checkpoint,
)
from app.services.study_service import StudyService


LOGGER = logging.getLogger("market_twin.worker")
MAX_WORKER_ATTEMPTS = 2


class RetryableRunError(RuntimeError):
    """Signal Cloud Run Jobs to retry the same durable run exactly once."""


def _is_retryable_error(error: BaseException) -> bool:
    """Separate invalid model inputs from transient execution failures."""

    return not isinstance(
        error,
        (ValueError, KeyError, TypeError, AssertionError),
    )


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
        created_at=utc_isoformat(record.created_at),
        updated_at=utc_isoformat(record.updated_at),
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
        if not job or job.status not in {"QUEUED", "RUNNING"}:
            return
        job.progress_stage = stage
        job.progress_percent = max(0, min(100, int(percent)))
        component_run = (
            db.query(ModelComponentRunRecord)
            .filter(
                ModelComponentRunRecord.simulation_run_id == job.id,
                ModelComponentRunRecord.status == "RUNNING",
            )
            .order_by(ModelComponentRunRecord.created_at.desc())
            .first()
        )
        update_run_checkpoint(
            job,
            stage=stage,
            percent=job.progress_percent,
            component_run=component_run,
        )
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
    if job.status in {"COMPLETED", "CANCELLED"}:
        return job, db.query(StudyRecord).filter(
            StudyRecord.id == job.study_id
        ).one(), None
    if job.status not in {"QUEUED", "RUNNING"}:
        raise RuntimeError(f"Simulation run is not executable: {job.status}")
    if int(job.attempt_count or 0) >= MAX_WORKER_ATTEMPTS:
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
    job.error_code = None
    job.completed_at = None
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
        (job.frozen_facts_json or study.facts_json or {}).get("category"),
        model_study_type,
    )
    if (
        job.frozen_inputs_json or study.inputs_json or {}
    ).get("observed_choice_data"):
        job.calibration_tier = "CUSTOMER_OBSERVED_CHOICE"
    elif platform_override:
        job.calibration_tier = "PLATFORM_CATEGORY_BENCHMARK"
    else:
        job.calibration_tier = "PUBLIC_EVIDENCE"
    db.commit()
    db.refresh(job)
    return job, study, platform_override


def _handle_job_failure(
    run_job_id: str,
    component_run_id: Optional[str],
    error: BaseException,
) -> bool:
    """Checkpoint a retry or close and refund a terminal failure.

    Returns ``True`` only when Cloud Run should retry this same job.  No new
    billing reservation is created: the original reservation remains held
    until either the retry succeeds or the final attempt is refunded.
    """

    db = SessionLocal()
    try:
        job = (
            db.query(SimulationRunRecord)
            .filter(SimulationRunRecord.id == run_job_id)
            .with_for_update()
            .first()
        )
        if not job or job.status in {"COMPLETED", "CANCELLED"}:
            return False
        reservation = _reservation(job)
        billing_reference = f"{job.user_id}:{job.request_key}"
        study = (
            db.query(StudyRecord)
            .filter(StudyRecord.id == job.study_id)
            .first()
        )
        component_run = None
        if component_run_id:
            component_run = (
                db.query(ModelComponentRunRecord)
                .filter(ModelComponentRunRecord.id == component_run_id)
                .first()
            )
            fail_component_run(component_run, error)
        error_code = type(error).__name__[:120]
        should_retry = (
            _is_retryable_error(error)
            and int(job.attempt_count or 0) < MAX_WORKER_ATTEMPTS
        )
        if should_retry:
            job.status = "QUEUED"
            job.progress_stage = "RETRYING"
            job.progress_percent = min(
                95,
                max(0, int(job.progress_percent or 0)),
            )
            job.error_code = error_code
            job.completed_at = None
            if study:
                study.status = "RETRYING"
            update_run_checkpoint(
                job,
                stage="RETRYING",
                percent=job.progress_percent,
                component_run=component_run,
                error_code=error_code,
            )
            db.commit()
            return True

        job.status = "FAILED"
        job.progress_stage = "FAILED_RECOVERABLE"
        job.progress_percent = 100
        job.error_code = error_code
        job.completed_at = datetime.utcnow()
        if study:
            study.status = "FAILED_RECOVERABLE"
        update_run_checkpoint(
            job,
            stage="FAILED_RECOVERABLE",
            percent=100,
            component_run=component_run,
            error_code=error_code,
        )
        refund_run_reservation(
            db,
            job.user_id,
            reservation,
            billing_reference,
        )
        db.commit()
        return False
    finally:
        db.close()


async def execute_run_job(run_job_id: str) -> Optional[str]:
    db = SessionLocal()
    component_run_id: Optional[str] = None
    try:
        try:
            job, study_record, platform_override = _prepare_job(
                db,
                run_job_id,
            )
            if job.status in {"COMPLETED", "CANCELLED"}:
                return job.report_id
            component_run = begin_native_component_run(db, job)
            component_run_id = component_run.id
            update_run_checkpoint(
                job,
                stage="PREPARING_POPULATION",
                percent=5,
                component_run=component_run,
            )
            db.commit()
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
                "inputs_json": dict(
                    job.frozen_inputs_json or study_record.inputs_json or {}
                ),
                "facts_json": dict(
                    job.frozen_facts_json or study_record.facts_json or {}
                ),
                "created_at": study_record.created_at,
                "updated_at": study_record.updated_at,
            }
        except Exception as error:
            LOGGER.exception("Simulation worker setup failed for %s", run_job_id)
            db.rollback()
            if _handle_job_failure(run_job_id, component_run_id, error):
                raise RetryableRunError(
                    f"Simulation job {run_job_id} scheduled for retry"
                ) from error
            return None
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
        created_at=utc_isoformat(study_data["created_at"]),
        updated_at=utc_isoformat(study_data["updated_at"]),
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
            job = (
                db.query(SimulationRunRecord)
                .filter(SimulationRunRecord.id == run_job_id)
                .with_for_update()
                .one()
            )
            if job.status == "CANCELLED":
                component_run = None
                if component_run_id:
                    component_run = (
                        db.query(ModelComponentRunRecord)
                        .filter(ModelComponentRunRecord.id == component_run_id)
                        .first()
                    )
                    cancel_component_run(component_run)
                update_run_checkpoint(
                    job,
                    stage="CANCELLED",
                    percent=100,
                    component_run=component_run,
                    error_code="CANCELLED_BY_USER",
                )
                db.commit()
                return None
            component_run = None
            if component_run_id:
                component_run = (
                    db.query(ModelComponentRunRecord)
                    .filter(ModelComponentRunRecord.id == component_run_id)
                    .one()
                )
                complete_component_run(
                    db,
                    component_run,
                    report_id=report["report_id"],
                    report_run_id=report["run_id"],
                    report_payload=report,
                )
                report["model_components"] = [
                    component_run_lineage(component_run)
                ]
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
            update_run_checkpoint(
                job,
                stage="COMPLETED",
                percent=100,
                component_run=component_run,
            )
            study.status = "COMPLETED"
            study.plan_code = job.plan_code
            db.commit()
            return report_record.id
        finally:
            db.close()
    except Exception as error:
        LOGGER.exception("Simulation worker failed for %s", run_job_id)
        if _handle_job_failure(run_job_id, component_run_id, error):
            raise RetryableRunError(
                f"Simulation job {run_job_id} scheduled for retry"
            ) from error
        return None


def run_worker(run_job_id: str) -> Optional[str]:
    return asyncio.run(execute_run_job(run_job_id))
