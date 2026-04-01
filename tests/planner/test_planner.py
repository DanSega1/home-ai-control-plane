"""Tests for planner memory prompt injection."""

from __future__ import annotations

import asyncio
import importlib
from pathlib import Path
import sys
import types
from unittest.mock import AsyncMock

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

    litellm_module = types.ModuleType("litellm")

    async def acompletion(*args, **kwargs):  # pragma: no cover - replaced in tests
        raise RuntimeError("litellm.acompletion should be mocked in tests")

    settings_module.BaseSettings = BaseSettings
    litellm_module.acompletion = acompletion
    monkeypatch.setitem(sys.modules, "pydantic_settings", settings_module)
    monkeypatch.setitem(sys.modules, "litellm", litellm_module)

    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            sys.modules.pop(name)

    return planner_path


def test_generate_plan_injects_memory_context(planner_app_path: Path, monkeypatch) -> None:
    planner_module = importlib.import_module("app.planner")

    fake_response = type(
        "Response",
        (),
        {
            "choices": [
                type(
                    "Choice",
                    (),
                    {
                        "message": type(
                            "Message",
                            (),
                            {
                                "content": (
                                    '{"steps": [], "estimated_total_tokens": 0, "approval_tier": '
                                    '"low", "risk_level": "low", "requires_snapshot": false, '
                                    '"reasoning": "ok"}'
                                )
                            },
                        )()
                    },
                )()
            ],
            "usage": type("Usage", (), {"total_tokens": 12})(),
            "model": "gpt-4o-mini",
        },
    )()

    acompletion = AsyncMock(return_value=fake_response)
    monkeypatch.setattr(planner_module.litellm, "acompletion", acompletion)
    monkeypatch.setattr(
        planner_module,
        "get_relevant_memory_context",
        AsyncMock(return_value="## Relevant Memory\n1. [conversation] copilot-1.md\nPrefers PKM"),
    )

    result = asyncio.run(planner_module.generate_plan("task-1", "Build memory", "Use memory"))

    assert result["tokens_used"] == 12
    message = acompletion.await_args.kwargs["messages"][1]["content"]
    assert "## Relevant Memory" in message
    assert "Prefers PKM" in message
