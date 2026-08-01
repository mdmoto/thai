"""Canonical frozen input manifests used across safe job retries."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Mapping


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


@dataclass(frozen=True)
class FrozenInputManifest:
    manifest_id: str
    component: str
    backend: str
    backend_version: str
    config_version: str
    seed: int
    payload_sha256: str
    payload: Mapping[str, Any]
    created_at: str | None

    @classmethod
    def freeze(
        cls,
        *,
        component: str,
        backend: str,
        backend_version: str,
        config_version: str,
        seed: int,
        payload: Mapping[str, Any],
        created_at: str | None = None,
    ) -> "FrozenInputManifest":
        canonical = _canonical_json(payload)
        payload_sha256 = hashlib.sha256(canonical).hexdigest()
        identity = _canonical_json(
            {
                "component": component,
                "backend": backend,
                "backend_version": backend_version,
                "config_version": config_version,
                "seed": seed,
                "payload_sha256": payload_sha256,
            }
        )
        manifest_id = f"manifest_{hashlib.sha256(identity).hexdigest()[:24]}"
        return cls(
            manifest_id=manifest_id,
            component=component,
            backend=backend,
            backend_version=backend_version,
            config_version=config_version,
            seed=seed,
            payload_sha256=payload_sha256,
            payload=dict(payload),
            created_at=created_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_bytes(self) -> bytes:
        return _canonical_json(self.to_dict())
