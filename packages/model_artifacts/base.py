"""Contracts for immutable, content-addressed model artifacts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Protocol


@dataclass(frozen=True)
class ArtifactWriteRequest:
    component_run_id: str
    artifact_type: str
    payload: bytes
    media_type: str
    schema_version: str
    suffix: str = ""
    metadata: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class ArtifactDescriptor:
    component_run_id: str
    artifact_type: str
    uri: str
    sha256: str
    size_bytes: int
    media_type: str
    schema_version: str
    created_at: str
    object_path: str
    metadata: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ModelArtifactStore(Protocol):
    def put(self, request: ArtifactWriteRequest) -> ArtifactDescriptor:
        ...
