"""
Task orchestration service.

Lifecycle:
  1. create_task         → persists task, status=PENDING
  2. plan_task           → calls Planner agent, status=PLANNING → AWAITING_APPROVAL
  3. approve / reject    → status=APPROVED / REJECTED  (triggered by NotionSync polling)
  4. execute_task        → OPA check → Skill Runner, status=EXECUTING → COMPLETED / FAILED
"""
import logging
from datetime import datetime, timezone
from typing import List

import httpx

from app.config import settings
from app.db import get_db
from app.opa_client import check_budget, check_skill_access, check_task_execution
from contracts.task import (
    ApprovalTier,
    AuditEntry,
    CreateTaskRequest,
    ExecutionPlan,
    Task,
    TaskResult,
    TaskStatus,
)
from contracts.model_usage import BudgetStatus, ModelUsageRecord

log = logging.getLogger("supervisor.tasks")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


async def _get_budget_status() -> BudgetStatus:
    db = get_db()
    month = _now().strftime("%Y-%m")
    pipeline = [
        {"$match": {"timestamp": {"$regex": f"^{month}"}}},
        {"$group": {
            "_id": None,
            "tokens_used": {"$sum": "$total_tokens"},
            "cost_usd": {"$sum": "$cost_usd"},
        }},
    ]
    result = await db["model_usage"].aggregate(pipeline).to_list(1)
    tokens_used = result[0]["tokens_used"] if result else 0
    cost_usd = result[0]["cost_usd"] if result else 0.0

    return BudgetStatus(
        month=month,
        tokens_used=tokens_used,
        tokens_limit=settings.monthly_token_limit,
        cost_usd=cost_usd,
        cost_limit_usd=settings.monthly_cost_limit_usd,
        remaining_tokens=settings.monthly_token_limit - tokens_used,
        remaining_cost_usd=settings.monthly_cost_limit_usd - cost_usd,
        budget_exceeded=(
            tokens_used >= settings.monthly_token_limit
            or cost_usd >= settings.monthly_cost_limit_usd
        ),
    )


async def _audit(task: Task, actor: str, action: str, detail: str | None = None) -> None:
    entry = AuditEntry(timestamp=_now(), actor=actor, action=action, detail=detail)
    task.audit_trail.append(entry)
    task.updated_at = _now()


async def _save(task: Task) -> None:
    db = get_db()
    await db["tasks"].replace_one(
        {"task_id": task.task_id},
        task.model_dump(mode="json"),
        upsert=True,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def create_task(req: CreateTaskRequest) -> Task:
    task = Task(
        title=req.title,
        description=req.description,
        requestor=req.requestor,
        approval_tier=req.approval_tier,
    )
    await _audit(task, "supervisor", "task_created")
    await _save(task)
    log.info("Task %s created: %s", task.task_id, task.title)

    # Kick off planning asynchronously
    await plan_task(task)
    return task


async def plan_task(task: Task) -> Task:
    """Call the Planner agent to generate an execution plan."""
    task.status = TaskStatus.PLANNING
    await _audit(task, "supervisor", "planning_started")
    await _save(task)

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{settings.planner_url}/plan",
                json={"task_id": task.task_id, "title": task.title, "description": task.description},
            )
            resp.raise_for_status()
            plan_data = resp.json()

        plan = ExecutionPlan(**plan_data["plan"])
        tokens_used = plan_data.get("tokens_used", 0)
        task.plan = plan
        task.total_tokens_used += tokens_used

        # Record token usage
        db = get_db()
        usage = ModelUsageRecord(
            task_id=task.task_id,
            agent="planner",
            model=plan_data.get("model", "unknown"),
            total_tokens=tokens_used,
        )
        await db["model_usage"].insert_one(usage.model_dump(mode="json"))

        # Move to awaiting approval unless low-risk auto-approve
        if task.approval_tier == ApprovalTier.LOW and plan.risk_level in ("low",):
            task.status = TaskStatus.APPROVED
            await _audit(task, "supervisor", "auto_approved", "low tier / low risk")
        else:
            task.status = TaskStatus.AWAITING_APPROVAL
            await _audit(task, "supervisor", "awaiting_approval")

        await _save(task)
        log.info("Task %s plan generated, status=%s", task.task_id, task.status)

    except Exception as exc:
        log.error("Planning failed for task %s: %s", task.task_id, exc)
        task.status = TaskStatus.FAILED
        await _audit(task, "supervisor", "planning_failed", str(exc))
        await _save(task)

    return task


