"""Home AI Control Plane - Planner Agent."""

import logging

from fastapi import FastAPI

from app.routes.plan import router as plan_router

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Home AI - Planner Agent", version="0.1.0")
app.include_router(plan_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "planner"}
