"""Dispatch long-running simulations to a Cloud Run Job."""

from __future__ import annotations

import os
import re
from typing import Any, Dict

import google.auth
import httpx
from google.auth.transport.requests import Request as GoogleAuthRequest


_EXECUTION_NAME_PATTERN = re.compile(
    r"projects/[^/]+/locations/[^/]+/jobs/[^/]+/executions/[^/]+"
)


def _execution_name_from_operation(payload: Any) -> str | None:
    """Find the immutable Execution resource in a Run operation payload."""

    if isinstance(payload, str):
        match = _EXECUTION_NAME_PATTERN.search(payload)
        return match.group(0) if match else None
    if isinstance(payload, dict):
        for value in payload.values():
            found = _execution_name_from_operation(value)
            if found:
                return found
    if isinstance(payload, list):
        for value in payload:
            found = _execution_name_from_operation(value)
            if found:
                return found
    return None


def _authorized_headers() -> dict[str, str]:
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    credentials.refresh(GoogleAuthRequest())
    return {
        "Authorization": f"Bearer {credentials.token}",
        "Content-Type": "application/json",
    }


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


def _dispatch_backend() -> str:
    """Return the configured durable-run provider.

    Existing Google deployments remain the default. AWS uses an ECS task per
    deep run so expensive simulation workers are not kept alive between jobs.
    """

    return os.environ.get("RUN_DISPATCH_BACKEND", "gcp_cloud_run").strip().lower()


def _csv_env(name: str) -> list[str]:
    values = [item.strip() for item in os.environ.get(name, "").split(",")]
    return [item for item in values if item]


def _dispatch_aws_ecs_run(run_job_id: str) -> Dict[str, Any]:
    """Start one Fargate worker task for an immutable queued run."""

    try:
        import boto3
    except ImportError as error:  # pragma: no cover - deployment packaging guard
        raise RuntimeError("AWS ECS dispatcher dependency is not installed") from error

    cluster = os.environ.get("AWS_ECS_CLUSTER", "").strip()
    task_definition = os.environ.get("AWS_ECS_TASK_DEFINITION", "").strip()
    subnets = _csv_env("AWS_ECS_SUBNETS")
    security_groups = _csv_env("AWS_ECS_SECURITY_GROUPS")
    if not cluster or not task_definition or not subnets or not security_groups:
        raise RuntimeError("AWS ECS task dispatch is not configured")

    response = boto3.client("ecs").run_task(
        cluster=cluster,
        taskDefinition=task_definition,
        launchType="FARGATE",
        platformVersion="LATEST",
        count=1,
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": subnets,
                "securityGroups": security_groups,
                "assignPublicIp": os.environ.get(
                    "AWS_ECS_ASSIGN_PUBLIC_IP", "ENABLED"
                ).strip().upper(),
            }
        },
        overrides={
            "containerOverrides": [
                {
                    "name": "runner",
                    "environment": [
                        {"name": "RUN_JOB_ID", "value": run_job_id}
                    ],
                }
            ]
        },
        startedBy=f"market-twin:{run_job_id}"[:36],
    )
    failures = response.get("failures") or []
    tasks = response.get("tasks") or []
    if failures or not tasks:
        reason = "; ".join(
            str(item.get("reason") or item) for item in failures
        )
        raise RuntimeError(f"AWS ECS task launch failed: {reason or 'no task returned'}")
    task_arn = str(tasks[0].get("taskArn") or "")
    if not task_arn:
        raise RuntimeError("AWS ECS task launch returned no task ARN")
    return {
        "operation_name": task_arn,
        "execution_name": task_arn,
        "done": False,
    }


def dispatch_run_job(run_job_id: str) -> Dict[str, Any]:
    if _dispatch_backend() == "aws_ecs":
        return _dispatch_aws_ecs_run(run_job_id)

    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
    region = os.environ.get(
        "RUN_JOB_REGION",
        os.environ.get("GOOGLE_CLOUD_LOCATION", ""),
    ).strip()
    job_name = os.environ.get("RUN_JOB_NAME", "").strip()
    if not project or not region or not job_name:
        raise RuntimeError("Cloud Run Job dispatch is not configured")

    endpoint = (
        "https://run.googleapis.com/v2/projects/"
        f"{project}/locations/{region}/jobs/{job_name}:run"
    )
    response = httpx.post(
        endpoint,
        headers=_authorized_headers(),
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
        "execution_name": _execution_name_from_operation(payload),
        "done": bool(payload.get("done", False)),
    }


def cancel_run_execution(provider_reference: str | None) -> bool:
    """Best-effort cancellation of the actual Cloud Run Job Execution.

    The jobs.run endpoint returns a long-running Operation.  Depending on its
    state, the Execution name may already be embedded in operation metadata;
    otherwise this function refreshes that operation once before cancelling.
    """

    reference = str(provider_reference or "").strip()
    if not reference:
        return False
    if _dispatch_backend() == "aws_ecs":
        try:
            import boto3
        except ImportError as error:  # pragma: no cover - packaging guard
            raise RuntimeError("AWS ECS dispatcher dependency is not installed") from error
        cluster = os.environ.get("AWS_ECS_CLUSTER", "").strip()
        if not cluster:
            raise RuntimeError("AWS ECS task cancellation is not configured")
        boto3.client("ecs").stop_task(
            cluster=cluster,
            task=reference,
            reason="Cancelled by Thailand Market Twin user",
        )
        return True
    headers = _authorized_headers()
    execution_name = _execution_name_from_operation(reference)
    if execution_name is None and "/operations/" in reference:
        operation_response = httpx.get(
            f"https://run.googleapis.com/v2/{reference}",
            headers=headers,
            timeout=10.0,
        )
        operation_response.raise_for_status()
        execution_name = _execution_name_from_operation(
            operation_response.json()
        )
    if execution_name is None:
        return False
    response = httpx.post(
        f"https://run.googleapis.com/v2/{execution_name}:cancel",
        headers=headers,
        json={},
        timeout=10.0,
    )
    response.raise_for_status()
    return True
