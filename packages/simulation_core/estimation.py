"""Observed-choice calibration utilities.

This module fits a conditional multinomial logit model from long-format choice
data.  It is intentionally independent of the LLM gateway: only observed
choices, surveys, transactions, or A/B-test assignments should be passed here.
"""

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd


@dataclass
class ConditionalLogitFit:
    coefficients: Dict[str, float]
    standard_errors: Dict[str, float]
    covariance: List[List[float]]
    log_likelihood: float
    converged: bool
    iterations: int
    choice_sets: int
    observations: int
    l2_penalty: float
    source_status: str = "estimated_from_observed_choices"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def calibration_override(self, study_type: str) -> Dict[str, Any]:
        return {
            "status": "observed_choice_fit_unvalidated",
            "study_models": {
                study_type.upper(): {
                    "coefficients": {
                        name: {
                            "mean": value,
                            "sd": max(self.standard_errors.get(name, 0.0), 1e-6),
                        }
                        for name, value in self.coefficients.items()
                    }
                }
            },
            "fit_diagnostics": {
                "method": "conditional_multinomial_logit_newton",
                "log_likelihood": self.log_likelihood,
                "converged": self.converged,
                "iterations": self.iterations,
                "choice_sets": self.choice_sets,
                "observations": self.observations,
                "l2_penalty": self.l2_penalty,
            },
        }


class ConditionalLogitEstimator:
    """Newton estimator for grouped multinomial choices."""

    def __init__(
        self,
        l2_penalty: float = 1e-4,
        max_iterations: int = 100,
        tolerance: float = 1e-7,
    ):
        if l2_penalty < 0:
            raise ValueError("l2_penalty must be non-negative")
        self.l2_penalty = float(l2_penalty)
        self.max_iterations = int(max_iterations)
        self.tolerance = float(tolerance)

    def _validate(
        self,
        frame: pd.DataFrame,
        feature_columns: Sequence[str],
        choice_set_column: str,
        chosen_column: str,
    ) -> None:
        required = set(feature_columns) | {choice_set_column, chosen_column}
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"Choice data is missing columns: {sorted(missing)}")
        if frame.empty:
            raise ValueError("Choice data must not be empty")
        if frame[list(feature_columns)].isnull().any().any():
            raise ValueError("Choice features contain missing values")
        chosen = frame[chosen_column].astype(int)
        if not chosen.isin([0, 1]).all():
            raise ValueError("chosen must contain only 0 and 1")
        chosen_per_set = frame.assign(_chosen=chosen).groupby(
            choice_set_column
        )["_chosen"].sum()
        if not (chosen_per_set == 1).all():
            raise ValueError("Every choice set must contain exactly one chosen row")
        alternatives_per_set = frame.groupby(choice_set_column).size()
        if (alternatives_per_set < 2).any():
            raise ValueError("Every choice set must contain at least two alternatives")

    def _probabilities(
        self,
        utilities: np.ndarray,
        group_indices: Sequence[np.ndarray],
    ) -> np.ndarray:
        probabilities = np.zeros_like(utilities, dtype=float)
        for indices in group_indices:
            group_utility = utilities[indices]
            shifted = group_utility - np.max(group_utility)
            numerator = np.exp(np.clip(shifted, -40.0, 40.0))
            probabilities[indices] = numerator / numerator.sum()
        return probabilities

    def _objective(
        self,
        matrix: np.ndarray,
        chosen: np.ndarray,
        beta: np.ndarray,
        group_indices: Sequence[np.ndarray],
    ) -> float:
        probabilities = self._probabilities(matrix @ beta, group_indices)
        likelihood = float(
            np.sum(chosen * np.log(np.clip(probabilities, 1e-15, 1.0)))
        )
        penalty = 0.5 * self.l2_penalty * float(beta @ beta)
        return likelihood - penalty

    def fit(
        self,
        frame: pd.DataFrame,
        feature_columns: Sequence[str],
        choice_set_column: str = "choice_set_id",
        chosen_column: str = "chosen",
        initial_coefficients: Optional[Dict[str, float]] = None,
    ) -> ConditionalLogitFit:
        self._validate(
            frame,
            feature_columns,
            choice_set_column,
            chosen_column,
        )
        matrix = frame[list(feature_columns)].to_numpy(dtype=float)
        chosen = frame[chosen_column].to_numpy(dtype=float)
        _, group_codes = np.unique(
            frame[choice_set_column].to_numpy(),
            return_inverse=True,
        )
        group_indices = [
            np.where(group_codes == group_code)[0]
            for group_code in range(int(group_codes.max()) + 1)
        ]

        beta = np.array(
            [
                float((initial_coefficients or {}).get(name, 0.0))
                for name in feature_columns
            ],
            dtype=float,
        )
        identity = np.eye(len(feature_columns), dtype=float)
        converged = False
        last_hessian = -identity
        iteration = 0

        for iteration in range(1, self.max_iterations + 1):
            utilities = matrix @ beta
            probabilities = self._probabilities(utilities, group_indices)
            gradient = matrix.T @ (chosen - probabilities)
            gradient -= self.l2_penalty * beta

            negative_hessian = self.l2_penalty * identity
            for indices in group_indices:
                group_matrix = matrix[indices]
                group_prob = probabilities[indices]
                covariance = np.diag(group_prob) - np.outer(
                    group_prob,
                    group_prob,
                )
                negative_hessian += (
                    group_matrix.T @ covariance @ group_matrix
                )
            last_hessian = -negative_hessian

            try:
                step = np.linalg.solve(negative_hessian, gradient)
            except np.linalg.LinAlgError:
                step = np.linalg.pinv(negative_hessian) @ gradient

            current_objective = self._objective(
                matrix,
                chosen,
                beta,
                group_indices,
            )
            damping = 1.0
            candidate = beta + step
            while damping >= 1e-4:
                candidate = beta + damping * step
                candidate_objective = self._objective(
                    matrix,
                    chosen,
                    candidate,
                    group_indices,
                )
                if candidate_objective >= current_objective:
                    break
                damping *= 0.5

            update = candidate - beta
            beta = candidate
            if float(np.max(np.abs(update))) < self.tolerance:
                converged = True
                break

        covariance_matrix = np.linalg.pinv(-last_hessian)
        standard_errors = np.sqrt(
            np.clip(np.diag(covariance_matrix), 0.0, None)
        )
        return ConditionalLogitFit(
            coefficients={
                name: round(float(value), 8)
                for name, value in zip(feature_columns, beta)
            },
            standard_errors={
                name: round(float(value), 8)
                for name, value in zip(feature_columns, standard_errors)
            },
            covariance=covariance_matrix.tolist(),
            log_likelihood=round(
                self._objective(
                    matrix,
                    chosen,
                    beta,
                    group_indices,
                ),
                8,
            ),
            converged=converged,
            iterations=iteration,
            choice_sets=len(group_indices),
            observations=len(frame),
            l2_penalty=self.l2_penalty,
        )
