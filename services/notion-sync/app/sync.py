"""
Bidirectional sync loop.

Every poll_interval_seconds:
  1. Ask Supervisor for tasks in AWAITING_APPROVAL that have no Notion page yet
     → create Notion pages for them.
  2. Ask Notion for pages with status Approved or Rejected
     → call Supervisor approve/reject endpoint.
"""
from __future__ import annotations

import asyncio
import logging

import httpx

from app.config import settings
from app.notion_client import (
    create_task_page,
    query_awaiting_approval_tasks,
    update_page_status,
)

log = logging.getLogger("notion-sync.sync")

# In-memory set of task_ids we've already pushed to Notion
# (in production this would be persisted in Mongo)
_synced_to_notion: set[str] = set()
_processed_approvals: set[str] = set()


async def _sync_pending_to_notion() -> None:
    """Push AWAITING_APPROVAL tasks to Notion if not yet created."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.supervisor_url}/tasks",
                params={"status": "awaiting_approval", "limit": 50},
            )
            resp.raise_for_status()
            tasks = resp.json()
    except Exception as exc:
        log.error("Failed to fetch tasks from supervisor: %s", exc)
        return

    for task in tasks:
        task_id = task["task_id"]
        if task_id in _synced_to_notion:
            continue
        if task.get("notion_page_id"):
            _synced_to_notion.add(task_id)
            continue

        try:
            page_id = await create_task_page(
                task_id=task_id,
                title=task["title"],
                description=task.get("description", ""),
                approval_tier=task.get("approval_tier", "high"),
            )
            # Persist the notion_page_id back to the supervisor
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.patch(
                    f"{settings.supervisor_url}/tasks/{task_id}",
                    json={"notion_page_id": page_id},
                )
            _synced_to_notion.add(task_id)
            log.info("Task %s synced to Notion page %s", task_id, page_id)
        except Exception as exc:
            log.error("Failed to create Notion page for task %s: %s", task_id, exc)


async def _sync_approvals_from_notion() -> None:
    """Poll Notion for human decisions and propagate to Supervisor."""
    try:
        approved_pages = await query_awaiting_approval_tasks()
    except Exception as exc:
        log.error("Failed to query Notion: %s", exc)
        return

    for item in approved_pages:
        task_id = item["task_id"]
        if task_id in _processed_approvals:
            continue

        notion_status = item["notion_status"]
        endpoint = "approve" if notion_status == "Approved" else "reject"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{settings.supervisor_url}/tasks/{task_id}/{endpoint}"
                )
                resp.raise_for_status()

            _processed_approvals.add(task_id)
            log.info("Task %s %s via Notion", task_id, endpoint + "d")

            # Update page to reflect the system processed it
            final_status = "Processing" if endpoint == "approve" else "Rejected – Processed"
            await update_page_status(item["page_id"], final_status)

        except Exception as exc:
            log.error("Failed to propagate %s for task %s: %s", endpoint, task_id, exc)


async def run_sync_loop() -> None:
    """Main background loop."""
    log.info("Sync loop started")
    while True:
        await _sync_pending_to_notion()
        await _sync_approvals_from_notion()
        await asyncio.sleep(settings.poll_interval_seconds)
