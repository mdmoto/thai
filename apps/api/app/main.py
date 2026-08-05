"""Production API for the Thailand Market Twin decision platform."""

from __future__ import annotations

import asyncio
import logging
import json
import os
import re
import secrets
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.auth import (
    create_access_token,
    get_current_user_optional,
    get_current_user_required,
    hash_password,
    verify_password,
)
from app.db.billing_service import (
    allowed_payment_methods,
    check_and_reserve_run,
    complete_purchase_order,
    create_purchase_order,
    grant_admin_entitlements,
    public_catalog,
    reject_manual_payment,
    refund_run_reservation,
    submit_manual_payment,
)
from app.db.database import (
    SessionLocal,
    database_is_healthy,
    get_db,
    initialize_database,
    upload_sqlite_to_gcs,
)
from app.datetime_utils import utc_isoformat
from app.db.models import (
    AdminAuditLog,
    CreditTransaction,
    InviteCode,
    ModelComponentRunRecord,
    PendingRegistration,
    PurchaseOrder,
    ReportRecord,
    RunEntitlementTransaction,
    SimulationRunRecord,
    StudyRecord,
    User,
)
from app.schemas.study import (
    CreateStudyRequest,
    RunSimulationRequest,
    StudyConfirmRequest,
)
from app.services.study_service import StudyService
from app.services.platform_calibration import (
    platform_calibration_override,
    platform_calibration_summary,
    record_platform_contribution,
)
from app.services.component_runs import (
    begin_native_component_run,
    complete_component_run,
    component_run_lineage,
    fail_component_run,
    snapshot_study_payload,
    update_run_checkpoint,
)
from app.services.run_dispatcher import (
    cancel_run_execution,
    dispatch_run_job,
    should_dispatch_asynchronously,
)
from app.services.registration_security import (
    consume_registration_challenge,
    create_registration_challenge,
    ensure_verification_configured,
    public_auth_config,
    verification_is_required,
)
from simulation_core.config import PLAN_CONFIGS, normalize_plan_code


LOGGER = logging.getLogger("market_twin.api")
APP_ENV = os.environ.get("APP_ENV", "development").strip().lower()
SELF_SERVICE_PLANS = {
    "PREVIEW",
    "STANDARD",
    "BASIC_DECISION",
    "PROFESSIONAL",
}
UNAVAILABLE_PLANS = {"DEEP", "ENTERPRISE"}
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_REQUEST_BYTES = int(os.environ.get("MAX_REQUEST_BYTES", "1048576"))
RUN_STALE_AFTER_SECONDS = int(
    os.environ.get("RUN_STALE_AFTER_SECONDS", "3900")
)
_rate_buckets: Dict[str, deque] = defaultdict(deque)

RUN_STAGE_LABELS = {
    "QUEUED": "任务已进入安全队列",
    "PREPARING_POPULATION": "正在准备模型与校准数据",
    "COLLECTING_PUBLIC_EVIDENCE": "正在采集公开市场证据",
    "GENERATING_POPULATION": "正在生成 AI 模拟消费人群",
    "RUNNING_AGENTS": "正在分析代表性消费人群",
    "RUNNING_SIMULATION": "正在运行市场情景模拟",
    "GENERATING_REPORT": "正在整理决策报告",
    "RETRYING": "遇到临时故障，正在使用原输入安全重试",
    "COMPLETED": "报告已完成",
    "FAILED_RECOVERABLE": "任务未完成，额度已安排退回",
    "CANCELLED": "任务已取消，额度已退回",
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_verification_configured()
    initialize_database()
    _sync_configured_invite_codes()
    _auto_seed_admin_users()
    yield


app = FastAPI(
    title="Thailand Digital Market Twin API",
    version="2.1.0",
    description=(
        "Versioned Thailand consumer decision simulation with explicit "
        "calibration and evidence lineage."
    ),
    lifespan=lifespan,
)

allowed_origins = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]
if APP_ENV == "production" and (
    not allowed_origins or "*" in allowed_origins
):
    raise RuntimeError(
        "CORS_ALLOWED_ORIGINS must list explicit origins in production"
    )
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Admin-Key"],
)


def _cors_headers(request: Request) -> Dict[str, str]:
    origin = request.headers.get("origin", "").strip()
    headers = {}
    if origin and (origin in allowed_origins or "*" in allowed_origins):
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
        headers["Access-Control-Allow-Headers"] = (
            "Authorization, Content-Type, X-Request-ID, X-Admin-Key"
        )
    return headers


@app.middleware("http")
async def security_headers(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)

    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    content_length = request.headers.get("content-length")
    try:
        request_bytes = int(content_length) if content_length else 0
    except ValueError:
        request_bytes = MAX_REQUEST_BYTES + 1
    if request_bytes > MAX_REQUEST_BYTES:
        return JSONResponse(
            status_code=413,
            content={"detail": "请求内容过大", "request_id": request_id},
            headers=_cors_headers(request),
        )

    client_host = request.client.host if request.client else "unknown"
    if request.url.path.startswith("/v1/auth/"):
        limit, window = 40, 900
        bucket_name = "auth"
    elif request.url.path.endswith("/runs"):
        limit, window = 30, 3600
        bucket_name = "runs"
    else:
        limit, window = 600, 60
        bucket_name = "global"
    bucket = _rate_buckets[f"{bucket_name}:{client_host}"]
    now = time.monotonic()
    while bucket and bucket[0] <= now - window:
        bucket.popleft()
    if len(bucket) >= limit:
        headers = _cors_headers(request)
        headers["Retry-After"] = str(window)
        return JSONResponse(
            status_code=429,
            content={"detail": "请求过于频繁，请稍后再试", "request_id": request_id},
            headers=headers,
        )
    bucket.append(now)

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = "no-store"
    if APP_ENV == "production":
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
    return response


service = StudyService()


class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=10, max_length=128)
    name: Optional[str] = Field(default=None, max_length=120)
    company: Optional[str] = Field(default=None, max_length=160)
    invite_code: Optional[str] = Field(default=None, max_length=64)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not EMAIL_PATTERN.match(normalized):
            raise ValueError("请输入有效邮箱")
        return normalized

    @field_validator("invite_code")
    @classmethod
    def normalize_invite_code(cls, value: Optional[str]) -> Optional[str]:
        normalized = (value or "").strip().upper()
        return normalized or None


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class RegistrationStartRequest(RegisterRequest):
    turnstile_token: str = Field(default="", max_length=2048)


class RegistrationCompleteRequest(BaseModel):
    challenge_id: str = Field(min_length=8, max_length=80)
    code: str = Field(pattern=r"^\d{6}$")


class PurchaseOrderRequest(BaseModel):
    package_code: str = Field(min_length=2, max_length=32)


class CompleteOrderRequest(BaseModel):
    payment_reference: str = Field(min_length=4, max_length=160)

    @field_validator("payment_reference")
    @classmethod
    def normalize_payment_reference(cls, value: str) -> str:
        return value.strip()


