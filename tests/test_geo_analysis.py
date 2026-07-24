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
        self.assertEqual(location["observed_poi_status"], "public_snapshot")
        self.assertEqual(location["observed_poi"]["cafes"], 264)
        self.assertTrue(result["heatmap"])
        self.assertTrue(
            all(item["data_class"] == "model_inference" for item in result["heatmap"])
        )
        self.assertEqual(result["operations"]["status"], "operating_prior_not_observed")

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
