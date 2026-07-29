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
os.environ["ADMIN_USER_EMAILS"] = (
    "admin@example.com,bootstrap-admin@example.com"
)
os.environ["APP_ENV"] = "test"
os.environ["INVITE_CODES_JSON"] = (
    '{"TEST-INVITE":{"credits":5,"source":"AUTOMATED_TEST"}}'
)

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

    def _register(self, email: str, invite_code: str = "TEST-INVITE"):
        response = self.client.post(
            "/v1/auth/register",
            json={
                "email": email,
                "password": "a-secure-test-password",
                "name": "测试客户",
                "company": "Test Brand",
                "invite_code": invite_code,
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

    def test_signup_bonus_requires_valid_invite_and_tracks_source(self):
        no_invite, no_invite_headers = self._register(
            "organic@example.com",
            invite_code="",
        )
        self.assertEqual(no_invite["user"]["credits_balance"], 0)
        self.assertEqual(no_invite["user"]["invite_status"], "NOT_PROVIDED")
        self.assertEqual(
            no_invite["user"]["acquisition_source"],
            "ORGANIC",
        )

        invalid, _ = self._register(
            "invalid-invite@example.com",
            invite_code="NOT-A-REAL-CODE",
        )
        self.assertEqual(invalid["user"]["credits_balance"], 0)
        self.assertEqual(invalid["user"]["invite_status"], "INVALID")

        valid, _ = self._register("valid-invite@example.com")
        self.assertEqual(valid["user"]["credits_balance"], 5)
        self.assertEqual(valid["user"]["invite_status"], "VALID")
        self.assertEqual(
            valid["user"]["acquisition_source"],
            "AUTOMATED_TEST",
        )

        transactions = self.client.get(
            "/v1/billing/transactions",
            headers=no_invite_headers,
        ).json()
        self.assertEqual(transactions, [])

        acquisition = self.client.get(
            "/v1/admin/acquisition/users",
            headers={"X-Admin-Key": "test-admin-key"},
        )
        self.assertEqual(acquisition.status_code, 200)
        tracked = {
            item["email"]: item
            for item in acquisition.json()["users"]
        }
        self.assertEqual(
            tracked["valid-invite@example.com"]["acquisition_source"],
            "AUTOMATED_TEST",
        )

    def test_registration_requires_turnstile_and_email_code_when_enabled(self):
        verification_env = {
            "EMAIL_VERIFICATION_REQUIRED": "true",
            "TURNSTILE_SITE_KEY": "test-site-key",
            "TURNSTILE_SECRET_KEY": "test-secret-key",
            "TURNSTILE_EXPECTED_HOSTNAMES": "testserver",
            "RESEND_API_KEY": "test-resend-key",
            "REGISTRATION_SECURITY_KEY": (
                "test-registration-key-with-more-than-thirty-two-characters"
            ),
            "VERIFICATION_FROM_EMAIL": (
                "Chiang Mai AI Center <verify@auth.lazzor.com>"
            ),
        }
        payload = {
            "email": "verified-registration@example.com",
            "password": "a-secure-test-password",
            "name": "验证客户",
            "company": "Verified Brand",
            "invite_code": "TEST-INVITE",
            "turnstile_token": "valid-test-token",
        }
        with (
            patch.dict(os.environ, verification_env),
            patch(
                "app.services.registration_security.verify_turnstile",
                new=AsyncMock(),
            ) as turnstile,
            patch(
                "app.services.registration_security._send_verification_email",
                new=AsyncMock(),
            ) as sender,
        ):
            config = self.client.get("/v1/auth/config")
            self.assertEqual(
                config.json(),
                {
                    "email_verification_required": True,
                    "turnstile_site_key": "test-site-key",
                },
            )
            bypass = self.client.post(
                "/v1/auth/register",
                json={
                    key: value
                    for key, value in payload.items()
                    if key != "turnstile_token"
                },
            )
            self.assertEqual(bypass.status_code, 403)

            started = self.client.post(
                "/v1/auth/register/verification/start",
                json=payload,
            )
            self.assertEqual(started.status_code, 202, started.text)
            challenge = started.json()
            turnstile.assert_awaited_once()
            sender.assert_awaited_once()
            sent_code = sender.await_args.args[1]
            self.assertRegex(sent_code, r"^\d{6}$")

            wrong = self.client.post(
                "/v1/auth/register/verification/complete",
                json={
                    "challenge_id": challenge["challenge_id"],
                    "code": "999999" if sent_code != "999999" else "888888",
                },
            )
            self.assertEqual(wrong.status_code, 400)

            completed = self.client.post(
                "/v1/auth/register/verification/complete",
                json={
                    "challenge_id": challenge["challenge_id"],
                    "code": sent_code,
                },
            )
            self.assertEqual(completed.status_code, 201, completed.text)
            self.assertEqual(completed.json()["user"]["credits_balance"], 5)

            replay = self.client.post(
                "/v1/auth/register/verification/complete",
                json={
                    "challenge_id": challenge["challenge_id"],
                    "code": sent_code,
                },
            )
            self.assertEqual(replay.status_code, 400)

    def test_registration_rate_limit_is_durable_across_requests(self):
        verification_env = {
            "EMAIL_VERIFICATION_REQUIRED": "true",
            "TURNSTILE_SITE_KEY": "test-site-key",
            "TURNSTILE_SECRET_KEY": "test-secret-key",
            "TURNSTILE_EXPECTED_HOSTNAMES": "testserver",
            "RESEND_API_KEY": "test-resend-key",
            "REGISTRATION_SECURITY_KEY": (
                "test-registration-key-with-more-than-thirty-two-characters"
            ),
            "VERIFICATION_FROM_EMAIL": (
                "Chiang Mai AI Center <verify@auth.lazzor.com>"
            ),
            "REGISTRATION_IP_HOURLY_LIMIT": "1",
            "REGISTRATION_EMAIL_HOURLY_LIMIT": "3",
            "REGISTRATION_SUBNET_DAILY_LIMIT": "10",
        }
        with (
            patch.dict(os.environ, verification_env),
            patch(
                "app.services.registration_security._request_ip",
                return_value="203.0.113.99",
            ),
            patch(
                "app.services.registration_security.verify_turnstile",
                new=AsyncMock(),
            ),
            patch(
                "app.services.registration_security._send_verification_email",
                new=AsyncMock(),
            ),
        ):
            first = self.client.post(
                "/v1/auth/register/verification/start",
                json={
                    "email": "rate-one@example.com",
                    "password": "a-secure-test-password",
                    "name": "Rate One",
                    "turnstile_token": "valid-test-token",
                },
            )
            self.assertEqual(first.status_code, 202, first.text)
            blocked = self.client.post(
                "/v1/auth/register/verification/start",
                json={
                    "email": "rate-two@example.com",
                    "password": "a-secure-test-password",
                    "name": "Rate Two",
                    "turnstile_token": "valid-test-token",
                },
            )
            self.assertEqual(blocked.status_code, 429, blocked.text)

    def test_public_catalog_excludes_internal_plans(self):
        response = self.client.get("/v1/catalog")
        self.assertEqual(response.status_code, 200, response.text)
        catalog = response.json()
        expected = [
            "PREVIEW",
            "STANDARD",
            "BASIC_DECISION",
            "PROFESSIONAL",
        ]
        self.assertEqual(catalog["self_service_plans"], expected)
        self.assertEqual(catalog["assisted_plans"], [])
        self.assertEqual(list(catalog["credit_pricing"]), expected)
        self.assertEqual(list(catalog["plans"]), expected)
        packages = {
            item["code"]: item for item in catalog["packages"]
        }
        self.assertEqual(packages["STARTER"]["bonus_credits"], 10)
        self.assertEqual(packages["GROWTH"]["bonus_credits"], 50)
        self.assertEqual(packages["SCALE"]["bonus_credits"], 200)
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
        self.assertEqual(credited["deep_decision_runs_balance"], 1)

    def test_admin_account_and_dashboard_require_allowlisted_user(self):
        provisioned = self.client.post(
            "/v1/admin/accounts/provision",
            headers={"X-Admin-Key": "test-admin-key"},
            json={
                "email": "bootstrap-admin@example.com",
                "password": "Admin-1!",
                "name": "平台管理员",
            },
        )
        self.assertEqual(provisioned.status_code, 200, provisioned.text)
        self.assertTrue(provisioned.json()["is_admin"])

        login = self.client.post(
            "/v1/auth/login",
            json={
                "email": "bootstrap-admin@example.com",
                "password": "Admin-1!",
            },
        )
        self.assertEqual(login.status_code, 200, login.text)
        admin_headers = {
            "Authorization": f"Bearer {login.json()['access_token']}"
        }
        customer, customer_headers = self._register(
            "admin-dashboard-customer@example.com"
        )
        denied = self.client.get(
            "/v1/admin/dashboard",
            headers=customer_headers,
        )
        self.assertEqual(denied.status_code, 403)

        order = self.client.post(
            "/v1/billing/orders",
            headers=customer_headers,
            json={"package_code": "BASIC_DECISION_SINGLE"},
        ).json()
        completed = self.client.post(
            f"/v1/admin/billing/orders/{order['id']}/complete",
            headers=admin_headers,
            json={"payment_reference": "admin-dashboard-payment"},
        )
        self.assertEqual(completed.status_code, 200, completed.text)

        dashboard = self.client.get(
            "/v1/admin/dashboard",
            headers=admin_headers,
        )
        self.assertEqual(dashboard.status_code, 200, dashboard.text)
        payload = dashboard.json()
        self.assertGreaterEqual(payload["overview"]["total_users"], 2)
        self.assertGreaterEqual(payload["overview"]["paid_orders"], 1)
        tracked = {
            item["email"]: item for item in payload["users"]
        }
        self.assertEqual(
            tracked[customer["user"]["email"]]["order_count"],
            1,
        )
        self.assertTrue(
            any(
                item["action"] == "PAYMENT_CONFIRMED"
                for item in payload["audit_logs"]
            )
        )

    def test_admin_manages_invite_codes_and_preserves_commission_history(self):
        provisioned = self.client.post(
            "/v1/admin/accounts/provision",
            headers={"X-Admin-Key": "test-admin-key"},
            json={
                "email": "bootstrap-admin@example.com",
                "password": "Admin-1!",
                "name": "平台管理员",
            },
        )
        self.assertEqual(provisioned.status_code, 200, provisioned.text)
        login = self.client.post(
            "/v1/auth/login",
            json={
                "email": "bootstrap-admin@example.com",
                "password": "Admin-1!",
            },
        )
        self.assertEqual(login.status_code, 200, login.text)
        admin_headers = {
            "Authorization": f"Bearer {login.json()['access_token']}"
        }

        created = self.client.post(
            "/v1/admin/invite-codes",
            headers=admin_headers,
            json={
                "code": "partner-one",
                "source_name": "清迈合作伙伴",
                "owner_name": "Partner One",
                "owner_contact": "partner@example.com",
                "commission_percent": 12.5,
                "bonus_credits": 5,
                "notes": "按已付款订单结算",
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["code"], "PARTNER-ONE")

        customer, customer_headers = self._register(
            "partner-customer@example.com",
            invite_code="partner-one",
        )
        profile = customer["user"]
        self.assertEqual(profile["credits_balance"], 5)
        self.assertEqual(profile["invite_code"], "PARTNER-ONE")
        self.assertEqual(profile["acquisition_source"], "清迈合作伙伴")
        self.assertEqual(profile["invite_owner"], "Partner One")
        self.assertEqual(profile["invite_commission_percent"], 12.5)

        order = self.client.post(
            "/v1/billing/orders",
            headers=customer_headers,
            json={"package_code": "BASIC_DECISION_SINGLE"},
        ).json()
        completed = self.client.post(
            f"/v1/admin/billing/orders/{order['id']}/complete",
            headers=admin_headers,
            json={"payment_reference": "partner-commission-payment"},
        )
        self.assertEqual(completed.status_code, 200, completed.text)

        dashboard = self.client.get(
            "/v1/admin/dashboard",
            headers=admin_headers,
        )
        self.assertEqual(dashboard.status_code, 200, dashboard.text)
        payload = dashboard.json()
        invite = next(
            item
            for item in payload["invite_codes"]
            if item["code"] == "PARTNER-ONE"
        )
        self.assertEqual(invite["registrations"], 1)
        self.assertEqual(invite["paid_revenue_minor"], 99_000)
        self.assertEqual(invite["commission_due_minor"], 12_375)
        tracked = {
            item["email"]: item for item in payload["users"]
        }
        self.assertEqual(
            tracked["partner-customer@example.com"][
                "referral_commission_minor"
            ],
            12_375,
        )

        deactivated = self.client.delete(
            "/v1/admin/invite-codes/PARTNER-ONE",
            headers=admin_headers,
        )
        self.assertEqual(deactivated.status_code, 200, deactivated.text)
        self.assertFalse(deactivated.json()["active"])

        invalid_after_stop, _ = self._register(
            "partner-after-stop@example.com",
            invite_code="PARTNER-ONE",
        )
        self.assertEqual(
            invalid_after_stop["user"]["invite_status"],
            "INVALID",
        )
        self.assertEqual(invalid_after_stop["user"]["credits_balance"], 0)

        after_stop = self.client.get(
            "/v1/admin/dashboard",
            headers=admin_headers,
        ).json()
        historical = {
            item["email"]: item for item in after_stop["users"]
        }
        self.assertEqual(
            historical["partner-customer@example.com"]["invite_owner"],
            "Partner One",
        )
        stopped_code = next(
            item
            for item in after_stop["invite_codes"]
            if item["code"] == "PARTNER-ONE"
        )
        self.assertFalse(stopped_code["active"])
        self.assertEqual(stopped_code["commission_due_minor"], 12_375)

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
            self.assertIsNone(
                pop_size,
                "自助套餐必须忽略客户端人口参数并使用固定产品规格",
            )
            population = 5_000 if plan_code == "STANDARD" else 300_000
            rounds = 80 if plan_code == "STANDARD" else 220
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
                ("PROFESSIONAL", 10),
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
                        "population_size": 123,
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
        self.assertEqual(reservations, [-5])

    def test_basic_decision_package_grants_one_run_and_one_bonus_credit(self):
        account, headers = self._register("basic-decision@example.com")
        starting_credits = account["user"]["credits_balance"]
        order = self.client.post(
            "/v1/billing/orders",
            headers=headers,
            json={"package_code": "BASIC_DECISION_SINGLE"},
        ).json()
        self.assertEqual(order["amount_minor"], 99_000)
        self.assertEqual(order["bonus_credits"], 1)
        self.assertEqual(order["run_entitlements"], {"BASIC_DECISION": 1})

        completed = self.client.post(
            f"/v1/admin/billing/orders/{order['id']}/complete",
            headers={"X-Admin-Key": "test-admin-key"},
            json={"payment_reference": "basic-decision-payment-test"},
        )
        self.assertEqual(completed.status_code, 200, completed.text)
        profile = self.client.get("/v1/auth/me", headers=headers).json()
        self.assertEqual(profile["credits_balance"], starting_credits + 1)
        self.assertEqual(profile["basic_decision_runs_balance"], 1)

        study = self.client.post(
            "/v1/studies",
            headers=headers,
            json={
                "name": "基础决策真实运行验证",
                "study_type": "PRODUCT_VALIDATION",
                "plan_code": "BASIC_DECISION",
                "product_name": "Test Product",
                "category": "GENERIC_CONSUMER_PRODUCT",
                "price": 990,
            },
        ).json()
        confirmed = self.client.post(
            f"/v1/studies/{study['id']}/confirm",
            headers=headers,
            json={"overrides": {}},
        )
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        disabled_ai = {
            "GEMINI_API_KEY_PRIMARY": "",
            "GEMINI_API_KEY_SECONDARY": "",
            "GEMINI_API_KEY": "",
            "GEMINI_VERTEX_FALLBACK": "false",
        }
        with patch.dict(os.environ, disabled_ai):
            run = self.client.post(
                f"/v1/studies/{study['id']}/runs",
                headers=headers,
                json={
                    "study_id": study["id"],
                    "plan_code": "BASIC_DECISION",
                    "population_size": 123,
                    "idempotency_key": "basic-decision-real-run-test",
                },
            )
        self.assertEqual(run.status_code, 200, run.text)
        self.assertEqual(run.json()["plan_code"], "BASIC_DECISION")
        self.assertEqual(run.json()["population_size"], 20_000)
        after_run = self.client.get("/v1/auth/me", headers=headers).json()
        self.assertEqual(after_run["basic_decision_runs_balance"], 0)


if __name__ == "__main__":
    unittest.main()
