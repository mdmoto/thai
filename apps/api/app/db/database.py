"""
Database Configuration & SQLAlchemy Session Management.
Supports SQLite (file-based persistence) and PostgreSQL (via DATABASE_URL env var).
"""

import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

APP_ENV = os.environ.get("APP_ENV", "development").strip().lower()
DATABASE_URL = os.environ.get("DATABASE_URL")
if APP_ENV == "production" and not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is required when APP_ENV=production")
DATABASE_URL = DATABASE_URL or "sqlite:////tmp/market_twin.db"

# For SQLite, enable check_same_thread=False for FastAPI multithreading
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def initialize_database() -> None:
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _upgrade_legacy_schema()


def _upgrade_legacy_schema() -> None:
    """Upgrade the pre-v2 prototype schema without discarding customer data."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    statements = []
    if "credit_transactions" in tables:
        columns = {
            item["name"] for item in inspector.get_columns("credit_transactions")
        }
        if "reference_id" not in columns:
            statements.append(
                "ALTER TABLE credit_transactions ADD COLUMN reference_id VARCHAR"
            )
        if "balance_after" not in columns:
            statements.append(
                "ALTER TABLE credit_transactions ADD COLUMN balance_after INTEGER"
            )
    if "reports" in tables:
        columns = {item["name"] for item in inspector.get_columns("reports")}
        if "user_id" not in columns:
            statements.append("ALTER TABLE reports ADD COLUMN user_id VARCHAR")
        if "request_key" not in columns:
            statements.append("ALTER TABLE reports ADD COLUMN request_key VARCHAR")

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
        if "reports" in tables and "studies" in tables:
            connection.execute(
                text(
                    "UPDATE reports SET user_id = "
                    "(SELECT studies.user_id FROM studies "
                    "WHERE studies.id = reports.study_id) "
                    "WHERE user_id IS NULL"
                )
            )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "ix_credit_transactions_reference_id "
                "ON credit_transactions (reference_id)"
            )
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "ix_reports_user_request_key "
                "ON reports (user_id, request_key)"
            )
        )


def database_is_healthy() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
