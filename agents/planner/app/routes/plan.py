from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.planner import generate_plan

router = APIRouter(tags=["planning"])


class PlanRequest(BaseModel):
    task_id: str
    title: str
    description: str


@router.post("/plan")
async def plan(req: PlanRequest) -> dict:
    try:
        return await generate_plan(req.task_id, req.title, req.description)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
