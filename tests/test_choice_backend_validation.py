import hashlib
import json
import unittest
from pathlib import Path


class ChoiceBackendValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        cls.report = json.loads(
            (
                cls.root
                / "docs/validation/choice-learn-phase1.json"
            ).read_text("utf-8")
        )

    def test_choice_learn_passes_functional_not_promotion_gate(self) -> None:
        gate = self.report["gate"]
        self.assertTrue(gate["functional_validation_passed"])
        self.assertFalse(gate["choice_learn_materially_better"])
        self.assertEqual(
            gate["production_recommendation"],
            "retain_native_default",
        )

    def test_direction_probability_and_outside_option_gates_hold(self) -> None:
        for comparison in self.report["comparisons"]:
            candidate = comparison["choice_learn"]
            self.assertTrue(candidate["converged"])
            self.assertLess(
                candidate["coefficients"]["price_log_ratio"],
                0,
            )
            self.assertGreater(
                candidate["coefficients"]["quality_fit"],
                0,
            )
            self.assertLess(
                candidate["holdout"]["probability_sum_max_error"],
                1e-12,
            )
            self.assertEqual(
                candidate["fit_diagnostics"]["outside_option_status"],
                "present_in_every_choice_set",
            )

    def test_checked_in_fit_artifacts_match_their_hashes(self) -> None:
        artifact_root = (
            self.root / "docs/validation/choice-artifacts"
        )
        for comparison in self.report["comparisons"]:
            for backend in ("native", "choice_learn"):
                descriptor = comparison[backend]["artifact"]
                self.assertEqual(
                    descriptor["uri_type"],
                    "relative_to_artifact_directory",
                )
                path = artifact_root / descriptor["object_path"]
                payload = path.read_bytes()
                self.assertEqual(
                    hashlib.sha256(payload).hexdigest(),
                    descriptor["sha256"],
                )
                self.assertEqual(
                    len(payload),
                    descriptor["size_bytes"],
                )


if __name__ == "__main__":
    unittest.main()
