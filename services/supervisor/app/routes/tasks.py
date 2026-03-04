from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.task_service import (
    create_task,
    execute_task,
    get_task,
    list_tasks,
    update_task_approval,
)
from contracts.task import CreateTaskRequest, Task, TaskStatusResponse

router = APIRouter(tags=["tasks"])


@router.post("/", response_model=Task, status_code=201)
async def create(req: CreateTaskRequest) -> Task:
    return await create_task(req)


@router.get("/", response_model=List[Task])
async def list_(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> List[Task]:
    return await list_tasks(status=status, limit=limit)


@router.get("/{task_id}", response_model=Task)
async def get(task_id: str) -> Task:
    task = await get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return task


@router.post("/{task_id}/execute", response_model=Task)
async def execute(task_id: str) -> Task:
    try:
        return await execute_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{task_id}/approve", response_model=Task)
async def approve(task_id: str) -> Task:
    task = await update_task_approval(task_id, approved=True)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return task


@router.post("/{task_id}/reject", response_model=Task)
async def reject(task_id: str) -> Task:
    task = await update_task_approval(task_id, approved=False)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return task


class PatchTaskRequest(BaseModel):
    notion_page_id: Optional[str] = None


@router.patch("/{task_id}", response_model=Task)
async def patch(task_id: str, req: PatchTaskRequest) -> Task:
    """Partial update – used by notion-sync to write back the Notion page ID."""
    from app.db import get_db
    from datetime import datetime, timezone
    db = get_db()
    update: dict = {"updated_at": datetime.now(tz=timezone.utc).isoformat()}
    if req.notion_page_id is not None:
        update["notion_page_id"] = req.notion_page_id
    result = await db["tasks"].update_one({"task_id": task_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    doc = await db["tasks"].find_one({"task_id": task_id})
    return Task(**doc)
