import unittest

import pandas as pd

from simulation_core.calibration import load_calibration_profile
from world_model.generator import PopulationGenerator


class PopulationGeneratorTests(unittest.TestCase):
    def setUp(self):
        self.profile = load_calibration_profile()

    def test_generation_is_reproducible(self):
        first = PopulationGenerator(
            seed=12,
            calibration_profile=self.profile,
        ).generate(500, "PRODUCT_VALIDATION")
        second = PopulationGenerator(
            seed=12,
            calibration_profile=self.profile,
        ).generate(500, "PRODUCT_VALIDATION")
        pd.testing.assert_frame_equal(first, second)

    def test_population_margins_track_versioned_profile(self):
        population = PopulationGenerator(
            seed=21,
            calibration_profile=self.profile,
        ).generate(20_000, "PRODUCT_VALIDATION")
        observed = population["region"].value_counts(normalize=True)
        for region, expected in self.profile["population"]["region"].items():
            self.assertAlmostEqual(observed[region], expected, delta=0.02)

    def test_household_income_tracks_official_region_targets(self):
        population = PopulationGenerator(
            seed=27,
            calibration_profile=self.profile,
        ).generate(50_000, "PRODUCT_VALIDATION")
        observed = population.groupby("region")[
            "household_monthly_income_thb"
        ].mean()
        targets = self.profile["population"][
            "official_region_household_income_thb"
        ]
        for region, target in targets.items():
            self.assertAlmostEqual(
                observed[region] / target,
                1.0,
                delta=0.05,
            )
        self.assertEqual(population["province"].nunique(), 77)

    def test_study_type_changes_category_engagement(self):
        cafe = PopulationGenerator(
            seed=8,
            calibration_profile=self.profile,
        ).generate(3_000, "CAFE")
        bar = PopulationGenerator(
            seed=8,
            calibration_profile=self.profile,
        ).generate(3_000, "BAR")
        self.assertGreater(
            cafe["category_engagement"].mean(),
            bar["category_engagement"].mean(),
        )

    def test_pet_water_fountain_profile_limits_eligibility_to_pet_households(self):
        population = PopulationGenerator(
            seed=18,
            calibration_profile=self.profile,
        ).generate(
            8_000,
            "PRODUCT_VALIDATION",
            category="宠物智能饮水机",
        )
        self.assertEqual(
            set(population["category_key"]),
            {"PET_WATER_FOUNTAIN"},
        )
        self.assertTrue(
            (
                population["category_eligible"]
                == population["has_pets"]
            ).all()
        )
        self.assertTrue(
            (
                population.loc[
                    ~population["category_eligible"],
                    "category_engagement",
                ]
                == 0
            ).all()
        )

    def test_stratified_sample_expands_to_population(self):
        generator = PopulationGenerator(
            seed=9,
            calibration_profile=self.profile,
        )
        population = generator.generate(5_000, "RETAIL")
        sample = generator.stratified_sample(population, 60, seed=9)
        self.assertEqual(len(sample), 60)
        self.assertAlmostEqual(
            sample["expansion_weight"].sum(),
            population["sample_weight"].sum(),
            delta=1e-6,
        )


if __name__ == "__main__":
    unittest.main()
