from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging
import os
from app.api import router

# Configuración de logs según convenciones
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("semantic_adapter_v2")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Lógica de encendido
    logger.info("Starting Semantic Adapter V2...")
    yield
    # Lógica de apagado
    logger.info("Stopping Semantic Adapter V2...")

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Semantic Adapter V2 API",
    version="2.0.0",
    lifespan=lifespan
)

cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:8083,http://localhost:8086,http://192.168.0.37:8083,http://192.168.0.37:8086",
    ).split(",")
    if origin.strip()
]

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["*"],
    allow_credentials=("*" not in cors_origins),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclusión de rutas con el prefijo oficial
app.include_router(router, prefix="/api/v2")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "semantic-adapter-v2"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
