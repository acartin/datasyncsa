import os
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from app.schemas.chat import ChatRequest, InitRequest, InternalMemoryResetRequest
from app.schemas.ui import SDUIResponse

app = FastAPI(title="Realtor Chat Polymorphic Bridge")

cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:8087,http://192.168.0.37:8087",
    ).split(",")
    if origin.strip()
]
allow_credentials = "*" not in cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["*"],
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "operational", "service": "realtor-chat-bridge"}

from app.core.inference_bridge import InferenceClient
from app.core.memory_reset import MemoryResetClient
from app.transformer.core import SDUITransformer
from app.session.manager import SessionManager

inference_client = InferenceClient()
memory_reset_client = MemoryResetClient()
transformer = SDUITransformer()
session_manager = SessionManager()

@app.post("/chat/init", response_model=SDUIResponse)
async def chat_init(req: InitRequest):
    client_id = str(req.client_id)
    return await transformer.transform(
        {"answer": "", "sources": []},
        "init",
        client_id,
        brand_project=req.brand_project,
        include_fallback_text=False,
    )


@app.post("/chat", response_model=SDUIResponse)
async def chat_interaction(query: ChatRequest):
    # Backwards compatibility: keep accepting is_init on /chat
    if query.is_init:
        return await chat_init(InitRequest(client_id=query.client_id, brand_project=query.brand_project))

    client_id = str(query.client_id)

    # 1. Recuperar contexto de Redis
    session_data = await session_manager.get_session(client_id)
    
    # Mezclar contexto entrante (si el frontend envía datos frescos) con el guardado
    # Importante: El frontend es la fuente de verdad de la INTENCIÓN, Redis del HISTORIAL.
    session_context = {
        "client_id": client_id,
        "conversation_id": str(query.conversation_id) if query.conversation_id else session_data.get("conversation_id"),
        "lead_id": session_data.get("lead_id"),
        "brand_project": query.brand_project or session_data.get("brand_project"),
        "utm_source": query.utm_source or session_data.get("utm_source"),
        "utm_medium": query.utm_medium or session_data.get("utm_medium"),
        "utm_campaign": query.utm_campaign or session_data.get("utm_campaign"),
        "utm_content": query.utm_content or session_data.get("utm_content"),
        "utm_term": query.utm_term or session_data.get("utm_term"),
        "gclid": query.gclid or session_data.get("gclid"),
        "fbclid": query.fbclid or session_data.get("fbclid"),
        "ttclid": query.ttclid or session_data.get("ttclid"),
        "msclkid": query.msclkid or session_data.get("msclkid"),
        "li_fat_id": query.li_fat_id or session_data.get("li_fat_id"),
        "gbraid": query.gbraid or session_data.get("gbraid"),
        "wbraid": query.wbraid or session_data.get("wbraid"),
        "referrer_url": query.referrer_url or session_data.get("referrer_url"),
        "source_property_ref": query.source_property_ref or session_data.get("source_property_ref"),
        "landing_page_url": query.landing_page_url or session_data.get("landing_page_url"),
    }

    try:
        # 2. Llamar al Cerebro Real
        ai_response = await inference_client.chat(user_query=query.text, session=session_context)
        
        # 2.5 Actualizar Memoria (Guardamos el conversation_id nuevo si cambió)
        new_conversation_id = ai_response.get("conversation_id") or session_context.get("conversation_id")
        if new_conversation_id:
            await session_manager.update_session(client_id, {
                "conversation_id": new_conversation_id,
                "brand_project": session_context.get("brand_project"),
                "utm_source": session_context.get("utm_source"),
                "utm_medium": session_context.get("utm_medium"),
                "utm_campaign": session_context.get("utm_campaign"),
                "utm_content": session_context.get("utm_content"),
                "utm_term": session_context.get("utm_term"),
                "gclid": session_context.get("gclid"),
                "fbclid": session_context.get("fbclid"),
                "ttclid": session_context.get("ttclid"),
                "msclkid": session_context.get("msclkid"),
                "li_fat_id": session_context.get("li_fat_id"),
                "gbraid": session_context.get("gbraid"),
                "wbraid": session_context.get("wbraid"),
                "referrer_url": session_context.get("referrer_url"),
                "source_property_ref": session_context.get("source_property_ref"),
                "landing_page_url": session_context.get("landing_page_url"),
                "last_interaction": datetime.now(timezone.utc).isoformat(),
            })

        # 3. Transformación Polimórfica (La Magia)
        sdui_response = await transformer.transform(
            ai_response,
            str(new_conversation_id or "init"),
            client_id,
            brand_project=session_context.get("brand_project"),
        )
        
        return sdui_response

    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error interno del bridge") from e

@app.get("/")
async def root():
    return {"message": "Realtor Chat SDUI Bridge is running"}


def _assert_internal_token(request: Request):
    expected = (os.getenv("INTERNAL_API_TOKEN") or "").strip()
    if not expected:
        return
    provided = (request.headers.get("X-Internal-Token") or "").strip()
    if provided != expected:
        raise HTTPException(status_code=401, detail="Invalid internal token")


@app.post("/internal/memory/reset")
async def internal_memory_reset(payload: InternalMemoryResetRequest, request: Request):
    """
    Internal endpoint: resets chat memory for a client.
    Clears bridge session (Redis) and inference conversation memory.
    """
    _assert_internal_token(request)

    client_id = str(payload.client_id)
    session_deleted = await session_manager.delete_session(client_id)
    try:
        inference_result = await memory_reset_client.reset_inference_memory(
            client_id=client_id,
            reason=payload.reason,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Inference memory reset failed: {e}") from e

    return {
        "status": "ok",
        "client_id": client_id,
        "session_deleted": session_deleted,
        "inference": inference_result,
    }
