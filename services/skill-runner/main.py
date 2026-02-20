"""Home AI Control Plane – Skill Runner."""
import logging

from fastapi import FastAPI

from app.routes.execute import router as execute_router

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Home AI – Skill Runner", version="0.1.0")
app.include_router(execute_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "skill-runner"}
