"""Adapter for the existing conditional multinomial logit estimator."""

from __future__ import annotations

import os

from simulation_core.choice_backends.base import (
    ChoiceFitRequest,
    ChoiceFitResult,
    ChoicePredictionResult,
    ChoiceModelBackend,
)
from simulation_core.choice_backends.common import (
    alternative_labels,
    canonical_choice_records,
    choice_fit_artifact,
    grouped_probabilities,
    outside_option_status,
    probability_diagnostics,
)
from simulation_core.estimation import ConditionalLogitEstimator


NATIVE_CHOICE_BACKEND_VERSION = "native-conditional-logit-1"


class NativeChoiceModelBackend:
    backend_id = "native"
    backend_version = NATIVE_CHOICE_BACKEND_VERSION

    def __init__(
        self,
        l2_penalty: float = 0.05,
        max_iterations: int = 150,
        tolerance: float = 1e-7,
    ):
        self.estimator = ConditionalLogitEstimator(
            l2_penalty=l2_penalty,
            max_iterations=max_iterations,
            tolerance=tolerance,
        )

    def fit(self, request: ChoiceFitRequest) -> ChoiceFitResult:
        fit = self.estimator.fit(
            request.frame,
            request.feature_columns,
            choice_set_column=request.choice_set_column,
            chosen_column=request.chosen_column,
            initial_coefficients=dict(
                request.initial_coefficients or {}
            ),
        )
        choice_set_ids, probabilities = grouped_probabilities(
            request.frame,
            request.feature_columns,
            fit.coefficients,
            request.choice_set_column,
        )
        diagnostics = {
            "seed": request.seed,
            "choice_sets": fit.choice_sets,
            "observations": fit.observations,
            "converged": fit.converged,
            "outside_option_status": outside_option_status(
                request.frame,
                request.choice_set_column,
                request.outside_option_column,
            ),
            **probability_diagnostics(probabilities),
        }
        artifact_payload, artifact_metadata = choice_fit_artifact(
            fit=fit,
            backend_id=self.backend_id,
            backend_version=self.backend_version,
            request_payload={
                "records": canonical_choice_records(
                    request.frame,
                    [
                        request.choice_set_column,
                        request.chosen_column,
                        *request.feature_columns,
                    ],
                )
            },
            feature_columns=request.feature_columns,
            seed=request.seed,
            diagnostics=diagnostics,
            validation_status=request.validation_policy,
        )
        return ChoiceFitResult(
            fit=fit,
            backend_id=self.backend_id,
            backend_version=self.backend_version,
            model_family=request.model_family,
            validation_status=request.validation_policy,
            diagnostics=diagnostics,
            artifact_payload=artifact_payload,
            artifact_metadata=artifact_metadata,
        )

    def predict(
        self,
        fit_result: ChoiceFitResult,
        frame,
        feature_columns,
        *,
        choice_set_column: str = "choice_set_id",
        alternative_column: str = "alternative",
    ) -> ChoicePredictionResult:
        choice_set_ids, probabilities = grouped_probabilities(
            frame,
            feature_columns,
            fit_result.fit.coefficients,
            choice_set_column,
        )
        return ChoicePredictionResult(
            probabilities=probabilities,
            choice_set_ids=choice_set_ids,
            alternative_labels=alternative_labels(
                frame,
                choice_set_column,
                alternative_column,
            ),
            backend_id=self.backend_id,
            backend_version=self.backend_version,
            diagnostics=probability_diagnostics(probabilities),
        )


def get_choice_model_backend(
    backend_id: str | None = None,
) -> ChoiceModelBackend:
    selected = (
        backend_id
        or os.environ.get("CHOICE_MODEL_BACKEND", "native")
    ).strip().lower()
    if selected in {"native", "native_conditional_logit"}:
        return NativeChoiceModelBackend()
    if selected in {"choice_learn", "choice-learn"}:
        from simulation_core.choice_backends.choice_learn import (
            ChoiceLearnModelBackend,
        )

        return ChoiceLearnModelBackend()
    raise ValueError(f"Unsupported choice model backend: {selected}")
