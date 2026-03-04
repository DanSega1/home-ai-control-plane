"""Home AI Control Plane – Skill Runner."""
import logging

from fastapi import FastAPI

from app.routes.execute import router as execute_router
from app.skill_loader import prefetch_all
from app.registry import list_skills

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("skill-runner")

app = FastAPI(title="Home AI – Skill Runner", version="0.1.0")
app.include_router(execute_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "skill-runner"}


@app.get("/skills")
async def skills() -> dict:
    """List all registered skills and their registry info."""
    from app.skill_loader import get_registry
    return {"skills": get_registry()}


@app.on_event("startup")
async def startup() -> None:
    log.info("Skill Runner starting – warming skill cache...")
    await prefetch_all()
    log.info("Skill Runner ready. Registered skills: %s", list_skills())
