#!/usr/bin/env python3
"""Phase 1 E2E smoke test against the running Supervisor API.

Flow:
1. Check supervisor health
2. Create task
3. Wait for planning to finish
4. Approve task (if awaiting approval)
5. Wait for terminal status
6. Verify result persistence for executed tasks
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import sys
import time
from typing import Any

import httpx

TERMINAL_STATUSES = {"completed", "failed", "policy_denied", "rejected", "cancelled"}
EXECUTED_TERMINAL_STATUSES = {"completed", "failed"}


@dataclass
class SmokeConfig:
    base_url: str
    requestor: str
    approval_tier: str
    timeout_seconds: int
    poll_interval_seconds: float
    allow_policy_denied: bool


class SmokeError(RuntimeError):
    """Raised when smoke verification fails."""


def _url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}{path}"


def _request(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = client.request(method, url, json=json_body)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise SmokeError(f"Expected JSON object from {url}, got: {type(data).__name__}")
    return data


def _wait_for_status(
    client: httpx.Client,
    base_url: str,
    task_id: str,
    target_statuses: set[str],
    timeout_seconds: int,
    poll_interval_seconds: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_status = "unknown"

    while time.time() < deadline:
        task = _request(client, "GET", _url(base_url, f"/tasks/{task_id}"))
        status = str(task.get("status", "unknown"))
        last_status = status
        if status in target_statuses:
            return task
        time.sleep(poll_interval_seconds)

    raise SmokeError(
        f"Timed out waiting for status in {sorted(target_statuses)} for task {task_id}. "
        f"Last status: {last_status}"
    )


def run_smoke(config: SmokeConfig) -> None:
    title = f"smoke-{int(time.time())}"
    description = "Phase 1 smoke test task"

    with httpx.Client(timeout=30.0) as client:
        health = _request(client, "GET", _url(config.base_url, "/health"))
        if health.get("status") != "ok":
            raise SmokeError(f"Supervisor health check failed: {health}")

        created = _request(
            client,
            "POST",
            _url(config.base_url, "/tasks"),
            json_body={
                "title": title,
                "description": description,
                "requestor": config.requestor,
                "approval_tier": config.approval_tier,
            },
        )

        task_id = str(created.get("task_id", "")).strip()
        if not task_id:
            raise SmokeError(f"Create task response missing task_id: {json.dumps(created)}")

        task = _wait_for_status(
            client,
            config.base_url,
            task_id,
            {
                "awaiting_approval",
                "approved",
                "executing",
                "completed",
                "failed",
                "policy_denied",
            },
            config.timeout_seconds,
            config.poll_interval_seconds,
        )

        if task.get("status") == "awaiting_approval":
            _request(client, "POST", _url(config.base_url, f"/tasks/{task_id}/approve"))

        final_task = _wait_for_status(
            client,
            config.base_url,
            task_id,
            TERMINAL_STATUSES,
            config.timeout_seconds,
            config.poll_interval_seconds,
        )

    final_status = str(final_task.get("status", "unknown"))
    if final_status == "policy_denied" and not config.allow_policy_denied:
        raise SmokeError("Task ended in policy_denied (set --allow-policy-denied to allow this)")

    if final_status in EXECUTED_TERMINAL_STATUSES:
        result = final_task.get("result")
        if not isinstance(result, dict):
            raise SmokeError(
                "Expected task.result to be persisted for executed terminal states; got none"
            )

    summary = {
        "task_id": final_task.get("task_id"),
        "status": final_status,
        "approval_tier": final_task.get("approval_tier"),
        "total_tokens_used": final_task.get("total_tokens_used"),
        "has_result": isinstance(final_task.get("result"), dict),
    }
    print(json.dumps(summary, indent=2))


def parse_args() -> SmokeConfig:
    parser = argparse.ArgumentParser(description="Run Phase 1 smoke test")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--requestor", default="smoke-test")
    parser.add_argument(
        "--approval-tier", default="high", choices=["low", "medium", "high", "critical"]
    )
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--poll-interval-seconds", type=float, default=2.0)
    parser.add_argument("--allow-policy-denied", action="store_true")
    args = parser.parse_args()

    return SmokeConfig(
        base_url=args.base_url,
        requestor=args.requestor,
        approval_tier=args.approval_tier,
        timeout_seconds=args.timeout_seconds,
        poll_interval_seconds=args.poll_interval_seconds,
        allow_policy_denied=args.allow_policy_denied,
    )


def main() -> int:
    try:
        config = parse_args()
        run_smoke(config)
        return 0
    except (httpx.HTTPError, SmokeError) as exc:
        print(f"[e2e-smoke] FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
