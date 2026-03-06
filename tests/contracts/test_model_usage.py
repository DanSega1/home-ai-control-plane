"""Tests for contracts/model_usage.py — LLM usage tracking models."""

from __future__ import annotations

import pytest

from contracts.model_usage import BudgetStatus, ModelUsageRecord


class TestModelUsageRecord:
    def test_defaults(self) -> None:
        record = ModelUsageRecord(agent="planner", model="gpt-4o-mini")
        assert record.task_id is None
        assert record.prompt_tokens == 0
        assert record.completion_tokens == 0
        assert record.total_tokens == 0
        assert record.cost_usd == 0.0

    def test_record_id_auto_generated(self) -> None:
        r1 = ModelUsageRecord(agent="planner", model="gpt-4o-mini")
        r2 = ModelUsageRecord(agent="planner", model="gpt-4o-mini")
        assert r1.record_id != r2.record_id

    def test_with_token_counts(self) -> None:
        record = ModelUsageRecord(
            agent="planner",
            model="gpt-4o-mini",
            prompt_tokens=500,
            completion_tokens=200,
            total_tokens=700,
            cost_usd=0.0014,
        )
        assert record.total_tokens == 700
        assert record.cost_usd == pytest.approx(0.0014)

    def test_serialization_roundtrip(self) -> None:
        record = ModelUsageRecord(
            task_id="task-123",
            agent="planner",
            model="gpt-4o-mini",
            total_tokens=300,
        )
        data = record.model_dump(mode="json")
        restored = ModelUsageRecord(**data)
        assert restored.record_id == record.record_id
        assert restored.task_id == "task-123"


class TestBudgetStatus:
    def test_within_budget(self) -> None:
        status = BudgetStatus(
            month="2026-03",
            tokens_used=100_000,
            tokens_limit=500_000,
            cost_usd=2.0,
            cost_limit_usd=10.0,
            remaining_tokens=400_000,
            remaining_cost_usd=8.0,
            budget_exceeded=False,
        )
        assert status.budget_exceeded is False
        assert status.remaining_tokens == 400_000

    def test_exceeded_by_tokens(self) -> None:
        status = BudgetStatus(
            month="2026-03",
            tokens_used=500_001,
            tokens_limit=500_000,
            cost_usd=5.0,
            cost_limit_usd=10.0,
            remaining_tokens=0,
            remaining_cost_usd=5.0,
            budget_exceeded=True,
        )
        assert status.budget_exceeded is True

    def test_exceeded_by_cost(self) -> None:
        status = BudgetStatus(
            month="2026-03",
            tokens_used=10_000,
            tokens_limit=500_000,
            cost_usd=10.01,
            cost_limit_usd=10.0,
            remaining_tokens=490_000,
            remaining_cost_usd=0.0,
            budget_exceeded=True,
        )
        assert status.budget_exceeded is True

    def test_month_format(self) -> None:
        status = BudgetStatus(
            month="2026-03",
            tokens_used=0,
            tokens_limit=500_000,
            cost_usd=0.0,
            cost_limit_usd=10.0,
            remaining_tokens=500_000,
            remaining_cost_usd=10.0,
            budget_exceeded=False,
        )
        assert status.month == "2026-03"
