"""
Database Configuration & SQLAlchemy Session Management.
Supports SQLite (file-based persistence) and PostgreSQL (via DATABASE_URL env var).
"""

import logging
import os
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

LOGGER = logging.getLogger("market_twin.db")

APP_ENV = os.environ.get("APP_ENV", "development").strip().lower()
DATABASE_URL = os.environ.get("DATABASE_URL") or "sqlite:////tmp/market_twin.db"

GCS_DB_BUCKET = os.environ.get("GCS_SQLITE_BUCKET", "thai-503312-sqlite-db")
GCS_DB_BLOB = os.environ.get("GCS_SQLITE_BLOB", "market_twin.db")
LOCAL_DB_FILE = "/tmp/market_twin.db"


def download_sqlite_from_gcs() -> bool:
    """Download persisted SQLite database from GCS bucket on container startup."""
    if not DATABASE_URL.startswith("sqlite"):
        return False
    try:
        from google.cloud import storage
        client = storage.Client()
        bucket = client.bucket(GCS_DB_BUCKET)
        blob = bucket.blob(GCS_DB_BLOB)
        if blob.exists():
            blob.download_to_filename(LOCAL_DB_FILE)
            LOGGER.info("Successfully restored SQLite DB from gs://%s/%s", GCS_DB_BUCKET, GCS_DB_BLOB)
            return True
    except Exception as exc:
        LOGGER.warning("Could not download SQLite DB from GCS: %s", exc)
    return False


def upload_sqlite_to_gcs() -> bool:
    """Upload current SQLite database snapshot to GCS bucket for permanent persistence."""
    if not DATABASE_URL.startswith("sqlite") or not os.path.exists(LOCAL_DB_FILE):
        return False
    try:
        from google.cloud import storage
        client = storage.Client()
        bucket = client.bucket(GCS_DB_BUCKET)
        blob = bucket.blob(GCS_DB_BLOB)
        blob.upload_from_filename(LOCAL_DB_FILE)
        LOGGER.info("Successfully backed up SQLite DB to gs://%s/%s", GCS_DB_BUCKET, GCS_DB_BLOB)
        return True
    except Exception as exc:
        LOGGER.warning("Could not backup SQLite DB to GCS: %s", exc)
    return False


# For SQLite, enable check_same_thread=False for FastAPI multithreading
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)

if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def initialize_database() -> None:
    from app.db import models  # noqa: F401

    download_sqlite_from_gcs()
    Base.metadata.create_all(bind=engine)
    _upgrade_legacy_schema()
    upload_sqlite_to_gcs()


