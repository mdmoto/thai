"""Dispatch long-running simulations to a Cloud Run Job."""

from __future__ import annotations

import os
from typing import Any, Dict

import google.auth
import httpx
from google.auth.transport.requests import Request as GoogleAuthRequest


def asynchronous_plan_codes() -> set[str]:
    return {
        item.strip().upper()
        for item in os.environ.get(
            "ASYNC_RUN_PLAN_CODES",
            "",
        ).split(",")
        if item.strip()
    }


def should_dispatch_asynchronously(plan_code: str) -> bool:
    return plan_code.strip().upper() in asynchronous_plan_codes()


def dispatch_run_job(run_job_id: str) -> Dict[str, Any]:
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
    region = os.environ.get(
        "RUN_JOB_REGION",
        os.environ.get("GOOGLE_CLOUD_LOCATION", ""),
    ).strip()
    job_name = os.environ.get("RUN_JOB_NAME", "").strip()
    if not project or not region or not job_name:
        raise RuntimeError("Cloud Run Job dispatch is not configured")

    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    credentials.refresh(GoogleAuthRequest())
    endpoint = (
        "https://run.googleapis.com/v2/projects/"
        f"{project}/locations/{region}/jobs/{job_name}:run"
    )
    response = httpx.post(
        endpoint,
        headers={
            "Authorization": f"Bearer {credentials.token}",
            "Content-Type": "application/json",
        },
        json={
            "overrides": {
                "containerOverrides": [
                    {
                        "env": [
                            {
                                "name": "RUN_JOB_ID",
                                "value": run_job_id,
                            }
                        ]
                    }
                ],
                "taskCount": 1,
                "timeout": "3300s",
            }
        },
        timeout=30.0,
    )
    response.raise_for_status()
    payload = response.json()
    return {
        "operation_name": payload.get("name"),
        "done": bool(payload.get("done", False)),
    }
