import hashlib
import json
import unittest
from pathlib import Path

import httpx

from data_pipeline.nso import (
    DataSourceError,
    NsoCollector,
    SOURCES,
    read_snapshot,
)
from data_pipeline.product_pages import (
    ProductPageError,
    PublicProductPageCollector,
)
from simulation_core.calibration import load_calibration_profile


REPO_ROOT = Path(__file__).resolve().parents[1]


class OfficialSnapshotTests(unittest.TestCase):
    def test_default_profile_uses_traceable_official_macro_margins(self):
        profile = load_calibration_profile()
        self.assertEqual(
            profile["status"],
            "official_macro_calibrated_choice_prior",
        )
        self.assertEqual(
            profile["population"]["registered_population_total"],
            65_809_011,
        )
        self.assertEqual(
            sum(
                len(provinces)
                for provinces in profile["population"][
                    "province_by_region"
                ].values()
            ),
            77,
        )
        self.assertAlmostEqual(
            sum(profile["population"]["region"].values()),
            1.0,
        )
        observed_sources = [
            source for source in profile["sources"] if source.get("observed")
        ]
        self.assertEqual(len(observed_sources), 4)
        self.assertTrue(
            all(source["sha256"] for source in observed_sources)
        )
        self.assertIn(
            "choice_coefficients",
            profile["unobserved_dimensions"],
        )

    def test_snapshot_hashes_match_manifest(self):
        manifest_paths = sorted(
            (
                REPO_ROOT
                / "data_catalog"
                / "raw"
                / "nso"
            ).glob("*/manifest.json")
        )
        self.assertTrue(manifest_paths)
        manifest_path = manifest_paths[-1]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for source in manifest["sources"].values():
            snapshot_path = REPO_ROOT / source["snapshot_path"]
            rows = read_snapshot(snapshot_path)
            canonical = json.dumps(
                rows,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            self.assertEqual(
                hashlib.sha256(canonical).hexdigest(),
                source["sha256"],
            )
            self.assertEqual(len(rows), source["record_count"])

    def test_nso_schema_drift_fails_closed(self):
        source = SOURCES["household_income_distribution"]
        with self.assertRaises(DataSourceError):
            NsoCollector.validate_rows(
                source,
                [{"YEAR": 2566}] * source.minimum_records,
            )


class PublicProductPageCollectorTests(unittest.TestCase):
    def test_extracts_product_json_ld_without_claiming_transactions(self):
        html = """
        <html><head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Test Water Fountain",
          "description": "2.5 litre tank, 4-stage filter and stainless tray",
          "brand": {"@type": "Brand", "name": "Example"},
          "offers": {
            "price": "1290",
            "priceCurrency": "THB",
            "priceValidUntil": "2026-08-01"
          },
          "aggregateRating": {"ratingValue": "4.6", "reviewCount": "238"}
        }
        </script>
        </head><body>
        Related product: app-connected fountain with UV sterilizer.
        </body></html>
        """

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/robots.txt":
                return httpx.Response(
                    200,
                    text="User-agent: *\nAllow: /\n",
                )
            return httpx.Response(
                200,
                text=html,
                headers={"content-type": "text/html; charset=utf-8"},
            )

        with httpx.Client(
            transport=httpx.MockTransport(handler),
            headers={"User-Agent": "ThailandMarketTwin/2.0"},
        ) as client:
            collector = PublicProductPageCollector(
                minimum_interval_seconds=0,
                client=client,
            )
            record = collector.collect("https://example.test/product/1")

        self.assertEqual(record["name"], "Test Water Fountain")
        self.assertEqual(record["price"], 1290.0)
        self.assertEqual(record["currency"], "THB")
        self.assertEqual(record["price_valid_until"], "2026-08-01")
        self.assertEqual(record["page_claims"]["capacity_liters"], 2.5)
        self.assertEqual(record["page_claims"]["filtration_stages"], 4)
        self.assertTrue(record["page_claims"]["stainless_surface"])
        self.assertFalse(record["page_claims"]["app_connected"])
        self.assertFalse(record["page_claims"]["uv_sterilization"])
        self.assertFalse(record["transaction_data"])
        competitor = collector.to_competitor_data(record)
        self.assertAlmostEqual(competitor["review_score"], 0.92)
        self.assertFalse(competitor["evidence"]["transaction_data"])

    def test_robots_disallow_is_respected(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/robots.txt":
                return httpx.Response(
                    200,
                    text="User-agent: *\nDisallow: /private\n",
                )
            return httpx.Response(
                200,
                text="<html></html>",
                headers={"content-type": "text/html"},
            )

        with httpx.Client(
            transport=httpx.MockTransport(handler),
        ) as client:
            collector = PublicProductPageCollector(
                minimum_interval_seconds=0,
                client=client,
            )
            with self.assertRaises(ProductPageError):
                collector.collect("https://example.test/private/product")

    def test_checked_in_category_panel_is_traceable_and_benchmark_ready(self):
        panel_path = (
            REPO_ROOT
            / "data_catalog"
            / "categories"
            / "pet_water_fountain_th_v1.json"
        )
        panel = json.loads(panel_path.read_text(encoding="utf-8"))
        self.assertGreaterEqual(panel["offer_count"], 10)
        self.assertEqual(panel["retailer_count"], 3)
        self.assertEqual(
            panel["benchmark_study_input"]["category"],
            "PET_WATER_FOUNTAIN",
        )
        self.assertEqual(len(panel["professional_choice_set"]), 5)
        self.assertTrue(
            all(
                not product["transaction_data"]
                for product in panel["products"]
            )
        )


if __name__ == "__main__":
    unittest.main()
