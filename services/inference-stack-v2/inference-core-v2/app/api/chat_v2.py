from fastapi import APIRouter, HTTPException, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.models.chat_v2 import (
    ChatV2Request,
    ChatV2Response,
    ScorecardResponse,
    ActiveModelResponse,
    InternalMemoryResetRequest,
    InternalMemoryResetResponse,
)
from app.services.scoring_orchestrator import ScoringOrchestrator
from app.dependencies.database import get_db_session
from app.services.cache_service import cache_service
from app.core.config import settings
import logging


router = APIRouter()
logger = logging.getLogger("inference-core-v2.api")


def _assert_internal_token(request: Request):
    expected = (settings.internal_api_token or "").strip()
    if not expected:
        return
    provided = (request.headers.get("X-Internal-Token") or "").strip()
    if provided != expected:
        raise HTTPException(status_code=401, detail="Invalid internal token")


@router.post("/chat", response_model=ChatV2Response)
async def chat_v2_endpoint(
    request: ChatV2Request,
    db_session: AsyncSession = Depends(get_db_session)
):
    """
    Principal endpoint para interactuar con el bot v2.
    
    Realiza búsqueda semántica, genera respuesta con LLM y scoring configurable.
    
    Requerido:
    - client_id: Tenant para resolver vertical y modelo de scoring
    
    Opcional:
    - business_domain: Dominio de negocio para granularidad adicional
    """
    try:
        # Initialize orchestrator
        orchestrator = ScoringOrchestrator(db_session)
        
        # Process chat with scoring
        response = await orchestrator.process_chat(request)
        
        return response
        
    except ValueError as e:
        error = str(e)
        logger.warning(f"Validation error in /api/v2/chat: {error}")
        if error == "CLIENT_NOT_FOUND":
            raise HTTPException(status_code=404, detail=error)
        if error in ("TENANT_VERTICAL_NOT_CONFIGURED",):
            raise HTTPException(status_code=422, detail=error)
        if error.startswith("NO_ACTIVE_VERTICAL_SCORING_MODEL"):
            raise HTTPException(status_code=404, detail=error)
        if error.startswith("LLM_ENGINE_NOT_AVAILABLE"):
            raise HTTPException(status_code=503, detail=error)
        raise HTTPException(status_code=400, detail=error)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled error in /api/v2/chat")
        raise HTTPException(status_code=500, detail="Internal inference error")


@router.get("/leads/{lead_id}/scorecards/latest", response_model=ScorecardResponse)
async def get_latest_scorecard(
    lead_id: UUID,
    db_session: AsyncSession = Depends(get_db_session)
):
    """Get the latest scorecard for a lead"""
    try:
        orchestrator = ScoringOrchestrator(db_session)
        scorecard = await orchestrator.get_latest_scorecard_response(lead_id)
        
        if not scorecard:
            raise HTTPException(status_code=404, detail="No scorecards found for this lead")
        
        return scorecard
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting latest scorecard for lead {lead_id}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/leads/{lead_id}/scorecards/{scorecard_id}", response_model=ScorecardResponse)
async def get_scorecard(
    lead_id: UUID,
    scorecard_id: UUID,
    db_session: AsyncSession = Depends(get_db_session)
):
    """Get specific scorecard for a lead"""
    try:
        orchestrator = ScoringOrchestrator(db_session)
        scorecard = await orchestrator.get_scorecard_response(scorecard_id)
        
        if not scorecard:
            raise HTTPException(status_code=404, detail="Scorecard not found")
        
        # Verify scorecard belongs to lead
        if UUID(scorecard["lead_id"]) != lead_id:
            raise HTTPException(status_code=404, detail="Scorecard not found for this lead")
        
        return scorecard
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting scorecard {scorecard_id} for lead {lead_id}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/scoring/models/active", response_model=ActiveModelResponse)
async def get_active_scoring_model(
    client_id: UUID = Query(..., description="Tenant/client identifier"),
    business_domain: str = None,
    db_session: AsyncSession = Depends(get_db_session)
):
    """Get active scoring model configuration for tenant scope"""
    try:
        orchestrator = ScoringOrchestrator(db_session)
        vertical_ctx = await orchestrator.resolve_vertical_for_client(client_id)
        vertical_id = int(vertical_ctx["vertical_id"])
        model_data = await orchestrator.get_active_scoring_model(
            vertical_id=vertical_id,
            business_domain=business_domain
        )
        
        if not model_data:
            raise HTTPException(
                status_code=404,
                detail=(
                    "No active scoring model found for "
                    f"vertical_id={vertical_id}, business_domain={business_domain}"
                ),
            )
        
        return ActiveModelResponse(
            model_id=UUID(model_data["id"]),
            model_version=model_data["version"],
            prompt_version=model_data["prompt_version"],
            criteria=model_data["criteria"]
        )
        
    except ValueError as e:
        error = str(e)
        if error == "CLIENT_NOT_FOUND":
            raise HTTPException(status_code=404, detail=error)
        if error in ("TENANT_VERTICAL_NOT_CONFIGURED",):
            raise HTTPException(status_code=422, detail=error)
        raise HTTPException(status_code=400, detail=error)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting active scoring model")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/cache/invalidate")
async def invalidate_cache(
    vertical_id: int = None,
    business_domain: str = None
):
    """Invalidate cache entries (internal use)"""
    try:
        # Validate input combinations
        if vertical_id and business_domain is None:
            # Invalidate by vertical
            success = await cache_service.invalidate_active_model(
                vertical_id=vertical_id,
                business_domain=None,
            )

            if success:
                return {"status": "success", "message": "Cache invalidated"}
            raise HTTPException(status_code=500, detail="Cache invalidation failed")

        if vertical_id and business_domain is not None:
            # Invalidate specific model cache
            success = await cache_service.invalidate_active_model(
                vertical_id=vertical_id,
                business_domain=business_domain
            )
            
            if success:
                return {"status": "success", "message": "Cache invalidated"}
            else:
                raise HTTPException(status_code=500, detail="Cache invalidation failed")
        if not vertical_id and not business_domain:
            # Invalidate all cache
            success = await cache_service.invalidate_all_models()
            
            if success:
                return {"status": "success", "message": "All cache invalidated"}
            raise HTTPException(status_code=500, detail="Cache invalidation failed")

        raise HTTPException(
            status_code=400,
            detail="Invalid parameters. Provide either: 1) vertical_id only, or 2) vertical_id + business_domain, or 3) none to invalidate all",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error invalidating cache")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check cache connectivity if enabled
        cache_status = "disabled"
        if cache_service.is_enabled():
            cache_status = "connected"
        
        return {
            "status": "healthy",
            "service": "inference-core-v2",
            "cache": cache_status,
            "version": "2.0.0"
        }
    except Exception as e:
        logger.exception("Health check failed")
        raise HTTPException(status_code=503, detail="Service unhealthy")


@router.post("/internal/memory/reset", response_model=InternalMemoryResetResponse)
async def reset_client_memory(
    payload: InternalMemoryResetRequest,
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
):
    """
    Internal endpoint: clears conversation memory for one client in V2.
    """
    _assert_internal_token(request)
    try:
        orchestrator = ScoringOrchestrator(db_session)
        deleted = await orchestrator.repo.delete_conversations_by_client(payload.client_id)
        return InternalMemoryResetResponse(
            status="ok",
            client_id=payload.client_id,
            conversations_deleted=deleted,
        )
    except Exception:
        logger.exception("Error resetting client memory (v2)")
        raise HTTPException(status_code=500, detail="Memory reset failed")
