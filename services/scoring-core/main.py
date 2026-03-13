from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.scoring import router as scoring_router
from app.core.config import settings
from app.dependencies.database import close_database, init_database
from app.services.cache_service import cache_service


logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("scoring-core.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting scoring-core")
    try:
        await init_database()
        logger.info("Database initialized")
    except Exception:
        logger.exception("Database initialization failed")

    try:
        await cache_service.connect()
    except Exception:
        logger.exception("Cache initialization failed")

    yield

    logger.info("Shutting down scoring-core")
    await cache_service.disconnect()
    await close_database()


app = FastAPI(
    title="Scoring Core",
    description="Async scoring service decoupled from agent-core",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scoring_router, prefix=settings.api_prefix, tags=["scoring"])


@app.get("/")
async def root():
    return {
        "service": "scoring-core",
        "version": "1.0.0",
        "status": "running",
        "docs": f"{settings.api_prefix}/docs",
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )
