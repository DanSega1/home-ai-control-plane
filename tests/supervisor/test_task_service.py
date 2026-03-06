"""Tests for supervisor/app/services/task_service.py — orchestration logic."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from contracts.task import (
    ApprovalTier,
    CreateTaskRequest,
    ExecutionPlan,
    ExecutionStep,
    RiskLevel,
    Task,
    TaskStatus,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task(**kwargs: Any) -> Task:
    defaults = {"title": "Save bookmark", "description": "Save URL to Raindrop"}
    return Task(**{**defaults, **kwargs})


def _make_plan(**kwargs: Any) -> ExecutionPlan:
    step = ExecutionStep(skill="raindrop-io", action="Save", estimated_tokens=100)
    defaults = {
        "steps": [step],
        "estimated_total_tokens": 100,
        "risk_level": RiskLevel.LOW,
        "approval_tier": ApprovalTier.HIGH,
    }
    return ExecutionPlan(**{**defaults, **kwargs})


# ---------------------------------------------------------------------------
# _get_budget_status
# ---------------------------------------------------------------------------


class TestGetBudgetStatus:
    @pytest.mark.asyncio
    async def test_returns_zero_usage_when_no_records(self) -> None:
        from services.supervisor.app.services import task_service

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=MagicMock())
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[])
        mock_db["model_usage"].aggregate.return_value = mock_cursor

        with patch.object(task_service, "get_db", return_value=mock_db):
            budget = await task_service._get_budget_status()

        assert budget.tokens_used == 0
        assert budget.cost_usd == 0.0
        assert budget.budget_exceeded is False

    @pytest.mark.asyncio
    async def test_returns_aggregated_usage(self) -> None:
        from services.supervisor.app.services import task_service

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[{"tokens_used": 10_000, "cost_usd": 0.5}])
        mock_db.__getitem__ = MagicMock(return_value=MagicMock())
        mock_db["model_usage"].aggregate.return_value = mock_cursor

        with patch.object(task_service, "get_db", return_value=mock_db):
            budget = await task_service._get_budget_status()

        assert budget.tokens_used == 10_000
        assert budget.cost_usd == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_budget_exceeded_when_over_token_limit(self) -> None:
        from services.supervisor.app.services import task_service

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[{"tokens_used": 600_000, "cost_usd": 1.0}])
        mock_db.__getitem__ = MagicMock(return_value=MagicMock())
        mock_db["model_usage"].aggregate.return_value = mock_cursor

        with (
            patch.object(task_service, "get_db", return_value=mock_db),
            patch.object(task_service.settings, "monthly_token_limit", 500_000),
        ):
            budget = await task_service._get_budget_status()

        assert budget.budget_exceeded is True


# ---------------------------------------------------------------------------
# execute_task - OPA gate
# ---------------------------------------------------------------------------


class TestExecuteTask:
    @pytest.mark.asyncio
    async def test_raises_if_task_not_found(self) -> None:
        from services.supervisor.app.services import task_service

        mock_db = MagicMock()
        mock_db["tasks"].find_one = AsyncMock(return_value=None)

        with patch.object(task_service, "get_db", return_value=mock_db):
            with pytest.raises(ValueError, match="not found"):
                await task_service.execute_task("nonexistent-id")

    @pytest.mark.asyncio
    async def test_raises_if_task_not_approved(self) -> None:
        from services.supervisor.app.services import task_service

        task = _make_task(status=TaskStatus.PENDING)
        doc = task.model_dump(mode="json")

        mock_db = MagicMock()
        mock_db["tasks"].find_one = AsyncMock(return_value=doc)
        mock_db["tasks"].replace_one = AsyncMock()

        with patch.object(task_service, "get_db", return_value=mock_db):
            with pytest.raises(ValueError, match="not approved"):
                await task_service.execute_task(task.task_id)

    @pytest.mark.asyncio
    async def test_raises_if_task_has_no_plan(self) -> None:
        from services.supervisor.app.services import task_service

        task = _make_task(status=TaskStatus.APPROVED, plan=None)
        doc = task.model_dump(mode="json")

        mock_db = MagicMock()
        mock_db["tasks"].find_one = AsyncMock(return_value=doc)
        mock_db["tasks"].replace_one = AsyncMock()

        with patch.object(task_service, "get_db", return_value=mock_db):
            with pytest.raises(ValueError, match="no execution plan"):
                await task_service.execute_task(task.task_id)

    @pytest.mark.asyncio
    async def test_policy_denied_when_opa_rejects_task(self) -> None:
        from services.supervisor.app.services import task_service

        plan = _make_plan()
        task = _make_task(status=TaskStatus.APPROVED, plan=plan)
        doc = task.model_dump(mode="json")

        mock_db = MagicMock()
        mock_db["tasks"].find_one = AsyncMock(return_value=doc)
        mock_db["tasks"].replace_one = AsyncMock()
        mock_db["model_usage"].aggregate.return_value.to_list = AsyncMock(return_value=[])

        with (
            patch.object(task_service, "get_db", return_value=mock_db),
            patch.object(task_service, "check_task_execution", new_callable=AsyncMock) as mock_opa,
            patch.object(task_service, "_get_budget_status", new_callable=AsyncMock) as mock_budget,
        ):
            mock_budget.return_value = MagicMock(
                tokens_used=0,
                cost_usd=0.0,
                budget_exceeded=False,
                model_dump=MagicMock(return_value={}),
            )
            mock_opa.return_value = (False, None)  # OPA denies

            result = await task_service.execute_task(task.task_id)

        assert result.status == TaskStatus.POLICY_DENIED

    @pytest.mark.asyncio
    async def test_policy_denied_when_budget_exceeded(self) -> None:
        from services.supervisor.app.services import task_service

        plan = _make_plan()
        task = _make_task(status=TaskStatus.APPROVED, plan=plan)
        doc = task.model_dump(mode="json")

        mock_db = MagicMock()
        mock_db["tasks"].find_one = AsyncMock(return_value=doc)
        mock_db["tasks"].replace_one = AsyncMock()

        with (
            patch.object(task_service, "get_db", return_value=mock_db),
            patch.object(
                task_service, "check_task_execution", new_callable=AsyncMock
            ) as mock_task_opa,
            patch.object(task_service, "check_budget", new_callable=AsyncMock) as mock_budget_opa,
            patch.object(task_service, "_get_budget_status", new_callable=AsyncMock) as mock_budget,
        ):
            mock_budget.return_value = MagicMock(
                tokens_used=0,
                cost_usd=0.0,
                budget_exceeded=False,
                model_dump=MagicMock(return_value={}),
            )
            mock_task_opa.return_value = (True, True)
            mock_budget_opa.return_value = (False, None)  # budget denied

            result = await task_service.execute_task(task.task_id)

        assert result.status == TaskStatus.POLICY_DENIED


# ---------------------------------------------------------------------------
# create_task
# ---------------------------------------------------------------------------


class TestCreateTask:
    @pytest.mark.asyncio
    async def test_creates_and_persists_task(self) -> None:
        from services.supervisor.app.services import task_service

        req = CreateTaskRequest(title="Test", description="Do something")

        mock_db = MagicMock()
        mock_db["tasks"].replace_one = AsyncMock()
        mock_db["model_usage"].insert_one = AsyncMock()

        plan = _make_plan(approval_tier=ApprovalTier.HIGH)
        planner_resp = MagicMock()
        planner_resp.raise_for_status = MagicMock()
        planner_resp.json.return_value = {
            "plan": plan.model_dump(mode="json"),
            "tokens_used": 100,
            "model": "gpt-4o-mini",
        }

        mock_http_client = AsyncMock()
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)
        mock_http_client.post = AsyncMock(return_value=planner_resp)

        with (
            patch.object(task_service, "get_db", return_value=mock_db),
            patch("httpx.AsyncClient", return_value=mock_http_client),
        ):
            task = await task_service.create_task(req)

        assert task.title == "Test"
        assert task.status in (TaskStatus.AWAITING_APPROVAL, TaskStatus.APPROVED)
        mock_db["tasks"].replace_one.assert_called()
