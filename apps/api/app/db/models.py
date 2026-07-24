"""
SQLAlchemy ORM Models for User Accounts, Credits Billing, Studies, and Reports.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, ForeignKey, JSON
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
    credits_balance = Column(Integer, default=50)  # 50 free initial credits
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    transactions = relationship("CreditTransaction", back_populates="user")
    studies = relationship("StudyRecord", back_populates="user")

class CreditTransaction(Base):
    __tablename__ = "credit_transactions"

    id = Column(String, primary_key=True, default=lambda: f"tx_{uuid.uuid4().hex[:8]}")
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    amount = Column(Integer, nullable=False)  # Positive for recharge, negative for deduction
    transaction_type = Column(String, nullable=False)  # RECHARGE, DEDUCTION, SIGNUP_BONUS
    description = Column(String, nullable=True)
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

    id = Column(String, primary_key=True, default=lambda: f"rpt_{uuid.uuid4().hex[:8]}")
    run_id = Column(String, nullable=False)
    study_id = Column(String, ForeignKey("studies.id"), nullable=False)
    population_size = Column(Integer, nullable=False)
    mc_rounds = Column(Integer, nullable=False)
    report_data = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    study = relationship("StudyRecord", back_populates="reports")
