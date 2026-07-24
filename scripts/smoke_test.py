#!/usr/bin/env python3
"""Run the non-destructive production acceptance flow against one API."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple


def request_json(
    api_url: str,
    method: str,
    path: str,
    payload: Optional[Dict[str, Any]] = None,
    token: Optional[str] = None,
    admin_key: Optional[str] = None,
) -> Tuple[int, Dict[str, Any]]:
    headers = {
        "Accept": "application/json",
        "X-Request-ID": f"production-smoke-{secrets.token_hex(8)}",
    }
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if admin_key:
        headers["X-Admin-Key"] = admin_key
    request = urllib.request.Request(
        f"{api_url}{path}",
        data=(
            json.dumps(payload).encode("utf-8")
            if payload is not None
            else None
        ),
        method=method,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=900) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"detail": body}
        return error.code, parsed


def expect(
    actual: Any,
    expected: Any,
    message: str,
) -> None:
    if actual != expected:
        raise RuntimeError(
            f"{message}: expected {expected!r}, received {actual!r}"
        )


def register(
    api_url: str,
    email: str,
    password: str,
) -> Tuple[str, Dict[str, Any]]:
    status, body = request_json(
        api_url,
        "POST",
        "/v1/auth/register",
        {
            "email": email,
            "password": password,
            "name": "Production Smoke Test",
            "company": "Lazzor QA",
        },
    )
    expect(status, 201, "registration failed")
    expect(body["user"]["credits_balance"], 5, "signup credit mismatch")
    return body["access_token"], body["user"]


def create_and_run(
    api_url: str,
    token: str,
    plan_code: str,
    suffix: str,
) -> Dict[str, Any]:
    status, study = request_json(
        api_url,
        "POST",
        "/v1/studies",
        {
            "name": f"Production smoke {plan_code} {suffix}",
            "study_type": "PRODUCT_VALIDATION",
            "plan_code": plan_code,
            "product_name": "QuietFlow Smoke Fixture",
            "category": "PET_WATER_FOUNTAIN",
            "price": 1290,
            "selling_points": ["quiet pump", "local warranty"],
        },
        token=token,
    )
    expect(status, 201, f"{plan_code} study creation failed")

    status, _ = request_json(
        api_url,
        "POST",
        f"/v1/studies/{study['id']}/confirm",
        {"overrides": {}},
        token=token,
    )
    expect(status, 200, f"{plan_code} study confirmation failed")

    run_payload = {
        "study_id": study["id"],
        "plan_code": plan_code,
        "idempotency_key": f"production-smoke-{plan_code.lower()}-{suffix}",
    }
    status, report = request_json(
        api_url,
        "POST",
        f"/v1/studies/{study['id']}/runs",
        run_payload,
        token=token,
    )
    expect(status, 200, f"{plan_code} run failed")
    expect(report["plan_code"], plan_code, f"{plan_code} report mismatch")
    expect(
        report["category_key"],
        "PET_WATER_FOUNTAIN",
        f"{plan_code} category mismatch",
    )

    status, replay = request_json(
        api_url,
        "POST",
        f"/v1/studies/{study['id']}/runs",
        run_payload,
        token=token,
    )
    expect(status, 200, f"{plan_code} replay failed")
    expect(
        replay["report_id"],
        report["report_id"],
        f"{plan_code} idempotency failed",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api-url",
        default=os.environ.get("MARKET_TWIN_API_URL", ""),
    )
    parser.add_argument(
        "--admin-key",
        default=os.environ.get("MARKET_TWIN_ADMIN_API_KEY", ""),
        help="Optional: also verify paid-order completion and idempotency.",
    )
    args = parser.parse_args()
    api_url = args.api_url.rstrip("/")
    if not api_url.startswith("https://"):
        parser.error("--api-url must be a production HTTPS URL")

    status, health = request_json(api_url, "GET", "/v1/health")
    expect(status, 200, "health check failed")
    expect(health.get("database"), "connected", "database is not connected")
    status, catalog = request_json(api_url, "GET", "/v1/catalog")
    expect(status, 200, "catalog request failed")
    expect(
        catalog.get("self_service_plans"),
        ["PREVIEW", "STANDARD", "PROFESSIONAL"],
        "public plan catalog mismatch",
    )

    suffix = f"{int(time.time())}-{secrets.token_hex(3)}"
    password = f"Smoke-{secrets.token_urlsafe(20)}"
    owner_token, _ = register(
        api_url,
        f"smoke-owner-{suffix}@example.invalid",
        password,
    )
    other_token, _ = register(
        api_url,
        f"smoke-other-{suffix}@example.invalid",
        password,
    )

    preview = create_and_run(api_url, owner_token, "PREVIEW", suffix)
    status, _ = request_json(
        api_url,
        "GET",
        f"/v1/reports/{preview['report_id']}",
        token=other_token,
    )
    expect(status, 404, "cross-account report isolation failed")

    standard = create_and_run(api_url, owner_token, "STANDARD", suffix)
    expect(standard["population_size"], 10_000, "Standard sample mismatch")
    status, profile = request_json(
        api_url,
        "GET",
        "/v1/auth/me",
        token=owner_token,
    )
    expect(status, 200, "profile read failed")
    expect(profile["credits_balance"], 0, "Standard credit charge mismatch")

    status, order = request_json(
        api_url,
        "POST",
        "/v1/billing/orders",
        {"package_code": "STARTER"},
        token=owner_token,
    )
    expect(status, 201, "order creation failed")
    expect(order["status"], "PENDING_PAYMENT", "new order status mismatch")

    if args.admin_key:
        payment_reference = f"SMOKE-{suffix}"
        for _ in range(2):
            status, completed = request_json(
                api_url,
                "POST",
                f"/v1/admin/billing/orders/{order['id']}/complete",
                {"payment_reference": payment_reference},
                admin_key=args.admin_key,
            )
            expect(status, 200, "verified order completion failed")
            expect(completed["status"], "PAID", "paid order status mismatch")
        status, profile = request_json(
            api_url,
            "GET",
            "/v1/auth/me",
            token=owner_token,
        )
        expect(status, 200, "credited profile read failed")
        expect(profile["credits_balance"], 20, "order credit mismatch")

    print(
        json.dumps(
            {
                "status": "ok",
                "api_url": api_url,
                "database": health.get("database"),
                "preview_report_id": preview["report_id"],
                "standard_report_id": standard["report_id"],
                "cross_account_isolation": "passed",
                "idempotency": "passed",
                "order_status": (
                    "paid_once"
                    if args.admin_key
                    else "pending_without_credit"
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
