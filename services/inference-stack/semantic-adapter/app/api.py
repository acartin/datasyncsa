from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from uuid import UUID
import logging

from app.embedder import GeminiEmbedder
from app.vector_repo import VectorRepository

router = APIRouter()
logger = logging.getLogger("semantic_adapter.api")

# Instancias Globales
try:
    embedder = GeminiEmbedder()
except ValueError as e:
    embedder = None
    logger.warning("Embedder not initialized: %s", e)

try:
    repo = VectorRepository()
except Exception as e:
    repo = None
    logger.warning("Vector repository not initialized: %s", e)

class SearchRequest(BaseModel):
    query_text: str
    client_id: UUID
    filters: Optional[Dict[str, Any]] = None
    top_k: int = Field(default=5, ge=1, le=20)

class SearchResult(BaseModel):
    content_id: str
    title: Optional[str]
    body_content: str
    metadata: Dict[str, Any]
    score: float

class SearchResponse(BaseModel):
    results: List[SearchResult]
    query_text: str
    client_id: UUID

@router.get("/health")
async def health_check():
    """
    Health check endpoint to verify service status.
    """
    db_status = "not_configured"
    try:
        if repo:
            is_connected = await run_in_threadpool(repo.ping)
            db_status = "connected" if is_connected else "disconnected"
    except Exception:
        db_status = "disconnected"
        
    return {
        "status": "ok", 
        "service": "semantic-adapter", 
        "mode": "read-only",
        "embedder": "ready" if embedder else "not_configured",
        "db": db_status
    }

@router.post("/search", response_model=SearchResponse)
async def search_documents(req: SearchRequest):
    """
    Realiza una búsqueda semántica basada en el texto de consulta.
    """
    if not embedder:
        raise HTTPException(status_code=503, detail="Embedder service not configured")
    if not repo:
        raise HTTPException(status_code=503, detail="Vector repository is not available")

    # 1. Generar embedding para la query
    try:
        query_vector = await embedder.embed_query(req.query_text)
    except Exception as e:
        logger.exception("Embedding generation failed")
        raise HTTPException(status_code=500, detail="Embedding generation failed")

    # 2. Búsqueda en DB (en threadpool ya que search_similar es síncrona)
    try:
        db_results = await run_in_threadpool(
            repo.search_similar, 
            str(req.client_id), 
            query_vector, 
            req.top_k,
            req.filters
        )
    except Exception as e:
        logger.exception("Database search failed")
        raise HTTPException(status_code=500, detail="Database search failed")

    # 3. Formatear resultados
    formatted_results = []
    for row in db_results:
        formatted_results.append(SearchResult(
            content_id=row["content_id"],
            title=row["title"],
            body_content=row["body_content"],
            metadata=row["metadata"],
            score=row["similarity"]
        ))

    return SearchResponse(
        results=formatted_results,
        query_text=req.query_text,
        client_id=req.client_id
    )
