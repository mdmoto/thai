"""Local immutable artifact store for development and automated tests."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from model_artifacts.base import ArtifactDescriptor, ArtifactWriteRequest
from model_artifacts.paths import object_path, sha256_hex, validate_request


class LocalArtifactStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, request: ArtifactWriteRequest) -> ArtifactDescriptor:
        validate_request(request)
        digest = sha256_hex(request.payload)
        relative_path = object_path(request, digest)
        target = (self.root / relative_path).resolve()
        if self.root not in target.parents:
            raise ValueError("Artifact path escapes configured local root")
        target.parent.mkdir(parents=True, exist_ok=True)

        created_at = datetime.now(timezone.utc).isoformat()
        if target.exists():
            existing = target.read_bytes()
            if sha256_hex(existing) != digest:
                raise RuntimeError("Immutable artifact path contains other data")
            metadata_path = target.with_name(f"{target.name}.metadata.json")
            if metadata_path.exists():
                stored = json.loads(metadata_path.read_text("utf-8"))
                created_at = str(stored.get("created_at") or created_at)
            return self._descriptor(
                request,
                digest,
                relative_path,
                target,
                created_at,
            )

        self._atomic_write(target, request.payload)
        descriptor = self._descriptor(
            request,
            digest,
            relative_path,
            target,
            created_at,
        )
        metadata_bytes = json.dumps(
            descriptor.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self._atomic_write(
            target.with_name(f"{target.name}.metadata.json"),
            metadata_bytes,
        )
        return descriptor

    @staticmethod
    def _atomic_write(target: Path, payload: bytes) -> None:
        file_descriptor, temporary_name = tempfile.mkstemp(
            dir=target.parent,
            prefix=f".{target.name}.",
        )
        try:
            with os.fdopen(file_descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, target)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)

    @staticmethod
    def _descriptor(
        request: ArtifactWriteRequest,
        digest: str,
        relative_path: str,
        target: Path,
        created_at: str,
    ) -> ArtifactDescriptor:
        return ArtifactDescriptor(
            component_run_id=request.component_run_id,
            artifact_type=request.artifact_type,
            uri=target.as_uri(),
            sha256=digest,
            size_bytes=len(request.payload),
            media_type=request.media_type,
            schema_version=request.schema_version,
            created_at=created_at,
            object_path=relative_path,
            metadata=dict(request.metadata or {}),
        )
