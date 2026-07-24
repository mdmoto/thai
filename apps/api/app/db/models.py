"""
SQLAlchemy ORM Models for User Accounts, Credits Billing, Studies, and Reports.
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
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
    plan_tier = Column(String, default="FREE")  # FREE, PROFESSIONAL, ENTERPRISE
    credits_balance = Column(Integer, default=0)  # Bonuses are granted explicitly.
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    transactions = relationship("CreditTransaction", back_populates="user")
    studies = relationship("StudyRecord", back_populates="user")
    reports = relationship("ReportRecord", back_populates="user")
    purchase_orders = relationship("PurchaseOrder", back_populates="user")
    simulation_runs = relationship("SimulationRunRecord", back_populates="user")

class CreditTransaction(Base):
    __tablename__ = "credit_transactions"

    id = Column(String, primary_key=True, default=lambda: f"tx_{uuid.uuid4().hex[:8]}")
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    amount = Column(Integer, nullable=False)  # Positive for recharge, negative for deduction
    transaction_type = Column(String, nullable=False)  # RECHARGE, DEDUCTION, SIGNUP_BONUS
    description = Column(String, nullable=True)
    reference_id = Column(String, unique=True, index=True, nullable=True)
    balance_after = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="transactions")

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
    amount_minor = Column(Integer, nullable=False)
    currency = Column(String, nullable=False, default="THB")
    status = Column(String, nullable=False, default="PENDING_PAYMENT")
    payment_reference = Column(String, unique=True, nullable=True)
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
    report_id = Column(String, ForeignKey("reports.id"), nullable=True)
    error_code = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    user = relationship("User", back_populates="simulation_runs")
