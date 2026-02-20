"""
Skill registry helpers.

Skills are declared in skills/registry.yaml (mounted into the container).
This module provides lookup utilities used by other parts of the skill runner.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.skill_loader import get_registry


def skill_exists(skill_id: str) -> bool:
    return skill_id in get_registry()


def list_skills() -> List[str]:
    return list(get_registry().keys())


def get_skill_info(skill_id: str) -> Optional[Dict[str, Any]]:
    return get_registry().get(skill_id)

