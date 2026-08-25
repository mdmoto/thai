import json
import tempfile
import unittest
from pathlib import Path

import httpx
from data_pipeline.bot import BotDataSourceError, BotStatisticsClient
from data_pipeline.customer_data import validate_customer_rows
from data_pipeline.moc import (
    MocCollector,
    MocDataSourceError,
    build_macro_context,
    load_latest_moc_context,
)


class MocCollectorTests(unittest.TestCase):
    def test_refresh_writes_versioned_manifest_and_context(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/cpig-indexes"):
                region_id = int(request.url.params["region_id"])
                return httpx.Response(
                    200,
                    json=[
                        {
                            "index_id": "0000000000000000",
                            "index_description": "All items",
                            "region_id": region_id,
                            "region_name": ("Kingdom" if region_id == 5 else "Bangkok"),
                            "base_year": 2023,
                            "year": 2026,
                            "month": 7,
                            "price_index": 101.2,
                            "mom": 0.1,
                            "yoy": 1.4,
                            "aoa": 1.1,
                        }
                    ],
                )
            if request.url.path.endswith("/cci-indexes"):
                return httpx.Response(
                    200,
                    json=[
                        {
                            "year": 2026,
                            "month": 7,
                            "index_all": 49.2,
                            "index_current": 42.1,
                            "index_future": 54.0,
                        }
                    ],
                )
            raise AssertionError(f"unexpected request: {request.url}")

        with tempfile.TemporaryDirectory() as directory:
            catalog_root = Path(directory)
            with httpx.Client(transport=httpx.MockTransport(handler)) as client:
                result = MocCollector(client=client).refresh_macro_context(
                    catalog_root / "raw" / "moc",
                    2025,
                    2026,
                    region_ids=(0, 5),
                )
            manifest_path = Path(result["manifest_path"])
            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["sources"]), 3)
            self.assertEqual(
                manifest["context"]["quantitative_effect"],
                "context_only_until_backtested",
            )
            context = load_latest_moc_context(catalog_root)
            self.assertEqual(context["national_cpi"]["yoy"], 1.4)
            self.assertEqual(context["consumer_confidence"]["index_all"], 49.2)

    def test_schema_drift_fails_closed(self):
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[{"year": 2026}])

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaises(MocDataSourceError):
                MocCollector(client=client).fetch_regional_cpi(5, 2026, 2026)

    def test_macro_context_uses_latest_period(self):
        context = build_macro_context(
            [
                {
                    "region_id": 5,
                    "region_name": "Thailand",
                    "year": 2025,
                    "month": 12,
                    "price_index": 100,
                    "mom": 0,
                    "yoy": 1,
                    "aoa": 1,
                },
                {
                    "region_id": 5,
                    "region_name": "Thailand",
                    "year": 2026,
                    "month": 1,
                    "price_index": 101,
                    "mom": 1,
                    "yoy": 2,
                    "aoa": 2,
                },
            ],
            [
                {
                    "year": 2026,
                    "month": 1,
                    "index_all": 48,
                    "index_current": 40,
                    "index_future": 52,
                }
            ],
        )
        self.assertEqual(context["national_cpi"]["year"], 2026)
        self.assertEqual(context["national_cpi"]["price_index"], 101.0)


class CustomerDataReadinessTests(unittest.TestCase):
    def test_observed_choices_are_ready_at_minimum_threshold(self):
        rows = []
        for index in range(20):
            rows.extend(
                [
                    {
                        "choice_set_id": f"set-{index}",
                        "alternative": "product",
                        "chosen": "1",
                        "price_log_ratio": "0.1",
                    },
                    {
                        "choice_set_id": f"set-{index}",
                        "alternative": "no_purchase",
                        "chosen": "0",
                        "price_log_ratio": "0",
                    },
                ]
            )
        report = validate_customer_rows(
            "observed_choices",
            ("choice_set_id", "alternative", "chosen", "price_log_ratio"),
            rows,
        )
        self.assertEqual(report["status"], "ready_for_import")
        self.assertTrue(report["ready_for_model_use"])

    def test_direct_pii_blocks_import(self):
        report = validate_customer_rows(
            "transactions",
            (
                "transaction_id",
                "occurred_at",
                "sku",
                "units",
                "net_revenue_thb",
                "channel",
                "province",
                "email",
            ),
            [
                {
                    "transaction_id": "1",
                    "occurred_at": "2026-01-01",
                    "sku": "a",
                    "units": "1",
                    "net_revenue_thb": "100",
                    "channel": "web",
                    "province": "bangkok",
                    "email": "person@example.com",
                }
            ]
            * 100,
        )
        self.assertFalse(report["safe_to_import"])
        self.assertIn("email", report["direct_pii_fields"])

    def test_orders_are_explicitly_descriptive_only(self):
        fields = (
            "transaction_id",
            "occurred_at",
            "sku",
            "units",
            "net_revenue_thb",
            "channel",
            "province",
        )
        rows = [
            {
                "transaction_id": str(index),
                "occurred_at": "2026-01-01",
                "sku": "a",
                "units": "1",
                "net_revenue_thb": "100",
                "channel": "web",
                "province": "bangkok",
            }
            for index in range(100)
        ]
        report = validate_customer_rows("transactions", fields, rows)
        self.assertEqual(report["status"], "descriptive_only_ready")
        self.assertFalse(report["ready_for_model_use"])


class BotClientTests(unittest.TestCase):
    def test_api_key_is_required(self):
        with self.assertRaises(BotDataSourceError):
            BotStatisticsClient(api_key="").search_series("household debt")

    def test_authorization_header_is_sent(self):
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.headers["Authorization"], "secret")
            self.assertEqual(request.url.params["keyword"], "household debt")
            return httpx.Response(200, json={"result": []})

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            result = BotStatisticsClient(
                api_key="secret",
                client=client,
            ).search_series("household debt")
        self.assertEqual(
            result["manifest"]["quantitative_effect"],
            "none_series_discovery_only",
        )


if __name__ == "__main__":
    unittest.main()
