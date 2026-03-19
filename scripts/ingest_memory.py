#!/usr/bin/env python3
"""Run the planner memory ingestion job."""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
CONDUCTOR_ENGINE_ROOT = ROOT.parent / "Conductor-Engine"
if CONDUCTOR_ENGINE_ROOT.exists():
    sys.path.insert(0, str(CONDUCTOR_ENGINE_ROOT))
sys.path.insert(0, str(ROOT / "agents" / "planner"))

from app.memory import dumps_ingestion_summary  # noqa: E402
from app.memory_ingest import run_ingestion_job  # noqa: E402


async def _main() -> int:
    stats = await run_ingestion_job()
    print(dumps_ingestion_summary(stats.to_dict()))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
