import unittest

from simulation_core.geo import build_geo_analysis


class GeoAnalysisTests(unittest.TestCase):
    def test_nimman_cafe_uses_observed_poi_and_model_heatmap(self):
        result = build_geo_analysis(
            study_type="VENUE_STUDY",
            venue_type="CAFE",
            inputs={
                "location": {
                    "label": "Chiang Mai, Nimman Road",
                    "latitude": 18.7966,
                    "longitude": 98.9677,
                }
            },
            capacity=48,
            average_check=220,
        )
        self.assertIsNotNone(result)
        location = result["locations"][0]
        self.assertEqual(location["observed_poi_status"], "osm_versioned_snapshot")
        self.assertEqual(location["observed_poi"]["cafes"], 264)
        self.assertTrue(result["heatmap"])
        self.assertTrue(
            all(item["data_class"] == "model_inference" for item in result["heatmap"])
        )
        self.assertEqual(result["operations"]["status"], "operating_prior_not_observed")

    def test_live_thailand_evidence_differentiates_unknown_city_locations(self):
        result = build_geo_analysis(
            study_type="SITE_COMPARISON",
            venue_type="CAFE",
            inputs={
                "candidate_locations": [
                    {"label": "Thonglor Bangkok"},
                    {"label": "Phuket Old Town"},
                ]
            },
            capacity=40,
            average_check=180,
            external_evidence={
                "status": "observed",
                "version": "test-live-v1",
                "locations": {
                    "thonglor bangkok": {
                        "latitude": 13.73,
                        "longitude": 100.58,
                        "coordinate_source": "google_geocoding_v4",
                        "observed_poi_status": "google_places_aggregate_live",
                        "observed_poi": {
                            "restaurants": 180,
                            "cafes": 90,
                            "bars_pubs": 40,
                            "shops": 75,
                            "parking": 18,
                            "transit": 12,
                            "tourism_lodging": 28,
                        },
                        "catchments": [
                            {
                                "minutes": 15,
                                "mode": "walking_network_isochrone",
                                "area_km2": 1.12,
                                "data_class": "external_market_data",
                                "estimated_resident_population": 32000,
                            }
                        ],
                    },
                    "phuket old town": {
                        "latitude": 7.89,
                        "longitude": 98.39,
                        "coordinate_source": "google_geocoding_v4",
                        "observed_poi_status": "google_places_aggregate_live",
                        "observed_poi": {
                            "restaurants": 85,
                            "cafes": 48,
                            "bars_pubs": 9,
                            "shops": 28,
                            "parking": 4,
                            "transit": 2,
                            "tourism_lodging": 42,
                        },
                        "catchments": [
                            {
                                "minutes": 15,
                                "mode": "walking_network_isochrone",
                                "area_km2": 0.74,
                                "data_class": "external_market_data",
                                "estimated_resident_population": 12000,
                            }
                        ],
                    },
                },
                "sources": [{"name": "test source"}],
            },
        )
        self.assertEqual(result["schema_version"], "3")
        self.assertNotEqual(
            result["locations"][0]["site_score"],
            result["locations"][1]["site_score"],
        )
        self.assertTrue(
            all(
                item["score_status"]
                == "observed_geospatial_population_features_with_unvalidated_weights"
                for item in result["locations"]
            )
        )
        self.assertTrue(
            all(
                item["footfall_opportunity_status"]
                == "modeled_opportunity_not_measured_footfall"
                for item in result["locations"]
            )
        )
        self.assertEqual(
            result["score_method"],
            "observed_feature_population_weighting_unvalidated",
        )

    def test_population_grid_remains_useful_when_poi_collection_is_unavailable(self):
        result = build_geo_analysis(
            study_type="SITE_COMPARISON",
            venue_type="RETAIL",
            inputs={"candidate_locations": [{"label": "Resolved population-only site"}]},
            capacity=30,
            average_check=250,
            external_evidence={
                "status": "partial",
                "locations": {
                    "resolved population-only site": {
                        "latitude": 13.74,
                        "longitude": 100.58,
                        "catchments": [
                            {
                                "minutes": 15,
                                "mode": "walking_network_isochrone",
                                "estimated_resident_population": 25000,
                            }
                        ],
                    }
                },
            },
        )
        location = result["locations"][0]
        self.assertEqual(
            location["score_status"],
            "population_only_geospatial_evidence_unvalidated",
        )
        self.assertEqual(location["resident_catchment_population_15m"], 25000)
        self.assertIsNotNone(location["footfall_opportunity_index"])
        self.assertTrue(
            all(
                item["mode"] == "walking_network_isochrone"
                for item in result["catchments"]
            )
        )

    def test_unknown_locations_are_explicitly_insufficient_not_fake_observed(self):
        result = build_geo_analysis(
            study_type="SITE_COMPARISON",
            venue_type="RETAIL",
            inputs={
                "candidate_locations": [
                    {"label": "Unknown Bangkok Site A"},
                    {"label": "Unknown Bangkok Site B"},
                ]
            },
            capacity=20,
            average_check=300,
            external_evidence={"status": "unavailable", "locations": {}},
        )
        self.assertTrue(
            all(
                item["score_status"] == "insufficient_geospatial_evidence"
                for item in result["locations"]
            )
        )
        self.assertTrue(
            any("中性占位" in warning for warning in result["warnings"])
        )

    def test_customer_hourly_history_calibrates_operations(self):
        history = [
            {
                "date": f"2026-07-{day:02d}",
                "hour": hour,
                "visits": 20 + hour,
                "service_minutes": 55,
            }
            for day in range(1, 5)
            for hour in (10, 12, 18, 20)
        ]
        result = build_geo_analysis(
            study_type="VENUE_STUDY",
            venue_type="RESTAURANT",
            inputs={
                "location": {"label": "Nimman Road"},
                "venue_history": history,
            },
            capacity=50,
            average_check=250,
        )
        self.assertEqual(
            result["operations"]["status"],
            "customer_operations_calibrated_unvalidated",
        )
        self.assertTrue(
            all(
                item["data_class"] == "customer_observation"
                for item in result["operations"]["hourly_demand"]
            )
        )

    def test_site_comparison_ranks_multiple_named_zones(self):
        result = build_geo_analysis(
            study_type="SITE_COMPARISON",
            venue_type="RETAIL",
            inputs={
                "candidate_locations": [
                    {"label": "Nimman Road"},
                    {"label": "Chiang Mai Old City"},
                    {"label": "Chiang Mai Night Bazaar"},
                ]
            },
            capacity=70,
            average_check=300,
        )
        self.assertEqual(len(result["locations"]), 3)
        self.assertEqual(
            [item["rank"] for item in result["locations"]],
            [1, 2, 3],
        )
        self.assertTrue(
            all(item["coordinate_status"] == "resolved" for item in result["locations"])
        )

    def test_product_study_does_not_create_geo_analysis(self):
        result = build_geo_analysis(
            study_type="PRODUCT_VALIDATION",
            venue_type="PRODUCT_VALIDATION",
            inputs={},
            capacity=None,
            average_check=None,
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