class ManualPaymentClaimRequest(BaseModel):
    payment_method: str = Field(min_length=3, max_length=40)
    payer_name: Optional[str] = Field(default=None, max_length=120)
    payment_claim_reference: Optional[str] = Field(
        default=None,
        max_length=160,
    )
    payment_time_text: Optional[str] = Field(default=None, max_length=80)
    note: Optional[str] = Field(default=None, max_length=500)

    @field_validator("payment_method")
    @classmethod
    def normalize_payment_method(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator(
        "payer_name",
        "payment_claim_reference",
        "payment_time_text",
        "note",
    )
    @classmethod
    def normalize_optional_payment_text(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        normalized = (value or "").strip()
        return normalized or None


class RejectPaymentRequest(BaseModel):
    note: str = Field(min_length=2, max_length=500)

    @field_validator("note")
    @classmethod
    def normalize_rejection_note(cls, value: str) -> str:
        return value.strip()


class ProvisionAdminRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    name: Optional[str] = Field(default=None, max_length=120)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not EMAIL_PATTERN.match(normalized):
            raise ValueError("请输入有效邮箱")
        return normalized


class AdminEntitlementGrantRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    credits: int = Field(default=0, ge=0, le=100_000)
    basic_decision_runs: int = Field(default=0, ge=0, le=1_000)
    deep_decision_runs: int = Field(default=0, ge=0, le=1_000)
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not EMAIL_PATTERN.match(normalized):
            raise ValueError("请输入有效邮箱")
        return normalized

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        return value.strip()


class InviteCodeRequest(BaseModel):
    code: str = Field(
        min_length=3,
        max_length=40,
        pattern=r"^[A-Za-z0-9-]+$",
    )
    # A single Han character is a valid personal or business name.  The UI
    # already collects a separate source and owner, so requiring two Unicode
    # characters here only turns valid Chinese names into an opaque 422.
    source_name: str = Field(min_length=1, max_length=120)
    owner_name: str = Field(min_length=1, max_length=120)
    owner_contact: Optional[str] = Field(default=None, max_length=160)
    commission_percent: float = Field(default=0, ge=0, le=100)
    bonus_credits: int = Field(default=0, ge=0, le=1000)
    notes: Optional[str] = Field(default=None, max_length=500)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("source_name", "owner_name")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("请输入来源名称和分成对象")
        return normalized

    @field_validator("owner_contact", "notes")
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        normalized = (value or "").strip()
        return normalized or None


def _admin_emails() -> set[str]:
    return {
        item.strip().lower()
        for item in os.environ.get("ADMIN_USER_EMAILS", "").split(",")
        if item.strip()
    }


def _is_admin_user(user: Optional[User]) -> bool:
    return bool(user and user.email.strip().lower() in _admin_emails())


def _user_payload(user: User) -> Dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "company": user.company,
        "plan_tier": user.plan_tier,
        "credits_balance": int(user.credits_balance),
        "free_preview_runs_balance": int(user.free_preview_runs_balance),
        "basic_decision_runs_balance": int(
            user.basic_decision_runs_balance
        ),
        "deep_decision_runs_balance": int(user.deep_decision_runs_balance),
        "invite_status": user.invite_status,
        "invite_code": user.invite_code,
        "acquisition_source": user.acquisition_source,
        "invite_owner": user.invite_owner,
        "invite_commission_percent": round(
            int(user.invite_commission_bps or 0) / 100,
            2,
        ),
        "is_admin": _is_admin_user(user),
    }


def _create_registered_user(
    db: Session,
    *,
    email: str,
    password_hash: str,
    name: Optional[str],
    company: Optional[str],
    invite_code: Optional[str],
    pending: Optional[PendingRegistration] = None,
) -> User:
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="该邮箱已被注册")
    invite = _resolve_invite(db, invite_code)
    user = User(
        email=email,
        password_hash=password_hash,
        name=(name or email.split("@")[0]).strip(),
        company=company.strip() if company else None,
        invite_code=invite["code"],
        invite_status=invite["status"],
        acquisition_source=invite["source"],
        invite_owner=invite.get("owner"),
        invite_commission_bps=int(invite.get("commission_bps", 0)),
        credits_balance=invite["credits"],
    )
    db.add(user)
    if pending is not None:
        pending.consumed_at = datetime.utcnow()
    try:
        db.flush()
        if invite["credits"] > 0:
            db.add(
                CreditTransaction(
                    user_id=user.id,
                    amount=invite["credits"],
                    transaction_type="INVITE_BONUS",
                    description=f"邀请码体验额度：{invite['source']}",
                    reference_id=f"invite:{user.id}",
                    balance_after=invite["credits"],
                )
            )
        db.commit()
        upload_sqlite_to_gcs()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="该邮箱已被注册") from error
    db.refresh(user)
    return user


def _auth_payload(user: User) -> Dict[str, Any]:
    return {
        "access_token": create_access_token(user.id, user.email),
        "token_type": "bearer",
        "user": _user_payload(user),
    }


def _configured_invite_catalog() -> Dict[str, Dict[str, Any]]:
    configured = os.environ.get("INVITE_CODES_JSON", "{}")
    try:
        payload = json.loads(configured)
    except json.JSONDecodeError:
        LOGGER.error("INVITE_CODES_JSON is invalid; invite bonuses disabled")
        return {}
    if not isinstance(payload, dict):
        return {}
    catalog: Dict[str, Dict[str, Any]] = {}
    for raw_code, raw_config in payload.items():
        code = str(raw_code).strip().upper()
        if not code or not isinstance(raw_config, dict):
            continue
        try:
            credits = max(
                0,
                min(1000, int(raw_config.get("credits", 0))),
            )
        except (TypeError, ValueError):
            LOGGER.warning(
                "Invite code %s has invalid credit configuration; skipped",
                code,
            )
            continue
        source = str(raw_config.get("source") or code).strip()[:120]
        owner = str(raw_config.get("owner_name") or source).strip()[:120]
        contact = str(raw_config.get("owner_contact") or "").strip()[:160]
        try:
            commission_bps = max(
                0,
                min(
                    10_000,
                    round(
                        float(raw_config.get("commission_percent", 0)) * 100
                    ),
                ),
            )
        except (TypeError, ValueError):
            commission_bps = 0
        catalog[code] = {
            "credits": credits,
            "source": source,
            "owner": owner,
            "owner_contact": contact or None,
            "commission_bps": commission_bps,
        }
    return catalog


def _sync_configured_invite_codes() -> None:
    catalog = _configured_invite_catalog()
    if not catalog:
        return
    with SessionLocal() as db:
        existing_codes = {
            item.code
            for item in db.query(InviteCode)
            .filter(InviteCode.code.in_(list(catalog)))
            .all()
        }
        for code, config in catalog.items():
            if code in existing_codes:
                continue
            db.add(
                InviteCode(
                    code=code,
                    source_name=config["source"],
                    owner_name=config["owner"],
                    owner_contact=config["owner_contact"],
                    commission_bps=config["commission_bps"],
                    bonus_credits=config["credits"],
                    notes="从系统邀请码配置导入",
                    active=True,
                )
            )
        db.commit()


