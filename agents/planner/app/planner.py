"""
Core planning logic.

Calls an LLM via LiteLLM and produces a structured ExecutionPlan.
The LLM is prompted with a system message that describes available skills
and asked to return a JSON plan conforming to the ExecutionPlan schema.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import litellm

from app.config import settings
from app.memory import get_relevant_memory_context
from contracts.task import ApprovalTier, ExecutionPlan, ExecutionStep, RiskLevel

log = logging.getLogger("planner")

SYSTEM_PROMPT = """\
You are the Planner for a home AI control plane.
Your job is to produce a structured execution plan for a given task.

## Skill Model

Skills are **instruction-based** agents loaded from external repositories.
Each skill has its own SKILL.md guide and connects to an MCP server to execute actions.
You do NOT call specific API functions — you write natural language instructions that the skill will interpret.

## Available Skills (Phase 1)

| Skill ID     | Capability                                                         | Risk    |
|--------------|--------------------------------------------------------------------|---------|
| raindrop-io  | Manage bookmarks: save, search, organize collections, reading list | low-high |

### raindrop-io capabilities:
- Save a URL to a collection with tags
- Search bookmarks by keyword, tag, domain, or date range
- List collections
- Manage reading lists (add, mark read, highlights)
- Organize research collections with bulk tagging
- Delete bookmarks (HIGH RISK - requires approval)

## Output Format

Respond ONLY with a single valid JSON object matching this schema:
{
  "steps": [
    {
      "skill": "<skill_id>",
      "action": "<one-line summary of what this step does>",
      "instruction": "<natural language instruction for the skill - be specific and complete>",
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

## Rules

- Write `instruction` as a complete, self-contained natural language request a human would say to the skill.
  Example: "Save https://example.com to my Reading List collection with tags: python, tutorial"
- If a step deletes data, set risk_level to "high" or "critical" and reversible to false.
- Set approval_tier to match risk_level (low→low, medium→medium, high→high, critical→critical).
- If no skill can handle the task, return one step with skill "none:unsupported" and explain in reasoning.
- Return RAW JSON only. No markdown, no text outside the JSON object.
"""


async def generate_plan(task_id: str, title: str, description: str) -> dict[str, Any]:
    """
    Call LiteLLM and return a dict with keys: plan, tokens_used, model.
    """
    memory_context = await get_relevant_memory_context(title, description)
    message_sections = [f"Task: {title}", f"Description: {description}"]
    if memory_context:
        message_sections.append(memory_context)
    user_message = "\n\n".join(message_sections)

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
    steps = []
    for s in plan_dict.get("steps", []):
        steps.append(
            ExecutionStep(
                skill=s.get("skill", ""),
                action=s.get("action", ""),
                instruction=s.get(
                    "instruction", s.get("action", "")
                ),  # fallback to action if missing
                context=s.get("context", {}),
                depends_on=s.get("depends_on", []),
                estimated_tokens=s.get("estimated_tokens", 0),
                reversible=s.get("reversible", True),
            )
        )
    plan = ExecutionPlan(
        steps=steps,
        estimated_total_tokens=plan_dict.get("estimated_total_tokens", 0),
        approval_tier=ApprovalTier(plan_dict.get("approval_tier", "high")),
        risk_level=RiskLevel(plan_dict.get("risk_level", "low")),
        requires_snapshot=plan_dict.get("requires_snapshot", False),
        reasoning=plan_dict.get("reasoning", ""),
    )

    log.info(
        "Task %s plan generated: %d steps, risk=%s, memory_context=%s",
        task_id,
        len(steps),
        plan.risk_level,
        bool(memory_context),
    )
    return {
        "plan": plan.model_dump(mode="json"),
        "tokens_used": tokens_used,
        "model": model_used,
    }
