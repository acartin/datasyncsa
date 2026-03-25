import os
import logging
import time
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import httpx
from app.schemas.chat import InitRequest, InternalMemoryResetRequest
from app.schemas.internal_chat import InternalChatRequest
from app.schemas.ui import SDUIResponse

app = FastAPI(title="Chat Web Renderer")
logger = logging.getLogger("chat_web_renderer.main")

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
    return {"status": "operational", "service": "chat-web-renderer-api"}


@app.get("/health/dependencies")
async def dependencies_health():
    """
    Lightweight dependency health for frontend status indicator.
    """
    timeout = float(os.getenv("HEALTHCHECK_TIMEOUT", "3"))
    inference_base = os.getenv(
        "AI_RUNTIME_API",
        os.getenv(
            "AGENT_CORE_API",
            os.getenv("INFERENCE_API_URL", os.getenv("INFERENCE_V2_URL", "http://ai-runtime:8000")),
        ),
    ).rstrip("/")
    inference_prefix = os.getenv(
        "AI_RUNTIME_API_PREFIX",
        os.getenv(
            "AGENT_CORE_API_PREFIX",
            os.getenv("INFERENCE_API_PREFIX", os.getenv("INFERENCE_V2_API_PREFIX", "/api/v1")),
        ),
    )
    inference_url = f"{inference_base}{inference_prefix}/health"

    result = {
        "status": "operational",
        "service": "chat-web-renderer-api",
        "dependencies": {
            "ai_runtime": {"ok": False, "url": inference_url},
        },
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        for name, url in (("ai_runtime", inference_url),):
            try:
                resp = await client.get(url)
                result["dependencies"][name]["ok"] = resp.status_code == 200
                if resp.status_code == 200:
                    try:
                        result["dependencies"][name]["detail"] = resp.json()
                    except Exception:
                        result["dependencies"][name]["detail"] = {"status_code": resp.status_code}
                else:
                    result["dependencies"][name]["error"] = f"HTTP {resp.status_code}"
            except Exception as exc:
                result["dependencies"][name]["error"] = str(exc)

    all_ok = all(dep.get("ok") for dep in result["dependencies"].values())
    result["status"] = "operational" if all_ok else "degraded"
    return result

from app.core.inference_bridge import InferenceClient
from app.core.memory_reset import MemoryResetClient, RuntimeMemoryResetError
from app.core.vertical_router import vertical_router
from app.transformer.core import SDUITransformer
from app.transformer.realtor_policy import RealtorRendererPolicy
from app.transformer.generic_policy import GenericRendererPolicy
from app.session.manager import SessionManager

inference_client = InferenceClient()
memory_reset_client = MemoryResetClient()
transformer = SDUITransformer()
session_manager = SessionManager()

vertical_router.register_strategy("realtor", "web_html", RealtorRendererPolicy(channel="web_html"))
vertical_router.register_strategy("generic", "web_html", GenericRendererPolicy(channel="web_html"))

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
async def chat_interaction(req: InternalChatRequest):
    """
    Canonical chat endpoint using InternalChatRequest contract.
    This endpoint is explicitly limited to web_html for predictable SDUI output.
    """
    if req.channel != "web_html":
        raise HTTPException(
            status_code=422,
            detail="/chat only supports channel='web_html'; use channel-specific endpoints for other channels",
        )
    
    client_id = str(req.client_id)
    channel = req.channel
    channel_user_id = req.channel_user_id
    metadata = dict(req.metadata or {})
    trace_id = str(metadata.get("debug_trace_id") or "")
    incoming_conversation_id = str(req.conversation_id) if req.conversation_id else None
    request_started = time.perf_counter()

    session_data = await session_manager.get_session_multichannel(
        client_id=client_id,
        channel=channel,
        channel_user_id=channel_user_id,
    )
    
    session_context = {
        "client_id": client_id,
        "conversation_id": incoming_conversation_id or session_data.get("conversation_id"),
        "lead_id": session_data.get("lead_id"),
        "brand_project": req.brand_project or session_data.get("brand_project"),
        "channel": channel,
        "channel_user_id": channel_user_id,
    }
    
    if metadata:
        session_context.update(metadata)

    logger.info(
        "CHAT_RENDERER_INBOUND trace_id=%s client_id=%s channel=%s channel_user_id=%s incoming_conversation_id=%s "
        "session_conversation_id=%s resolved_conversation_id=%s frontend_runtime_conversation_id=%s "
        "frontend_stored_conversation_id=%s frontend_had_stored_conversation_id=%s "
        "frontend_runtime_channel_user_id=%s frontend_stored_channel_user_id=%s "
        "frontend_had_stored_channel_user_id=%s frontend_had_frontend_state=%s frontend_had_window_state=%s "
        "frontend_message_seq=%s frontend_page_load_id=%s landing_page_url=%s referrer_url=%s",
        trace_id or "-",
        client_id,
        channel,
        channel_user_id,
        incoming_conversation_id or "-",
        session_data.get("conversation_id") or "-",
        session_context.get("conversation_id") or "-",
        metadata.get("frontend_runtime_conversation_id") or "-",
        metadata.get("frontend_stored_conversation_id") or "-",
        metadata.get("frontend_had_stored_conversation_id"),
        metadata.get("frontend_runtime_channel_user_id") or "-",
        metadata.get("frontend_stored_channel_user_id") or "-",
        metadata.get("frontend_had_stored_channel_user_id"),
        metadata.get("frontend_had_frontend_state"),
        metadata.get("frontend_had_window_state"),
        metadata.get("frontend_message_seq"),
        metadata.get("frontend_page_load_id") or "-",
        metadata.get("landing_page_url") or "-",
        metadata.get("referrer_url") or "-",
    )
    
    try:
        ai_response = await inference_client.chat(user_query=req.message_text, session=session_context)
        
        new_conversation_id = ai_response.get("conversation_id") or session_context.get("conversation_id")
        resolved_lead_id = ai_response.get("lead_id") or session_context.get("lead_id")
        if new_conversation_id:
            await session_manager.upsert_session(
                client_id=client_id,
                channel=channel,
                channel_user_id=channel_user_id,
                data={
                    "conversation_id": new_conversation_id,
                    "lead_id": str(resolved_lead_id) if resolved_lead_id else None,
                    "brand_project": session_context.get("brand_project"),
                    "last_interaction": datetime.now(timezone.utc).isoformat(),
                },
            )

        logger.info(
            "CHAT_RENDERER_OUTBOUND trace_id=%s client_id=%s channel=%s channel_user_id=%s incoming_conversation_id=%s "
            "resolved_conversation_id=%s outgoing_conversation_id=%s conversation_reused=%s "
            "session_fallback_used=%s components_count=%s answer_chars=%s latency_ms=%.1f",
            trace_id or "-",
            client_id,
            channel,
            channel_user_id,
            incoming_conversation_id or "-",
            session_context.get("conversation_id") or "-",
            new_conversation_id or "-",
            bool(incoming_conversation_id and str(incoming_conversation_id) == str(new_conversation_id)),
            bool((not incoming_conversation_id) and session_data.get("conversation_id")),
            len(ai_response.get("components") or []),
            len((ai_response.get("answer") or "").strip()),
            (time.perf_counter() - request_started) * 1000.0,
        )
        
        vertical = await vertical_router.resolve_vertical_for_client_async(client_id)
        policy_handler = await vertical_router.get_handler_async(client_id, channel)
        if not policy_handler:
            raise HTTPException(status_code=500, detail="No renderer policy available for resolved vertical/channel")
        
        ai_text = ai_response.get("answer")
        if isinstance(ai_text, dict):
            ai_text = str(ai_text.get("text", str(ai_text)))
        elif not isinstance(ai_text, str):
            ai_text = str(ai_text) if ai_text is not None else ""
        ai_text = (ai_text or "").strip()
        extracted_components = []
        canonical_components = ai_response.get("components") or []
        if canonical_components:
            extracted_components = transformer.parse_canonical_components(canonical_components)
        else:
            sources = ai_response.get("sources", [])
            if sources:
                property_cards = await transformer._extract_properties_from_sources(sources)
                if property_cards:
                    if len(property_cards) == 1:
                        extracted_components.append(property_cards[0])
                    else:
                        from app.schemas.ui import PropertyGrid
                        extracted_components.append(PropertyGrid(
                            title="Propiedades Relacionadas",
                            properties=property_cards
                        ))
        
        if "cita" in ai_text.lower() or "visita" in ai_text.lower():
            from app.schemas.ui import ActionMenu
            extracted_components.append(ActionMenu(
                options=[
                    {"label": "📅 Agendar Visita", "payload": "SCHEDULE_VISIT"},
                    {"label": "📞 Hablar con Asesor", "payload": "CALL_AGENT"}
                ]
            ))
        
        branding = await transformer._get_branding_for_client(
            client_id, 
            session_context.get("brand_project")
        )
        
        policy_response = policy_handler.build_response(
            ai_text=ai_text,
            components=extracted_components,
            session_id=str(new_conversation_id or "init"),
        )
        
        from app.schemas.ui import BaseComponent
        final_components = []
        for comp_data in policy_response.get("components", []):
            comp_type = comp_data.get("type")
            if comp_type == "chat":
                from app.schemas.ui import ChatMessage
                final_components.append(ChatMessage(**comp_data))
            elif comp_type == "property-card":
                from app.schemas.ui import PropertyCard
                final_components.append(PropertyCard(**comp_data))
            elif comp_type == "property-grid":
                from app.schemas.ui import PropertyGrid
                final_components.append(PropertyGrid(**comp_data))
            else:
                from app.schemas.ui import ChatMessage
                final_components.append(ChatMessage(text=comp_data.get("text", ""), sender="bot"))

        response_meta = {
            "conversation_id": str(new_conversation_id or ""),
            "lead_id": ai_response.get("lead_id"),
            "intent": ai_response.get("intent"),
            "scoringStatus": ai_response.get("scoring_status"),
            "scoringJobId": ai_response.get("scoring_job_id"),
            "scoringEta": ai_response.get("scoring_eta"),
        }
        if ai_response.get("metadata"):
            response_meta["metadata"] = ai_response.get("metadata")
        response_meta = {k: v for k, v in response_meta.items() if v is not None}

        return SDUIResponse(
            session_id=str(new_conversation_id or "init"),
            branding=branding,
            components=final_components,
            meta=response_meta,
        )

    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e)) from e
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error interno del bridge") from e


@app.get("/")
async def root():
    return {"message": "Chat Web Renderer is running"}


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
    Clears bridge session (Redis) and runtime memory in ai + scoring-core.
    """
    _assert_internal_token(request)

    client_id = str(payload.client_id)
    sessions_deleted = await session_manager.delete_sessions_by_client(client_id=client_id)
    try:
        runtime_results = await memory_reset_client.reset_runtime_memory(
            client_id=client_id,
            reason=payload.reason,
        )
    except RuntimeMemoryResetError as e:
        raise HTTPException(
            status_code=502,
            detail={
                "error": "runtime_memory_reset_failed",
                "failures": e.failures,
                "partial_results": e.partial_results,
            },
        ) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Runtime memory reset failed: {e}") from e

    return {
        "status": "ok",
        "client_id": client_id,
        "session_deleted": sessions_deleted > 0,
        "sessions_deleted": sessions_deleted,
        "resets": runtime_results,
        "inference": runtime_results.get("agent_core"),  # Backward compatibility.
    }
