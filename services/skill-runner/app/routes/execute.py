"""
Execution route - receives a plan, runs steps sequentially respecting depends_on,
returns a TaskResult.

Each ExecutionStep now carries:
    skill    - skill_id in the registry (e.g. "raindrop-io")
    action   - human-readable summary
    instruction - natural language instruction passed to the skill's SKILL.md context

The Skill Executor drives an LLM + MCP tool loop per step.
"""

import logging
import time
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.registry import skill_exists
from app.skill_executor import execute_instruction
from contracts.task import ExecutionPlan, TaskResult

log = logging.getLogger("skill-runner.execute")
router = APIRouter(tags=["execution"])


class ExecuteRequest(BaseModel):
    task_id: str
    plan: dict[str, Any]


@router.post("/execute", response_model=TaskResult)
async def execute(req: ExecuteRequest) -> TaskResult:
    start = time.time()
    plan = ExecutionPlan(**req.plan)

    step_outputs: dict[str, Any] = {}
    completed_ids: set = set()
    total_tokens = 0

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
        remaining: list = []

        for step in pending:
            if not all(dep in completed_ids for dep in step.depends_on):
                remaining.append(step)
                continue

            # Validate skill is registered
            if not skill_exists(step.skill):
                return TaskResult(
                    success=False,
                    error=f"Skill '{step.skill}' is not in the registry",
                    duration_seconds=time.time() - start,
                )

            # Build the instruction for this step
            instruction = (
                step.instruction
                if hasattr(step, "instruction") and step.instruction
                else step.action
            )
            if step_outputs:
                # Provide previous step context so the skill can refer to prior results
                context = {"previous_step_outputs": step_outputs}
            else:
                context = None

            log.info(
                "Task %s - step %s (%s): %s",
                req.task_id,
                step.step_id,
                step.skill,
                instruction[:80],
            )

            result = await execute_instruction(step.skill, instruction, context)
            total_tokens += result.get("tokens_used", 0)

            if not result["success"]:
                return TaskResult(
                    success=False,
                    error=f"Step '{step.action}' ({step.skill}) failed: {result.get('error')}",
                    output={"completed_steps": step_outputs, "failed_step": step.step_id},
                    tokens_used=total_tokens,
                    duration_seconds=time.time() - start,
                )

            step_outputs[step.step_id] = {
                "output": result["output"],
                "tool_calls": result["tool_calls"],
            }
            completed_ids.add(step.step_id)
            progress = True

        pending = remaining
        if not progress and pending:
            return TaskResult(
                success=False,
                error="Could not resolve step dependencies",
                duration_seconds=time.time() - start,
            )

    return TaskResult(
        success=True,
        output=step_outputs,
        tokens_used=total_tokens,
        duration_seconds=time.time() - start,
    )
