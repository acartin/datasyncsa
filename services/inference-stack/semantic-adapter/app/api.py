from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.embedder import GeminiEmbedder
from app.vector_repo import VectorRepository

router = APIRouter()

# Instancias Globales
try:
    embedder = GeminiEmbedder()
except ValueError as e:
    embedder = None
    print(f"Warning: Embedder not initialized: {e}")

repo = VectorRepository()

class SearchRequest(BaseModel):
    query_text: str
    client_id: str
    filters: Optional[Dict[str, Any]] = None
    top_k: int = 5

class SearchResult(BaseModel):
    content_id: str
    title: Optional[str]
    body_content: str
    metadata: Dict[str, Any]
    score: float

class SearchResponse(BaseModel):
    results: List[SearchResult]
    query_text: str
    client_id: str

@router.get("/health")
async def health_check():
    """
    Health check endpoint to verify service status.
    """
    db_status = "unknown"
    try:
        # Simple verficación de conexión si fuera necesario
        # with repo._get_connection() as conn: ...
        db_status = "connected"
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

    # 1. Generar embedding para la query
    try:
        query_vector = await embedder.embed_query(req.query_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding generation failed: {str(e)}")

    # 2. Búsqueda en DB (en threadpool ya que search_similar es síncrona)
    try:
        db_results = await run_in_threadpool(
            repo.search_similar, 
            req.client_id, 
            query_vector, 
            req.top_k,
            req.filters
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database search failed: {str(e)}")

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
