"""Immutable lineage records for long-running model components.

This module deliberately stores only compact manifests and hashes in the
business database.  Raw customer inputs, synthetic-population rows, complete
Persona transcripts, and model payloads belong in a private artifact store.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from typing import Any, Mapping

from sqlalchemy.orm import Session

from app.db.models import (
    ModelArtifactRecord,
    ModelComponentRunRecord,
    SimulationRunRecord,
)
from model_artifacts.base import ArtifactWriteRequest
from model_artifacts.factory import artifact_store_from_environment
from model_artifacts.manifest import FrozenInputManifest


COMPONENT_RUN_SCHEMA_VERSION = "component-run-v1"
NATIVE_SIMULATION_BACKEND = "native"
NATIVE_SIMULATION_BACKEND_VERSION = "native-runner-1"
NATIVE_SIMULATION_CONFIG_VERSION = "run-snapshot-1"


def _artifact_persistence_enabled() -> bool:
    """Keep new persistence opt-in until its private bucket is provisioned."""

    return os.environ.get(
        "ENABLE_MODEL_ARTIFACT_PERSISTENCE", "false"
    ).strip().lower() in {"1", "true", "yes"}


def _persist_manifest(
    db: Session,
    record: ModelComponentRunRecord,
    *,
    manifest: FrozenInputManifest,
    artifact_type: str,
) -> str | None:
    """Write a safe, hash-only manifest when private storage is enabled.

    The manifest contains no raw study input, customer facts, Persona text,
    or report body.  That lets retries remain auditable without turning the
    artifact store into an ungoverned customer-data replica.
    """

    if not _artifact_persistence_enabled():
        return None
    existing = (
        db.query(ModelArtifactRecord)
        .filter(
            ModelArtifactRecord.component_run_id == record.id,
            ModelArtifactRecord.artifact_type == artifact_type,
        )
        .first()
    )
    if existing:
        return existing.uri

    store = artifact_store_from_environment()
    descriptor = store.put(
        ArtifactWriteRequest(
            component_run_id=record.id,
            artifact_type=artifact_type,
            payload=manifest.to_bytes(),
            media_type="application/json",
            schema_version=COMPONENT_RUN_SCHEMA_VERSION,
            suffix=".json",
            metadata={
                "manifest_id": manifest.manifest_id,
                "component": manifest.component,
                "backend": manifest.backend,
                "backend_version": manifest.backend_version,
                "config_version": manifest.config_version,
                "seed": manifest.seed,
                "payload_sha256": manifest.payload_sha256,
            },
        )
    )
    db.add(
        ModelArtifactRecord(
            component_run_id=record.id,
            artifact_type=artifact_type,
            uri=descriptor.uri,
            sha256=descriptor.sha256,
            size_bytes=descriptor.size_bytes,
            media_type=descriptor.media_type,
            schema_version=descriptor.schema_version,
        )
    )
    return descriptor.uri


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest_json(value: Mapping[str, Any] | None) -> str:
    return hashlib.sha256(_canonical_bytes(value or {})).hexdigest()


def snapshot_study_payload(
    *,
    inputs: Mapping[str, Any] | None,
    facts: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Return a detached, canonical study snapshot and its stable digest."""

    frozen_inputs = json.loads(_canonical_bytes(inputs or {}).decode("utf-8"))
    frozen_facts = json.loads(_canonical_bytes(facts or {}).decode("utf-8"))
    snapshot_digest = digest_json(
        {
            "schema_version": "study-run-snapshot-v1",
            "inputs": frozen_inputs,
            "facts": frozen_facts,
        }
    )
    return frozen_inputs, frozen_facts, snapshot_digest


def native_run_manifest(
    run: SimulationRunRecord,
) -> FrozenInputManifest:
    """Build a non-sensitive manifest for one billed simulation request."""

    payload = {
        "schema_version": "native-run-input-v1",
        "study_id": run.study_id,
        "plan_code": run.plan_code,
        "requested_population": run.requested_population,
        "requested_mc_rounds": run.requested_mc_rounds,
        "study_snapshot_sha256": run.frozen_input_digest
        or digest_json(
            {
                "inputs": run.frozen_inputs_json or {},
                "facts": run.frozen_facts_json or {},
            }
        ),
    }
    return FrozenInputManifest.freeze(
        component="native_simulation",
        backend=NATIVE_SIMULATION_BACKEND,
        backend_version=NATIVE_SIMULATION_BACKEND_VERSION,
        config_version=NATIVE_SIMULATION_CONFIG_VERSION,
        seed=int(run.seed or 42),
        payload=payload,
        created_at=datetime.utcnow().isoformat() + "Z",
    )


