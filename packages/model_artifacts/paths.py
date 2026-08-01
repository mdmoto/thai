"""Validation and canonical paths shared by artifact-store implementations."""

from __future__ import annotations

import hashlib
import re

from model_artifacts.base import ArtifactWriteRequest


_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SAFE_SUFFIX = re.compile(r"^(?:\.[A-Za-z0-9]{1,12})?$")


def validate_request(request: ArtifactWriteRequest) -> None:
    for label, value in (
        ("component_run_id", request.component_run_id),
        ("artifact_type", request.artifact_type),
        ("schema_version", request.schema_version),
    ):
        if not _SAFE_SEGMENT.fullmatch(str(value)):
            raise ValueError(f"Unsafe artifact {label}: {value!r}")
    if not request.media_type or "/" not in request.media_type:
        raise ValueError("Artifact media_type must be a MIME type")
    if not _SAFE_SUFFIX.fullmatch(request.suffix):
        raise ValueError(f"Unsafe artifact suffix: {request.suffix!r}")
    if not isinstance(request.payload, bytes):
        raise TypeError("Artifact payload must be bytes")


def sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def object_path(
    request: ArtifactWriteRequest,
    digest: str,
    prefix: str = "",
) -> str:
    parts = [
        request.component_run_id,
        request.artifact_type,
        f"{digest}{request.suffix}",
    ]
    clean_prefix = prefix.strip("/")
    if clean_prefix:
        parts.insert(0, clean_prefix)
    return "/".join(parts)