async def execute_task(task_id: str) -> Task:
    """Execute an approved task after OPA validation."""
    db = get_db()
    doc = await db["tasks"].find_one({"task_id": task_id})
    if not doc:
        raise ValueError(f"Task {task_id} not found")

    task = Task(**doc)

    if task.status != TaskStatus.APPROVED:
        raise ValueError(f"Task {task_id} is not approved (status={task.status})")

    if not task.plan:
        raise ValueError(f"Task {task_id} has no execution plan")

    # --- OPA task execution check ---
    budget = await _get_budget_status()
    opa_input = {
        "current_status": task.status,
        "requested_status": "executing",
        "plan": task.plan.model_dump(mode="json"),
        "budget": budget.model_dump(mode="json"),
    }
    allowed, _ = await check_task_execution(opa_input)
    if not allowed:
        task.status = TaskStatus.POLICY_DENIED
        await _audit(task, "opa", "policy_denied")
        await _save(task)
        log.warning("Task %s denied by OPA", task_id)
        return task

    # --- OPA budget check ---
    budget_input = {
        "monthly_tokens_used": budget.tokens_used,
        "monthly_token_limit": settings.monthly_token_limit,
        "monthly_cost_usd": budget.cost_usd,
        "monthly_cost_limit_usd": settings.monthly_cost_limit_usd,
        "estimated_tokens": task.plan.estimated_total_tokens,
        "estimated_cost_usd": 0.0,
        "per_task_token_limit": settings.per_task_token_limit,
    }
    budget_ok, _ = await check_budget(budget_input)
    if not budget_ok:
        task.status = TaskStatus.POLICY_DENIED
        await _audit(task, "opa", "budget_denied")
        await _save(task)
        log.warning("Task %s denied by budget policy", task_id)
        return task

    # --- OPA skill access check (per step) ---
    for step in task.plan.steps:
        skill_input = {
            "skill": step.skill,
            "agent": "supervisor",
            "task_status": task.status,
            "plan_risk_level": task.plan.risk_level,
        }
        skill_ok, _ = await check_skill_access(skill_input)
        if not skill_ok:
            task.status = TaskStatus.POLICY_DENIED
            await _audit(task, "opa", "skill_access_denied", step.skill)
            await _save(task)
            log.warning("Task %s skill %s denied by OPA", task_id, step.skill)
            return task

    # --- Execute via Skill Runner ---
    task.status = TaskStatus.EXECUTING
    task.iteration_count += 1
    await _audit(task, "supervisor", "execution_started")
    await _save(task)

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{settings.skill_runner_url}/execute",
                json={"task_id": task.task_id, "plan": task.plan.model_dump(mode="json")},
            )
            resp.raise_for_status()
            result_data = resp.json()

        result = TaskResult(**result_data)
        task.result = result
        task.total_tokens_used += result.tokens_used
        task.status = TaskStatus.COMPLETED if result.success else TaskStatus.FAILED
        await _audit(task, "supervisor", "execution_completed", f"success={result.success}")

    except Exception as exc:
        log.error("Execution failed for task %s: %s", task_id, exc)
        task.status = TaskStatus.FAILED
        task.result = TaskResult(success=False, error=str(exc))
        await _audit(task, "supervisor", "execution_failed", str(exc))

    await _save(task)
    log.info("Task %s finished with status=%s", task_id, task.status)
    return task


async def list_tasks(status: str | None = None, limit: int = 50) -> List[Task]:
    db = get_db()
    query = {"status": status} if status else {}
    docs = await db["tasks"].find(query).sort("created_at", -1).limit(limit).to_list(limit)
    return [Task(**d) for d in docs]


async def get_task(task_id: str) -> Task | None:
    db = get_db()
    doc = await db["tasks"].find_one({"task_id": task_id})
    return Task(**doc) if doc else None


async def update_task_approval(task_id: str, approved: bool) -> Task | None:
    """Called by Notion Sync when a human approves/rejects a task."""
    task = await get_task(task_id)
    if not task:
        return None
    if task.status != TaskStatus.AWAITING_APPROVAL:
        return task

    if approved:
        task.status = TaskStatus.APPROVED
        await _audit(task, "notion-sync", "human_approved")
        await _save(task)
        # Trigger execution immediately after approval
        await execute_task(task_id)
    else:
        task.status = TaskStatus.REJECTED
        await _audit(task, "notion-sync", "human_rejected")
        await _save(task)

    return task
