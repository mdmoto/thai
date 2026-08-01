"""Population-control conversion and checked-in Phase 2 validation tests."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from data_pipeline.population_synthesis import (
    build_population_synthesis_inputs,
    control_comparison,
)
from simulation_core.calibration import load_calibration_profile


class PopulationInputBuilderTests(unittest.TestCase):
    def test_builder_is_deterministic_and_controls_represented_population(self):
        frame = pd.DataFrame(
            {
                "person_id": ["TH_1", "TH_2", "TH_3"],
                "region": ["North", "South", "North"],
                "gender": ["Female", "Male", "Female"],
                "income_tier": ["LOW", "MID_LOW", "HIGH"],
                "age_group": ["25-34", "35-44", "45-54"],
                "province": ["Chiang Mai", "Phuket", "Chiang Mai"],
                "household_size": [2, 3, 1],
            }
        )
        profile = load_calibration_profile()
        first = build_population_synthesis_inputs(
            frame,
            profile,
            represented_population=300_000,
            seed=91,
        )
        second = build_population_synthesis_inputs(
            frame,
            profile,
            represented_population=300_000,
            seed=91,
        )
        self.assertEqual(
            first.manifest["manifest_sha256"],
            second.manifest["manifest_sha256"],
        )
        self.assertEqual(first.controls["total_persons"], 300_000)
        self.assertEqual(first.manifest["seed_rows"], 3)
        self.assertEqual(
            first.manifest["seed_sample_status"],
            "synthetic_seed_not_observed_microdata",
        )

    def test_control_comparison_reports_exact_weighted_totals(self):
        incidence = pd.DataFrame(
            {
                "total_persons": [1.0, 1.0],
                "gender__Female": [1.0, 0.0],
                "gender__Male": [0.0, 1.0],
            }
        )
        controls = pd.Series(
            {
                "total_persons": 100.0,
                "gender__Female": 60.0,
                "gender__Male": 40.0,
            }
        )
        comparison = control_comparison(
            incidence,
            np.array([60.0, 40.0]),
            controls,
        )
        self.assertAlmostEqual(
            float(comparison["absolute_error"].max()),
            0.0,
        )


class PopulationBackendValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        cls.report = json.loads(
            (
                cls.root
                / "docs/validation/populationsim-phase2.json"
            ).read_text("utf-8")
        )

    def test_300k_candidate_passes_technical_not_production_gate(self):
        gate = self.report["gate"]
        self.assertTrue(gate["functional_validation_passed"])
        self.assertTrue(gate["marginal_calibration_materially_better"])
        self.assertFalse(gate["household_person_consistency_validated"])
        self.assertFalse(gate["observed_microdata_validated"])
        self.assertFalse(gate["production_ready"])
        self.assertEqual(
            gate["production_recommendation"],
            "retain_native_default_until_authorized_microdata_validation",
        )

    def test_each_run_has_300k_rows_positive_weights_and_explicit_failure(self):
        for comparison in self.report["comparisons"]:
            candidate = comparison["population_sim"]
            diagnostics = candidate["diagnostics"]
            self.assertEqual(candidate["population_rows"], 300_000)
            self.assertTrue(diagnostics["converged"])
            self.assertGreater(diagnostics["minimum_weight"], 0)
            self.assertEqual(diagnostics["zero_weight_rows"], 0)
            self.assertGreaterEqual(
                diagnostics["effective_sample_share"],
                0.99,
            )
            self.assertEqual(
                diagnostics["persons_without_household"],
                300_000,
            )
            self.assertEqual(
                diagnostics["household_person_consistency_status"],
                "not_available_synthetic_decision_unit_seed",
            )
            self.assertEqual(
                {item["artifact_type"] for item in candidate["artifacts"]},
                {
                    "population",
                    "persons",
                    "households",
                    "control_comparison",
                    "calibration_diagnostics",
                    "population_run_manifest",
                },
            )

    def test_checked_in_artifacts_match_content_hashes(self):
        artifact_root = (
            self.root / "docs/validation/population-artifacts"
        )
        for comparison in self.report["comparisons"]:
            for descriptor in comparison["population_sim"]["artifacts"]:
                self.assertEqual(
                    descriptor["uri_type"],
                    "relative_to_artifact_directory",
                )
                path = artifact_root / descriptor["object_path"]
                digest = hashlib.sha256()
                size = 0
                with path.open("rb") as stream:
                    while chunk := stream.read(1024 * 1024):
                        digest.update(chunk)
                        size += len(chunk)
                self.assertEqual(digest.hexdigest(), descriptor["sha256"])
                self.assertEqual(size, descriptor["size_bytes"])


if __name__ == "__main__":
    unittest.main()
