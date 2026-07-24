"""Production API for the Thailand Market Twin decision platform."""

from __future__ import annotations

import logging
import os
import re
import secrets
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.auth import (
    create_access_token,
    get_current_user_required,
    hash_password,
    verify_password,
)
from app.db.billing_service import (
    check_and_deduct_credits,
    complete_purchase_order,
    create_purchase_order,
    public_catalog,
    refund_reserved_credits,
)
from app.db.database import (
    database_is_healthy,
    get_db,
    initialize_database,
)
from app.db.models import (
    CreditTransaction,
    PurchaseOrder,
    ReportRecord,
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
from simulation_core.config import PLAN_CONFIGS, normalize_plan_code


LOGGER = logging.getLogger("market_twin.api")
APP_ENV = os.environ.get("APP_ENV", "development").strip().lower()
SELF_SERVICE_PLANS = {"PREVIEW", "STANDARD", "PROFESSIONAL"}
ASSISTED_PLANS = {"DEEP", "ENTERPRISE"}
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_REQUEST_BYTES = int(os.environ.get("MAX_REQUEST_BYTES", "1048576"))
FREE_PREVIEW_LIMIT = int(os.environ.get("FREE_PREVIEW_LIMIT", "1"))
_rate_buckets: Dict[str, deque] = defaultdict(deque)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
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
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Admin-Key"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
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
        return JSONResponse(
            status_code=429,
            content={"detail": "请求过于频繁，请稍后再试", "request_id": request_id},
            headers={"Retry-After": str(window)},
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

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not EMAIL_PATTERN.match(normalized):
            raise ValueError("请输入有效邮箱")
        return normalized


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class PurchaseOrderRequest(BaseModel):
    package_code: str = Field(min_length=2, max_length=32)


class CompleteOrderRequest(BaseModel):
    payment_reference: str = Field(min_length=4, max_length=160)


def _user_payload(user: User) -> Dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "company": user.company,
        "plan_tier": user.plan_tier,
        "credits_balance": int(user.credits_balance),
    }


def _order_payload(order: PurchaseOrder) -> Dict[str, Any]:
    return {
        "id": order.id,
        "package_code": order.package_code,
        "credits": order.credits,
        "amount_minor": order.amount_minor,
        "currency": order.currency,
        "status": order.status,
        "payment_reference": order.payment_reference,
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat(),
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
        created_at=record.created_at.isoformat() if record.created_at else None,
        updated_at=record.updated_at.isoformat() if record.updated_at else None,
    )


def _require_admin_key(value: Optional[str]) -> None:
    expected = os.environ.get("ADMIN_API_KEY")
    if not expected:
        raise HTTPException(status_code=503, detail="管理接口尚未配置")
    if not value or not secrets.compare_digest(value, expected):
        raise HTTPException(status_code=403, detail="管理凭证无效")


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
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="该邮箱已被注册")
    user = User(
        email=req.email,
        password_hash=hash_password(req.password),
        name=(req.name or req.email.split("@")[0]).strip(),
        company=req.company.strip() if req.company else None,
        credits_balance=5,
    )
    db.add(user)
    db.flush()
    db.add(
        CreditTransaction(
            user_id=user.id,
            amount=5,
            transaction_type="SIGNUP_BONUS",
            description="新用户 Standard 体验额度",
            reference_id=f"signup:{user.id}",
            balance_after=5,
        )
    )
    db.commit()
    db.refresh(user)
    return {
        "access_token": create_access_token(user.id, user.email),
        "token_type": "bearer",
        "user": _user_payload(user),
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
            "created_at": item.created_at.isoformat(),
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
        "payment_mode": "sales_verified_invoice",
        "next_step": (
            "请保存订单编号并通过 Lazzor 官方销售渠道完成付款；"
            "确认到账后积分只会由受保护的管理接口入账。"
        ),
    }


@app.post("/v1/admin/billing/orders/{order_id}/complete")
def admin_complete_order(
    order_id: str,
    req: CompleteOrderRequest,
    x_admin_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    _require_admin_key(x_admin_key)
    order = complete_purchase_order(
        db,
        order_id,
        req.payment_reference,
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
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
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
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
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
    if record.status not in {"READY", "FAILED_RECOVERABLE", "COMPLETED"}:
        raise HTTPException(
            status_code=409,
            detail="请先确认研究输入后再运行",
        )
    _hydrate_service_study(record)
    try:
        plan_code = normalize_plan_code(req.plan_code or record.plan_code)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if plan_code in ASSISTED_PLANS:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{plan_code} 当前采用销售协助交付；"
                "自助版本请选择 PROFESSIONAL。"
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

    if plan_code == "PREVIEW":
        prior_reports = (
            db.query(ReportRecord)
            .filter(ReportRecord.user_id == user.id)
            .order_by(ReportRecord.created_at.desc())
            .limit(max(FREE_PREVIEW_LIMIT, 1) + 10)
            .all()
        )
        preview_count = sum(
            1
            for item in prior_reports
            if (item.report_data or {}).get("plan_code") == "PREVIEW"
        )
        if preview_count >= FREE_PREVIEW_LIMIT:
            raise HTTPException(
                status_code=402,
                detail=(
                    "每个账号包含 1 次免费 Preview。"
                    "请使用注册赠送积分运行 Standard，或购买积分。"
                ),
            )

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
        raise HTTPException(
            status_code=409,
            detail=(
                "相同请求正在执行，请稍后读取研究报告。"
                if existing_job.status in {"PENDING", "RUNNING"}
                else "上次请求已失败，请使用新的请求编号重试。"
            ),
        )

    run_job = SimulationRunRecord(
        user_id=user.id,
        study_id=study_id,
        request_key=request_key,
        plan_code=plan_code,
        status="PENDING",
    )
    db.add(run_job)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="相同请求已经被接收，请稍后读取研究报告。",
        ) from error

    billing_reference = f"{user.id}:{request_key}"
    try:
        reservation = check_and_deduct_credits(
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
    run_job.status = "RUNNING"
    run_job.credits_reserved = int(reservation["deducted"])
    db.commit()

    try:
        report = await service.execute_run(
            study_id=study_id,
            pop_size=req.population_size,
            mc_rounds=req.mc_rounds,
            seed=req.seed,
            plan_code=plan_code,
        )
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
        failed_job.error_code = type(error).__name__[:120]
        db.commit()
        refund_reserved_credits(
            db,
            user.id,
            int(reservation["deducted"]),
            billing_reference,
        )
        LOGGER.exception("Simulation failed for study %s", study_id)
        if isinstance(error, HTTPException):
            raise
        if isinstance(error, ValueError):
            raise HTTPException(status_code=400, detail=str(error)) from error
        raise HTTPException(
            status_code=500,
            detail="模拟失败，预留积分已自动退回；项目可以重新运行。",
        ) from error


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
