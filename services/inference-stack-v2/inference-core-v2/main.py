from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
from contextlib import asynccontextmanager

from app.core.config import settings
from app.api.chat_v2 import router as chat_v2_router
from app.dependencies.database import init_database, close_database
from app.services.cache_service import cache_service


# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("inference-core-v2.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info("Starting inference-core-v2...")
    
    # Initialize database
    try:
        await init_database()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
    
    # Initialize cache
    try:
        await cache_service.connect()
    except Exception as e:
        logger.error(f"Cache initialization failed: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down inference-core-v2...")
    
    # Close cache
    await cache_service.disconnect()
    
    # Close database
    await close_database()


# Create FastAPI app
app = FastAPI(
    title="Inference Core V2",
    description="Decoupled scoring engine with configurable models",
    version="2.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat_v2_router, prefix=settings.api_prefix, tags=["chat-v2"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "inference-core-v2",
        "version": "2.0.0",
        "status": "running",
        "docs": f"{settings.api_prefix}/docs"
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,  # Disable reload in production
        log_level=settings.log_level.lower()
    )