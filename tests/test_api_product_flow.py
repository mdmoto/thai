"""End-to-end API contract tests for the sellable self-service flow."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


_DATABASE_FILE = tempfile.NamedTemporaryFile(
    prefix="market-twin-api-test-",
    suffix=".db",
    delete=False,
)
_DATABASE_FILE.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_DATABASE_FILE.name}"
os.environ["JWT_SECRET_KEY"] = "test-secret-with-more-than-thirty-two-characters"
os.environ["ADMIN_API_KEY"] = "test-admin-key"
os.environ["APP_ENV"] = "test"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app, service  # noqa: E402


class ApiProductFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)
        Path(_DATABASE_FILE.name).unlink(missing_ok=True)

    def _register(self, email: str):
        response = self.client.post(
            "/v1/auth/register",
            json={
                "email": email,
                "password": "a-secure-test-password",
                "name": "测试客户",
                "company": "Test Brand",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        return body, {"Authorization": f"Bearer {body['access_token']}"}

    def test_public_health_reports_database_connectivity(self):
        response = self.client.get("/v1/health")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json(),
            {"status": "healthy", "database": "connected"},
        )

    def test_public_catalog_excludes_internal_plans(self):
        response = self.client.get("/v1/catalog")
        self.assertEqual(response.status_code, 200, response.text)
        catalog = response.json()
        expected = ["PREVIEW", "STANDARD", "PROFESSIONAL"]
        self.assertEqual(catalog["self_service_plans"], expected)
        self.assertEqual(catalog["assisted_plans"], [])
        self.assertEqual(list(catalog["credit_pricing"]), expected)
        self.assertEqual(list(catalog["plans"]), expected)
        self.assertNotIn("DEEP", response.text)
        self.assertNotIn("ENTERPRISE", response.text)

    def test_authenticated_product_flow_is_private_and_idempotent(self):
        first_user, first_headers = self._register("owner@example.com")
        _, second_headers = self._register("other@example.com")
        self.assertEqual(first_user["user"]["credits_balance"], 5)

        duplicate = self.client.post(
            "/v1/auth/register",
            json={
                "email": "owner@example.com",
                "password": "a-secure-test-password",
            },
        )
        self.assertEqual(duplicate.status_code, 409)

        anonymous = self.client.post(
            "/v1/studies",
            json={
                "name": "anonymous",
                "study_type": "PRODUCT_VALIDATION",
                "price": 1290,
            },
        )
        self.assertEqual(anonymous.status_code, 401)

        created = self.client.post(
            "/v1/studies",
            headers=first_headers,
            json={
                "name": "泰国宠物饮水机上市验证",
                "study_type": "PRODUCT_VALIDATION",
                "plan_code": "PREVIEW",
                "product_name": "QuietFlow",
                "category": "PET_WATER_FOUNTAIN",
                "price": 1290,
                "selling_points": ["静音", "本地保修"],
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        study = created.json()
        self.assertEqual(study["facts"]["category"], "PET_WATER_FOUNTAIN")
        self.assertTrue(study["facts"]["category_panel_version"])
        self.assertGreaterEqual(len(study["facts"]["competitor_data"]), 3)

        private_read = self.client.get(
            f"/v1/studies/{study['id']}",
            headers=second_headers,
        )
        self.assertEqual(private_read.status_code, 404)

        confirmed = self.client.post(
            f"/v1/studies/{study['id']}/confirm",
            headers=first_headers,
            json={"overrides": {}},
        )
        self.assertEqual(confirmed.status_code, 200, confirmed.text)

        request = {
            "study_id": study["id"],
            "plan_code": "PREVIEW",
            "idempotency_key": "api-contract-preview-run-1",
        }
        first_run = self.client.post(
            f"/v1/studies/{study['id']}/runs",
            headers=first_headers,
            json=request,
        )
        self.assertEqual(first_run.status_code, 200, first_run.text)
        report = first_run.json()
        self.assertEqual(report["plan_code"], "PREVIEW")
        self.assertEqual(report["population_size"], 100)
        self.assertEqual(report["category_key"], "PET_WATER_FOUNTAIN")
        self.assertIn("model_lineage", report)

        replay = self.client.post(
            f"/v1/studies/{study['id']}/runs",
            headers=first_headers,
            json=request,
        )
        self.assertEqual(replay.status_code, 200, replay.text)
        self.assertEqual(replay.json()["report_id"], report["report_id"])

        owner_report = self.client.get(
            f"/v1/reports/{report['report_id']}",
            headers=first_headers,
        )
        self.assertEqual(owner_report.status_code, 200)
        forbidden_report = self.client.get(
            f"/v1/reports/{report['report_id']}",
            headers=second_headers,
        )
        self.assertEqual(forbidden_report.status_code, 404)

    def test_purchase_order_requires_verified_admin_completion(self):
        account, headers = self._register("buyer@example.com")
        starting_balance = account["user"]["credits_balance"]

        order_response = self.client.post(
            "/v1/billing/orders",
            headers=headers,
            json={"package_code": "STARTER"},
        )
        self.assertEqual(order_response.status_code, 201, order_response.text)
        order = order_response.json()
        self.assertEqual(order["status"], "PENDING_PAYMENT")

        unchanged = self.client.get("/v1/auth/me", headers=headers).json()
        self.assertEqual(unchanged["credits_balance"], starting_balance)

        wrong_key = self.client.post(
            f"/v1/admin/billing/orders/{order['id']}/complete",
            headers={"X-Admin-Key": "wrong"},
            json={"payment_reference": "bank-transfer-test-1"},
        )
        self.assertEqual(wrong_key.status_code, 403)

        completed = self.client.post(
            f"/v1/admin/billing/orders/{order['id']}/complete",
            headers={"X-Admin-Key": "test-admin-key"},
            json={"payment_reference": "bank-transfer-test-1"},
        )
        self.assertEqual(completed.status_code, 200, completed.text)
        self.assertEqual(completed.json()["status"], "PAID")

        replay = self.client.post(
            f"/v1/admin/billing/orders/{order['id']}/complete",
            headers={"X-Admin-Key": "test-admin-key"},
            json={"payment_reference": "bank-transfer-test-1"},
        )
        self.assertEqual(replay.status_code, 200)

        credited = self.client.get("/v1/auth/me", headers=headers).json()
        self.assertEqual(
            credited["credits_balance"],
            starting_balance + order["credits"],
        )

    def test_failed_paid_run_refunds_reserved_credits(self):
        _, headers = self._register("refund@example.com")
        created = self.client.post(
            "/v1/studies",
            headers=headers,
            json={
                "name": "失败退款验证",
                "study_type": "PRODUCT_VALIDATION",
                "plan_code": "STANDARD",
                "product_name": "Test Product",
                "category": "GENERIC_CONSUMER_PRODUCT",
                "price": 499,
            },
        ).json()
        self.client.post(
            f"/v1/studies/{created['id']}/confirm",
            headers=headers,
            json={"overrides": {}},
        )

        with patch.object(
            service,
            "execute_run",
            new=AsyncMock(side_effect=RuntimeError("forced failure")),
        ):
            failed = self.client.post(
                f"/v1/studies/{created['id']}/runs",
                headers=headers,
                json={
                    "study_id": created["id"],
                    "plan_code": "STANDARD",
                    "idempotency_key": "forced-refund-run-1",
                },
            )
        self.assertEqual(failed.status_code, 500, failed.text)
        account = self.client.get("/v1/auth/me", headers=headers).json()
        self.assertEqual(account["credits_balance"], 5)

        transactions = self.client.get(
            "/v1/billing/transactions",
            headers=headers,
        ).json()
        self.assertEqual(
            [item["type"] for item in transactions[:2]],
            ["FAILED_RUN_REFUND", "RUN_RESERVATION"],
        )

    def test_standard_and_professional_charge_real_catalog_costs(self):
        _, headers = self._register("plan-charges@example.com")

        async def fake_report(
            study_id,
            pop_size=None,
            mc_rounds=None,
            seed=None,
            plan_code=None,
        ):
            population = 10_000 if plan_code == "STANDARD" else 30_000
            rounds = 80 if plan_code == "STANDARD" else 150
            return {
                "report_id": f"rpt_charge_{plan_code.lower()}",
                "run_id": f"run_charge_{plan_code.lower()}",
                "study_id": study_id,
                "plan_code": plan_code,
                "population_size": population,
                "mc_rounds": rounds,
            }

        with patch.object(
            service,
            "execute_run",
            new=AsyncMock(side_effect=fake_report),
        ):
            for plan_code, expected_balance in (
                ("STANDARD", 0),
                ("PROFESSIONAL", 0),
            ):
                if plan_code == "PROFESSIONAL":
                    order = self.client.post(
                        "/v1/billing/orders",
                        headers=headers,
                        json={"package_code": "STARTER"},
                    ).json()
                    completed = self.client.post(
                        f"/v1/admin/billing/orders/{order['id']}/complete",
                        headers={"X-Admin-Key": "test-admin-key"},
                        json={
                            "payment_reference": (
                                "catalog-charge-professional-test"
                            )
                        },
                    )
                    self.assertEqual(completed.status_code, 200, completed.text)

                created = self.client.post(
                    "/v1/studies",
                    headers=headers,
                    json={
                        "name": f"{plan_code} 收费验证",
                        "study_type": "PRODUCT_VALIDATION",
                        "plan_code": plan_code,
                        "product_name": "Test Product",
                        "category": "PET_WATER_FOUNTAIN",
                        "price": 1290,
                    },
                ).json()
                self.client.post(
                    f"/v1/studies/{created['id']}/confirm",
                    headers=headers,
                    json={"overrides": {}},
                )
                run = self.client.post(
                    f"/v1/studies/{created['id']}/runs",
                    headers=headers,
                    json={
                        "study_id": created["id"],
                        "plan_code": plan_code,
                        "idempotency_key": (
                            f"catalog-charge-{plan_code.lower()}"
                        ),
                    },
                )
                self.assertEqual(run.status_code, 200, run.text)
                account = self.client.get(
                    "/v1/auth/me",
                    headers=headers,
                ).json()
                self.assertEqual(
                    account["credits_balance"],
                    expected_balance,
                )

        transactions = self.client.get(
            "/v1/billing/transactions",
            headers=headers,
        ).json()
        reservations = [
            item["amount"]
            for item in transactions
            if item["type"] == "RUN_RESERVATION"
        ]
        self.assertEqual(reservations, [-20, -5])


if __name__ == "__main__":
    unittest.main()
