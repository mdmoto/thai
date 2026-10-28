import json
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
            from simulation_core.calibration import derive_profile_status
            expected_status = (
                "official_macro_population_with_localized_choice_priors"
                if code in {"TH", "MY"}
                else "official_macro_population_with_transferred_choice_priors"
            )
            self.assertEqual(profile["status"], expected_status)
            self.assertEqual(profile["status"], derive_profile_status(profile["calibration_scope"]))
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

            # Validate calibration_scope and sources title
            self.assertIn("calibration_scope", profile, f"{code} must have calibration_scope")
            self.assertIsNotNone(profile["calibration_scope"])
            for s in profile.get("sources", []):
                self.assertTrue(bool(s.get("title")), f"{code} source {s.get('source_id')} missing title")

    def test_all_ten_study_models_are_differentiated_across_six_countries(self):
        profiles = {code: load_calibration_profile(country_code=code) for code in ["TH", "MY", "ID", "VN", "PH", "SG"]}
        models = list(profiles["TH"]["study_models"].keys())
        self.assertEqual(len(models), 10, "Should have exactly 10 study models")

        # Verify Thailand pricing study is aligned with product validation (-1.35), not historical -1.9
        th_pricing_plr = profiles["TH"]["study_models"]["PRICING_STUDY"]["coefficients"]["price_log_ratio"]["mean"]
        self.assertEqual(th_pricing_plr, -1.35, "Thailand PRICING_STUDY price_log_ratio should be -1.35")

        for model_name in models:
            unique_sets = set()
            plrs = []
            for code in ["SG", "MY", "TH", "VN", "PH", "ID"]:
                m = profiles[code]["study_models"][model_name]
                unique_sets.add(json.dumps(m["coefficients"], sort_keys=True))
                plrs.append(m["coefficients"]["price_log_ratio"]["mean"])

            self.assertEqual(
                len(unique_sets), 6,
                f"Model {model_name} must have 6/6 unique coefficient sets across the 6 countries"
            )
            # Ensure price elasticity follows the gradient (SG least elastic, ID most elastic)
            for i in range(len(plrs) - 1):
                self.assertGreater(
                    plrs[i], plrs[i + 1],
                    f"Model {model_name} price elasticity gradient violated: {plrs}"
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

    def test_cross_layer_calibration_scope_consistency(self):
        from simulation_core.calibration import derive_profile_status
        from pathlib import Path
        import re

        # 1. Verify all 6 country profiles have self-consistent status and calibration_scope
        for code in ["TH", "MY", "ID", "VN", "PH", "SG"]:
            profile = load_calibration_profile(country_code=code)
            scope = profile["calibration_scope"]
            self.assertIn("choice_coefficients", scope)
            self.assertIn("behavioral_traits", scope)

            expected_status = derive_profile_status(scope)
            self.assertEqual(
                profile["status"], expected_status,
                f"{code} profile status ({profile['status']}) contradicts calibration_scope ({expected_status})"
            )

            if code in {"TH", "MY"}:
                self.assertEqual(scope["choice_coefficients"], "localized_expert_prior")
                self.assertEqual(profile["status"], "official_macro_population_with_localized_choice_priors")
            else:
                self.assertEqual(scope["choice_coefficients"], "unvalidated_cross_market_prior")
                self.assertEqual(profile["status"], "official_macro_population_with_transferred_choice_priors")

        # 2. Verify Frontend MARKET_CONFIG (wizard-client.tsx) matches data catalog calibration_scope
        wizard_ts = (
            Path(__file__).resolve().parents[1]
            / "apps" / "web" / "app" / "studies" / "new" / "wizard-client.tsx"
        ).read_text(encoding="utf-8")

        for code in ["TH", "MY", "ID", "VN", "PH", "SG"]:
            profile = load_calibration_profile(country_code=code)
            expected_choice = profile["calibration_scope"]["choice_coefficients"]
            pattern = rf'{code}:\s*\{{[^}}]*choice_coefficients:\s*["\']([^"\']+)["\']'
            match = re.search(pattern, wizard_ts, re.DOTALL)
            self.assertIsNotNone(match, f"Could not find choice_coefficients for {code} in wizard-client.tsx")
            frontend_choice = match.group(1)
            self.assertEqual(
                frontend_choice,
                expected_choice,
                f"Frontend wizard-client.tsx choice_coefficients for {code} ({frontend_choice}) drifts from profile ({expected_choice})!"
            )
