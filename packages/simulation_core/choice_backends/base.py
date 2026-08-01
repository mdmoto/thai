"""Contracts for fitting observed discrete choices."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence

import pandas as pd

from simulation_core.estimation import ConditionalLogitFit


@dataclass(frozen=True)
class ChoiceFitRequest:
    frame: pd.DataFrame
    feature_columns: Sequence[str]
    study_type: str
    seed: int
    initial_coefficients: Mapping[str, float] | None = None
    choice_set_column: str = "choice_set_id"
    chosen_column: str = "chosen"
    alternative_column: str = "alternative"
    outside_option_column: str = "is_outside_option"
    model_family: str = "conditional_logit"
    validation_policy: str = "unvalidated_fit_only"


@dataclass(frozen=True)
class ChoiceFitResult:
    fit: ConditionalLogitFit
    backend_id: str
    backend_version: str
    model_family: str
    validation_status: str
    diagnostics: Mapping[str, Any]
    artifact_payload: bytes | None = field(
        default=None,
        repr=False,
        compare=False,
    )
    artifact_metadata: Mapping[str, Any] = field(default_factory=dict)
    runtime_context: Any = field(
        default=None,
        repr=False,
        compare=False,
    )

    def lineage(self) -> dict[str, Any]:
        return {
            "component": "choice_model",
            "backend": self.backend_id,
            "backend_version": self.backend_version,
            "model_family": self.model_family,
            "validation_status": self.validation_status,
            "diagnostics": dict(self.diagnostics),
            "artifact_metadata": dict(self.artifact_metadata),
        }


@dataclass(frozen=True)
class ChoicePredictionResult:
    probabilities: Sequence[Sequence[float]]
    choice_set_ids: Sequence[str]
    alternative_labels: Sequence[Sequence[str]]
    backend_id: str
    backend_version: str
    diagnostics: Mapping[str, Any]


class ChoiceModelBackend(Protocol):
    backend_id: str
    backend_version: str

    def fit(self, request: ChoiceFitRequest) -> ChoiceFitResult:
        ...

    def predict(
        self,
        fit_result: ChoiceFitResult,
        frame: pd.DataFrame,
        feature_columns: Sequence[str],
        *,
        choice_set_column: str = "choice_set_id",
        alternative_column: str = "alternative",
    ) -> ChoicePredictionResult:
        ...
