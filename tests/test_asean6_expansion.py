import math
import unittest
import numpy as np

from app.schemas.study import CreateStudyRequest
from market_config.countries import get_country_config, COUNTRIES
from simulation_core.calibration import load_calibration_profile
from world_model.country_geo import point_in_country, sample_point_in_province
from world_model.generator import PopulationGenerator


class Asean6ExpansionTests(unittest.TestCase):
    def test_all_six_countries_registered(self):
        expected_countries = {"TH", "MY", "ID", "VN", "PH", "SG"}
        self.assertEqual(set(COUNTRIES.keys()), expected_countries)

    def test_all_six_macro_profiles_valid_and_non_uniform(self):
        for code, expected_cur in [
            ("TH", "THB"),
            ("MY", "MYR"),
            ("ID", "IDR"),
            ("VN", "VND"),
            ("PH", "PHP"),
            ("SG", "SGD"),
        ]:
            profile = load_calibration_profile(country_code=code)
            self.assertEqual(profile["country_code"], code)
            self.assertEqual(profile["currency_code"], expected_cur)
            self.assertEqual(profile["status"], "official_macro_calibrated_choice_prior")
            self.assertGreater(profile["population"]["registered_population_total"], 5_000_000)

            # Validate income tier is NOT uniform 0.2 placeholder
            income_tier = profile["population"]["income_tier"]
            luxury_share = income_tier["LUXURY"]
            self.assertLess(luxury_share, 0.05, f"{code} luxury tier is unrealistically high ({luxury_share})")
            self.assertNotEqual(income_tier["LOW"], income_tier["LUXURY"], f"{code} income tiers must be non-uniform")

            # Validate income_tier_by_region exists and sums to 1.0
            self.assertIn("income_tier_by_region", profile["population"], f"{code} is missing income_tier_by_region")
            for region, dist in profile["population"]["income_tier_by_region"].items():
                self.assertTrue(
                    math.isclose(sum(dist.values()), 1.0, abs_tol=1e-5),
                    f"{code} region {region} income tier distribution does not sum to 1.0",
                )

            for dist in ("age_group", "gender", "region", "income_tier"):
                self.assertTrue(
                    math.isclose(sum(profile["population"][dist].values()), 1.0, abs_tol=1e-5),
                    f"{code} {dist} probabilities do not sum to 1.0",
                )

    def test_behavior_and_elasticity_are_differentiated(self):
        sg = load_calibration_profile(country_code="SG")
        id_prof = load_calibration_profile(country_code="ID")
        vn = load_calibration_profile(country_code="VN")
        my = load_calibration_profile(country_code="MY")
        th = load_calibration_profile(country_code="TH")

        # Singapore vs Indonesia:
        # Singapore should have higher online affinity than Indonesia
        sg_online = sg["behavior"]["online_affinity_beta"][0] / sum(sg["behavior"]["online_affinity_beta"])
        id_online = id_prof["behavior"]["online_affinity_beta"][0] / sum(id_prof["behavior"]["online_affinity_beta"])
        self.assertGreater(sg_online, id_online, "Singapore online affinity should exceed Indonesia")

        # Indonesia should have higher review sensitivity than Singapore
        sg_rev = sg["behavior"]["review_sensitivity_beta"][0] / sum(sg["behavior"]["review_sensitivity_beta"])
        id_rev = id_prof["behavior"]["review_sensitivity_beta"][0] / sum(id_prof["behavior"]["review_sensitivity_beta"])
        self.assertGreater(id_rev, sg_rev, "Indonesia review sensitivity should exceed Singapore")

        # Price elasticity: Singapore should be less price elastic (-1.05) than Indonesia (-1.58)
        sg_elast = sg["study_models"]["PRODUCT_VALIDATION"]["coefficients"]["price_log_ratio"]["mean"]
        id_elast = id_prof["study_models"]["PRODUCT_VALIDATION"]["coefficients"]["price_log_ratio"]["mean"]
        self.assertGreater(sg_elast, id_elast, "Singapore should be less price elastic than Indonesia")

        # Verify behavior hash is not identical across countries
        behaviors = [sg["behavior"], id_prof["behavior"], vn["behavior"], my["behavior"], th["behavior"]]
        unique_online = {tuple(b["online_affinity_beta"]) for b in behaviors}
        self.assertGreaterEqual(len(unique_online), 4, "Online affinity should be differentiated across markets")

    def test_population_generation_for_all_six_countries(self):
        for code in ["TH", "MY", "ID", "VN", "PH", "SG"]:
            profile = load_calibration_profile(country_code=code)
            pop = PopulationGenerator(seed=101, calibration_profile=profile).generate(200)
            self.assertEqual(set(pop["country_code"]), {code})
            cfg = get_country_config(code)
            self.assertEqual(set(pop["currency_code"]), {cfg.currency_code})
            self.assertGreater(len(set(pop["province"])), 0)

    def test_spatial_sampling_for_all_six_countries(self):
        rng = np.random.default_rng(2026)
        for code in ["TH", "MY", "ID", "VN", "PH", "SG"]:
            profile = load_calibration_profile(country_code=code)
            first_prov = list(profile["population"]["province_income_multiplier"].keys())[0]
            lat, lng = sample_point_in_province(code, first_prov, rng)
            self.assertTrue(point_in_country(code, lng, lat), f"Sampled point for {code} is outside country boundaries")

    def test_study_request_schema_accepts_six_countries(self):
        for code in ["TH", "MY", "ID", "VN", "PH", "SG"]:
            req = CreateStudyRequest(
                name=f"Test {code} Study",
                study_type="PRODUCT_VALIDATION",
                category="GENERIC_CONSUMER_PRODUCT",
                product_name="Eco Water Bottle",
                price=50.0,
                country_code=code,
            )
            self.assertEqual(req.country_code, code)

        with self.assertRaises(ValueError):
            CreateStudyRequest(
                name="Test Invalid Study",
                study_type="PRODUCT_VALIDATION",
                category="GENERIC_CONSUMER_PRODUCT",
                product_name="Item",
                price=10.0,
                country_code="US",
            )
