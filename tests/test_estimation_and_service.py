import asyncio
import os
import unittest

import numpy as np
import pandas as pd

from app.services.study_service import StudyService
from simulation_core.calibration import load_calibration_profile
from simulation_core.estimation import ConditionalLogitEstimator


class ConditionalLogitEstimatorTests(unittest.TestCase):
    def test_estimator_recovers_price_and_quality_direction(self):
        rng = np.random.default_rng(17)
        rows = []
        true_beta = np.array([-1.4, 1.1])
        for choice_set_id in range(800):
            focal = np.array(
                [
                    rng.uniform(0.6, 1.4),
                    rng.uniform(0.2, 1.0),
                ]
            )
            utilities = np.array([0.0, float(focal @ true_beta)])
            probabilities = np.exp(utilities - utilities.max())
            probabilities = probabilities / probabilities.sum()
            chosen_alternative = int(rng.choice([0, 1], p=probabilities))
            rows.append(
                {
                    "choice_set_id": choice_set_id,
                    "alternative": "outside",
                    "price_log_ratio": 0.0,
                    "quality_fit": 0.0,
                    "chosen": int(chosen_alternative == 0),
                }
            )
            rows.append(
                {
                    "choice_set_id": choice_set_id,
                    "alternative": "focal",
                    "price_log_ratio": focal[0],
                    "quality_fit": focal[1],
                    "chosen": int(chosen_alternative == 1),
                }
            )

        fit = ConditionalLogitEstimator(
            l2_penalty=1e-3,
            max_iterations=80,
        ).fit(
            pd.DataFrame(rows),
            ["price_log_ratio", "quality_fit"],
        )
        self.assertTrue(fit.converged)
        self.assertLess(fit.coefficients["price_log_ratio"], 0)
        self.assertGreater(fit.coefficients["quality_fit"], 0)
        override = fit.calibration_override("PRODUCT_VALIDATION")
        self.assertEqual(
            override["status"],
            "observed_choice_fit_unvalidated",
        )
        calibrated = load_calibration_profile(overrides=override)
        self.assertEqual(
            calibrated["status"],
            "observed_choice_fit_unvalidated",
        )
        self.assertAlmostEqual(
            calibrated["study_models"]["PRODUCT_VALIDATION"]["coefficients"][
                "price_log_ratio"
            ]["mean"],
            fit.coefficients["price_log_ratio"],
        )


class StudyServiceTests(unittest.TestCase):
    def test_service_runs_without_mock_personas(self):
        previous_key = os.environ.get("GEMINI_API_KEY")
        os.environ["GEMINI_API_KEY"] = ""
        try:
            service = StudyService()
            study = service.create_study(
                {
                    "name": "Algorithm integration",
                    "study_type": "PRICING_STUDY",
                    "plan_code": "PROFESSIONAL",
                    "price": 499,
                    "competitor_data": [
                        {
                            "name": "Competitor",
                            "price": 459,
                            "awareness": 0.55,
                            "quality_score": 0.6,
                        }
                    ],
                }
            )
            service.confirm_study(study["id"], {})
            report = asyncio.run(
                service.execute_run(
                    study["id"],
                    pop_size=200,
                    mc_rounds=20,
                    seed=13,
                )
            )
        finally:
            if previous_key is None:
                os.environ.pop("GEMINI_API_KEY", None)
            else:
                os.environ["GEMINI_API_KEY"] = previous_key

        self.assertTrue(report["report_id"].startswith("rpt_"))
        self.assertEqual(report["consumer_voices"], [])
        self.assertEqual(
            report["model_lineage"]["agent_signal"]["effective_weight"],
            0.0,
        )
        self.assertEqual(
            report["calibration_status"],
            "official_macro_calibrated_choice_prior",
        )
        self.assertTrue(
            any(
                source.get("observed")
                for source in report["model_lineage"]["calibration"]["sources"]
            )
        )
        self.assertIn("model_lineage", report)
        self.assertGreater(len(report["price_elasticity"]), 3)


if __name__ == "__main__":
    unittest.main()
