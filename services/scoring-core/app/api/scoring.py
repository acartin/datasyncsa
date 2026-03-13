from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.dependencies.database import get_db_session
from app.models.contracts import (
    ActiveModelResponse,
    CacheInvalidateResponse,
    EnqueueScoreJobResponse,
    InternalMemoryResetRequest,
    InternalMemoryResetResponse,
    ScoreConversationRequest,
    ScorecardResponse,
    ScoringJobResponse,
    ScoringOpsSummaryResponse,
)
from app.services.cache_service import cache_service
from app.services.scoring_orchestrator import ScoringOrchestrator

router = APIRouter()
logger = logging.getLogger("scoring-core.api")


def _assert_internal_token(request: Request) -> None:
    expected = (settings.internal_api_token or "").strip()
    if not expected:
        return
    provided = (request.headers.get("X-Internal-Token") or "").strip()
    if provided != expected:
        raise HTTPException(status_code=401, detail="Invalid internal token")


def _raise_validation_error(error: str) -> None:
    if error == "CLIENT_NOT_FOUND":
        raise HTTPException(status_code=404, detail=error)
    if error in ("TENANT_VERTICAL_NOT_CONFIGURED", "TENANT_SCORING_MODEL_NOT_CONFIGURED"):
        raise HTTPException(status_code=422, detail=error)
    if error in ("LEAD_NOT_FOUND_FOR_CLIENT", "SCORING_PROMPT_NOT_FOUND"):
        raise HTTPException(status_code=404, detail=error)
    if error.startswith("NO_ACTIVE_VERTICAL_SCORING_MODEL"):
        raise HTTPException(status_code=404, detail=error)
    raise HTTPException(status_code=400, detail=error)


@router.post("/scoring/jobs/enqueue", response_model=EnqueueScoreJobResponse)
async def enqueue_scoring_job(
    payload: ScoreConversationRequest,
    db_session: AsyncSession = Depends(get_db_session),
):
    """Create or refresh one async scoring job for a conversation."""
    try:
        orchestrator = ScoringOrchestrator(db_session)
        job = await orchestrator.enqueue_scoring_job(payload)
        return EnqueueScoreJobResponse(
            id=UUID(str(job["id"])),
            status=str(job.get("status") or "queued"),
            scheduled_for=job.get("scheduled_for"),
        )
    except ValueError as exc:
        _raise_validation_error(str(exc))
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error enqueuing scoring job")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/scoring/jobs/{job_id}", response_model=ScoringJobResponse)
async def get_scoring_job(
    job_id: UUID,
    db_session: AsyncSession = Depends(get_db_session),
):
    """Get status/metrics for one scoring job."""
    try:
        orchestrator = ScoringOrchestrator(db_session)
        job = await orchestrator.get_scoring_job_response(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Scoring job not found")
        return ScoringJobResponse(**job)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error getting scoring job %s", job_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/scoring/ops/summary", response_model=ScoringOpsSummaryResponse)
async def get_scoring_ops_summary(
    request: Request,
    window_minutes: int = Query(60, ge=5, le=1440),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Internal metrics endpoint for queue/worker health."""
    _assert_internal_token(request)
    try:
        orchestrator = ScoringOrchestrator(db_session)
        summary = await orchestrator.get_scoring_ops_summary(window_minutes=window_minutes)
        return ScoringOpsSummaryResponse(**summary)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error getting scoring ops summary")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/leads/{lead_id}/scorecards/latest", response_model=ScorecardResponse)
async def get_latest_scorecard(
    lead_id: UUID,
    client_id: UUID = Query(..., description="Tenant/client identifier"),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Get latest scorecard for one lead under tenant scope."""
    try:
        orchestrator = ScoringOrchestrator(db_session)
        lead_snapshot = await orchestrator.repo.get_lead_snapshot(lead_id=lead_id, client_id=client_id)
        if not lead_snapshot:
            raise HTTPException(status_code=404, detail="Lead not found for this client")

        scorecard = await orchestrator.get_latest_scorecard_response(lead_id)
        if not scorecard:
            raise HTTPException(status_code=404, detail="No scorecards found for this lead")
        return ScorecardResponse(**scorecard)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error getting latest scorecard for lead=%s", lead_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/leads/{lead_id}/scorecards/{scorecard_id}", response_model=ScorecardResponse)
