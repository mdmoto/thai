#!/usr/bin/env python3
"""Fail fast when the ECS runtime database secret differs from RDS.

This release preflight deliberately never prints connection strings or
passwords.  It requires an authenticated AWS CLI profile with permission to
read the two named Secrets Manager secrets and describe the DB instance.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Any
from urllib.parse import unquote, urlsplit


def aws_json(arguments: list[str]) -> Any:
    completed = subprocess.run(
        ["aws", *arguments, "--output", "json"],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def secret_json(secret_id: str, region: str) -> dict[str, Any]:
    payload = aws_json(
        [
            "secretsmanager",
            "get-secret-value",
            "--secret-id",
            secret_id,
            "--version-stage",
            "AWSCURRENT",
            "--region",
            region,
        ]
    )
    return json.loads(payload["SecretString"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", required=True)
    parser.add_argument("--db-instance", required=True)
    parser.add_argument("--runtime-secret", required=True)
    arguments = parser.parse_args()

    try:
        database = aws_json(
            [
                "rds",
                "describe-db-instances",
                "--db-instance-identifier",
                arguments.db_instance,
                "--region",
                arguments.region,
            ]
        )["DBInstances"][0]
        managed_secret_arn = database.get("MasterUserSecret", {}).get("SecretArn")
        if not managed_secret_arn:
            raise RuntimeError("RDS is not configured with a managed master secret")

        runtime = secret_json(arguments.runtime_secret, arguments.region)
        managed = secret_json(managed_secret_arn, arguments.region)
        connection = urlsplit(runtime["DATABASE_URL"])
        checks = {
            "runtime secret has database URL": bool(runtime.get("DATABASE_URL")),
            "database user": connection.username == managed.get("username"),
            "database host": connection.hostname == database["Endpoint"]["Address"],
            "database port": connection.port == database["Endpoint"]["Port"],
            "database password": unquote(connection.password or "") == managed.get("password"),
        }
    except (KeyError, RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"Database credential preflight could not complete: {type(error).__name__}", file=sys.stderr)
        return 2

    failures = [name for name, passed in checks.items() if not passed]
    if failures:
        print("Database credential preflight failed: " + "; ".join(failures), file=sys.stderr)
        print("No connection strings or passwords were printed.", file=sys.stderr)
        return 1

    print("Database credential preflight passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
