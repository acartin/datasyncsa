from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.api.chat_v3 import router as chat_v3_router
from app.core.config import settings
from app.dependencies.database import init_database, close_database
from app.services.cache_service import cache_service


logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("inference-core-v3.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    logger.info("Starting inference-core-v3...")
    try:
        await init_database()
        logger.info("Database initialized")
    except Exception as e:
        logger.error("Database initialization failed: %s", e)

    try:
        await cache_service.connect()
        logger.info("Cache initialized")
    except Exception as e:
        logger.warning("Cache initialization failed: %s", e)

    try:
        yield
    finally:
        logger.info("Shutting down inference-core-v3...")
        await cache_service.disconnect()
        await close_database()


app = FastAPI(
    title="Inference Core V3",
    description="LangGraph orchestrator for unified AI flow",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_v3_router, prefix=settings.api_prefix, tags=["chat-v3"])


@app.get("/")
async def root():
    return {
        "service": "inference-core-v3",
        "version": "3.0.0",
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
