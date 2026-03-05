"""
Home AI Control Plane - Supervisor
Entry point for the FastAPI application.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import close_mongo, init_mongo
from app.routes.health import router as health_router
from app.routes.tasks import router as tasks_router

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("supervisor")

app = FastAPI(
    title="Home AI Control Plane - Supervisor",
    version="0.1.0",
    description="Policy-governed orchestration engine for the home AI control plane.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(tasks_router, prefix="/tasks")


@app.on_event("startup")
async def startup() -> None:
    log.info("Supervisor starting - connecting to MongoDB at %s", settings.mongo_uri)
    await init_mongo()
    log.info("Supervisor ready.")


@app.on_event("shutdown")
async def shutdown() -> None:
    await close_mongo()
