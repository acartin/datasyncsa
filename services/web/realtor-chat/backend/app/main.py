import os
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.schemas.chat import ChatRequest, InitRequest
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
from app.transformer.core import SDUITransformer
from app.session.manager import SessionManager

inference_client = InferenceClient()
transformer = SDUITransformer()
session_manager = SessionManager()

@app.post("/chat/init", response_model=SDUIResponse)
async def chat_init(req: InitRequest):
    client_id = str(req.client_id)
    return await transformer.transform(
        {"answer": "", "sources": []},
        "init",
        client_id,
        include_fallback_text=False,
    )


@app.post("/chat", response_model=SDUIResponse)
async def chat_interaction(query: ChatRequest):
    # Backwards compatibility: keep accepting is_init on /chat
    if query.is_init:
        return await chat_init(InitRequest(client_id=query.client_id))

    client_id = str(query.client_id)

    # 1. Recuperar contexto de Redis
    session_data = await session_manager.get_session(client_id)
    
    # Mezclar contexto entrante (si el frontend envía datos frescos) con el guardado
    # Importante: El frontend es la fuente de verdad de la INTENCIÓN, Redis del HISTORIAL.
    session_context = {
        "client_id": client_id,
        "conversation_id": str(query.conversation_id) if query.conversation_id else session_data.get("conversation_id"),
        "lead_id": session_data.get("lead_id"),
        "utm_source": query.utm_source or session_data.get("utm_source"),
        "utm_medium": query.utm_medium or session_data.get("utm_medium"),
        "utm_campaign": query.utm_campaign or session_data.get("utm_campaign"),
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
                "utm_source": session_context.get("utm_source"),
                "utm_medium": session_context.get("utm_medium"),
                "utm_campaign": session_context.get("utm_campaign"),
                "source_property_ref": session_context.get("source_property_ref"),
                "landing_page_url": session_context.get("landing_page_url"),
                "last_interaction": datetime.now(timezone.utc).isoformat(),
            })

        # 3. Transformación Polimórfica (La Magia)
        sdui_response = await transformer.transform(
            ai_response,
            str(new_conversation_id or "init"),
            client_id,
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