def begin_native_component_run(
    db: Session,
    run: SimulationRunRecord,
) -> ModelComponentRunRecord:
    """Create or resume exactly one native-component record for a run."""

    manifest = native_run_manifest(run)
    record = (
        db.query(ModelComponentRunRecord)
        .filter(
            ModelComponentRunRecord.simulation_run_id == run.id,
            ModelComponentRunRecord.component == manifest.component,
            ModelComponentRunRecord.input_manifest_sha256
            == manifest.payload_sha256,
        )
        .order_by(ModelComponentRunRecord.created_at.desc())
        .first()
    )
    now = datetime.utcnow()
    if record is None:
        record = ModelComponentRunRecord(
            simulation_run_id=run.id,
            component=manifest.component,
            backend=manifest.backend,
            backend_version=manifest.backend_version,
            config_version=manifest.config_version,
            seed=manifest.seed,
            input_manifest_sha256=manifest.payload_sha256,
            status="RUNNING",
            started_at=now,
        )
        db.add(record)
    else:
        record.backend = manifest.backend
        record.backend_version = manifest.backend_version
        record.config_version = manifest.config_version
        record.seed = manifest.seed
        record.status = "RUNNING"
        record.error_code = None
        record.started_at = record.started_at or now
        record.completed_at = None
    db.flush()
    input_manifest_uri = _persist_manifest(
        db,
        record,
        manifest=manifest,
        artifact_type="input_manifest",
    )
    if input_manifest_uri:
        record.input_manifest_uri = input_manifest_uri
    return record


def update_run_checkpoint(
    run: SimulationRunRecord,
    *,
    stage: str,
    percent: int,
    component_run: ModelComponentRunRecord | None = None,
    error_code: str | None = None,
) -> dict[str, Any]:
    """Persist a small restart checkpoint without copying customer data.

    A retry intentionally restarts the current model component from its
    frozen input manifest.  The checkpoint proves which immutable input,
    backend, version, configuration, and seed must be reused; it is not a
    partial scientific result and cannot be mistaken for one.
    """

    now = datetime.utcnow()
    payload = {
        "schema_version": "native-run-checkpoint-v1",
        "simulation_run_id": run.id,
        "stage": str(stage),
        "progress_percent": max(0, min(100, int(percent))),
        "attempt_count": int(run.attempt_count or 0),
        "study_snapshot_sha256": run.frozen_input_digest,
        "component": (
            component_run.component
            if component_run is not None
            else "native_simulation"
        ),
        "backend": (
            component_run.backend
            if component_run is not None
            else NATIVE_SIMULATION_BACKEND
        ),
        "backend_version": (
            component_run.backend_version
            if component_run is not None
            else NATIVE_SIMULATION_BACKEND_VERSION
        ),
        "config_version": (
            component_run.config_version
            if component_run is not None
            else NATIVE_SIMULATION_CONFIG_VERSION
        ),
        "seed": int(
            component_run.seed
            if component_run is not None
            else (run.seed or 42)
        ),
        "input_manifest_sha256": (
            component_run.input_manifest_sha256
            if component_run is not None
            else native_run_manifest(run).payload_sha256
        ),
        "error_code": error_code,
        "recorded_at": now.isoformat() + "Z",
    }
    run.checkpoint_json = payload
    run.checkpoint_sha256 = digest_json(payload)
    run.checkpoint_stage = str(stage)
    run.checkpoint_updated_at = now
    return payload


def complete_component_run(
    db: Session,
    record: ModelComponentRunRecord,
    *,
    report_id: str,
    report_run_id: str,
    report_payload: Mapping[str, Any],
) -> None:
    """Record a hash-only immutable output manifest after a successful run."""

    output_manifest = FrozenInputManifest.freeze(
        component=record.component,
        backend=record.backend,
        backend_version=record.backend_version,
        config_version=record.config_version,
        seed=record.seed,
        payload={
            "schema_version": "native-run-output-v1",
            "report_id": report_id,
            "report_run_id": report_run_id,
            "report_sha256": digest_json(report_payload),
        },
        created_at=datetime.utcnow().isoformat() + "Z",
    )
    record.output_manifest_sha256 = output_manifest.payload_sha256
    output_manifest_uri = _persist_manifest(
        db,
        record,
        manifest=output_manifest,
        artifact_type="output_manifest",
    )
    if output_manifest_uri:
        record.output_manifest_uri = output_manifest_uri
    record.status = "COMPLETED"
    record.error_code = None
    record.completed_at = datetime.utcnow()


def fail_component_run(
    record: ModelComponentRunRecord | None,
    error: BaseException,
) -> None:
    if record is None or record.status == "COMPLETED":
        return
    record.status = "FAILED"
    record.error_code = type(error).__name__[:120]
    record.completed_at = datetime.utcnow()


def cancel_component_run(
    record: ModelComponentRunRecord | None,
) -> None:
    """Close a component without treating an owner cancellation as failure."""

    if record is None or record.status == "COMPLETED":
        return
    record.status = "CANCELLED"
    record.error_code = "CANCELLED_BY_USER"
    record.completed_at = datetime.utcnow()


def component_run_lineage(
    record: ModelComponentRunRecord,
) -> dict[str, Any]:
    """Return report-safe lineage without exposing object-store internals."""

    return {
        "component": record.component,
        "backend": record.backend,
        "backend_version": record.backend_version,
        "dependency_version": record.dependency_version,
        "config_version": record.config_version,
        "seed": record.seed,
        "status": record.status,
        "input_manifest_sha256": record.input_manifest_sha256,
        "output_manifest_sha256": record.output_manifest_sha256,
        "artifact_persistence": (
            "configured"
            if record.input_manifest_uri or record.output_manifest_uri
            else "not_configured"
        ),
    }
