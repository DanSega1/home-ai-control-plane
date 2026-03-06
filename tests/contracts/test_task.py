"""Tests for contracts/task.py — shared task data models."""

from __future__ import annotations

import pytest

from contracts.task import (
    ApprovalTier,
    AuditEntry,
    CreateTaskRequest,
    ExecutionPlan,
    ExecutionStep,
    RiskLevel,
    Task,
    TaskResult,
    TaskStatus,
    TaskStatusResponse,
)

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class TestTaskStatus:
    def test_all_values_are_strings(self) -> None:
        for member in TaskStatus:
            assert isinstance(member.value, str)

    def test_terminal_statuses(self) -> None:
        terminal = {
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
            TaskStatus.REJECTED,
            TaskStatus.POLICY_DENIED,
        }
        assert len(terminal) == 5

    def test_pending_is_initial(self) -> None:
        task = Task(title="t", description="d")
        assert task.status == TaskStatus.PENDING


class TestApprovalTier:
    def test_values(self) -> None:
        assert ApprovalTier.LOW == "low"
        assert ApprovalTier.MEDIUM == "medium"
        assert ApprovalTier.HIGH == "high"
        assert ApprovalTier.CRITICAL == "critical"


class TestRiskLevel:
    def test_values(self) -> None:
        assert RiskLevel.LOW == "low"
        assert RiskLevel.HIGH == "high"
        assert RiskLevel.CRITICAL == "critical"


# ---------------------------------------------------------------------------
# ExecutionStep
# ---------------------------------------------------------------------------


class TestExecutionStep:
    def test_defaults(self) -> None:
        step = ExecutionStep(skill="raindrop-io", action="save")
        assert step.instruction == ""
        assert step.context == {}
        assert step.depends_on == []
        assert step.estimated_tokens == 0
        assert step.reversible is True

    def test_step_id_auto_generated(self) -> None:
        s1 = ExecutionStep(skill="raindrop-io", action="save")
        s2 = ExecutionStep(skill="raindrop-io", action="save")
        assert s1.step_id != s2.step_id

    def test_custom_fields(self) -> None:
        step = ExecutionStep(
            skill="raindrop-io",
            action="delete bookmark",
            estimated_tokens=50,
            reversible=False,
        )
        assert step.reversible is False
        assert step.estimated_tokens == 50


# ---------------------------------------------------------------------------
# ExecutionPlan
# ---------------------------------------------------------------------------


class TestExecutionPlan:
    def test_defaults(self) -> None:
        plan = ExecutionPlan()
        assert plan.steps == []
        assert plan.estimated_total_tokens == 0
        assert plan.approval_tier == ApprovalTier.HIGH
        assert plan.risk_level == RiskLevel.LOW
        assert plan.requires_snapshot is False

    def test_plan_id_auto_generated(self) -> None:
        p1 = ExecutionPlan()
        p2 = ExecutionPlan()
        assert p1.plan_id != p2.plan_id

    def test_with_steps(self, sample_step: ExecutionStep) -> None:
        plan = ExecutionPlan(steps=[sample_step], estimated_total_tokens=100)
        assert len(plan.steps) == 1
        assert plan.estimated_total_tokens == 100

    def test_serialization_roundtrip(self, sample_plan: ExecutionPlan) -> None:
        data = sample_plan.model_dump(mode="json")
        restored = ExecutionPlan(**data)
        assert restored.plan_id == sample_plan.plan_id
        assert len(restored.steps) == len(sample_plan.steps)


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------


class TestTask:
    def test_defaults(self) -> None:
        task = Task(title="Test", description="A test task")
        assert task.status == TaskStatus.PENDING
        assert task.approval_tier == ApprovalTier.HIGH
        assert task.plan is None
        assert task.result is None
        assert task.audit_trail == []
        assert task.total_tokens_used == 0
        assert task.iteration_count == 0
        assert task.max_iterations == 10

    def test_task_id_auto_generated(self) -> None:
        t1 = Task(title="t", description="d")
        t2 = Task(title="t", description="d")
        assert t1.task_id != t2.task_id

    def test_requestor_default(self) -> None:
        task = Task(title="t", description="d")
        assert task.requestor == "user"

    def test_status_assignment(self) -> None:
        task = Task(title="t", description="d")
        task.status = TaskStatus.EXECUTING
        assert task.status == TaskStatus.EXECUTING

    def test_serialization_roundtrip(self, sample_task: Task) -> None:
        data = sample_task.model_dump(mode="json")
        restored = Task(**data)
        assert restored.task_id == sample_task.task_id
        assert restored.status == sample_task.status

    def test_with_plan(self, sample_task: Task, sample_plan: ExecutionPlan) -> None:
        assert sample_task.plan is not None
        assert sample_task.plan.plan_id == sample_plan.plan_id

    def test_audit_trail_appended(self) -> None:
        task = Task(title="t", description="d")
        entry = AuditEntry(actor="supervisor", action="task_created")
        task.audit_trail.append(entry)
        assert len(task.audit_trail) == 1
        assert task.audit_trail[0].actor == "supervisor"

    def test_notion_page_id_nullable(self) -> None:
        task = Task(title="t", description="d")
        assert task.notion_page_id is None
        task.notion_page_id = "abc-123"
        assert task.notion_page_id == "abc-123"


# ---------------------------------------------------------------------------
# TaskResult
# ---------------------------------------------------------------------------


class TestTaskResult:
    def test_success(self) -> None:
        result = TaskResult(success=True, output={"bookmarks": 1}, tokens_used=50)
        assert result.success is True
        assert result.error is None

    def test_failure(self) -> None:
        result = TaskResult(success=False, error="MCP connection refused")
        assert result.success is False
        assert result.error == "MCP connection refused"

    def test_defaults(self) -> None:
        result = TaskResult(success=True)
        assert result.output is None
        assert result.tokens_used == 0
        assert result.duration_seconds == 0.0


# ---------------------------------------------------------------------------
# CreateTaskRequest
# ---------------------------------------------------------------------------


class TestCreateTaskRequest:
    def test_required_fields(self) -> None:
        req = CreateTaskRequest(title="Test task", description="Do something")
        assert req.title == "Test task"
        assert req.description == "Do something"
        assert req.requestor == "user"
        assert req.approval_tier == ApprovalTier.HIGH

    def test_custom_approval_tier(self) -> None:
        req = CreateTaskRequest(
            title="t",
            description="d",
            approval_tier=ApprovalTier.LOW,
        )
        assert req.approval_tier == ApprovalTier.LOW

    def test_missing_required_fields(self) -> None:
        with pytest.raises(ValueError):
            CreateTaskRequest(title="only title")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# TaskStatusResponse
# ---------------------------------------------------------------------------


class TestTaskStatusResponse:
    def test_minimal(self) -> None:
        resp = TaskStatusResponse(
            task_id="abc",
            status=TaskStatus.PENDING,
            approval_tier=ApprovalTier.HIGH,
        )
        assert resp.notion_page_id is None
        assert resp.result is None

    def test_with_result(self) -> None:
        result = TaskResult(success=True)
        resp = TaskStatusResponse(
            task_id="abc",
            status=TaskStatus.COMPLETED,
            approval_tier=ApprovalTier.HIGH,
            result=result,
        )
        assert resp.result is not None
        assert resp.result.success is True
