#!/usr/bin/env python3
"""
One-shot script: creates the Notion database used by notion-sync.

Usage:
    NOTION_API_KEY=secret_xxx NOTION_PARENT_PAGE_ID=<page-id> python scripts/setup_notion_db.py

After running, paste the printed DATABASE_ID into config/.env.notion-sync
as NOTION_TASKS_DATABASE_ID.

Requirements:
    pip install httpx python-dotenv
"""
from __future__ import annotations

import json
import os
import sys

import httpx

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


DATABASE_SCHEMA = {
    # ---- Required title property (Notion mandates exactly one) ----
    "Name": {
        "title": {}
    },

    # ---- Plain-text fields ----
    "Task ID": {
        "rich_text": {}
    },
    "Description": {
        "rich_text": {}
    },

    # ---- Status of the approval workflow ----
    # Values the notion-sync service reads/writes:
    #   "Awaiting Approval" → pushed by the sync service, awaiting human decision
    #   "Approved"         → human sets this in Notion; sync forwards to supervisor
    #   "Rejected"         → human sets this in Notion; sync forwards to supervisor
    #   "Processing"       → supervisor is currently executing the task
    #   "Completed"        → task finished successfully
    #   "Failed"           → task failed
    "Status": {
        "select": {
            "options": [
                {"name": "Awaiting Approval", "color": "yellow"},
                {"name": "Approved",          "color": "green"},
                {"name": "Rejected",          "color": "red"},
                {"name": "Processing",        "color": "blue"},
                {"name": "Completed",         "color": "purple"},
                {"name": "Failed",            "color": "gray"},
            ]
        }
    },

    # ---- Risk / urgency tier set by the planner agent ----
    # Maps 1:1 to contracts.task.ApprovalTier
    "Approval Tier": {
        "select": {
            "options": [
                {"name": "Low",      "color": "green"},
                {"name": "Medium",   "color": "yellow"},
                {"name": "High",     "color": "orange"},
                {"name": "Critical", "color": "red"},
            ]
        }
    },
}


def create_database(api_key: str, parent_page_id: str) -> dict:
    payload = {
        "parent": {
            "type": "page_id",
            "page_id": parent_page_id,
        },
        "icon": {"type": "emoji", "emoji": "🤖"},
        "title": [
            {
                "type": "text",
                "text": {"content": "AI Task Approvals"},
            }
        ],
        "properties": DATABASE_SCHEMA,
    }

    with httpx.Client(timeout=20.0) as client:
        resp = client.post(
            f"{NOTION_API}/databases",
            headers=headers(api_key),
            json=payload,
        )

    if resp.status_code != 200:
        print(f"[ERROR] {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(1)

    return resp.json()


def main() -> None:
    api_key = os.environ.get("NOTION_API_KEY")
    parent_page_id = os.environ.get("NOTION_PARENT_PAGE_ID")

    if not api_key or not parent_page_id:
        print(
            "Usage: NOTION_API_KEY=secret_xxx NOTION_PARENT_PAGE_ID=<page-id> "
            "python scripts/setup_notion_db.py",
            file=sys.stderr,
        )
        sys.exit(1)

    print("Creating Notion database …")
    db = create_database(api_key, parent_page_id)
    db_id = db["id"]

    print(f"\n✅  Database created!")
    print(f"\n    DATABASE_ID = {db_id}")
    print(f"\nAdd this to config/.env.notion-sync:")
    print(f"\n    NOTION_TASKS_DATABASE_ID={db_id}\n")


if __name__ == "__main__":
    main()
