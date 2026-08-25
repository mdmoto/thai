import asyncio
import math
import unittest

import numpy as np

from app.schemas.study import CreateStudyRequest
from app.services.study_service import StudyService
from data_pipeline.market_research import PublicMarketResearch, _market_signals
from simulation_core.calibration import load_calibration_profile
from simulation_core.geo import build_geo_analysis
from simulation_core.population_grid import estimate_population_for_geojson
from world_model.country_geo import point_in_country, sample_point_in_province
from world_model.generator import PopulationGenerator


class MalaysiaExpansionTests(unittest.TestCase):
    def test_official_macro_profile_is_valid_and_complete(self):
        profile = load_calibration_profile(country_code="MY")

        self.assertEqual(profile["country_code"], "MY")
        self.assertEqual(profile["currency_code"], "MYR")
        self.assertEqual(
            profile["status"],
            "official_macro_calibrated_choice_prior",
        )
        self.assertEqual(
            profile["population"]["registered_population_total"],
            34_389_300,
        )
        self.assertEqual(
            len(profile["population"]["province_income_multiplier"]),
            16,
        )
        for field in ("age_group", "gender", "region", "income_tier"):
            self.assertTrue(
                math.isclose(
                    sum(profile["population"][field].values()),
                    1.0,
                    abs_tol=1e-6,
                )
            )
        self.assertEqual(
            profile["model_transfer"]["status"],
            "unvalidated_cross_market_prior",
        )
        self.assertEqual(
            profile["macro_context"]["district_context"]["district_count"],
            160,
        )

    def test_population_and_boundaries_cover_all_malaysia_adm1_areas(self):
        profile = load_calibration_profile(country_code="MY")
        population = PopulationGenerator(
            seed=19,
            calibration_profile=profile,
        ).generate(5_000)

        self.assertEqual(set(population["country_code"]), {"MY"})
        self.assertEqual(set(population["currency_code"]), {"MYR"})
        self.assertEqual(population["province"].nunique(), 16)
        self.assertTrue((population["monthly_income_local"] > 0).all())

        rng = np.random.default_rng(9)
        for state in (
            "Selangor",
            "W.P. Kuala Lumpur",
            "Melaka",
            "Pulau Pinang",
            "W.P. Labuan",
        ):
            latitude, longitude = sample_point_in_province(
                "MY",
                state,
                rng,
            )
            self.assertTrue(point_in_country("MY", longitude, latitude))

        catchment = estimate_population_for_geojson(
            {
                "type": "Polygon",
                "coordinates": [
                    [
                        [101.62, 3.0],
                        [101.8, 3.0],
                        [101.8, 3.25],
                        [101.62, 3.25],
                        [101.62, 3.0],
                    ]
                ],
            },
            "MY",
        )
        self.assertIsNotNone(catchment)
        self.assertGreater(catchment["estimated_resident_population"], 1_000_000)
        self.assertEqual(
            catchment["population_dataset_id"],
            "worldpop_mys_2025_500m_v1",
        )

    def test_market_research_uses_malaysia_queries_and_prices(self):
        study = {
            "name": "Skin care launch",
            "study_type": "PRICING_STUDY",
            "facts": {
                "country_code": "MY",
                "category": "skin care",
            },
            "inputs": {},
        }

        query = PublicMarketResearch._search_query(study)
        clustered = PublicMarketResearch._consumer_search_queries(study)
        signals = _market_signals("Harga promosi RM 79.90, MYR 99")

        self.assertIn("Malaysia ulasan review", query)
        self.assertTrue(any("Shopee Malaysia" in item for item in clustered))
        self.assertIn("RM 79.90", signals["prices"])
        self.assertIn("MYR 99", signals["prices"])

    def test_location_study_uses_malaysia_grid_for_coordinate_fallback(self):
        result = build_geo_analysis(
            study_type="VENUE_STUDY",
            venue_type="CAFE",
            inputs={
                "country_code": "MY",
                "candidate_locations": [
                    {
                        "label": "Kuala Lumpur test location",
                        "latitude": 3.139,
                        "longitude": 101.687,
                    }
                ],
            },
            capacity=40,
            average_check=20,
            external_evidence={"status": "unavailable", "locations": {}},
        )

        self.assertIsNotNone(result)
        self.assertEqual(
            result["locations"][0]["score_status"],
            "population_only_geospatial_evidence_unvalidated",
        )
        self.assertGreater(
            result["locations"][0]["resident_catchment_population_15m"],
            0,
        )
        self.assertTrue(
            all(
                item["mode"] == "walking_radial_proxy"
                for item in result["catchments"]
            )
        )

    def test_malaysia_study_runs_with_local_currency_and_channels(self):
        payload = CreateStudyRequest(
            name="Malaysia launch",
            country_code="MY",
            study_type="PRICING_STUDY",
            plan_code="PROFESSIONAL",
            category="skin care",
            price=79,
        )
        self.assertEqual(payload.country_code, "MY")

        service = StudyService()
        study = service.create_study(payload.model_dump())
        service.confirm_study(study["id"], {})
        report = asyncio.run(
            service.execute_run(
                study["id"],
                pop_size=120,
                mc_rounds=10,
                seed=31,
            )
        )

        self.assertEqual(report["country_code"], "MY")
        self.assertEqual(report["currency_code"], "MYR")
        self.assertEqual(report["currency_symbol"], "RM")
        self.assertEqual(
            report["sample_profile"]["location_status"],
            "synthetic_adm1_polygon_sample",
        )
        self.assertIn(
            "Shopee Malaysia",
            {item["channel"] for item in report["channels"]},
        )
        self.assertTrue(
            any("马来西亚本地化" in item["name"] for item in report["scenarios"])
        )


if __name__ == "__main__":
    unittest.main()
