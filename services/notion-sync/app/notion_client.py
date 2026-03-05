"""
Thin async wrapper around the Notion API v1.
https://developers.notion.com/reference/intro
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger("notion-sync.notion")

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.notion_api_key}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Pages / tasks
# ---------------------------------------------------------------------------


async def create_task_page(task_id: str, title: str, description: str, approval_tier: str) -> str:
    """Create a Notion page in the tasks DB. Returns the Notion page ID."""
    payload = {
        "parent": {"database_id": settings.notion_tasks_database_id},
        "properties": {
            "Name": {"title": [{"text": {"content": title}}]},
            "Task ID": {"rich_text": [{"text": {"content": task_id}}]},
            "Status": {"select": {"name": "Awaiting Approval"}},
            "Approval Tier": {"select": {"name": approval_tier.replace("_", " ").title()}},
        },
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": description}}]},
            }
        ],
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(f"{NOTION_API}/pages", headers=_headers(), json=payload)
        resp.raise_for_status()
        data = resp.json()

    page_id = data["id"]
    log.info("Notion page created for task %s: %s", task_id, page_id)
    return page_id


async def get_page_status(page_id: str) -> str | None:
    """Fetch the Status select value of a Notion page."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{NOTION_API}/pages/{page_id}", headers=_headers())
        resp.raise_for_status()
        data = resp.json()

    status_prop = data.get("properties", {}).get("Status", {})
    select = status_prop.get("select")
    return select.get("name") if select else None


async def query_awaiting_approval_tasks() -> list[dict[str, Any]]:
    """
    Query the Notion DB for pages that have been manually set to
    'Approved' or 'Rejected' so we can propagate the decision.
    """
    payload = {
        "filter": {
            "or": [
                {"property": "Status", "select": {"equals": "Approved"}},
                {"property": "Status", "select": {"equals": "Rejected"}},
            ]
        }
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{NOTION_API}/databases/{settings.notion_tasks_database_id}/query",
            headers=_headers(),
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for page in data.get("results", []):
        props = page.get("properties", {})
        task_id_prop = props.get("Task ID", {}).get("rich_text", [])
        status_prop = props.get("Status", {}).get("select", {})
        if task_id_prop:
            results.append(
                {
                    "page_id": page["id"],
                    "task_id": task_id_prop[0]["text"]["content"],
                    "notion_status": status_prop.get("name", ""),
                }
            )
    return results


async def update_page_status(page_id: str, status: str) -> None:
    """Update the Status property of a Notion page."""
    payload = {"properties": {"Status": {"select": {"name": status}}}}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.patch(f"{NOTION_API}/pages/{page_id}", headers=_headers(), json=payload)
        resp.raise_for_status()
    log.info("Notion page %s status updated to %s", page_id, status)
