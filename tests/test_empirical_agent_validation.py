"""Tests for observed-human versus AI-persona distribution validation."""

from __future__ import annotations

import unittest

from agents.empirical_validation import (
    human_comparison_input_schema,
    validate_human_ai_responses,
)


class EmpiricalAgentValidationTests(unittest.TestCase):
    def test_no_human_dataset_does_not_invent_validation(self):
        result = validate_human_ai_responses(None)
        self.assertEqual(result["status"], "not_run_no_human_dataset")
        self.assertEqual(result["questions"], [])

    def test_non_observed_dataset_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "observed_human_survey"):
            validate_human_ai_responses(
                {"human_dataset_status": "llm_generated"}
            )

    def test_weighted_distribution_reports_pass_and_failure(self):
        payload = {
            "human_dataset_status": "observed_human_survey",
            "human_dataset_id": "survey_1",
            "human_dataset_version": "v1",
            "model_version": "tinytroupe-test",
            "prompt_version": "prompt-test",
            "questions": [
                {
                    "question_id": "buy",
                    "allowed_answers": ["yes", "no"],
                    "maximum_total_variation_distance": 0.15,
                },
                {
                    "question_id": "trust",
                    "allowed_answers": ["yes", "no"],
                    "maximum_total_variation_distance": 0.05,
                },
            ],
            "human_responses": [
                {
                    "respondent_id": "H1",
                    "question_id": "buy",
                    "answer": "yes",
                    "survey_weight": 6,
                },
                {
                    "respondent_id": "H2",
                    "question_id": "buy",
                    "answer": "no",
                    "survey_weight": 4,
                },
                {
                    "respondent_id": "H1",
                    "question_id": "trust",
                    "answer": "yes",
                    "survey_weight": 8,
                },
                {
                    "respondent_id": "H2",
                    "question_id": "trust",
                    "answer": "no",
                    "survey_weight": 2,
                },
            ],
            "ai_responses": [
                {
                    "representative_id": "A1",
                    "question_id": "buy",
                    "answer": "yes",
                    "expansion_weight": 7,
                },
                {
                    "representative_id": "A2",
                    "question_id": "buy",
                    "answer": "no",
                    "expansion_weight": 3,
                },
                {
                    "representative_id": "A1",
                    "question_id": "trust",
                    "answer": "yes",
                    "expansion_weight": 6,
                },
                {
                    "representative_id": "A2",
                    "question_id": "trust",
                    "answer": "no",
                    "expansion_weight": 4,
                },
            ],
        }
        result = validate_human_ai_responses(payload)
        self.assertEqual(result["status"], "failed_distribution_tolerance")
        self.assertEqual(result["failed_questions"], ["trust"])
        self.assertAlmostEqual(
            result["questions"][0]["total_variation_distance"],
            0.1,
        )
        self.assertAlmostEqual(
            result["questions"][1]["total_variation_distance"],
            0.2,
        )

    def test_schema_requires_observed_dataset_and_versions(self):
        schema = human_comparison_input_schema()
        self.assertEqual(
            schema["human_dataset_status"]["const"],
            "observed_human_survey",
        )
        self.assertIn("model_version", schema["required"])
        self.assertIn("prompt_version", schema["required"])


if __name__ == "__main__":
    unittest.main()
