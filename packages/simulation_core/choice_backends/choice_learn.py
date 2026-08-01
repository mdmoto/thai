"""Optional Choice-Learn conditional-logit validation backend."""

from __future__ import annotations

import importlib.metadata
import os
from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np
import pandas as pd

from simulation_core.choice_backends.base import (
    ChoiceFitRequest,
    ChoiceFitResult,
    ChoicePredictionResult,
)
from simulation_core.choice_backends.common import (
    alternative_labels,
    canonical_choice_records,
    choice_fit_artifact,
    conditional_logit_diagnostics,
    outside_option_status,
    probability_diagnostics,
    validate_choice_frame,
)
from simulation_core.estimation import ConditionalLogitFit


CHOICE_LEARN_BACKEND_VERSION = "choice-learn-adapter-1"


class ChoiceBackendUnavailable(RuntimeError):
    """Raised before fitting when the isolated dependency is unavailable."""


@dataclass
class _ChoiceLearnContext:
    model: Any
    feature_columns: tuple[str, ...]
    n_items: int


def _load_choice_learn() -> tuple[Any, Any, Any]:
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    try:
        import tensorflow as tf
        from choice_learn.data import ChoiceDataset
        from choice_learn.models import ConditionalLogit
    except ImportError as error:
        raise ChoiceBackendUnavailable(
            "Choice-Learn backend is unavailable in this image"
        ) from error
    return tf, ChoiceDataset, ConditionalLogit


def _dataset_from_long_frame(
    frame: pd.DataFrame,
    feature_columns: Sequence[str],
    choice_set_column: str,
    chosen_column: str,
    choice_dataset_class: Any,
    *,
    n_items: int | None = None,
) -> tuple[Any, list[str], list[int]]:
    groups = list(frame.groupby(choice_set_column, sort=False))
    required_items = max(len(group) for _, group in groups)
    item_count = n_items or required_items
    if required_items > item_count:
        raise ValueError(
            "Prediction choice set contains more alternatives than the fit"
        )
    item_features = np.zeros(
        (len(groups), item_count, len(feature_columns)),
        dtype=np.float32,
    )
    available = np.zeros((len(groups), item_count), dtype=np.float32)
    choices = np.zeros(len(groups), dtype=np.int32)
    choice_set_ids: list[str] = []
    group_lengths: list[int] = []
    for group_index, (choice_set_id, group) in enumerate(groups):
        length = len(group)
        group_lengths.append(length)
        choice_set_ids.append(str(choice_set_id))
        item_features[group_index, :length, :] = group[
            list(feature_columns)
        ].to_numpy(dtype=np.float32)
        available[group_index, :length] = 1.0
        chosen_positions = np.flatnonzero(
            group[chosen_column].to_numpy(dtype=int)
        )
        choices[group_index] = int(chosen_positions[0])
    dataset = choice_dataset_class(
        choices=choices,
        items_features_by_choice=item_features,
        available_items_by_choice=available,
        items_features_by_choice_names=list(feature_columns),
    )
    return dataset, choice_set_ids, group_lengths


