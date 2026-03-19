"""Tests for planner-side memory retrieval and ingestion."""

from __future__ import annotations

import asyncio
import importlib
from pathlib import Path
import sys
import types

from engine.interfaces.memory import MemoryHit
import pytest


@pytest.fixture
def planner_app_path(monkeypatch) -> Path:
    root = Path(__file__).resolve().parents[2]
    planner_path = root / "agents" / "planner"
    monkeypatch.syspath_prepend(str(planner_path))

    settings_module = types.ModuleType("pydantic_settings")

    class BaseSettings:
        def __init__(self, **kwargs) -> None:
            for name, value in self.__class__.__dict__.items():
                if name.startswith("_") or name == "Config":
                    continue
                if isinstance(value, property) or callable(value):
                    continue
                setattr(self, name, kwargs.get(name, value))

    settings_module.BaseSettings = BaseSettings
    monkeypatch.setitem(sys.modules, "pydantic_settings", settings_module)

    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            sys.modules.pop(name)

    return planner_path


def test_format_memory_context_includes_namespace_and_score(planner_app_path: Path) -> None:
    memory_module = importlib.import_module("app.memory")

    context = memory_module.format_memory_context(
        [
            MemoryHit(
                external_id="conversation:copilot-1.md",
                content="User likes PKM workflows.",
                metadata={"namespace": "conversation", "relative_path": "copilot-1.md"},
                score=0.88,
            )
        ]
    )

    assert context is not None
    assert "## Relevant Memory" in context
    assert "[conversation] copilot-1.md" in context
    assert "User likes PKM workflows." in context


def test_retrieve_relevant_memories_returns_empty_when_disabled(
    planner_app_path: Path, monkeypatch
) -> None:
    memory_module = importlib.import_module("app.memory")
    monkeypatch.setattr(memory_module.settings, "memu_enabled", False)

    hits = asyncio.run(memory_module.retrieve_relevant_memories("Task", "Description"))

    assert hits == []


def test_ingestion_job_is_idempotent(planner_app_path: Path, tmp_path: Path, monkeypatch) -> None:
    ingest_module = importlib.import_module("app.memory_ingest")

    conversation_root = tmp_path / "conversations"
    pkm_root = tmp_path / "pkm"
    manifest_path = tmp_path / "manifest.json"

    conversation_root.mkdir()
    pkm_root.mkdir()
    (conversation_root / "chat.md").write_text("Conversation memory")
    (pkm_root / "notes.md").write_text("PKM memory")

    monkeypatch.setattr(ingest_module.settings, "memu_enabled", True)
    monkeypatch.setattr(ingest_module.settings, "memu_conversation_root", str(conversation_root))
    monkeypatch.setattr(ingest_module.settings, "memu_pkm_root", str(pkm_root))
    monkeypatch.setattr(ingest_module.settings, "memu_manifest_path", str(manifest_path))

    class FakeProvider:
        def __init__(self) -> None:
            self.calls = []

        async def memorize(self, documents):
            self.calls.extend(documents)
            return [{"count": len(documents)}]

    provider = FakeProvider()

    first = asyncio.run(ingest_module.run_ingestion_job(provider=provider))
    second = asyncio.run(ingest_module.run_ingestion_job(provider=provider))

    assert first.to_dict() == {
        "scanned": 2,
        "ingested": 2,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
    }
    assert second.to_dict() == {
        "scanned": 2,
        "ingested": 0,
        "updated": 0,
        "skipped": 2,
        "failed": 0,
    }
    assert len(provider.calls) == 2
