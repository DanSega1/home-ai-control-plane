"""
Execution route – receives a plan, runs steps in dependency order,
returns a TaskResult.
"""
import logging
import time
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.registry import dispatch
from contracts.task import ExecutionPlan, TaskResult

log = logging.getLogger("skill-runner.execute")
router = APIRouter(tags=["execution"])


class ExecuteRequest(BaseModel):
    task_id: str
    plan: Dict[str, Any]


@router.post("/execute", response_model=TaskResult)
async def execute(req: ExecuteRequest) -> TaskResult:
    start = time.time()
    plan = ExecutionPlan(**req.plan)

    # Topological execution – respect depends_on
    step_outputs: Dict[str, Any] = {}
    completed_ids: set = set()

    # Build execution order (simple linear pass, supports basic DAG)
    pending = list(plan.steps)
    max_passes = len(pending) + 1
    passes = 0

    while pending:
        passes += 1
        if passes > max_passes:
            return TaskResult(
                success=False,
                error="Circular dependency detected in plan steps",
                duration_seconds=time.time() - start,
            )

        progress = False
        remaining: List = []

        for step in pending:
            if all(dep in completed_ids for dep in step.depends_on):
                try:
                    log.info("Task %s – executing step %s (%s)", req.task_id, step.step_id, step.skill)
                    # Inject outputs from previous steps into parameters
                    enriched_params = {**step.parameters, "_previous_outputs": step_outputs}
                    output = await dispatch(step.skill, enriched_params)
                    step_outputs[step.step_id] = output
                    completed_ids.add(step.step_id)
                    progress = True
                except Exception as exc:
                    log.error("Step %s failed: %s", step.step_id, exc)
                    return TaskResult(
                        success=False,
                        error=f"Step '{step.action}' ({step.skill}) failed: {exc}",
                        output=step_outputs,
                        duration_seconds=time.time() - start,
                    )
            else:
                remaining.append(step)

        pending = remaining
        if not progress and pending:
            return TaskResult(
                success=False,
                error="Could not resolve step dependencies – possible circular reference",
                duration_seconds=time.time() - start,
            )

    return TaskResult(
        success=True,
        output=step_outputs,
        duration_seconds=time.time() - start,
    )
