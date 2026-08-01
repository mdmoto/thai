"""Contracts shared by native and optional population-synthesis backends."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

import pandas as pd


@dataclass(frozen=True)
class PopulationSynthesisRequest:
    population_size: int
    study_type: str
    category: str | None
    seed: int
    calibration_profile: Mapping[str, Any]
    control_totals_version: str | None = None
    seed_sample_version: str | None = None
    geography_level: str = "province"
    output_schema_version: str = "population-v1"


@dataclass
class PopulationSynthesisResult:
    population: pd.DataFrame
    backend_id: str
    backend_version: str
    status: str
    diagnostics: dict[str, Any]
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    runtime_context: Any = field(default=None, repr=False)

    def lineage(self) -> dict[str, Any]:
        return {
            "component": "population_synthesis",
            "backend": self.backend_id,
            "backend_version": self.backend_version,
            "status": self.status,
            "diagnostics": self.diagnostics,
            "artifacts": self.artifacts,
            "limitations": self.limitations,
        }


class PopulationSynthesisBackend(Protocol):
    backend_id: str
    backend_version: str

    def generate(
        self,
        request: PopulationSynthesisRequest,
    ) -> PopulationSynthesisResult:
        ...

    def stratified_sample(
        self,
        result: PopulationSynthesisResult,
        sample_size: int,
        seed: int,
    ) -> pd.DataFrame:
        ...
