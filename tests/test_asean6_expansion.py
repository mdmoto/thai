import math
import unittest
import numpy as np

from app.schemas.study import CreateStudyRequest
from app.services.study_service import StudyService
from market_config.countries import get_country_config, COUNTRIES
from simulation_core.calibration import load_calibration_profile
from world_model.country_geo import point_in_country, sample_point_in_province
from world_model.generator import PopulationGenerator


class Asean6ExpansionTests(unittest.TestCase):
    def test_all_six_countries_registered(self):
        expected_countries = {"TH", "MY", "ID", "VN", "PH", "SG"}
        self.assertEqual(set(COUNTRIES.keys()), expected_countries)

    def test_all_six_macro_profiles_valid(self):
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

            for dist in ("age_group", "gender", "region", "income_tier"):
                self.assertTrue(
                    math.isclose(sum(profile["population"][dist].values()), 1.0, abs_tol=1e-5),
                    f"{code} {dist} probabilities do not sum to 1.0",
                )

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
