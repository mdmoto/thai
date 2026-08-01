"""Google Cloud Storage artifact store with immutable object preconditions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from model_artifacts.base import ArtifactDescriptor, ArtifactWriteRequest
from model_artifacts.paths import object_path, sha256_hex, validate_request


class GCSArtifactStore:
    def __init__(
        self,
        bucket_name: str,
        prefix: str = "model-artifacts",
        client: Any = None,
    ) -> None:
        if not bucket_name.strip():
            raise RuntimeError("MODEL_ARTIFACT_BUCKET is required")
        self.bucket_name = bucket_name.strip()
        self.prefix = prefix.strip("/")
        if client is None:
            try:
                from google.cloud import storage
            except ImportError as error:
                raise RuntimeError(
                    "google-cloud-storage is required for the GCS artifact store"
                ) from error
            client = storage.Client()
        self.client = client
        self.bucket = client.bucket(self.bucket_name)

    def put(self, request: ArtifactWriteRequest) -> ArtifactDescriptor:
        validate_request(request)
        digest = sha256_hex(request.payload)
        path = object_path(request, digest, self.prefix)
        blob = self.bucket.blob(path)
        created_at = datetime.now(timezone.utc).isoformat()
        metadata = {
            "component_run_id": request.component_run_id,
            "artifact_type": request.artifact_type,
            "sha256": digest,
            "size_bytes": str(len(request.payload)),
            "media_type": request.media_type,
            "schema_version": request.schema_version,
            "created_at": created_at,
            **{
                str(key): str(value)
                for key, value in (request.metadata or {}).items()
            },
        }
        blob.metadata = metadata
        try:
            blob.upload_from_string(
                request.payload,
                content_type=request.media_type,
                if_generation_match=0,
            )
        except Exception as error:
            if not self._already_exists(error):
                raise
            blob.reload()
            remote_hash = (blob.metadata or {}).get("sha256")
            remote_size = int(
                (blob.metadata or {}).get("size_bytes")
                or getattr(blob, "size", 0)
                or 0
            )
            if remote_hash != digest or remote_size != len(request.payload):
                raise RuntimeError(
                    "Immutable GCS artifact path contains other data"
                ) from error
            created_at = str(
                (blob.metadata or {}).get("created_at") or created_at
            )

        return ArtifactDescriptor(
            component_run_id=request.component_run_id,
            artifact_type=request.artifact_type,
            uri=f"gs://{self.bucket_name}/{path}",
            sha256=digest,
            size_bytes=len(request.payload),
            media_type=request.media_type,
            schema_version=request.schema_version,
            created_at=created_at,
            object_path=path,
            metadata=dict(request.metadata or {}),
        )

    @staticmethod
    def _already_exists(error: Exception) -> bool:
        return (
            type(error).__name__ in {"PreconditionFailed", "Conflict"}
            or getattr(error, "code", None) in {409, 412}
        )
