"""
Task contract – shared data model for the entire control plane.
All services import from this module (or its JSON schema equivalent).
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class TaskStatus(str, Enum):
    PENDING = "pending"               # just created
    PLANNING = "planning"             # planner is generating an execution plan
    AWAITING_APPROVAL = "awaiting_approval"  # waiting for human sign-off
    APPROVED = "approved"             # human approved
    REJECTED = "rejected"             # human rejected
    POLICY_DENIED = "policy_denied"   # OPA rejected
    EXECUTING = "executing"           # skill runner is working
    COMPLETED = "completed"           # finished successfully
    FAILED = "failed"                 # finished with an error
    CANCELLED = "cancelled"           # cancelled by user or supervisor


class ApprovalTier(str, Enum):
    LOW = "low"           # auto-approve
    MEDIUM = "medium"     # notify only
    HIGH = "high"         # manual approval required
    CRITICAL = "critical" # multi-step approval


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class ExecutionStep(BaseModel):
    """A single step inside a planner-generated execution plan."""
    step_id: str = Field(default_factory=lambda: str(uuid4()))
    skill: str                              # skill_id in registry.yaml – e.g. "raindrop-io"
    action: str                             # human-readable summary of what this step does
    instruction: str = ""                   # natural language instruction passed to the skill executor
    context: Dict[str, Any] = {}            # optional structured context for the instruction
    depends_on: List[str] = []              # step_ids this step depends on
    estimated_tokens: int = 0
    reversible: bool = True


class ExecutionPlan(BaseModel):
    """Structured plan produced by the Planner agent."""
    plan_id: str = Field(default_factory=lambda: str(uuid4()))
    steps: List[ExecutionStep] = []
    estimated_total_tokens: int = 0
    approval_tier: ApprovalTier = ApprovalTier.HIGH
    risk_level: RiskLevel = RiskLevel.LOW
    requires_snapshot: bool = False
    reasoning: str = ""


class AuditEntry(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    actor: str                          # service or agent name
    action: str
    detail: Optional[str] = None


class TaskResult(BaseModel):
    """Outcome from the skill runner after execution."""
    success: bool
    output: Any = None
    error: Optional[str] = None
    tokens_used: int = 0
    duration_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Primary Task model
# ---------------------------------------------------------------------------


class Task(BaseModel):
    """Core task document – stored in MongoDB `tasks` collection."""
    task_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    title: str
    description: str
    requestor: str = "user"             # who initiated the task

    status: TaskStatus = TaskStatus.PENDING
    approval_tier: ApprovalTier = ApprovalTier.HIGH

    plan: Optional[ExecutionPlan] = None
    result: Optional[TaskResult] = None

    audit_trail: List[AuditEntry] = []

    # Notion integration
    notion_page_id: Optional[str] = None

    # Budget tracking
    total_tokens_used: int = 0

    # Iteration guard
    iteration_count: int = 0
    max_iterations: int = 10

    class Config:
        use_enum_values = True


# ---------------------------------------------------------------------------
# API request / response models
# ---------------------------------------------------------------------------


class CreateTaskRequest(BaseModel):
    title: str
    description: str
    requestor: str = "user"
    approval_tier: ApprovalTier = ApprovalTier.HIGH


class TaskStatusResponse(BaseModel):
    task_id: str
    status: TaskStatus
    approval_tier: ApprovalTier
    notion_page_id: Optional[str] = None
    result: Optional[TaskResult] = None
