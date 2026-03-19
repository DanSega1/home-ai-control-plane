"""Planner-facing memory retrieval helpers."""

from __future__ import annotations

import json
import logging

from engine.interfaces.memory import MemoryHit, MemoryProvider, MemoryQuery
from engine.memory.providers.memu import MemUProvider

from app.config import settings

log = logging.getLogger("planner.memory")


def build_memory_provider() -> MemoryProvider:
    return MemUProvider(
        service_config=settings.memu_service_config,
        scope={"user_id": settings.memu_scope_user_id},
    )


async def retrieve_relevant_memories(
    title: str,
    description: str,
    provider: MemoryProvider | None = None,
) -> list[MemoryHit]:
    if not settings.memu_enabled:
        return []

    memory_provider = provider or build_memory_provider()

    try:
        return await memory_provider.retrieve(
            MemoryQuery(
                query=f"{title}\n\n{description}".strip(),
                namespaces=["conversation", "pkm"],
                limit=settings.memu_top_k,
            )
        )
    except Exception as exc:
        log.warning("Memory retrieval unavailable; continuing without memory context: %s", exc)
        return []


def format_memory_context(hits: list[MemoryHit]) -> str | None:
    if not hits:
        return None

    lines = ["## Relevant Memory"]
    for index, hit in enumerate(hits, start=1):
        namespace = str(hit.metadata.get("namespace", "unknown"))
        source = str(hit.metadata.get("relative_path", hit.external_id))
        score = f" (score={hit.score:.3f})" if hit.score is not None else ""

        lines.append(f"{index}. [{namespace}] {source}{score}")
        lines.append(hit.content.strip())

    return "\n".join(lines)


async def get_relevant_memory_context(
    title: str,
    description: str,
    provider: MemoryProvider | None = None,
) -> str | None:
    hits = await retrieve_relevant_memories(title, description, provider=provider)
    return format_memory_context(hits)


def dumps_ingestion_summary(summary: dict[str, int]) -> str:
    return json.dumps(summary, indent=2, sort_keys=True)
