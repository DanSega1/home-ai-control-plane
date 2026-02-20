"""
Skill registry – maps skill IDs to their handler callables.

Handlers are async functions with signature:
    async def handler(parameters: dict) -> dict
"""
from __future__ import annotations

import importlib
import logging
from typing import Any, Callable, Dict

log = logging.getLogger("skill-runner.registry")

# Lazy import map: skill_id → (module_path, function_name)
_SKILL_MAP: Dict[str, tuple[str, str]] = {
    "raindrop-io:bookmark_add":    ("skills.raindrop_io.skill", "bookmark_add"),
    "raindrop-io:bookmark_search": ("skills.raindrop_io.skill", "bookmark_search"),
    "raindrop-io:collection_list": ("skills.raindrop_io.skill", "collection_list"),
    "raindrop-io:bookmark_delete": ("skills.raindrop_io.skill", "bookmark_delete"),
}


def _load_handler(skill_id: str) -> Callable:
    if skill_id not in _SKILL_MAP:
        raise ValueError(f"Unknown skill: {skill_id}")
    module_path, fn_name = _SKILL_MAP[skill_id]
    module = importlib.import_module(module_path)
    return getattr(module, fn_name)


async def dispatch(skill_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    handler = _load_handler(skill_id)
    log.info("Dispatching skill %s", skill_id)
    return await handler(parameters)