async def get_scorecard(
    lead_id: UUID,
    scorecard_id: UUID,
    client_id: UUID = Query(..., description="Tenant/client identifier"),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Get one scorecard by id under tenant scope."""
    try:
        orchestrator = ScoringOrchestrator(db_session)
        lead_snapshot = await orchestrator.repo.get_lead_snapshot(lead_id=lead_id, client_id=client_id)
        if not lead_snapshot:
            raise HTTPException(status_code=404, detail="Lead not found for this client")

        scorecard = await orchestrator.get_scorecard_response(scorecard_id)
        if not scorecard:
            raise HTTPException(status_code=404, detail="Scorecard not found")
        if UUID(str(scorecard["lead_id"])) != lead_id:
            raise HTTPException(status_code=404, detail="Scorecard not found for this lead")
        return ScorecardResponse(**scorecard)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error getting scorecard=%s for lead=%s", scorecard_id, lead_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/scoring/models/active", response_model=ActiveModelResponse)
async def get_active_scoring_model(
    client_id: UUID = Query(..., description="Tenant/client identifier"),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Resolve active scoring model for tenant vertical."""
    try:
        orchestrator = ScoringOrchestrator(db_session)
        vertical_ctx = await orchestrator.resolve_vertical_for_client(client_id)
        vertical_id = int(vertical_ctx["vertical_id"])
        scoring_model_id = vertical_ctx.get("scoring_model_id")
        model_data = await orchestrator.get_active_scoring_model(
            client_id=client_id,
            vertical_id=vertical_id,
            scoring_model_id=scoring_model_id,
        )
        if not model_data:
            raise HTTPException(
                status_code=404,
                detail=(
                    "No active scoring model found for "
                    f"vertical_id={vertical_id}, scoring_model_id={scoring_model_id}"
                ),
            )

        return ActiveModelResponse(
            model_id=UUID(str(model_data["id"])),
            model_version=int(model_data.get("version", 1)),
            prompt_version=int(model_data.get("prompt_version", 1)),
            criteria=model_data.get("criteria") or [],
        )
    except ValueError as exc:
        _raise_validation_error(str(exc))
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error getting active scoring model")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/cache/invalidate", response_model=CacheInvalidateResponse)
async def invalidate_cache(
    request: Request,
    client_id: UUID | None = Query(default=None),
):
    """Internal cache invalidation endpoint."""
    _assert_internal_token(request)

    try:
        if client_id:
            active_ok = await cache_service.invalidate_active_model(client_id=client_id)
            prompts_ok = await cache_service.invalidate_client_prompts(client_id=client_id)
            if active_ok or prompts_ok:
                return CacheInvalidateResponse(status="ok", message="Cache invalidated")
            raise HTTPException(status_code=500, detail="Cache invalidation failed")

        models_ok = await cache_service.invalidate_all_models()
        prompts_ok = await cache_service.invalidate_all_prompts()
        if models_ok or prompts_ok:
            return CacheInvalidateResponse(status="ok", message="All cache invalidated")
        raise HTTPException(status_code=500, detail="Cache invalidation failed")
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error invalidating cache")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/internal/memory/reset", response_model=InternalMemoryResetResponse)
async def reset_client_memory(
    payload: InternalMemoryResetRequest,
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
):
    """Internal endpoint: clears lead conversation memory for one tenant."""
    _assert_internal_token(request)
    try:
        orchestrator = ScoringOrchestrator(db_session)
        deleted = await orchestrator.repo.delete_conversations_by_client(payload.client_id)
        await cache_service.invalidate_active_model(client_id=payload.client_id)
        await cache_service.invalidate_client_prompts(client_id=payload.client_id)
        return InternalMemoryResetResponse(
            status="ok",
            client_id=payload.client_id,
            conversations_deleted=deleted,
        )
    except Exception:
        logger.exception("Error resetting client memory")
        raise HTTPException(status_code=500, detail="Memory reset failed")


@router.get("/health")
async def health_check():
    cache_status = "connected" if cache_service.is_enabled() else "disabled"
    return {
        "status": "healthy",
        "service": "scoring-core",
        "cache": cache_status,
        "version": "1.0.0",
    }
