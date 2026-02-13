from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging
import os
from app.api import router

# Configuración de logs según convenciones
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("semantic_adapter")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Lógica de encendido
    logger.info("🚀 Iniciando Semantic Adapter...")
    yield
    # Lógica de apagado
    logger.info("🛑 Apagando Semantic Adapter...")

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Semantic Adapter API",
    version="1.0.0",
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
app.include_router(router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "semantic-adapter"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