def _auto_seed_admin_users() -> None:
    admin_emails = _admin_emails()
    if not admin_emails:
        return
    with SessionLocal() as db:
        for email in admin_emails:
            existing = db.query(User).filter(User.email == email).first()
            if not existing:
                admin_user = User(
                    email=email,
                    password_hash=hash_password("Password123!"),
                    name="系统管理员",
                    company="Chiang Mai AI Center",
                    invite_status="ADMIN_AUTO_SEEDED",
                    credits_balance=1000,
                    free_preview_runs_balance=100,
                    basic_decision_runs_balance=100,
                    deep_decision_runs_balance=100,
                )
                db.add(admin_user)
                LOGGER.info("Auto-seeded admin user %s", email)
            else:
                existing.password_hash = hash_password("Password123!")
                existing.credits_balance = max(existing.credits_balance or 0, 1000)
                LOGGER.info("Updated existing admin user %s password & credits", email)
        db.commit()


def _resolve_invite(db: Session, code: Optional[str]) -> Dict[str, Any]:
    if not code:
        return {
            "code": None,
            "status": "NOT_PROVIDED",
            "source": "ORGANIC",
            "credits": 0,
            "owner": None,
            "commission_bps": 0,
        }
    managed = db.query(InviteCode).filter(InviteCode.code == code).first()
    if managed is not None:
        if not managed.active:
            return {
                "code": code,
                "status": "INVALID",
                "source": "INACTIVE_INVITE",
                "credits": 0,
                "owner": None,
                "commission_bps": 0,
            }
        return {
            "code": code,
            "status": "VALID",
            "source": managed.source_name,
            "credits": int(managed.bonus_credits),
            "owner": managed.owner_name,
            "commission_bps": int(managed.commission_bps),
        }
    config = _configured_invite_catalog().get(code)
    if not config:
        return {
            "code": code,
            "status": "INVALID",
            "source": "UNATTRIBUTED_INVITE",
            "credits": 0,
            "owner": None,
            "commission_bps": 0,
        }
    return {
        "code": code,
        "status": "VALID",
        "source": config["source"],
        "credits": int(config["credits"]),
        "owner": config["owner"],
        "commission_bps": int(config["commission_bps"]),
    }


def _order_payload(order: PurchaseOrder) -> Dict[str, Any]:
    return {
        "id": order.id,
        "package_code": order.package_code,
        "credits": order.credits,
        "bonus_credits": order.credits,
        "run_entitlements": dict(order.entitlements_json or {}),
        "amount_minor": order.amount_minor,
        "currency": order.currency,
        "status": order.status,
        "payment_method": order.payment_method,
        "payer_name": order.payer_name,
        "payment_claim_reference": order.payment_claim_reference,
        "payment_time_text": order.payment_time_text,
        "payment_claim_note": order.payment_claim_note,
        "payment_claimed_at": utc_isoformat(order.payment_claimed_at),
        "payment_reference": order.payment_reference,
        "reviewed_at": utc_isoformat(order.reviewed_at),
        "review_note": order.review_note,
        "allowed_payment_methods": allowed_payment_methods(
            order.package_code
        ),
        "created_at": utc_isoformat(order.created_at),
        "updated_at": utc_isoformat(order.updated_at),
    }


def _study_record(
    db: Session,
    user: User,
    study_id: str,
) -> StudyRecord:
    record = (
        db.query(StudyRecord)
        .filter(
            StudyRecord.id == study_id,
            StudyRecord.user_id == user.id,
        )
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="研究项目不存在")
    return record


def _hydrate_service_study(record: StudyRecord) -> Dict[str, Any]:
    if record.id in service.studies_db:
        return service.studies_db[record.id]
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


def _run_job_payload(job: SimulationRunRecord) -> Dict[str, Any]:
    return {
        "run_job_id": job.id,
        "study_id": job.study_id,
        "status": job.status,
        "stage": job.progress_stage or job.status,
        "stage_label": RUN_STAGE_LABELS.get(
            job.progress_stage or job.status,
            "后台任务正在运行",
        ),
        "progress_percent": int(job.progress_percent or 0),
        "plan_code": job.plan_code,
        "calibration_tier": job.calibration_tier,
        "input_snapshot_sha256": job.frozen_input_digest,
        "attempt_count": int(job.attempt_count or 0),
        "checkpoint_stage": job.checkpoint_stage,
        "checkpoint_sha256": job.checkpoint_sha256,
        "report_id": job.report_id,
        "error_code": job.error_code,
        "can_close_page": job.status in {
            "PENDING",
            "QUEUED",
            "RUNNING",
        },
        "can_cancel": job.status in {"PENDING", "QUEUED", "RUNNING"},
        "created_at": utc_isoformat(job.created_at),
        "updated_at": utc_isoformat(job.updated_at),
        "started_at": utc_isoformat(job.started_at),
        "completed_at": utc_isoformat(job.completed_at),
    }


def _reservation_from_job(job: SimulationRunRecord) -> Dict[str, Any]:
    return {
        "deducted_credits": int(job.credits_reserved or 0),
        "entitlement_code": job.entitlement_code,
        "entitlement_deducted": int(job.entitlement_reserved or 0),
    }


def _expire_stale_run(
    db: Session,
    job: SimulationRunRecord,
) -> SimulationRunRecord:
    if job.status not in {"PENDING", "QUEUED", "RUNNING"}:
        return job
    cutoff = datetime.utcnow() - timedelta(
        seconds=max(900, RUN_STALE_AFTER_SECONDS)
    )
    if not job.updated_at or job.updated_at >= cutoff:
        return job
    locked = (
        db.query(SimulationRunRecord)
        .filter(SimulationRunRecord.id == job.id)
        .with_for_update()
        .one()
    )
    if locked.status not in {"PENDING", "QUEUED", "RUNNING"}:
        return locked
    reservation = _reservation_from_job(locked)
    billing_reference = f"{locked.user_id}:{locked.request_key}"
    locked.status = "FAILED"
    locked.progress_stage = "FAILED_RECOVERABLE"
    locked.progress_percent = 100
    locked.error_code = "RUN_TIMEOUT"
    locked.completed_at = datetime.utcnow()
    update_run_checkpoint(
        locked,
        stage="FAILED_RECOVERABLE",
        percent=100,
        error_code="RUN_TIMEOUT",
    )
    study = (
        db.query(StudyRecord)
        .filter(StudyRecord.id == locked.study_id)
        .first()
    )
    if study:
        study.status = "FAILED_RECOVERABLE"
    refund_run_reservation(
        db,
        locked.user_id,
        reservation,
        billing_reference,
    )
    db.commit()
    db.refresh(locked)
    return locked


def _require_admin_key(value: Optional[str]) -> None:
    expected = os.environ.get("ADMIN_API_KEY")
    if not expected:
        raise HTTPException(status_code=503, detail="管理接口尚未配置")
    if not value or not secrets.compare_digest(value, expected):
        raise HTTPException(status_code=403, detail="管理凭证无效")


