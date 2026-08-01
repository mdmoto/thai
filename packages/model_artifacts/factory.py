"""Fail-closed artifact-store configuration."""

from __future__ import annotations

import os
from pathlib import Path

from model_artifacts.base import ModelArtifactStore
from model_artifacts.gcs import GCSArtifactStore
from model_artifacts.local import LocalArtifactStore


def artifact_store_from_environment(
    app_env: str | None = None,
) -> ModelArtifactStore:
    environment = (
        app_env or os.environ.get("APP_ENV", "development")
    ).strip().lower()
    configured = os.environ.get("MODEL_ARTIFACT_STORE", "").strip().lower()
    if not configured:
        configured = "gcs" if environment == "production" else "local"

    if configured == "local":
        if environment == "production":
            raise RuntimeError(
                "Local artifact storage is disabled in production"
            )
        root = os.environ.get(
            "MODEL_ARTIFACT_LOCAL_ROOT",
            str(Path.cwd() / ".artifacts"),
        )
        return LocalArtifactStore(root)

    if configured == "gcs":
        bucket = os.environ.get("MODEL_ARTIFACT_BUCKET", "").strip()
        if not bucket:
            raise RuntimeError(
                "MODEL_ARTIFACT_BUCKET is required in production"
            )
        prefix = os.environ.get(
            "MODEL_ARTIFACT_PREFIX",
            "model-artifacts",
        )
        return GCSArtifactStore(bucket, prefix)

    raise RuntimeError(
        f"Unsupported MODEL_ARTIFACT_STORE: {configured!r}"
    )
