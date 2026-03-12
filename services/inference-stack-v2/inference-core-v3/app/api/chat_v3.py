from uuid import UUID
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.database import get_db_session
from app.models.chat_v3 import (
    CacheInvalidateResponse,
    ChatV3Request,
    ChatV3Response,
    InternalMemoryResetRequest,
    InternalMemoryResetResponse,
)
from app.core.config import settings
from app.services.cache_service import cache_service
from app.services.orchestrator import InferenceCoreV3Orchestrator
from app.repositories.vertical_runtime_repository import VerticalRuntimeRepository

router = APIRouter()
logger = logging.getLogger("inference-core-v3.api")


def _assert_internal_token(request: Request):
    expected = (settings.internal_api_token or "").strip()
    if not expected:
        return
    provided = (request.headers.get("X-Internal-Token") or "").strip()
    if provided != expected:
        raise HTTPException(status_code=401, detail="Invalid internal token")


@router.post("/chat", response_model=ChatV3Response)
async def chat_v3_endpoint(
    request: ChatV3Request,
    db_session: AsyncSession = Depends(get_db_session),
):
    try:
        orchestrator = InferenceCoreV3Orchestrator(db_session)
        result = await orchestrator.process_chat(request)
        return ChatV3Response(**result)
    except ValueError as exc:
        msg = str(exc)
        if msg == "CLIENT_NOT_FOUND":
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
    except Exception as exc:
        logger.exception("Unhandled chat error")
        raise HTTPException(status_code=500, detail="Internal inference-core-v3 error") from exc


@router.get("/health")
def health():
    return {
        "service": "inference-core-v3",
        "status": "healthy",
        "version": "3.0.0",
        "cache": "connected" if cache_service.is_enabled() else "disabled",
    }


@router.post("/cache/invalidate", response_model=CacheInvalidateResponse)
async def invalidate_cache(
    request: Request,
    client_id: UUID | None = Query(default=None),
):
    _assert_internal_token(request)

    if client_id:
        deleted = await cache_service.invalidate_tenant_runtime(str(client_id))
        return CacheInvalidateResponse(
            status="ok",
            client_id=client_id,
            cache_keys_deleted=deleted,
        )

    ok = await cache_service.invalidate_prefix(":tenant_runtime:*")
    return CacheInvalidateResponse(
        status="ok" if ok else "error",
        cache_keys_deleted=-1 if ok else 0,
    )


@router.post("/internal/memory/reset", response_model=InternalMemoryResetResponse)
async def reset_client_memory(
    payload: InternalMemoryResetRequest,
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
):
    _assert_internal_token(request)
    try:
        repo = VerticalRuntimeRepository(db_session)
        deleted = await repo.delete_conversations_by_client(payload.client_id)
        cache_deleted = await cache_service.invalidate_tenant_runtime(str(payload.client_id))
        return InternalMemoryResetResponse(
            status="ok",
            client_id=payload.client_id,
            conversations_deleted=deleted,
            cache_keys_deleted=cache_deleted,
        )
    except Exception as exc:
        logger.exception("Error resetting client memory (v3)")
        raise HTTPException(status_code=500, detail="Memory reset failed") from exc
