"""Observed-human versus AI-persona categorical response validation."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


HUMAN_COMPARISON_SCHEMA_VERSION = "human-ai-response-comparison-v1"
REQUIRED_HUMAN_DATASET_STATUS = "observed_human_survey"


def _weighted_distribution(
    rows: Sequence[Mapping[str, Any]],
    question_id: str,
    allowed_answers: Sequence[str],
    weight_field: str,
) -> dict[str, float]:
    totals = {str(answer): 0.0 for answer in allowed_answers}
    denominator = 0.0
    for row in rows:
        if str(row.get("question_id")) != question_id:
            continue
        answer = str(row.get("answer"))
        if answer not in totals:
            raise ValueError(
                f"Unknown answer {answer!r} for question {question_id!r}"
            )
        weight = float(row.get(weight_field, 1.0))
        if weight < 0:
            raise ValueError("Response weights must be non-negative")
        totals[answer] += weight
        denominator += weight
    if denominator <= 0:
        raise ValueError(f"No responses for question {question_id!r}")
    return {
        answer: value / denominator
        for answer, value in totals.items()
    }


def validate_human_ai_responses(
    payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Compare categorical distributions only for observed human surveys.

    This function deliberately refuses synthetic, inferred, or LLM-generated
    "human" datasets.
    """
    if not payload:
        return {
            "schema_version": HUMAN_COMPARISON_SCHEMA_VERSION,
            "status": "not_run_no_human_dataset",
            "questions": [],
            "failed_questions": [],
        }
    dataset_status = str(payload.get("human_dataset_status") or "")
    if dataset_status != REQUIRED_HUMAN_DATASET_STATUS:
        raise ValueError(
            "Empirical validation requires human_dataset_status="
            f"{REQUIRED_HUMAN_DATASET_STATUS!r}"
        )
    questions = list(payload.get("questions") or [])
    human_rows = list(payload.get("human_responses") or [])
    ai_rows = list(payload.get("ai_responses") or [])
    if not questions or not human_rows or not ai_rows:
        raise ValueError(
            "questions, human_responses and ai_responses are required"
        )

    seen_ids: set[str] = set()
    comparisons = []
    failed_questions = []
    for question in questions:
        question_id = str(question.get("question_id") or "")
        if not question_id or question_id in seen_ids:
            raise ValueError("question_id must be unique and non-empty")
        seen_ids.add(question_id)
        allowed_answers = [
            str(value) for value in question.get("allowed_answers") or []
        ]
        if len(allowed_answers) < 2:
            raise ValueError(
                f"Question {question_id!r} requires at least two answers"
            )
        threshold = float(
            question.get("maximum_total_variation_distance", 0.10)
        )
        human_distribution = _weighted_distribution(
            human_rows,
            question_id,
            allowed_answers,
            "survey_weight",
        )
        ai_distribution = _weighted_distribution(
            ai_rows,
            question_id,
            allowed_answers,
            "expansion_weight",
        )
        differences = {
            answer: ai_distribution[answer] - human_distribution[answer]
            for answer in allowed_answers
        }
        total_variation_distance = 0.5 * sum(
            abs(value) for value in differences.values()
        )
        passed = total_variation_distance <= threshold
        if not passed:
            failed_questions.append(question_id)
        comparisons.append(
            {
                "question_id": question_id,
                "human_distribution": human_distribution,
                "ai_persona_distribution": ai_distribution,
                "difference_ai_minus_human": differences,
                "total_variation_distance": total_variation_distance,
                "maximum_total_variation_distance": threshold,
                "passed": passed,
            }
        )
    return {
        "schema_version": HUMAN_COMPARISON_SCHEMA_VERSION,
        "status": (
            "passed"
            if not failed_questions
            else "failed_distribution_tolerance"
        ),
        "human_dataset_id": str(payload.get("human_dataset_id") or ""),
        "human_dataset_version": str(
            payload.get("human_dataset_version") or ""
        ),
        "model_version": str(payload.get("model_version") or ""),
        "prompt_version": str(payload.get("prompt_version") or ""),
        "questions": comparisons,
        "failed_questions": failed_questions,
    }


def human_comparison_input_schema() -> dict[str, Any]:
    """Machine-readable handoff contract for future observed surveys."""
    return {
        "schema_version": HUMAN_COMPARISON_SCHEMA_VERSION,
        "required": [
            "human_dataset_status",
            "human_dataset_id",
            "human_dataset_version",
            "model_version",
            "prompt_version",
            "questions",
            "human_responses",
            "ai_responses",
        ],
        "human_dataset_status": {
            "const": REQUIRED_HUMAN_DATASET_STATUS,
        },
        "questions[]": {
            "required": [
                "question_id",
                "allowed_answers",
                "maximum_total_variation_distance",
            ]
        },
        "human_responses[]": {
            "required": [
                "respondent_id",
                "question_id",
                "answer",
                "survey_weight",
            ]
        },
        "ai_responses[]": {
            "required": [
                "representative_id",
                "question_id",
                "answer",
                "expansion_weight",
            ]
        },
    }
