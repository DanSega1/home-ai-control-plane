"""Shared pytest fixtures for the home-ai-control-plane test suite."""

from __future__ import annotations

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


@pytest.fixture
def sample_step() -> ExecutionStep:
    return ExecutionStep(
        skill="raindrop-io",
        action="Save bookmark",
        instruction="Save https://example.com to research collection",
        estimated_tokens=100,
        reversible=True,
    )


@pytest.fixture
def sample_plan(sample_step: ExecutionStep) -> ExecutionPlan:
    return ExecutionPlan(
        steps=[sample_step],
        estimated_total_tokens=100,
        approval_tier=ApprovalTier.HIGH,
        risk_level=RiskLevel.LOW,
        requires_snapshot=False,
        reasoning="Single low-risk bookmark save",
    )


@pytest.fixture
def sample_task(sample_plan: ExecutionPlan) -> Task:
    return Task(
        title="Save bookmark",
        description="Save https://example.com to Raindrop research collection",
        requestor="user",
        approval_tier=ApprovalTier.HIGH,
        plan=sample_plan,
        status=TaskStatus.APPROVED,
    )


@pytest.fixture
def create_task_request() -> CreateTaskRequest:
    return CreateTaskRequest(
        title="Save bookmark",
        description="Save https://example.com to Raindrop research collection",
        approval_tier=ApprovalTier.HIGH,
    )
