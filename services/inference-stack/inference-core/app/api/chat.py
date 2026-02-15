from fastapi import APIRouter, HTTPException, Request
from app.models.chat import (
    ChatMessageRequest,
    ChatMessageResponse,
    InternalMemoryResetRequest,
    InternalMemoryResetResponse,
)
from app.services.chat_orchestrator import ChatOrchestrator
import logging
from uuid import UUID
from starlette.concurrency import run_in_threadpool
from app.core.config import settings

router = APIRouter()
orchestrator = ChatOrchestrator()
logger = logging.getLogger("inference-core.api")

@router.post("/chat", response_model=ChatMessageResponse)
async def chat_endpoint(request: ChatMessageRequest):
    """
    Principal endpoint para interactuar con el bot.
    Realiza búsqueda semántica y genera respuesta con LLM.
    """
    try:
        response = await orchestrator.chat(request)
        return response
    except Exception as e:
        logger.exception("Unhandled error in /chat")
        raise HTTPException(status_code=500, detail="Internal inference error")

@router.get("/chat/{conversation_id}")
async def get_chat_history(conversation_id: UUID):
    """
    Recupera el historial completo de una conversación.
    """
    try:
        history = await run_in_threadpool(orchestrator.get_conversation_history, conversation_id)
        return history
    except Exception as e:
        logger.exception("Error fetching history")
        raise HTTPException(status_code=500, detail="Internal inference error")

@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "inference-core"}


def _assert_internal_token(request: Request):
    expected = (settings.INTERNAL_API_TOKEN or "").strip()
    if not expected:
        return
    provided = (request.headers.get("X-Internal-Token") or "").strip()
    if provided != expected:
        raise HTTPException(status_code=401, detail="Invalid internal token")


@router.post("/internal/memory/reset", response_model=InternalMemoryResetResponse)
async def reset_client_memory(payload: InternalMemoryResetRequest, request: Request):
    """
    Internal endpoint: clears conversation memory for one client.
    """
    _assert_internal_token(request)
    try:
        deleted = await run_in_threadpool(
            orchestrator.repo.delete_conversations_by_client,
            payload.client_id,
        )
        return InternalMemoryResetResponse(
            status="ok",
            client_id=payload.client_id,
            conversations_deleted=deleted,
        )
    except Exception:
        logger.exception("Error resetting client memory")
        raise HTTPException(status_code=500, detail="Memory reset failed")