class ChoiceLearnModelBackend:
    backend_id = "choice_learn"
    backend_version = CHOICE_LEARN_BACKEND_VERSION

    def __init__(
        self,
        l2_penalty: float = 0.05,
        max_iterations: int = 150,
        tolerance: float = 1e-6,
    ) -> None:
        self.l2_penalty = float(l2_penalty)
        self.max_iterations = int(max_iterations)
        self.tolerance = float(tolerance)

    def fit(self, request: ChoiceFitRequest) -> ChoiceFitResult:
        validate_choice_frame(
            request.frame,
            request.feature_columns,
            request.choice_set_column,
            request.chosen_column,
        )
        tf, choice_dataset_class, conditional_logit_class = (
            _load_choice_learn()
        )
        tf.keras.utils.set_random_seed(request.seed)
        try:
            tf.config.experimental.enable_op_determinism()
        except Exception:
            pass

        dataset, _, group_lengths = _dataset_from_long_frame(
            request.frame,
            request.feature_columns,
            request.choice_set_column,
            request.chosen_column,
            choice_dataset_class,
        )
        choice_set_count = len(group_lengths)
        regularization = "l2" if self.l2_penalty > 0 else None
        model = conditional_logit_class(
            coefficients={
                feature: "constant"
                for feature in request.feature_columns
            },
            add_exit_choice=False,
            optimizer="lbfgs",
            epochs=self.max_iterations,
            lbfgs_tolerance=self.tolerance,
            regularization=regularization,
            regularization_strength=(
                self.l2_penalty / (2.0 * choice_set_count)
                if regularization
                else 0.0
            ),
        )
        model.instantiate(dataset)
        initial = request.initial_coefficients or {}
        model.set_weights(
            [
                np.array(
                    [[float(initial.get(feature, 0.0))]],
                    dtype=np.float32,
                )
                for feature in request.feature_columns
            ]
        )
        history = model.fit(dataset, verbose=0)
        coefficients = {
            feature: round(float(weight.numpy()[0][0]), 8)
            for feature, weight in zip(
                request.feature_columns,
                model.trainable_weights,
            )
        }
        (
            log_likelihood,
            gradient_max_abs,
            covariance,
            standard_errors,
        ) = conditional_logit_diagnostics(
            request.frame,
            request.feature_columns,
            coefficients,
            self.l2_penalty,
            request.choice_set_column,
            request.chosen_column,
        )
        predictions = np.asarray(
            model.predict_probas(dataset, batch_size=-1),
            dtype=float,
        )
        trimmed_probabilities = []
        for index, length in enumerate(group_lengths):
            values = predictions[index, :length]
            trimmed_probabilities.append((values / values.sum()).tolist())
        gradient_mean_abs = gradient_max_abs / choice_set_count
        finite = bool(
            np.isfinite(predictions).all()
            and all(np.isfinite(value) for value in coefficients.values())
            and np.isfinite(log_likelihood)
        )
        converged = bool(
            finite
            and gradient_mean_abs <= max(self.tolerance * 10.0, 1e-5)
        )
        iterations = len(history.get("train_loss", []))
        fit = ConditionalLogitFit(
            coefficients=coefficients,
            standard_errors=standard_errors,
            covariance=covariance,
            log_likelihood=round(log_likelihood, 8),
            converged=converged,
            iterations=iterations,
            choice_sets=len(group_lengths),
            observations=len(request.frame),
            l2_penalty=self.l2_penalty,
            source_status="estimated_from_observed_choices_choice_learn",
            estimation_method="choice_learn_conditional_logit_lbfgs",
        )
        dependency_version = importlib.metadata.version("choice-learn")
        tensorflow_version = importlib.metadata.version("tensorflow")
        diagnostics = {
            "seed": request.seed,
            "choice_sets": fit.choice_sets,
            "observations": fit.observations,
            "converged": fit.converged,
            "gradient_max_abs": gradient_max_abs,
            "gradient_mean_abs_per_choice_set": gradient_mean_abs,
            "choice_learn_version": dependency_version,
            "tensorflow_version": tensorflow_version,
            "optimizer": "lbfgs",
            "maximum_iterations": self.max_iterations,
            "iterations": iterations,
            "outside_option_status": outside_option_status(
                request.frame,
                request.choice_set_column,
                request.outside_option_column,
            ),
            **probability_diagnostics(trimmed_probabilities),
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
            runtime_context=_ChoiceLearnContext(
                model=model,
                feature_columns=tuple(request.feature_columns),
                n_items=predictions.shape[1],
            ),
        )

    def predict(
        self,
        fit_result: ChoiceFitResult,
        frame: pd.DataFrame,
        feature_columns: Sequence[str],
        *,
        choice_set_column: str = "choice_set_id",
        alternative_column: str = "alternative",
    ) -> ChoicePredictionResult:
        context = fit_result.runtime_context
        if not isinstance(context, _ChoiceLearnContext):
            raise RuntimeError(
                "Choice-Learn prediction requires its frozen fit context"
            )
        if tuple(feature_columns) != context.feature_columns:
            raise ValueError("Prediction feature mapping differs from fit")
        _, choice_dataset_class, _ = _load_choice_learn()
        chosen_column = "chosen"
        prediction_frame = frame.copy()
        if chosen_column not in prediction_frame:
            prediction_frame[chosen_column] = 0
            for _, group in prediction_frame.groupby(
                choice_set_column,
                sort=False,
            ):
                prediction_frame.loc[group.index[0], chosen_column] = 1
        validate_choice_frame(
            prediction_frame,
            feature_columns,
            choice_set_column,
            chosen_column,
        )
        dataset, choice_set_ids, group_lengths = _dataset_from_long_frame(
            prediction_frame,
            feature_columns,
            choice_set_column,
            chosen_column,
            choice_dataset_class,
            n_items=context.n_items,
        )
        raw = np.asarray(
            context.model.predict_probas(dataset, batch_size=-1),
            dtype=float,
        )
        probabilities = []
        for index, length in enumerate(group_lengths):
            values = raw[index, :length]
            probabilities.append((values / values.sum()).tolist())
        return ChoicePredictionResult(
            probabilities=probabilities,
            choice_set_ids=choice_set_ids,
            alternative_labels=alternative_labels(
                prediction_frame,
                choice_set_column,
                alternative_column,
            ),
            backend_id=self.backend_id,
            backend_version=self.backend_version,
            diagnostics=probability_diagnostics(probabilities),
        )
