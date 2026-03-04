"""
Skill Executor – drives a skill instruction using LiteLLM + MCP tools.

Flow per instruction:
  1. Load SKILL.md for the skill (cached via skill_loader)
  2. Build system prompt = SKILL.md content
  3. Open MCP connection → discover available tools
  4. Convert MCP tools → OpenAI function-calling spec
  5. LLM call with tools available
  6. If LLM returns tool_calls → execute via MCP → feed results back
  7. Repeat until LLM returns a final text response
  8. Return summary + raw tool outputs
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

import litellm

from app.config import settings
from app.mcp_client import MCPClient
from app.skill_loader import (
    fetch_skill,
    get_skill_auth_token,
    get_skill_mcp_server,
)

log = logging.getLogger("skill-runner.executor")

MAX_TOOL_ROUNDS = 10   # guard against infinite tool-call loops


async def execute_instruction(skill_id: str, instruction: str, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Execute a natural language instruction using the named skill.

    Returns:
        {
            "success": bool,
            "output": str,           # final LLM response
            "tool_calls": [...],     # all MCP tool calls made
            "tokens_used": int,
            "error": str | None,
        }
    """
    # 1. Load SKILL.md
    try:
        skill_md = await fetch_skill(skill_id)
    except Exception as exc:
        return {"success": False, "output": "", "tool_calls": [], "tokens_used": 0, "error": str(exc)}

    # 2. Build messages
    system_content = skill_md
    if context:
        system_content += f"\n\n## Execution Context\n{json.dumps(context, indent=2)}"

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": instruction},
    ]

    # 3. Get MCP server details
    mcp_url = get_skill_mcp_server(skill_id)
    auth_token = get_skill_auth_token(skill_id)

    all_tool_calls: List[Dict[str, Any]] = []
    total_tokens = 0

    try:
        # 4. Open MCP connection
        async with MCPClient(mcp_url, auth_token) as mcp:
            openai_tools = await mcp.tools_as_openai_spec()

            # 5. Agentic tool call loop
            for _round in range(MAX_TOOL_ROUNDS):
                response = await litellm.acompletion(
                    model=settings.execution_model,
                    api_base=settings.litellm_base_url,
                    api_key=settings.litellm_api_key,
                    messages=messages,
                    tools=openai_tools or None,
                    tool_choice="auto" if openai_tools else None,
                )

                total_tokens += response.usage.total_tokens if response.usage else 0
                choice = response.choices[0]
                msg = choice.message

                tool_calls = getattr(msg, "tool_calls", None) or []

                # Append assistant message to history
                messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
                    {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in tool_calls
                ]})

                if not tool_calls:
                    # Final answer – no more tool calls
                    return {
                        "success": True,
                        "output": msg.content or "",
                        "tool_calls": all_tool_calls,
                        "tokens_used": total_tokens,
                        "error": None,
                    }

                # 6. Execute MCP tool calls
                for tc in tool_calls:
                    fn_name = tc.function.name
                    try:
                        fn_args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        fn_args = {}

                    log.info("MCP tool call: %s(%s)", fn_name, fn_args)
                    try:
                        tool_result = await mcp.call_tool(fn_name, fn_args)
                    except Exception as exc:
                        tool_result = f"Error: {exc}"

                    all_tool_calls.append({"tool": fn_name, "args": fn_args, "result": tool_result})

                    # Feed result back into conversation
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": str(tool_result),
                    })

            # Exceeded MAX_TOOL_ROUNDS
            return {
                "success": False,
                "output": "",
                "tool_calls": all_tool_calls,
                "tokens_used": total_tokens,
                "error": f"Exceeded max tool rounds ({MAX_TOOL_ROUNDS})",
            }

    except Exception as exc:
        log.error("Skill execution failed for %s: %s", skill_id, exc)
        return {
            "success": False,
            "output": "",
            "tool_calls": all_tool_calls,
            "tokens_used": total_tokens,
            "error": str(exc),
        }
