"""
Home AI Control Plane – Notion Sync
Polls the Supervisor for tasks needing Notion cards,
and polls Notion for approval status changes.
"""
import asyncio
import logging

from fastapi import FastAPI

from app.config import settings
from app.sync import run_sync_loop

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("notion-sync")

app = FastAPI(title="Home AI – Notion Sync", version="0.1.0")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "notion-sync"}


@app.on_event("startup")
async def startup() -> None:
    log.info("Notion Sync starting – poll interval %ds", settings.poll_interval_seconds)
    asyncio.create_task(run_sync_loop())
