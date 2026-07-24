"""
Thailand Digital Market Twin Platform — FastAPI Service Entrypoint
Includes Auth, User Accounts, Credits Billing, Database Persistence, and Simulation Services.
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from app.db.database import engine, Base, get_db
from app.db.models import User, CreditTransaction, StudyRecord, ReportRecord
from app.db.auth import (
    hash_password, verify_password, create_access_token,
    get_current_user_optional, get_current_user_required
)
from app.db.billing_service import check_and_deduct_credits, recharge_credits
from app.schemas.study import CreateStudyRequest, StudyConfirmRequest, RunSimulationRequest
from app.services.study_service import StudyService

# Initialize Database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Thailand Digital Market Twin API",
    version="1.1.0",
    description="Backend API with Auth, Billing, Database, and Market Simulation"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

service = StudyService()

# ── Auth Pydantic Schemas ──────────────────
class RegisterRequest(BaseModel):
    email: str
    password: str
    name: Optional[str] = None
    company: Optional[str] = None

class LoginRequest(BaseModel):
    email: str
    password: str

class RechargeRequest(BaseModel):
    amount: int
    payment_ref: Optional[str] = "WX_PAY_DEMO"

# ── System Endpoints ──────────────────────
@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "Thailand Digital Market Twin Platform API",
        "version": "1.1.0"
    }

@app.get("/healthz")
def healthz():
    return {"status": "healthy"}

# ── Auth Endpoints ────────────────────────
@app.post("/v1/auth/register")
def register_user(req: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="该邮箱已被注册，请直接登录")

    user = User(
        email=req.email,
        password_hash=hash_password(req.password),
        name=req.name or req.email.split("@")[0],
        company=req.company,
        credits_balance=50  # 50 Initial signup credits
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Initial bonus tx
    tx = CreditTransaction(
        user_id=user.id,
        amount=50,
        transaction_type="SIGNUP_BONUS",
        description="新用户注册赠送初始体验积分 (+50 积分)"
    )
    db.add(tx)
    db.commit()

    token = create_access_token(user.id, user.email)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "company": user.company,
            "plan_tier": user.plan_tier,
            "credits_balance": user.credits_balance
        }
    }

@app.post("/v1/auth/login")
def login_user(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")

    token = create_access_token(user.id, user.email)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "company": user.company,
            "plan_tier": user.plan_tier,
            "credits_balance": user.credits_balance
        }
    }

@app.get("/v1/auth/me")
def get_current_user_profile(user: User = Depends(get_current_user_required)):
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "company": user.company,
        "plan_tier": user.plan_tier,
        "credits_balance": user.credits_balance
    }

# ── Billing & Credits Endpoints ───────────
@app.post("/v1/billing/recharge")
def recharge_credits_endpoint(
    req: RechargeRequest,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="充值积分额度必须大于 0")

    updated_user = recharge_credits(db, user, req.amount, req.payment_ref)
    return {
        "message": f"成功充值 {req.amount} 积分",
        "credits_balance": updated_user.credits_balance
    }

@app.get("/v1/billing/transactions")
def get_user_transactions(
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    txs = db.query(CreditTransaction).filter(CreditTransaction.user_id == user.id).order_by(CreditTransaction.created_at.desc()).all()
    return [
        {
            "id": tx.id,
            "amount": tx.amount,
            "type": tx.transaction_type,
            "description": tx.description,
            "created_at": tx.created_at.isoformat()
        } for tx in txs
    ]

# ── Study & Simulation Endpoints ──────────
@app.post("/v1/studies")
def create_study(
    req: CreateStudyRequest,
    user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    study_data = req.model_dump()
    study = service.create_study(study_data)

    # Save to persistent database if DB available
    rec = StudyRecord(
        id=study["id"],
        user_id=user.id if user else None,
        name=study["name"],
        study_type=study["study_type"],
        status=study["status"],
        plan_code=study["plan_code"],
        inputs_json=study["inputs"],
        facts_json=study["facts"]
    )
    db.add(rec)
    db.commit()

    return study

@app.get("/v1/studies/{study_id}")
def get_study(study_id: str, db: Session = Depends(get_db)):
    rec = db.query(StudyRecord).filter(StudyRecord.id == study_id).first()
    if rec:
        return {
            "id": rec.id,
            "name": rec.name,
            "study_type": rec.study_type,
            "status": rec.status,
            "plan_code": rec.plan_code,
            "inputs": rec.inputs_json,
            "facts": rec.facts_json,
            "created_at": rec.created_at.isoformat(),
            "updated_at": rec.updated_at.isoformat()
        }

    if study_id in service.studies_db:
        return service.studies_db[study_id]

    raise HTTPException(status_code=404, detail="Study not found")

@app.post("/v1/studies/{study_id}/confirm")
def confirm_study(study_id: str, req: StudyConfirmRequest, db: Session = Depends(get_db)):
    try:
        study = service.confirm_study(study_id, req.overrides)
        rec = db.query(StudyRecord).filter(StudyRecord.id == study_id).first()
        if rec:
            rec.status = "READY"
            rec.facts_json = study["facts"]
            db.commit()
        return study
    except KeyError:
        raise HTTPException(status_code=404, detail="Study not found")

@app.post("/v1/studies/{study_id}/runs")
async def run_simulation(
    study_id: str,
    req: RunSimulationRequest,
    user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    plan_code = req.plan_code or "FREE"

    # If user logged in and running paid tier (PROFESSIONAL / ENTERPRISE), deduct credits
    if user and plan_code in ["PROFESSIONAL", "ENTERPRISE", "DEEP"]:
        check_and_deduct_credits(db, user, plan_code)

    try:
        report = await service.execute_run(
            study_id=study_id,
            pop_size=req.population_size,
            mc_rounds=req.mc_rounds,
            seed=req.seed
        )

        # Save Report to Persistent DB
        rec = ReportRecord(
            id=report["report_id"],
            run_id=report["run_id"],
            study_id=study_id,
            population_size=report["population_size"],
            mc_rounds=report["mc_rounds"],
            report_data=report
        )
        db.add(rec)
        db.commit()

        return report
    except KeyError:
        raise HTTPException(status_code=404, detail="Study not found")

@app.get("/v1/reports/{report_id}")
def get_report(report_id: str, db: Session = Depends(get_db)):
    rec = db.query(ReportRecord).filter(ReportRecord.id == report_id).first()
    if rec:
        return rec.report_data

    if report_id in service.reports_db:
        return service.reports_db[report_id]

    raise HTTPException(status_code=404, detail="Report not found")
