"""
Model usage contract – tracks LLM token consumption for budget enforcement.
Stored in MongoDB `model_usage` collection.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class ModelUsageRecord(BaseModel):
    """Single LLM call record."""
    record_id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: Optional[str] = None
    agent: str                          # e.g. "planner", "supervisor"
    model: str                          # e.g. "gpt-4o-mini"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class BudgetStatus(BaseModel):
    """Current-month budget snapshot returned by the supervisor."""
    month: str                           # "YYYY-MM"
    tokens_used: int
    tokens_limit: int
    cost_usd: float
    cost_limit_usd: float
    remaining_tokens: int
    remaining_cost_usd: float
    budget_exceeded: bool
