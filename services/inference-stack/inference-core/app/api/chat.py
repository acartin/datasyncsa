from fastapi import APIRouter, HTTPException
from app.models.chat import ChatMessageRequest, ChatMessageResponse
from app.services.chat_orchestrator import ChatOrchestrator
import logging

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
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/chat/{conversation_id}")
async def get_chat_history(conversation_id: str):
    """
    Recupera el historial completo de una conversación.
    """
    try:
        from uuid import UUID
        history = orchestrator.get_conversation_history(UUID(conversation_id))
        if not history and len(history) == 0:
             # Si devuelve lista vacía puede ser que no exista o que esté vacía.
             # Por simplicidad devolvemos lista vacía.
             pass
        return history
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "inference-core"}
