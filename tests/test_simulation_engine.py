import unittest

from simulation_core.calibration import load_calibration_profile
from simulation_core.config import get_plan_config
from simulation_core.engine import SimulationEngine
from world_model.generator import PopulationGenerator


class SimulationEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = load_calibration_profile()
        cls.population = PopulationGenerator(
            seed=42,
            calibration_profile=cls.profile,
        ).generate(1_500, "PRODUCT_VALIDATION")

    def run_engine(self, **overrides):
        parameters = {
            "population_df": self.population,
            "study_type": "PRODUCT_VALIDATION",
            "price": 299.0,
            "ref_price": 299.0,
            "brand_awareness": 0.2,
            "mc_rounds": 30,
            "plan_code": "PREVIEW",
        }
        parameters.update(overrides)
        return SimulationEngine(
            seed=44,
            calibration_profile=self.profile,
        ).run_simulation(**parameters)

    def test_price_curve_is_downward_sloping(self):
        result = self.run_engine()
        curve = result["price_elasticity"]
        self.assertGreater(curve[0]["purchase_rate"], curve[-1]["purchase_rate"])

    def test_competitor_reduces_focal_choice_share(self):
        no_competitor = self.run_engine()
        with_competitor = self.run_engine(
            competitors=[
                {
                    "name": "Observed competitor",
                    "price": 279,
                    "awareness": 0.65,
                    "quality_score": 0.65,
                    "review_score": 0.7,
                }
            ]
        )
        self.assertLess(
            with_competitor["mean_purchase_rate"],
            no_competitor["mean_purchase_rate"],
        )

    def test_study_type_selects_a_different_model(self):
        product = self.run_engine(study_type="PRODUCT_VALIDATION")
        cafe = self.run_engine(study_type="CAFE")
        self.assertNotEqual(product["study_model_key"], cafe["study_model_key"])
        self.assertNotAlmostEqual(
            product["mean_purchase_rate"],
            cafe["mean_purchase_rate"],
            places=4,
        )

    def test_all_first_release_study_models_execute(self):
        expected_funnel_labels = {
            "PRODUCT_VALIDATION": "Purchased",
            "PRICING_STUDY": "Purchased",
            "CREATIVE_TEST": "Action Intended",
            "VENUE_STUDY": "Visited",
            "SITE_COMPARISON": "Visited",
            "OPERATING_SCENARIO": "Visited",
            "RESTAURANT": "Visited",
            "CAFE": "Visited",
            "BAR": "Visited",
            "RETAIL": "Visited",
        }
        model_keys = set()
        for study_type, final_label in expected_funnel_labels.items():
            with self.subTest(study_type=study_type):
                result = self.run_engine(
                    study_type=study_type,
                    mc_rounds=20,
                )
                model_keys.add(result["study_model_key"])
                purchased_stage = next(
                    item for item in result["funnel"]
                    if item["stage"] == "purchased"
                )
                self.assertEqual(purchased_stage["label"], final_label)
                self.assertGreaterEqual(result["mean_purchase_rate"], 0)
                self.assertLessEqual(result["mean_purchase_rate"], 1)
        self.assertGreaterEqual(len(model_keys), 6)

    def test_llm_signal_is_bounded_and_disclosed(self):
        result = self.run_engine(
            plan_code="PROFESSIONAL",
            agent_signals={
                "status": "available",
                "sample_size_completed": 20,
                "prompt_version": "test",
                "model_id": "test",
                "aggregate": {
                    "confidence": 1.0,
                    "awareness_lift": 0.25,
                    "attribute_importance": {
                        "price": 1.0,
                        "quality": 1.0,
                        "trust": 1.0,
                        "warranty": 1.0,
                        "design": 1.0,
                        "convenience": 1.0,
                        "social_proof": 1.0,
                    },
                },
            },
        )
        signal = result["model_lineage"]["agent_signal"]
        self.assertEqual(signal["status"], "available")
        self.assertLessEqual(signal["effective_weight"], 0.05)
        self.assertLessEqual(max(signal["coefficient_multiplier"].values()), 1.05)

    def test_plan_changes_model_and_evidence_depth(self):
        preview = get_plan_config("PREVIEW")
        deep = get_plan_config("DEEP")
        self.assertNotEqual(preview.model_family, deep.model_family)
        self.assertGreater(deep.default_population, preview.default_population)
        self.assertGreater(deep.elasticity_points, preview.elasticity_points)
        self.assertGreater(deep.dynamic_periods, preview.dynamic_periods)

    def test_interval_is_not_mislabelled_as_validated_confidence(self):
        result = self.run_engine()
        uncertainty = result["model_lineage"]["uncertainty"]
        self.assertEqual(
            uncertainty["interval_type"],
            "prior_predictive_p10_p90",
        )
        self.assertIsNone(uncertainty["validated_forecast_error"])

    def test_category_eligibility_is_applied_before_choice(self):
        pet_population = PopulationGenerator(
            seed=52,
            calibration_profile=self.profile,
        ).generate(
            1_500,
            "PRODUCT_VALIDATION",
            category="PET_WATER_FOUNTAIN",
        )
        result = self.run_engine(
            population_df=pet_population,
            price=1990.0,
            ref_price=1990.0,
            plan_code="PROFESSIONAL",
        )
        expected_eligible = int(pet_population["category_eligible"].sum())
        self.assertEqual(
            result["category_eligible_population"],
            expected_eligible,
        )
        self.assertEqual(
            result["funnel"][0]["value"],
            expected_eligible,
        )
        self.assertLessEqual(
            result["mean_purchase_rate"],
            result["funnel"][0]["rate"],
        )
        self.assertEqual(
            result["model_lineage"]["category"]["category_key"],
            "PET_WATER_FOUNTAIN",
        )


if __name__ == "__main__":
    unittest.main()
