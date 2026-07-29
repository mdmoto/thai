import asyncio
import os
import unittest
from unittest.mock import AsyncMock, patch

import numpy as np
import pandas as pd

from app.services.study_service import StudyService
from simulation_core.calibration import load_calibration_profile
from simulation_core.estimation import ConditionalLogitEstimator
from world_model.thailand_geo import point_in_province, point_in_thailand


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
    @staticmethod
    def _empty_research_bundle():
        return {
            "version": "test-research",
            "status": "succeeded",
            "source_count": 0,
            "evidence": [],
            "collectors": [],
            "warnings": [],
            "usage_policy": {
                "quantitative_effect": (
                    "verified_public_price_rating_fields_may_update_choice_"
                    "set_attributes_but_never_choice_coefficients"
                )
            },
        }

    def test_competitor_urls_are_research_sources_not_choice_names(self):
        service = StudyService()
        study = service.create_study(
            {
                "name": "Competitor source handling",
                "study_type": "PRODUCT_VALIDATION",
                "competitors": [
                    "Known Brand",
                    "https://example.com/competitor-product",
                ],
            }
        )
        self.assertEqual(
            [item["name"] for item in service._competitors(study)],
            ["Known Brand"],
        )

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
        self.assertEqual(report["sample_profile"]["display_sample_size"], 200)
        self.assertEqual(
            report["sample_profile"]["location_status"],
            "synthetic_province_polygon_sample",
        )
        self.assertTrue(report["sample_profile"]["points"])
        self.assertTrue(
            all(
                point_in_thailand(
                    point["longitude"],
                    point["latitude"],
                )
                and point_in_province(
                    point["longitude"],
                    point["latitude"],
                    point["province"],
                )
                for point in report["sample_profile"]["points"]
            )
        )
        self.assertTrue(report["social_dynamics"])
        self.assertEqual(
            report["social_evidence"]["policy"],
            "cloud_public_research_without_customer_authorization",
        )
        self.assertTrue(report["evidence_estimates"])
        self.assertTrue(
            all(
                item["result"] and item["limitation"]
                for item in report["evidence_estimates"]
            )
        )
        self.assertEqual(
            report["evidence_acquisition"]["execution_policy"],
            "independent_collectors_fail_open",
        )
        llm_collector = next(
            item
            for item in report["evidence_acquisition"]["collectors"]
            if item["collector"] == "Structured LLM research"
        )
        self.assertEqual(
            llm_collector["fallback_result"],
            "model_segment_summary",
        )

    def test_professional_run_applies_supplied_observed_choice_fit(self):
        rng = np.random.default_rng(29)
        rows = []
        true_beta = np.array([-1.2, 0.9])
        for choice_set_id in range(120):
            focal = np.array(
                [
                    rng.uniform(0.65, 1.35),
                    rng.uniform(0.15, 1.0),
                ]
            )
            utilities = np.array([0.0, float(focal @ true_beta)])
            probabilities = np.exp(utilities - utilities.max())
            probabilities = probabilities / probabilities.sum()
            chosen = int(rng.choice([0, 1], p=probabilities))
            rows.extend(
                [
                    {
                        "choice_set_id": f"set-{choice_set_id}",
                        "alternative": "outside",
                        "price_log_ratio": 0.0,
                        "quality_fit": 0.0,
                        "chosen": int(chosen == 0),
                    },
                    {
                        "choice_set_id": f"set-{choice_set_id}",
                        "alternative": "focal",
                        "price_log_ratio": float(focal[0]),
                        "quality_fit": float(focal[1]),
                        "chosen": int(chosen == 1),
                    },
                ]
            )

        service = StudyService()
        service.market_research.collect = AsyncMock(
            return_value=self._empty_research_bundle()
        )
        study = service.create_study(
            {
                "name": "Observed choice calibration",
                "study_type": "PRODUCT_VALIDATION",
                "plan_code": "PROFESSIONAL",
                "price": 799,
                "observed_choice_data": rows,
            }
        )
        service.confirm_study(study["id"], {})
        unavailable_agents = {
            "status": "unavailable",
            "source_type": "none",
            "prompt_version": "test",
            "model_id": "test",
            "plan_code": "PROFESSIONAL",
            "sample_size_requested": 96,
            "sample_size_completed": 0,
            "responses": [],
            "aggregate": {},
            "errors": ["disabled in test"],
            "quantitative_policy": "No LLM output used.",
        }
        with patch(
            "app.services.study_service.GeminiAgentGateway."
            "generate_research_signals",
            new=AsyncMock(return_value=unavailable_agents),
        ):
            report = asyncio.run(
                service.execute_run(
                    study["id"],
                    pop_size=600,
                    mc_rounds=20,
                    seed=31,
                )
            )

        self.assertEqual(
            report["calibration_status"],
            "observed_choice_fit_unvalidated",
        )
        estimation = report["model_lineage"]["choice_estimation"]
        self.assertEqual(estimation["status"], "applied_unvalidated")
        self.assertGreaterEqual(
            estimation["diagnostics"]["choice_sets"],
            120,
        )
        self.assertEqual(
            report["model_lineage"]["uncertainty"]["interval_type"],
            "fitted_model_predictive_p10_p90_unvalidated",
        )
        self.assertEqual(
            report["model_lineage"]["coefficient_priors"][
                "price_log_ratio"
            ]["source"],
            "observed_choice_fit_unvalidated",
        )
        choice_collector = next(
            item
            for item in report["evidence_acquisition"]["collectors"]
            if item["collector"] == "Customer observed choice calibration"
        )
        self.assertEqual(choice_collector["status"], "succeeded")
        self.assertEqual(choice_collector["result_count"], 120)

    def test_public_market_fields_enrich_choice_set_without_fitting_coefficients(
        self,
    ):
        service = StudyService()
        study = service.create_study(
            {
                "name": "Public competitor evidence",
                "study_type": "PRODUCT_VALIDATION",
                "plan_code": "PROFESSIONAL",
                "price": 1290,
                "competitor_data": [
                    {
                        "name": "Known Competitor",
                        "source_url": (
                            "https://www.lazada.co.th/products/known-item"
                        ),
                    }
                ],
            }
        )
        enriched = service._research_enriched_choice_inputs(
            study,
            {
                "evidence": [
                    {
                        "source_id": "src_marketplace_1",
                        "platform": "Lazada",
                        "title": "Known Competitor",
                        "url": (
                            "https://www.lazada.co.th/products/known-item"
                        ),
                        "market_signals": {
                            "prices": ["฿1,190"],
                            "ratings": ["4.8 / 5 rating"],
                            "review_mentions": ["350 reviews"],
                        },
                    }
                ]
            },
            competitor_limit=5,
        )
        competitor = enriched["competitors"][0]
        self.assertEqual(competitor["price"], 1190.0)
        self.assertAlmostEqual(competitor["review_score"], 0.96)
        self.assertGreater(competitor["social_proof_score"], 0.5)
        self.assertEqual(enriched["lineage"]["status"], "applied")
        self.assertEqual(enriched["lineage"]["coefficient_effect"], "none")

    def test_venue_uses_subtype_model_and_visit_language(self):
        previous_key = os.environ.get("GEMINI_API_KEY")
        os.environ["GEMINI_API_KEY"] = ""
        try:
            service = StudyService()
            study = service.create_study(
                {
                    "name": "Nimman cafe",
                    "study_type": "VENUE_STUDY",
                    "plan_code": "PREVIEW",
                    "product_name": "CMAI Cafe",
                    "venue_type": "CAFE",
                    "average_check": 220,
                    "capacity": 45,
                    "location": {"label": "Chiang Mai, Nimman"},
                }
            )
            service.confirm_study(study["id"], {})
            report = asyncio.run(
                service.execute_run(
                    study["id"],
                    pop_size=200,
                    mc_rounds=20,
                    seed=17,
                )
            )
        finally:
            if previous_key is None:
                os.environ.pop("GEMINI_API_KEY", None)
            else:
                os.environ["GEMINI_API_KEY"] = previous_key

        self.assertEqual(report["study_type"], "VENUE_STUDY")
        self.assertEqual(
            report["model_lineage"]["effective_model_type"],
            "CAFE",
        )
        self.assertEqual(
            report["executive_summary"]["key_metrics"][0]["label"],
            "总体到店概率",
        )
        visited = next(
            item for item in report["funnel"] if item["stage"] == "purchased"
        )
        self.assertEqual(visited["label"], "预计到店")
        self.assertEqual(report["geo_analysis"]["venue_type"], "CAFE")
        self.assertTrue(report["geo_analysis"]["heatmap"])
        self.assertEqual(
            report["geo_analysis"]["locations"][0]["observed_poi_status"],
            "osm_versioned_snapshot",
        )

    def test_ecommerce_template_has_distinct_checkout_analysis(self):
        service = StudyService()
        study = service.create_study(
            {
                "name": "Thailand ecommerce launch",
                "study_type": "PRODUCT_VALIDATION",
                "template_key": "ECOMMERCE",
                "price": 890,
                "marketplaces": ["Shopee", "Lazada", "TikTok Shop"],
                "shipping_fee": 80,
                "delivery_days": 7,
                "cod_available": False,
                "official_store": False,
            }
        )
        analysis = service._commerce_analysis(study)
        self.assertIsNotNone(analysis)
        self.assertLess(analysis["checkout_trust_index"], 50)
        self.assertGreaterEqual(len(analysis["frictions"]), 3)


if __name__ == "__main__":
    unittest.main()
