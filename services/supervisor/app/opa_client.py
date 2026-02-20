"""Thin async wrapper around the OPA REST API."""
import logging
from typing import Any, Dict, Tuple

import httpx

from app.config import settings

log = logging.getLogger("supervisor.opa")


async def evaluate(policy_path: str, input_data: Dict[str, Any]) -> Tuple[bool, Any]:
    """
    Call OPA and return (allowed: bool, result: Any).

    policy_path examples:
        "homeai/task/allow"
        "homeai/budget/allow"
        "homeai/skill/allow"
    """
    url = f"{settings.opa_url}/v1/data/{policy_path.replace('.', '/')}"
    payload = {"input": input_data}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            result = data.get("result", False)
            return bool(result), result
    except httpx.HTTPError as exc:
        log.error("OPA request failed: %s", exc)
        # Fail closed – deny if OPA is unreachable
        return False, None


async def check_task_execution(input_data: Dict[str, Any]) -> Tuple[bool, Any]:
    return await evaluate("homeai/task/allow", input_data)


async def check_budget(input_data: Dict[str, Any]) -> Tuple[bool, Any]:
    return await evaluate("homeai/budget/allow", input_data)


async def check_skill_access(input_data: Dict[str, Any]) -> Tuple[bool, Any]:
    return await evaluate("homeai/skill/allow", input_data)
