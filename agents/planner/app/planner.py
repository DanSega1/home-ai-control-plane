"""
Core planning logic.

Calls an LLM via LiteLLM and produces a structured ExecutionPlan.
The LLM is prompted with a system message that describes available skills
and asked to return a JSON plan conforming to the ExecutionPlan schema.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

import litellm

from app.config import settings
from contracts.task import ApprovalTier, ExecutionPlan, ExecutionStep, RiskLevel

log = logging.getLogger("planner")

SYSTEM_PROMPT = """\
You are the Planner for a home AI control plane.
Your job is to produce a structured execution plan for a given task.

## Available Skills (Phase 1)

| Skill ID                        | Description                         | Destructive |
|---------------------------------|-------------------------------------|-------------|
| raindrop-io:bookmark_add        | Add a URL bookmark                  | No          |
| raindrop-io:bookmark_search     | Search existing bookmarks           | No          |
| raindrop-io:collection_list     | List bookmark collections           | No          |
| raindrop-io:bookmark_delete     | Delete a bookmark (HIGH RISK)       | YES         |

## Output Format

Respond ONLY with a single valid JSON object matching this schema:
{
  "steps": [
    {
      "skill": "<skill_id>",
      "action": "<human readable description>",
      "parameters": { <key: value pairs for the skill> },
      "depends_on": [],
      "estimated_tokens": <int>,
      "reversible": <bool>
    }
  ],
  "estimated_total_tokens": <int>,
  "approval_tier": "<low|medium|high|critical>",
  "risk_level": "<low|medium|high|critical>",
  "requires_snapshot": <bool>,
  "reasoning": "<brief explanation of the plan>"
}

Rules:
- If any step calls a destructive skill, set risk_level to "high" or "critical" and requires_snapshot to true.
- Set approval_tier to match risk_level (low→low, medium→medium, high→high, critical→critical).
- If no suitable skill exists, return a single step with skill "none:unsupported" and explain in reasoning.
- Return RAW JSON only. No markdown, no explanation outside the JSON object.
"""


async def generate_plan(task_id: str, title: str, description: str) -> Dict[str, Any]:
    """
    Call LiteLLM and return a dict with keys: plan, tokens_used, model.
    """
    user_message = f"Task: {title}\n\nDescription: {description}"

    response = await litellm.acompletion(
        model=settings.default_model,
        api_base=settings.litellm_base_url,
        api_key=settings.litellm_api_key,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=settings.planning_temperature,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    tokens_used = response.usage.total_tokens if response.usage else 0
    model_used = response.model or settings.default_model

    try:
        plan_dict = json.loads(raw)
    except json.JSONDecodeError as exc:
        log.error("Failed to parse plan JSON: %s\nRaw: %s", exc, raw)
        raise ValueError(f"LLM returned invalid JSON: {exc}") from exc

    # Build and validate through Pydantic
    steps = [ExecutionStep(**s) for s in plan_dict.get("steps", [])]
    plan = ExecutionPlan(
        steps=steps,
        estimated_total_tokens=plan_dict.get("estimated_total_tokens", 0),
        approval_tier=ApprovalTier(plan_dict.get("approval_tier", "high")),
        risk_level=RiskLevel(plan_dict.get("risk_level", "low")),
        requires_snapshot=plan_dict.get("requires_snapshot", False),
        reasoning=plan_dict.get("reasoning", ""),
    )

    log.info("Task %s plan generated: %d steps, risk=%s", task_id, len(steps), plan.risk_level)
    return {
        "plan": plan.model_dump(mode="json"),
        "tokens_used": tokens_used,
        "model": model_used,
    }