def _upgrade_legacy_schema() -> None:
    """Upgrade the pre-v2 prototype schema without discarding customer data."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    statements = []
    datetime_type = (
        "DATETIME"
        if engine.dialect.name == "sqlite"
        else "TIMESTAMP WITHOUT TIME ZONE"
    )
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
    if "users" in tables:
        columns = {item["name"] for item in inspector.get_columns("users")}
        if "invite_code" not in columns:
            statements.append("ALTER TABLE users ADD COLUMN invite_code VARCHAR")
        if "invite_status" not in columns:
            statements.append(
                "ALTER TABLE users ADD COLUMN invite_status VARCHAR "
                "NOT NULL DEFAULT 'NOT_PROVIDED'"
            )
        if "acquisition_source" not in columns:
            statements.append(
                "ALTER TABLE users ADD COLUMN acquisition_source VARCHAR "
                "NOT NULL DEFAULT 'ORGANIC'"
            )
        if "invite_owner" not in columns:
            statements.append(
                "ALTER TABLE users ADD COLUMN invite_owner VARCHAR"
            )
        if "invite_commission_bps" not in columns:
            statements.append(
                "ALTER TABLE users ADD COLUMN invite_commission_bps "
                "INTEGER NOT NULL DEFAULT 0"
            )
        if "basic_decision_runs_balance" not in columns:
            statements.append(
                "ALTER TABLE users ADD COLUMN basic_decision_runs_balance "
                "INTEGER NOT NULL DEFAULT 0"
            )
        if "free_preview_runs_balance" not in columns:
            statements.append(
                "ALTER TABLE users ADD COLUMN free_preview_runs_balance "
                "INTEGER NOT NULL DEFAULT 1"
            )
        if "deep_decision_runs_balance" not in columns:
            statements.append(
                "ALTER TABLE users ADD COLUMN deep_decision_runs_balance "
                "INTEGER NOT NULL DEFAULT 0"
            )
    if "purchase_orders" in tables:
        columns = {
            item["name"] for item in inspector.get_columns("purchase_orders")
        }
        if "entitlements_json" not in columns:
            statements.append(
                "ALTER TABLE purchase_orders ADD COLUMN entitlements_json JSON"
            )
        if "payment_method" not in columns:
            statements.append(
                "ALTER TABLE purchase_orders ADD COLUMN payment_method VARCHAR"
            )
        if "payer_name" not in columns:
            statements.append(
                "ALTER TABLE purchase_orders ADD COLUMN payer_name VARCHAR"
            )
        if "payment_claim_reference" not in columns:
            statements.append(
                "ALTER TABLE purchase_orders ADD COLUMN "
                "payment_claim_reference VARCHAR"
            )
        if "payment_time_text" not in columns:
            statements.append(
                "ALTER TABLE purchase_orders ADD COLUMN payment_time_text VARCHAR"
            )
        if "payment_claim_note" not in columns:
            statements.append(
                "ALTER TABLE purchase_orders ADD COLUMN payment_claim_note VARCHAR"
            )
        if "payment_claimed_at" not in columns:
            statements.append(
                "ALTER TABLE purchase_orders ADD COLUMN payment_claimed_at "
                f"{datetime_type}"
            )
        if "reviewed_at" not in columns:
            statements.append(
                "ALTER TABLE purchase_orders ADD COLUMN reviewed_at "
                f"{datetime_type}"
            )
        if "review_note" not in columns:
            statements.append(
                "ALTER TABLE purchase_orders ADD COLUMN review_note VARCHAR"
            )
    if "simulation_runs" in tables:
        columns = {
            item["name"] for item in inspector.get_columns("simulation_runs")
        }
        if "entitlement_code" not in columns:
            statements.append(
                "ALTER TABLE simulation_runs ADD COLUMN entitlement_code VARCHAR"
            )
        if "entitlement_reserved" not in columns:
            statements.append(
                "ALTER TABLE simulation_runs ADD COLUMN entitlement_reserved "
                "INTEGER NOT NULL DEFAULT 0"
            )
        if "requested_population" not in columns:
            statements.append(
                "ALTER TABLE simulation_runs ADD COLUMN requested_population "
                "INTEGER"
            )
        if "requested_mc_rounds" not in columns:
            statements.append(
                "ALTER TABLE simulation_runs ADD COLUMN requested_mc_rounds "
                "INTEGER"
            )
        if "seed" not in columns:
            statements.append(
                "ALTER TABLE simulation_runs ADD COLUMN seed "
                "INTEGER NOT NULL DEFAULT 42"
            )
        if "frozen_inputs_json" not in columns:
            statements.append(
                "ALTER TABLE simulation_runs ADD COLUMN frozen_inputs_json JSON"
            )
        if "frozen_facts_json" not in columns:
            statements.append(
                "ALTER TABLE simulation_runs ADD COLUMN frozen_facts_json JSON"
            )
        if "frozen_input_digest" not in columns:
            statements.append(
                "ALTER TABLE simulation_runs ADD COLUMN frozen_input_digest VARCHAR"
            )
        if "checkpoint_json" not in columns:
            statements.append(
                "ALTER TABLE simulation_runs ADD COLUMN checkpoint_json JSON"
            )
        if "checkpoint_sha256" not in columns:
            statements.append(
                "ALTER TABLE simulation_runs ADD COLUMN checkpoint_sha256 VARCHAR"
            )
        if "checkpoint_stage" not in columns:
            statements.append(
                "ALTER TABLE simulation_runs ADD COLUMN checkpoint_stage VARCHAR"
            )
        if "checkpoint_updated_at" not in columns:
            statements.append(
                "ALTER TABLE simulation_runs ADD COLUMN checkpoint_updated_at "
                f"{datetime_type}"
            )
        if "progress_stage" not in columns:
            statements.append(
                "ALTER TABLE simulation_runs ADD COLUMN progress_stage "
                "VARCHAR NOT NULL DEFAULT 'QUEUED'"
            )
        if "progress_percent" not in columns:
            statements.append(
                "ALTER TABLE simulation_runs ADD COLUMN progress_percent "
                "INTEGER NOT NULL DEFAULT 0"
            )
        if "provider_execution_name" not in columns:
            statements.append(
                "ALTER TABLE simulation_runs ADD COLUMN "
                "provider_execution_name VARCHAR"
            )
        if "attempt_count" not in columns:
            statements.append(
                "ALTER TABLE simulation_runs ADD COLUMN attempt_count "
                "INTEGER NOT NULL DEFAULT 0"
            )
        if "calibration_tier" not in columns:
            statements.append(
                "ALTER TABLE simulation_runs ADD COLUMN calibration_tier "
                "VARCHAR NOT NULL DEFAULT 'PUBLIC_EVIDENCE'"
            )
        if "started_at" not in columns:
            statements.append(
                "ALTER TABLE simulation_runs ADD COLUMN started_at "
                f"{datetime_type}"
            )
        if "completed_at" not in columns:
            statements.append(
                "ALTER TABLE simulation_runs ADD COLUMN completed_at "
                f"{datetime_type}"
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
        if "users" in tables and "simulation_runs" in tables:
            connection.execute(
                text(
                    "UPDATE users SET free_preview_runs_balance = 0 "
                    "WHERE EXISTS ("
                    "SELECT 1 FROM simulation_runs "
                    "WHERE simulation_runs.user_id = users.id "
                    "AND simulation_runs.plan_code = 'PREVIEW' "
                    "AND simulation_runs.status IN "
                    "('PENDING', 'QUEUED', 'RUNNING', 'COMPLETED')"
                    ")"
                )
            )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "ix_credit_transactions_reference_id "
                "ON credit_transactions (reference_id)"
            )
        )
        if "simulation_runs" in tables:
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS "
                    "ix_simulation_runs_frozen_input_digest "
                    "ON simulation_runs (frozen_input_digest)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS "
                    "ix_simulation_runs_checkpoint_sha256 "
                    "ON simulation_runs (checkpoint_sha256)"
                )
            )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_users_invite_code "
                "ON users (invite_code)"
            )
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "ix_reports_user_request_key "
                "ON reports (user_id, request_key)"
            )
        )
        if "simulation_runs" in tables:
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "ix_simulation_runs_active_study "
                    "ON simulation_runs (user_id, study_id, plan_code) "
                    "WHERE status IN ('PENDING', 'QUEUED', 'RUNNING')"
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
