"""Versioned discrete-choice backend contracts."""

from simulation_core.choice_backends.base import (
    ChoiceFitRequest,
    ChoiceFitResult,
    ChoicePredictionResult,
    ChoiceModelBackend,
)
from simulation_core.choice_backends.choice_learn import (
    ChoiceBackendUnavailable,
    ChoiceLearnModelBackend,
)
from simulation_core.choice_backends.native import (
    NativeChoiceModelBackend,
    get_choice_model_backend,
)

__all__ = [
    "ChoiceFitRequest",
    "ChoiceFitResult",
    "ChoicePredictionResult",
    "ChoiceModelBackend",
    "ChoiceBackendUnavailable",
    "ChoiceLearnModelBackend",
    "NativeChoiceModelBackend",
    "get_choice_model_backend",
]