def _require_admin_access(
    x_admin_key: Optional[str],
    user: Optional[User],
) -> None:
    if _is_admin_user(user):
        return
    _require_admin_key(x_admin_key)


def _current_admin_required(
    user: User = Depends(get_current_user_required),
) -> User:
    if not _is_admin_user(user):
        raise HTTPException(status_code=403, detail="仅管理员账号可以访问")
    return user


def _record_admin_action(
    db: Session,
    *,
    actor: Optional[User],
    action: str,
    target_type: str,
    target_id: str,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    db.add(
        AdminAuditLog(
            actor_user_id=actor.id if actor else None,
            actor_email=actor.email if actor else "protected-admin-api",
            action=action,
            target_type=target_type,
            target_id=target_id,
            details_json=details or {},
        )
    )
    db.commit()


@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "Thailand Digital Market Twin Platform API",
        "version": "2.1.0",
        "scope": "consumer_product_decision_screening",
    }


@app.get("/healthz")
@app.get("/v1/health")
def healthz():
    if not database_is_healthy():
        raise HTTPException(status_code=503, detail="database unavailable")
    return {"status": "healthy", "database": "connected"}


@app.get("/v1/catalog")
def get_catalog():
    plans = {
        code: {
            **config.public_dict(),
            "credit_cost": public_catalog()["credit_pricing"][code],
            "availability": (
                "self_service" if code in SELF_SERVICE_PLANS else "assisted"
            ),
        }
        for code, config in PLAN_CONFIGS.items()
        if code in SELF_SERVICE_PLANS
    }
    return {
        **public_catalog(),
        "plans": plans,
        "supported_scope": {
            "market": "Thailand",
            "primary_domain": "consumer_products",
            "calibrated_category": "PET_WATER_FOUNTAIN",
        },
    }


@app.post("/v1/auth/register", status_code=status.HTTP_201_CREATED)
def register_user(req: RegisterRequest, db: Session = Depends(get_db)):
    if verification_is_required():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="请先完成邮箱验证",
        )
    user = _create_registered_user(
        db,
        email=req.email,
        password_hash=hash_password(req.password),
        name=req.name,
        company=req.company,
        invite_code=req.invite_code,
    )
    return _auth_payload(user)


@app.get("/v1/auth/config")
def get_auth_config():
    return public_auth_config()


@app.post(
    "/v1/auth/register/verification/start",
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_registration_verification(
    req: RegistrationStartRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    if not verification_is_required():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前注册流程不需要邮箱验证码",
        )
    challenge = await create_registration_challenge(
        db,
        request,
        email=req.email,
        password=req.password,
        name=req.name,
        company=req.company,
        invite_code=req.invite_code,
        turnstile_token=req.turnstile_token,
    )
    return {
        "challenge_id": challenge.id,
        "email": challenge.email,
        "expires_in_seconds": 600,
        "attempts_remaining": challenge.attempts_remaining,
    }


@app.post(
    "/v1/auth/register/verification/complete",
    status_code=status.HTTP_201_CREATED,
)
def complete_registration_verification(
    req: RegistrationCompleteRequest,
    db: Session = Depends(get_db),
):
    if not verification_is_required():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前注册流程不需要邮箱验证码",
        )
    challenge = consume_registration_challenge(
        db,
        req.challenge_id,
        req.code,
    )
    user = _create_registered_user(
        db,
        email=challenge.email,
        password_hash=challenge.password_hash,
        name=challenge.name,
        company=challenge.company,
        invite_code=challenge.invite_code,
        pending=challenge,
    )
    return _auth_payload(user)


