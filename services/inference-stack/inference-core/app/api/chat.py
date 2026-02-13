from fastapi import APIRouter, HTTPException
from app.models.chat import ChatMessageRequest, ChatMessageResponse
from app.services.chat_orchestrator import ChatOrchestrator
import logging
from uuid import UUID
from starlette.concurrency import run_in_threadpool

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
