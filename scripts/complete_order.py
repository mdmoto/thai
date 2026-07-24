#!/usr/bin/env python3
"""Confirm one externally verified payment through the protected API."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Grant credits for one verified Market Twin order.",
    )
    parser.add_argument("--order-id", required=True)
    parser.add_argument("--payment-reference", required=True)
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required safety switch after verifying funds.",
    )
    args = parser.parse_args()

    if not args.confirm:
        parser.error(
            "Refusing to change an order without --confirm after funds are verified."
        )
    api_url = os.environ.get("MARKET_TWIN_API_URL", "").rstrip("/")
    admin_key = os.environ.get("MARKET_TWIN_ADMIN_API_KEY", "")
    if not api_url or not admin_key:
        parser.error(
            "MARKET_TWIN_API_URL and MARKET_TWIN_ADMIN_API_KEY are required."
        )

    url = f"{api_url}/v1/admin/billing/orders/{args.order_id}/complete"
    body = json.dumps(
        {"payment_reference": args.payment_reference},
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Admin-Key": admin_key,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        message = error.read().decode("utf-8", errors="replace")
        print(f"Order completion failed ({error.code}): {message}", file=sys.stderr)
        return 1
    except urllib.error.URLError as error:
        print(f"Order completion failed: {error.reason}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "order_id": result.get("id"),
                "status": result.get("status"),
                "credits": result.get("credits"),
                "payment_reference": result.get("payment_reference"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