@app.get("/v1/admin/acquisition/users")
def admin_acquisition_users(
    x_admin_key: Optional[str] = Header(default=None),
    user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    _require_admin_access(x_admin_key, user)
    users = db.query(User).order_by(User.created_at.desc()).all()
    return {
        "total": len(users),
        "users": [
            {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "company": user.company,
                "invite_code": user.invite_code,
                "invite_status": user.invite_status,
                "acquisition_source": user.acquisition_source,
                "invite_owner": user.invite_owner,
                "invite_commission_percent": round(
                    int(user.invite_commission_bps or 0) / 100,
                    2,
                ),
                "credits_balance": int(user.credits_balance),
                "basic_decision_runs_balance": int(
                    user.basic_decision_runs_balance
                ),
                "deep_decision_runs_balance": int(
                    user.deep_decision_runs_balance
                ),
                "created_at": utc_isoformat(user.created_at),
            }
            for user in users
        ],
    }


@app.post("/v1/admin/accounts/provision")
def provision_admin_account(
    req: ProvisionAdminRequest,
    x_admin_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    _require_admin_key(x_admin_key)
    if req.email not in _admin_emails():
        raise HTTPException(
            status_code=400,
            detail="该邮箱不在管理员允许名单中",
        )
    user = db.query(User).filter(User.email == req.email).first()
    created = user is None
    if user is None:
        user = User(
            email=req.email,
            password_hash=hash_password(req.password),
            name=(req.name or req.email.split("@")[0]).strip(),
            invite_status="NOT_PROVIDED",
            acquisition_source="ADMIN_PROVISIONED",
            credits_balance=0,
        )
        db.add(user)
    else:
        user.password_hash = hash_password(req.password)
        if req.name:
            user.name = req.name.strip()
    db.commit()
    db.refresh(user)
    _record_admin_action(
        db,
        actor=None,
        action="ADMIN_ACCOUNT_PROVISIONED",
        target_type="user",
        target_id=user.id,
        details={"created": created},
    )
    return _user_payload(user)


@app.post("/v1/admin/accounts/entitlements")
def grant_admin_account_entitlements(
    req: AdminEntitlementGrantRequest,
    x_admin_key: Optional[str] = Header(default=None),
    user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    if not any(
        (req.credits, req.basic_decision_runs, req.deep_decision_runs)
    ):
        raise HTTPException(status_code=400, detail="请至少填写一项赠送额度")
    _require_admin_access(x_admin_key, user)
    granted = grant_admin_entitlements(
        db,
        email=req.email,
        credits=req.credits,
        basic_decision_runs=req.basic_decision_runs,
        deep_decision_runs=req.deep_decision_runs,
        reason=req.reason,
    )
    _record_admin_action(
        db,
        actor=user,
        action="ADMIN_ENTITLEMENT_GRANTED",
        target_type="user",
        target_id=granted.id,
        details={
            "credits": req.credits,
            "basic_decision_runs": req.basic_decision_runs,
            "deep_decision_runs": req.deep_decision_runs,
            "reason": req.reason,
            "non_revenue": True,
        },
    )
    return {
        **_user_payload(granted),
        "message": "已发放内部测试额度；该操作不会产生付款订单或计入营业收入。",
    }


@app.post("/v1/admin/invite-codes", status_code=status.HTTP_201_CREATED)
def create_invite_code(
    req: InviteCodeRequest,
    admin: User = Depends(_current_admin_required),
    db: Session = Depends(get_db),
):
    record = (
        db.query(InviteCode)
        .filter(InviteCode.code == req.code)
        .first()
    )
    reactivated = record is not None
    if record is None:
        record = InviteCode(
            code=req.code,
            created_by_user_id=admin.id,
        )
        db.add(record)
    record.source_name = req.source_name
    record.owner_name = req.owner_name
    record.owner_contact = req.owner_contact
    record.commission_bps = round(req.commission_percent * 100)
    record.bonus_credits = req.bonus_credits
    record.notes = req.notes
    record.active = True
    db.commit()
    db.refresh(record)
    _record_admin_action(
        db,
        actor=admin,
        action=(
            "INVITE_CODE_REACTIVATED"
            if reactivated
            else "INVITE_CODE_CREATED"
        ),
        target_type="invite_code",
        target_id=record.code,
        details={
            "owner_name": record.owner_name,
            "commission_percent": round(record.commission_bps / 100, 2),
            "bonus_credits": record.bonus_credits,
        },
    )
    return {
        "id": record.id,
        "code": record.code,
        "source_name": record.source_name,
        "owner_name": record.owner_name,
        "owner_contact": record.owner_contact,
        "commission_percent": round(record.commission_bps / 100, 2),
        "bonus_credits": record.bonus_credits,
        "notes": record.notes,
        "active": bool(record.active),
        "created_at": utc_isoformat(record.created_at),
        "updated_at": utc_isoformat(record.updated_at),
    }


@app.delete("/v1/admin/invite-codes/{code}")
def deactivate_invite_code(
    code: str,
    admin: User = Depends(_current_admin_required),
    db: Session = Depends(get_db),
):
    normalized = code.strip().upper()
    record = (
        db.query(InviteCode)
        .filter(InviteCode.code == normalized)
        .first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail="邀请码不存在")
    record.active = False
    db.commit()
    db.refresh(record)
    _record_admin_action(
        db,
        actor=admin,
        action="INVITE_CODE_DEACTIVATED",
        target_type="invite_code",
        target_id=record.code,
        details={
            "owner_name": record.owner_name,
            "historical_attribution_retained": True,
        },
    )
    return {
        "code": record.code,
        "active": False,
        "message": "邀请码已停用，历史客户归属和分成记录已保留",
    }


@app.get("/v1/admin/dashboard")
def admin_dashboard(
    _: User = Depends(_current_admin_required),
    db: Session = Depends(get_db),
):
    users = (
        db.query(User)
        .order_by(User.created_at.desc())
        .all()
    )
    order_rows = (
        db.query(PurchaseOrder, User)
        .join(User, User.id == PurchaseOrder.user_id)
        .order_by(PurchaseOrder.created_at.desc())
        .limit(500)
        .all()
    )
    order_metrics = {
        user_id: {
            "order_count": int(order_count),
            "paid_total_minor": int(paid_total_minor or 0),
        }
        for user_id, order_count, paid_total_minor in (
            db.query(
                PurchaseOrder.user_id,
                func.count(PurchaseOrder.id),
                func.sum(
                    case(
                        (
                            PurchaseOrder.status == "PAID",
                            PurchaseOrder.amount_minor,
                        ),
                        else_=0,
                    )
                ),
            )
            .group_by(PurchaseOrder.user_id)
            .all()
        )
    }
    invite_metrics: Dict[str, Dict[str, int]] = {}
    for user in users:
        if not user.invite_code:
            continue
        metrics = invite_metrics.setdefault(
            user.invite_code,
            {
                "registrations": 0,
                "paid_revenue_minor": 0,
                "commission_due_minor": 0,
            },
        )
        paid_total = int(
            order_metrics.get(user.id, {}).get("paid_total_minor", 0)
        )
        metrics["registrations"] += 1
        metrics["paid_revenue_minor"] += paid_total
        metrics["commission_due_minor"] += round(
            paid_total * int(user.invite_commission_bps or 0) / 10_000
        )
    invite_codes = (
        db.query(InviteCode)
        .order_by(InviteCode.created_at.desc())
        .all()
    )
    total_orders = db.query(PurchaseOrder).count()
    paid_orders = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.status == "PAID")
        .count()
    )
    pending_orders = (
        db.query(PurchaseOrder)
        .filter(
            PurchaseOrder.status.in_(
                ["PENDING_PAYMENT", "PAYMENT_REVIEW", "PAYMENT_REJECTED"]
            )
        )
        .count()
    )
    paid_revenue_minor = int(
        db.query(func.coalesce(func.sum(PurchaseOrder.amount_minor), 0))
        .filter(PurchaseOrder.status == "PAID")
        .scalar()
        or 0
    )
    total_runs = db.query(SimulationRunRecord).count()
    completed_runs = (
        db.query(SimulationRunRecord)
        .filter(SimulationRunRecord.status == "COMPLETED")
        .count()
    )
    failed_runs = (
        db.query(SimulationRunRecord)
        .filter(SimulationRunRecord.status == "FAILED")
        .count()
    )
    active_runs = (
        db.query(SimulationRunRecord)
        .filter(SimulationRunRecord.status.in_(["QUEUED", "RUNNING"]))
        .count()
    )
    calibration_summary = platform_calibration_summary(db)
    audit_logs = (
        db.query(AdminAuditLog)
        .order_by(AdminAuditLog.created_at.desc())
        .limit(100)
        .all()
    )
    return {
        "overview": {
            "total_users": db.query(User).count(),
            "total_orders": total_orders,
            "pending_orders": pending_orders,
            "paid_orders": paid_orders,
            "paid_revenue_minor": paid_revenue_minor,
            "total_runs": total_runs,
            "completed_runs": completed_runs,
            "failed_runs": failed_runs,
            "active_runs": active_runs,
            "active_invite_codes": sum(
                1 for item in invite_codes if item.active
            ),
            "calibration_contributions": calibration_summary[
                "total_contributions"
            ],
        },
        "calibration_benchmarks": calibration_summary,
        "users": [
            {
                **_user_payload(user),
                "created_at": utc_isoformat(user.created_at),
                "order_count": order_metrics.get(user.id, {}).get(
                    "order_count",
                    0,
                ),
                "paid_total_minor": order_metrics.get(user.id, {}).get(
                    "paid_total_minor",
                    0,
                ),
                "referral_commission_minor": round(
                    int(
                        order_metrics.get(user.id, {}).get(
                            "paid_total_minor",
                            0,
                        )
                    )
                    * int(user.invite_commission_bps or 0)
                    / 10_000
                ),
            }
            for user in users
        ],
        "orders": [
            {
                **_order_payload(order),
                "user_email": user.email,
                "user_name": user.name,
                "company": user.company,
                "invite_code": user.invite_code,
                "invite_owner": user.invite_owner,
                "referral_commission_minor": (
                    round(
                        order.amount_minor
                        * int(user.invite_commission_bps or 0)
                        / 10_000
                    )
                    if order.status == "PAID"
                    else 0
                ),
            }
            for order, user in order_rows
        ],
        "invite_codes": [
            {
                "id": item.id,
                "code": item.code,
                "source_name": item.source_name,
                "owner_name": item.owner_name,
                "owner_contact": item.owner_contact,
                "commission_percent": round(
                    int(item.commission_bps or 0) / 100,
                    2,
                ),
                "bonus_credits": int(item.bonus_credits),
                "notes": item.notes,
                "active": bool(item.active),
                "registrations": invite_metrics.get(item.code, {}).get(
                    "registrations",
                    0,
                ),
                "paid_revenue_minor": invite_metrics.get(item.code, {}).get(
                    "paid_revenue_minor",
                    0,
                ),
                "commission_due_minor": invite_metrics.get(item.code, {}).get(
                    "commission_due_minor",
                    0,
                ),
                "created_at": utc_isoformat(item.created_at),
                "updated_at": utc_isoformat(item.updated_at),
            }
            for item in invite_codes
        ],
        "audit_logs": [
            {
                "id": item.id,
                "actor_email": item.actor_email,
                "action": item.action,
                "target_type": item.target_type,
                "target_id": item.target_id,
                "details": dict(item.details_json or {}),
                "created_at": utc_isoformat(item.created_at),
            }
            for item in audit_logs
        ],
    }


@app.post("/v1/auth/login")
def login_user(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    return {
        "access_token": create_access_token(user.id, user.email),
        "token_type": "bearer",
        "user": _user_payload(user),
    }


@app.get("/v1/auth/me")
def get_current_user_profile(
    user: User = Depends(get_current_user_required),
):
    return _user_payload(user)


@app.get("/v1/billing/transactions")
def get_user_transactions(
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    transactions = (
        db.query(CreditTransaction)
        .filter(CreditTransaction.user_id == user.id)
        .order_by(CreditTransaction.created_at.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "id": item.id,
            "amount": item.amount,
            "type": item.transaction_type,
            "description": item.description,
            "balance_after": item.balance_after,
            "created_at": utc_isoformat(item.created_at),
        }
        for item in transactions
    ]


@app.get("/v1/billing/entitlement-transactions")
def get_user_entitlement_transactions(
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    transactions = (
        db.query(RunEntitlementTransaction)
        .filter(RunEntitlementTransaction.user_id == user.id)
        .order_by(RunEntitlementTransaction.created_at.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "id": item.id,
            "plan_code": item.plan_code,
            "amount": item.amount,
            "type": item.transaction_type,
            "description": item.description,
            "balance_after": item.balance_after,
            "created_at": utc_isoformat(item.created_at),
        }
        for item in transactions
    ]


@app.get("/v1/billing/orders")
def list_purchase_orders(
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    orders = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.user_id == user.id)
        .order_by(PurchaseOrder.created_at.desc())
        .limit(100)
        .all()
    )
    return [_order_payload(order) for order in orders]


@app.post("/v1/billing/orders", status_code=status.HTTP_201_CREATED)
def create_order(
    req: PurchaseOrderRequest,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    order = create_purchase_order(db, user, req.package_code)
    return {
        **_order_payload(order),
        "payment_mode": "manual_fixed_qr",
        "next_step": (
            "请选择订单允许的固定收款码完成付款，再提交付款信息。"
            "系统没有自动回调；管理员确认实际到账后才会入账。"
        ),
    }


@app.post("/v1/billing/orders/{order_id}/payment-claim")
def submit_order_payment_claim(
    order_id: str,
    req: ManualPaymentClaimRequest,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    order = (
        db.query(PurchaseOrder)
        .filter(
            PurchaseOrder.id == order_id,
            PurchaseOrder.user_id == user.id,
        )
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    order = submit_manual_payment(
        db,
        order=order,
        payment_method=req.payment_method,
        payer_name=req.payer_name,
        payment_claim_reference=req.payment_claim_reference,
        payment_time_text=req.payment_time_text,
        payment_claim_note=req.note,
    )
    return {
        **_order_payload(order),
        "message": (
            "付款信息已提交，订单正在等待人工核验。"
            "核验前不会发放决策次数或积分。"
        ),
    }


@app.post("/v1/admin/billing/orders/{order_id}/complete")
def admin_complete_order(
    order_id: str,
    req: CompleteOrderRequest,
    x_admin_key: Optional[str] = Header(default=None),
    user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    _require_admin_access(x_admin_key, user)
    order = complete_purchase_order(
        db,
        order_id,
        req.payment_reference,
    )
    _record_admin_action(
        db,
        actor=user,
        action="PAYMENT_CONFIRMED",
        target_type="purchase_order",
        target_id=order.id,
        details={
            "payment_reference": req.payment_reference,
            "amount_minor": order.amount_minor,
            "currency": order.currency,
        },
    )
    return _order_payload(order)


@app.post("/v1/admin/billing/orders/{order_id}/reject")
def admin_reject_order_payment(
    order_id: str,
    req: RejectPaymentRequest,
    x_admin_key: Optional[str] = Header(default=None),
    user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    _require_admin_access(x_admin_key, user)
    order = reject_manual_payment(
        db,
        order_id=order_id,
        review_note=req.note,
    )
    _record_admin_action(
        db,
        actor=user,
        action="PAYMENT_REJECTED",
        target_type="purchase_order",
        target_id=order.id,
        details={"note": req.note},
    )
    return _order_payload(order)


@app.post("/v1/studies", status_code=status.HTTP_201_CREATED)
def create_study(
    req: CreateStudyRequest,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    try:
        study = service.create_study(req.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    record = StudyRecord(
        id=study["id"],
        user_id=user.id,
        name=study["name"],
        study_type=study["study_type"],
        status=study["status"],
        plan_code=study["plan_code"],
        inputs_json=study["inputs"],
        facts_json=study["facts"],
    )
    db.add(record)
    db.commit()
    return study


@app.get("/v1/studies")
def list_studies(
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    records = (
        db.query(StudyRecord)
        .filter(StudyRecord.user_id == user.id)
        .order_by(StudyRecord.updated_at.desc())
        .limit(200)
        .all()
    )
    return [
        {
            "id": record.id,
            "name": record.name,
            "study_type": record.study_type,
            "status": record.status,
            "plan_code": record.plan_code,
            "category": (record.facts_json or {}).get("category"),
            "created_at": utc_isoformat(record.created_at),
            "updated_at": utc_isoformat(record.updated_at),
        }
        for record in records
    ]


@app.get("/v1/studies/{study_id}")
def get_study(
    study_id: str,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    record = _study_record(db, user, study_id)
    return {
        "id": record.id,
        "name": record.name,
        "study_type": record.study_type,
        "status": record.status,
        "plan_code": record.plan_code,
        "inputs": record.inputs_json,
        "facts": record.facts_json,
        "created_at": utc_isoformat(record.created_at),
        "updated_at": utc_isoformat(record.updated_at),
    }


@app.post("/v1/studies/{study_id}/confirm")
def confirm_study(
    study_id: str,
    req: StudyConfirmRequest,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    record = _study_record(db, user, study_id)
    _hydrate_service_study(record)
    try:
        study = service.confirm_study(study_id, req.overrides)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="研究项目不存在") from error
    record.status = "READY"
    record.facts_json = study["facts"]
    db.commit()
    return study


@app.post("/v1/studies/{study_id}/runs")
async def run_simulation(
    study_id: str,
    req: RunSimulationRequest,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    record = _study_record(db, user, study_id)
    if record.status not in {
        "READY",
        "FAILED_RECOVERABLE",
        "COMPLETED",
        "QUEUED",
        "RUNNING",
    }:
        raise HTTPException(
            status_code=409,
            detail="请先确认研究输入后再运行",
        )
    _hydrate_service_study(record)
    try:
        plan_code = normalize_plan_code(req.plan_code or record.plan_code)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if plan_code in UNAVAILABLE_PLANS:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{plan_code} 的独立执行后端尚未部署，"
                "系统不会扣费。当前请选择可自助运行的深度决策。"
            ),
        )

    request_key = req.idempotency_key or f"server-{uuid.uuid4().hex}"
    existing = (
        db.query(ReportRecord)
        .filter(
            ReportRecord.user_id == user.id,
            ReportRecord.request_key == request_key,
        )
        .first()
    )
    if existing:
        return existing.report_data

    existing_job = (
        db.query(SimulationRunRecord)
        .filter(
            SimulationRunRecord.user_id == user.id,
            SimulationRunRecord.request_key == request_key,
        )
        .first()
    )
    if existing_job:
        if existing_job.status == "COMPLETED" and existing_job.report_id:
            completed_report = (
                db.query(ReportRecord)
                .filter(
                    ReportRecord.user_id == user.id,
                    ReportRecord.id == existing_job.report_id,
                )
                .first()
            )
            if completed_report:
                return completed_report.report_data
        existing_job = _expire_stale_run(db, existing_job)
        if existing_job.status in {"PENDING", "QUEUED", "RUNNING"}:
            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content=_run_job_payload(existing_job),
            )
        raise HTTPException(
            status_code=409,
            detail="上次请求已失败，请使用新的请求编号重试。",
        )

    active_study_job = (
        db.query(SimulationRunRecord)
        .filter(
            SimulationRunRecord.user_id == user.id,
            SimulationRunRecord.study_id == study_id,
            SimulationRunRecord.plan_code == plan_code,
            SimulationRunRecord.status.in_(
                ["PENDING", "QUEUED", "RUNNING"]
            ),
        )
        .order_by(SimulationRunRecord.created_at.desc())
        .first()
    )
    if active_study_job:
        active_study_job = _expire_stale_run(db, active_study_job)
        if active_study_job.status in {"PENDING", "QUEUED", "RUNNING"}:
            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content=_run_job_payload(active_study_job),
            )
    if record.status in {"QUEUED", "RUNNING"}:
        raise HTTPException(
            status_code=409,
            detail="项目仍标记为运行中，但未找到可恢复的后台任务，请联系管理员。",
        )

    requested_population = (
        None
        if plan_code in SELF_SERVICE_PLANS
        else req.population_size
    )
    calibration_tier = (
        "CUSTOMER_OBSERVED_CHOICE"
        if (record.inputs_json or {}).get("observed_choice_data")
        else "PUBLIC_EVIDENCE"
    )
    frozen_inputs, frozen_facts, frozen_input_digest = snapshot_study_payload(
        inputs=record.inputs_json,
        facts=record.facts_json,
    )
    run_job = SimulationRunRecord(
        user_id=user.id,
        study_id=study_id,
        request_key=request_key,
        plan_code=plan_code,
        status="PENDING",
        requested_population=requested_population,
        requested_mc_rounds=req.mc_rounds,
        seed=req.seed,
        frozen_inputs_json=frozen_inputs,
        frozen_facts_json=frozen_facts,
        frozen_input_digest=frozen_input_digest,
        progress_stage="QUEUED",
        progress_percent=0,
        calibration_tier=calibration_tier,
    )
    db.add(run_job)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        active_study_job = (
            db.query(SimulationRunRecord)
            .filter(
                SimulationRunRecord.user_id == user.id,
                SimulationRunRecord.study_id == study_id,
                SimulationRunRecord.plan_code == plan_code,
                SimulationRunRecord.status.in_(
                    ["PENDING", "QUEUED", "RUNNING"]
                ),
            )
            .order_by(SimulationRunRecord.created_at.desc())
            .first()
        )
        if active_study_job:
            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content=_run_job_payload(active_study_job),
            )
        raise HTTPException(
            status_code=409,
            detail="相同请求已经被接收，请稍后读取研究报告。",
        ) from error

    billing_reference = f"{user.id}:{request_key}"
    try:
        reservation = check_and_reserve_run(
            db,
            user,
            plan_code,
            billing_reference,
        )
    except HTTPException:
        run_job = (
            db.query(SimulationRunRecord)
            .filter(SimulationRunRecord.id == run_job.id)
            .one()
        )
        run_job.status = "FAILED"
        run_job.error_code = "BILLING_REJECTED"
        db.commit()
        raise

    run_job = (
        db.query(SimulationRunRecord)
        .filter(SimulationRunRecord.id == run_job.id)
        .one()
    )
    run_job.credits_reserved = int(reservation["deducted_credits"])
    run_job.entitlement_code = reservation.get("entitlement_code")
    run_job.entitlement_reserved = int(
        reservation.get("entitlement_deducted") or 0
    )
    if should_dispatch_asynchronously(plan_code):
        run_job.status = "QUEUED"
        run_job.progress_stage = "QUEUED"
        run_job.progress_percent = 0
        record.status = "QUEUED"
        db.commit()
        try:
            dispatch_result = await asyncio.to_thread(
                dispatch_run_job,
                run_job.id,
            )
            run_job = (
                db.query(SimulationRunRecord)
                .filter(SimulationRunRecord.id == run_job.id)
                .one()
            )
            run_job.provider_execution_name = (
                dispatch_result.get("execution_name")
                or dispatch_result.get("operation_name")
            )
            db.commit()
            db.refresh(run_job)
            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content=_run_job_payload(run_job),
            )
        except Exception as error:
            db.rollback()
            failed_job = (
                db.query(SimulationRunRecord)
                .filter(SimulationRunRecord.id == run_job.id)
                .one()
            )
            failed_job.status = "FAILED"
            failed_job.progress_stage = "FAILED_RECOVERABLE"
            failed_job.progress_percent = 100
            failed_job.error_code = "DISPATCH_FAILED"
            failed_job.completed_at = datetime.utcnow()
            record = _study_record(db, user, study_id)
            record.status = "FAILED_RECOVERABLE"
            refund_run_reservation(
                db,
                user.id,
                reservation,
                billing_reference,
            )
            db.commit()
            LOGGER.exception(
                "Cloud Run Job dispatch failed for study %s",
                study_id,
            )
            raise HTTPException(
                status_code=503,
                detail=(
                    "后台任务暂时无法启动，预留的积分或决策次数"
                    "已自动退回，请稍后重试。"
                ),
            ) from error

    run_job.status = "RUNNING"
    run_job.progress_stage = "PREPARING_POPULATION"
    run_job.progress_percent = 5
    run_job.started_at = datetime.utcnow()
    db.commit()

    component_run = None
    component_run_id = None
    try:
        # Rehydrate from the immutable queued snapshot so a later study edit
        # cannot silently change an already billed run.
        service.hydrate_study(
            study_id=record.id,
            name=record.name,
            study_type=record.study_type,
            status=record.status,
            plan_code=record.plan_code,
            inputs=run_job.frozen_inputs_json or record.inputs_json,
            facts=run_job.frozen_facts_json or record.facts_json,
            created_at=utc_isoformat(record.created_at),
            updated_at=utc_isoformat(record.updated_at),
        )
        component_run = begin_native_component_run(db, run_job)
        component_run_id = component_run.id
        db.commit()
        model_study_type = service._effective_model_type(
            service.studies_db[study_id]
        )
        pooled_override = platform_calibration_override(
            db,
            (run_job.frozen_facts_json or record.facts_json or {}).get(
                "category"
            ),
            model_study_type,
        )
        if pooled_override and calibration_tier == "PUBLIC_EVIDENCE":
            run_job.calibration_tier = "PLATFORM_CATEGORY_BENCHMARK"
            db.commit()
        report = await service.execute_run(
            study_id=study_id,
            pop_size=requested_population,
            mc_rounds=req.mc_rounds,
            seed=req.seed,
            plan_code=plan_code,
            platform_calibration_override=pooled_override,
        )
        complete_component_run(
            db,
            component_run,
            report_id=report["report_id"],
            report_run_id=report["run_id"],
            report_payload=report,
        )
        report["model_components"] = [component_run_lineage(component_run)]
        report_record = ReportRecord(
            id=report["report_id"],
            user_id=user.id,
            run_id=report["run_id"],
            study_id=study_id,
            request_key=request_key,
            population_size=report["population_size"],
            mc_rounds=report["mc_rounds"],
            report_data=report,
        )
        db.add(report_record)
        record_platform_contribution(db, report)
        # PostgreSQL enforces the simulation_runs.report_id foreign key.
        # Flush the new report before linking the durable run record to it;
        # assigning only the scalar ID does not give SQLAlchemy an ORM
        # relationship from which it can infer insert ordering.
        db.flush()
        run_job = (
            db.query(SimulationRunRecord)
            .filter(SimulationRunRecord.id == run_job.id)
            .one()
        )
        run_job.status = "COMPLETED"
        run_job.progress_stage = "COMPLETED"
        run_job.progress_percent = 100
        run_job.completed_at = datetime.utcnow()
        run_job.report_id = report["report_id"]
        record.status = "COMPLETED"
        record.plan_code = plan_code
        db.commit()
        return report
    except Exception as error:
        db.rollback()
        record = _study_record(db, user, study_id)
        record.status = "FAILED_RECOVERABLE"
        failed_job = (
            db.query(SimulationRunRecord)
            .filter(
                SimulationRunRecord.user_id == user.id,
                SimulationRunRecord.request_key == request_key,
            )
            .one()
        )
        failed_job.status = "FAILED"
        failed_job.progress_stage = "FAILED_RECOVERABLE"
        failed_job.progress_percent = 100
        failed_job.error_code = type(error).__name__[:120]
        failed_job.completed_at = datetime.utcnow()
        if component_run_id:
            failed_component = (
                db.query(ModelComponentRunRecord)
                .filter(ModelComponentRunRecord.id == component_run_id)
                .first()
            )
            fail_component_run(failed_component, error)
        refund_run_reservation(
            db,
            user.id,
            reservation,
            billing_reference,
        )
        db.commit()
        LOGGER.exception("Simulation failed for study %s", study_id)
        if isinstance(error, HTTPException):
            raise
        if isinstance(error, ValueError):
            raise HTTPException(status_code=400, detail=str(error)) from error
        raise HTTPException(
            status_code=500,
            detail="模拟失败，预留的积分或决策次数已自动退回；项目可以重新运行。",
        ) from error


@app.get("/v1/runs/{run_job_id}")
def get_run_status(
    run_job_id: str,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    job = (
        db.query(SimulationRunRecord)
        .filter(
            SimulationRunRecord.id == run_job_id,
            SimulationRunRecord.user_id == user.id,
        )
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="后台任务不存在")
    job = _expire_stale_run(db, job)
    return _run_job_payload(job)


@app.post("/v1/runs/{run_job_id}/cancel")
def cancel_run(
    run_job_id: str,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """Cancel a queued/running customer run and refund its reservation once.

    A Cloud Run worker may take a moment to stop after its current compute
    slice.  It checks this durable state before writing a report, so a
    cancelled run never becomes a completed paid result.
    """

    job = (
        db.query(SimulationRunRecord)
        .filter(
            SimulationRunRecord.id == run_job_id,
            SimulationRunRecord.user_id == user.id,
        )
        .with_for_update()
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="后台任务不存在")
    if job.status not in {"PENDING", "QUEUED", "RUNNING"}:
        raise HTTPException(
            status_code=409,
            detail="该任务当前不能取消",
        )

    reservation = _reservation_from_job(job)
    job.status = "CANCELLED"
    job.progress_stage = "CANCELLED"
    job.progress_percent = 100
    job.error_code = "CANCELLED_BY_USER"
    job.completed_at = datetime.utcnow()
    update_run_checkpoint(
        job,
        stage="CANCELLED",
        percent=100,
        error_code="CANCELLED_BY_USER",
    )
    study = (
        db.query(StudyRecord)
        .filter(StudyRecord.id == job.study_id)
        .first()
    )
    if study:
        study.status = "READY"
    provider_reference = job.provider_execution_name
    refund_run_reservation(
        db,
        job.user_id,
        reservation,
        f"{job.user_id}:{job.request_key}",
    )
    db.commit()
    db.refresh(job)
    provider_cancel_requested = False
    if provider_reference:
        try:
            provider_cancel_requested = cancel_run_execution(
                provider_reference
            )
        except Exception:
            # Durable cancellation and refund are already committed.  The
            # worker still cannot publish a report even if the provider's
            # control-plane cancellation is temporarily unavailable.
            LOGGER.exception(
                "Cloud Run execution cancellation failed for %s",
                run_job_id,
            )
    payload = _run_job_payload(job)
    payload["provider_cancel_requested"] = provider_cancel_requested
    return payload


@app.get("/v1/reports/{report_id}")
def get_report(
    report_id: str,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    record = (
        db.query(ReportRecord)
        .filter(
            ReportRecord.user_id == user.id,
            ReportRecord.id == report_id,
        )
        .first()
    )
    if not record:
        record = (
            db.query(ReportRecord)
            .filter(
                ReportRecord.user_id == user.id,
                ReportRecord.study_id == report_id,
            )
            .order_by(ReportRecord.created_at.desc())
            .first()
        )
    if not record:
        raise HTTPException(status_code=404, detail="报告不存在")
    return record.report_data
