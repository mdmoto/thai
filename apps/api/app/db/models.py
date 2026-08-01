"""
SQLAlchemy ORM Models for User Accounts, Credits Billing, Studies, and Reports.
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    Boolean,
    String,
    Integer,
    DateTime,
    ForeignKey,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.db.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: f"usr_{uuid.uuid4().hex[:8]}")
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    name = Column(String, nullable=True)
    company = Column(String, nullable=True)
    invite_code = Column(String, nullable=True, index=True)
    invite_status = Column(String, nullable=False, default="NOT_PROVIDED")
    acquisition_source = Column(String, nullable=False, default="ORGANIC")
    invite_owner = Column(String, nullable=True)
    invite_commission_bps = Column(Integer, nullable=False, default=0)
    plan_tier = Column(String, default="FREE")  # FREE, PROFESSIONAL, ENTERPRISE
    credits_balance = Column(Integer, default=0)  # Bonuses are granted explicitly.
    free_preview_runs_balance = Column(Integer, nullable=False, default=1)
    basic_decision_runs_balance = Column(Integer, nullable=False, default=0)
    deep_decision_runs_balance = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    transactions = relationship("CreditTransaction", back_populates="user")
    studies = relationship("StudyRecord", back_populates="user")
    reports = relationship("ReportRecord", back_populates="user")
    purchase_orders = relationship("PurchaseOrder", back_populates="user")
    simulation_runs = relationship("SimulationRunRecord", back_populates="user")
    entitlement_transactions = relationship(
        "RunEntitlementTransaction",
        back_populates="user",
    )

class CreditTransaction(Base):
    __tablename__ = "credit_transactions"

    id = Column(String, primary_key=True, default=lambda: f"tx_{uuid.uuid4().hex[:8]}")
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    amount = Column(Integer, nullable=False)  # Positive for recharge, negative for deduction
    transaction_type = Column(String, nullable=False)  # RECHARGE, DEDUCTION, INVITE_BONUS
    description = Column(String, nullable=True)
    reference_id = Column(String, unique=True, index=True, nullable=True)
    balance_after = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="transactions")


class RunEntitlementTransaction(Base):
    """Auditable changes to purchased decision-run balances."""

    __tablename__ = "run_entitlement_transactions"

    id = Column(
        String,
        primary_key=True,
        default=lambda: f"entx_{uuid.uuid4().hex[:10]}",
    )
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    plan_code = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    transaction_type = Column(String, nullable=False)
    description = Column(String, nullable=True)
    reference_id = Column(String, unique=True, index=True, nullable=True)
    balance_after = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="entitlement_transactions")


class PendingRegistration(Base):
    """Short-lived registration state awaiting an email verification code."""

    __tablename__ = "pending_registrations"

    id = Column(
        String,
        primary_key=True,
        default=lambda: f"reg_{uuid.uuid4().hex[:16]}",
    )
    email = Column(String, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    name = Column(String, nullable=True)
    company = Column(String, nullable=True)
    invite_code = Column(String, nullable=True)
    code_digest = Column(String, nullable=False)
    attempts_remaining = Column(Integer, nullable=False, default=5)
    expires_at = Column(DateTime, nullable=False, index=True)
    consumed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class RegistrationAttempt(Base):
    """Privacy-preserving registration rate-limit record."""

    __tablename__ = "registration_attempts"

    id = Column(
        String,
        primary_key=True,
        default=lambda: f"rega_{uuid.uuid4().hex[:16]}",
    )
    ip_hash = Column(String, nullable=False, index=True)
    subnet_hash = Column(String, nullable=False, index=True)
    email_hash = Column(String, nullable=False, index=True)
    outcome = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class AdminAuditLog(Base):
    """Auditable record of sensitive administrator actions."""

    __tablename__ = "admin_audit_logs"

    id = Column(
        String,
        primary_key=True,
        default=lambda: f"admlog_{uuid.uuid4().hex[:12]}",
    )
    actor_user_id = Column(
        String,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    actor_email = Column(String, nullable=False)
    action = Column(String, nullable=False, index=True)
    target_type = Column(String, nullable=False)
    target_id = Column(String, nullable=False, index=True)
    details_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class InviteCode(Base):
    """Administrator-managed referral code and commission terms."""

    __tablename__ = "invite_codes"

    id = Column(
        String,
        primary_key=True,
        default=lambda: f"inv_{uuid.uuid4().hex[:10]}",
    )
    code = Column(String, unique=True, nullable=False, index=True)
    source_name = Column(String, nullable=False)
    owner_name = Column(String, nullable=False)
    owner_contact = Column(String, nullable=True)
    commission_bps = Column(Integer, nullable=False, default=0)
    bonus_credits = Column(Integer, nullable=False, default=0)
    notes = Column(String, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_by_user_id = Column(
        String,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class StudyRecord(Base):
    __tablename__ = "studies"

    id = Column(String, primary_key=True, default=lambda: f"study_{uuid.uuid4().hex[:8]}")
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    name = Column(String, nullable=False)
    study_type = Column(String, nullable=False)
    status = Column(String, default="NEEDS_CONFIRMATION")
    plan_code = Column(String, default="FREE")
    inputs_json = Column(JSON, nullable=True)
    facts_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="studies")
    reports = relationship("ReportRecord", back_populates="study")

class ReportRecord(Base):
    __tablename__ = "reports"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "request_key",
            name="uq_reports_user_request_key",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: f"rpt_{uuid.uuid4().hex[:8]}")
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    run_id = Column(String, nullable=False)
    study_id = Column(String, ForeignKey("studies.id"), nullable=False)
    request_key = Column(String, nullable=True, index=True)
    population_size = Column(Integer, nullable=False)
    mc_rounds = Column(Integer, nullable=False)
    report_data = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    study = relationship("StudyRecord", back_populates="reports")
    user = relationship("User", back_populates="reports")


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(
        String,
        primary_key=True,
        default=lambda: f"ord_{uuid.uuid4().hex[:10]}",
    )
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    package_code = Column(String, nullable=False)
    credits = Column(Integer, nullable=False)
    entitlements_json = Column(JSON, nullable=True)
    amount_minor = Column(Integer, nullable=False)
    currency = Column(String, nullable=False, default="THB")
    status = Column(String, nullable=False, default="PENDING_PAYMENT")
    payment_method = Column(String, nullable=True)
    payer_name = Column(String, nullable=True)
    payment_claim_reference = Column(String, nullable=True)
    payment_time_text = Column(String, nullable=True)
    payment_claim_note = Column(String, nullable=True)
    payment_claimed_at = Column(DateTime, nullable=True)
    payment_reference = Column(String, unique=True, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_note = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    user = relationship("User", back_populates="purchase_orders")


class SimulationRunRecord(Base):
    """Durable idempotency and billing state for one simulation request."""

    __tablename__ = "simulation_runs"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "request_key",
            name="uq_simulation_runs_user_request_key",
        ),
    )

    id = Column(
        String,
        primary_key=True,
        default=lambda: f"runjob_{uuid.uuid4().hex[:12]}",
    )
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    study_id = Column(String, ForeignKey("studies.id"), nullable=False, index=True)
    request_key = Column(String, nullable=False)
    plan_code = Column(String, nullable=False)
    status = Column(String, nullable=False, default="PENDING")
    credits_reserved = Column(Integer, nullable=False, default=0)
    entitlement_code = Column(String, nullable=True)
    entitlement_reserved = Column(Integer, nullable=False, default=0)
    report_id = Column(String, ForeignKey("reports.id"), nullable=True)
    error_code = Column(String, nullable=True)
    requested_population = Column(Integer, nullable=True)
    requested_mc_rounds = Column(Integer, nullable=True)
    seed = Column(Integer, nullable=False, default=42)
    # Heavy jobs must run from the exact confirmed study snapshot that was
    # billed and queued.  These nullable fields preserve legacy runs created
    # before immutable run inputs were introduced.
    frozen_inputs_json = Column(JSON, nullable=True)
    frozen_facts_json = Column(JSON, nullable=True)
    frozen_input_digest = Column(String, nullable=True, index=True)
    # Checkpoints contain execution metadata and hashes only.  They never
    # duplicate customer inputs, research evidence, or report content.
    checkpoint_json = Column(JSON, nullable=True)
    checkpoint_sha256 = Column(String, nullable=True, index=True)
    checkpoint_stage = Column(String, nullable=True)
    checkpoint_updated_at = Column(DateTime, nullable=True)
    progress_stage = Column(String, nullable=False, default="QUEUED")
    progress_percent = Column(Integer, nullable=False, default=0)
    provider_execution_name = Column(String, nullable=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    calibration_tier = Column(
        String,
        nullable=False,
        default="PUBLIC_EVIDENCE",
    )
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    user = relationship("User", back_populates="simulation_runs")
    component_runs = relationship(
        "ModelComponentRunRecord",
        back_populates="simulation_run",
        cascade="all, delete-orphan",
    )


class ModelComponentRunRecord(Base):
    """Auditable lifecycle for one model component within a study run.

    Large payloads remain in immutable object storage.  This table contains
    only lineage, hashes, resource accounting, and object references.
    """

    __tablename__ = "model_component_runs"

    id = Column(
        String,
        primary_key=True,
        default=lambda: f"comp_{uuid.uuid4().hex[:12]}",
    )
    simulation_run_id = Column(
        String,
        ForeignKey("simulation_runs.id"),
        nullable=False,
        index=True,
    )
    component = Column(String, nullable=False, index=True)
    backend = Column(String, nullable=False)
    backend_version = Column(String, nullable=False)
    dependency_version = Column(String, nullable=True)
    config_version = Column(String, nullable=False)
    seed = Column(Integer, nullable=False)
    input_manifest_uri = Column(String, nullable=True)
    input_manifest_sha256 = Column(String, nullable=False, index=True)
    output_manifest_uri = Column(String, nullable=True)
    output_manifest_sha256 = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, default="QUEUED", index=True)
    error_code = Column(String, nullable=True)
    cost_minor = Column(Integer, nullable=False, default=0)
    cost_currency = Column(String, nullable=False, default="THB")
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    simulation_run = relationship(
        "SimulationRunRecord",
        back_populates="component_runs",
    )
    artifacts = relationship(
        "ModelArtifactRecord",
        back_populates="component_run",
        cascade="all, delete-orphan",
    )


class ModelArtifactRecord(Base):
    """Immutable object-store descriptor; never stores artifact bytes."""

    __tablename__ = "model_artifacts"

    id = Column(
        String,
        primary_key=True,
        default=lambda: f"artifact_{uuid.uuid4().hex[:12]}",
    )
    component_run_id = Column(
        String,
        ForeignKey("model_component_runs.id"),
        nullable=False,
        index=True,
    )
    artifact_type = Column(String, nullable=False)
    uri = Column(String, nullable=False)
    sha256 = Column(String, nullable=False, index=True)
    size_bytes = Column(Integer, nullable=False)
    media_type = Column(String, nullable=False)
    schema_version = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    component_run = relationship(
        "ModelComponentRunRecord",
        back_populates="artifacts",
    )


class CalibrationContribution(Base):
    """De-identified fitted-choice statistics for pooled category calibration."""

    __tablename__ = "calibration_contributions"

    id = Column(
        String,
        primary_key=True,
        default=lambda: f"cal_{uuid.uuid4().hex[:12]}",
    )
    source_digest = Column(String, unique=True, nullable=False, index=True)
    category_key = Column(String, nullable=False, index=True)
    study_type = Column(String, nullable=False, index=True)
    choice_set_count = Column(Integer, nullable=False)
    observation_count = Column(Integer, nullable=False)
    coefficients_json = Column(JSON, nullable=False)
    standard_errors_json = Column(JSON, nullable=False)
    source_status = Column(
        String,
        nullable=False,
        default="OBSERVED_CHOICE_FIT_UNVALIDATED",
    )
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
