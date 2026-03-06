import os
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import httpx
from app.schemas.chat import InitRequest, InternalMemoryResetRequest
from app.schemas.internal_chat import InternalChatRequest
from app.schemas.ui import SDUIResponse
from app.planner.sql_planner import SQLPlanner
from app.planner.llm_client import build_sql_planner_llm_client

app = FastAPI(title="Realtor Chat Polymorphic Bridge")

PROPERTY_SEARCH_LIMIT = max(1, min(int(os.getenv("REALTOR_PROPERTY_SEARCH_LIMIT", "4")), 12))

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


@app.get("/health/dependencies")
async def dependencies_health():
    """
    Lightweight dependency health for frontend status indicator.
    """
    timeout = float(os.getenv("HEALTHCHECK_TIMEOUT", "3"))
    inference_url = os.getenv("INFERENCE_V2_URL", "http://inference-core-v2:8000").rstrip("/") + "/api/v2/health"
    retriever_url = os.getenv("RAG_RETRIEVER_V2_URL", "http://semantic-adapter-v2:8000").rstrip("/") + "/api/v2/health"

    result = {
        "status": "operational",
        "service": "realtor-chat-bridge",
        "dependencies": {
            "inference_core_v2": {"ok": False, "url": inference_url},
            "semantic_adapter_v2": {"ok": False, "url": retriever_url},
        },
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        for name, url in (
            ("inference_core_v2", inference_url),
            ("semantic_adapter_v2", retriever_url),
        ):
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
from app.core.memory_reset import MemoryResetClient
from app.core.vertical_router import vertical_router
from app.transformer.core import SDUITransformer
from app.transformer.realtor_policy import RealtorRendererPolicy
from app.transformer.generic_policy import GenericRendererPolicy
from app.core.feature_flags import feature_flags
from app.session.manager import SessionManager

inference_client = InferenceClient()
memory_reset_client = MemoryResetClient()
transformer = SDUITransformer()
session_manager = SessionManager()
sql_planner = SQLPlanner(
    search_limit=PROPERTY_SEARCH_LIMIT,
    llm_client=build_sql_planner_llm_client(),
)

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

    if feature_flags.SESSION_MULTICHANNEL_ENABLED:
        session_data = await session_manager.get_session_multichannel(
            client_id=client_id,
            channel=channel,
            channel_user_id=channel_user_id,
        )
    else:
        session_data = await session_manager.get_session(client_id)
    
    session_context = {
        "client_id": client_id,
        "conversation_id": str(req.conversation_id) if req.conversation_id else session_data.get("conversation_id"),
        "lead_id": session_data.get("lead_id"),
        "brand_project": req.brand_project or session_data.get("brand_project"),
        "channel": channel,
        "channel_user_id": channel_user_id,
    }
    
    if req.metadata:
        session_context.update(req.metadata)
    
    try:
        ai_response = await inference_client.chat(user_query=req.message_text, session=session_context)
        
        new_conversation_id = ai_response.get("conversation_id") or session_context.get("conversation_id")
        if new_conversation_id:
            if feature_flags.SESSION_MULTICHANNEL_ENABLED:
                await session_manager.upsert_session(
                    client_id=client_id,
                    channel=channel,
                    channel_user_id=channel_user_id,
                    data={
                        "conversation_id": new_conversation_id,
                        "brand_project": session_context.get("brand_project"),
                        "last_interaction": datetime.now(timezone.utc).isoformat(),
                    },
                )
            else:
                await session_manager.update_session(
                    client_id,
                    {
                        "conversation_id": new_conversation_id,
                        "brand_project": session_context.get("brand_project"),
                        "channel": channel,
                        "channel_user_id": channel_user_id,
                        "last_interaction": datetime.now(timezone.utc).isoformat(),
                    },
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
        deferred_footer_text = None
        
        extracted_components = []
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

        if vertical == "realtor":
            planner_session_data = dict(session_data or {})
            planner_session_data["client_id"] = client_id
            plan = await sql_planner.plan(req.message_text, session_data=planner_session_data)
            planner_result = await sql_planner.execute(
                plan=plan,
                client_id=client_id,
                transformer=transformer,
            )

            if planner_result.handled:
                if plan.needs_clarification:
                    extracted_components = []
                    ai_text = planner_result.answer_override or ai_text
                    deferred_footer_text = None
                else:
                    if planner_result.components:
                        extracted_components = []
                        if planner_result.answer_override:
                            deferred_footer_text = planner_result.answer_override
                            ai_text = ""
                        for component_payload in planner_result.components:
                            comp_type = component_payload.get("type")
                            if comp_type == "property-card":
                                from app.schemas.ui import PropertyCard
                                extracted_components.append(PropertyCard(**component_payload))
                            elif comp_type == "property-grid":
                                from app.schemas.ui import PropertyGrid
                                extracted_components.append(PropertyGrid(**component_payload))
                    elif planner_result.answer_override:
                        ai_text = planner_result.answer_override

                if planner_result.session_updates:
                    if feature_flags.SESSION_MULTICHANNEL_ENABLED:
                        await session_manager.upsert_session(
                            client_id=client_id,
                            channel=channel,
                            channel_user_id=channel_user_id,
                            data=planner_result.session_updates,
                        )
                    else:
                        await session_manager.update_session(client_id, planner_result.session_updates)
        
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

        if deferred_footer_text:
            from app.schemas.ui import ChatMessage
            final_components.append(ChatMessage(text=deferred_footer_text, sender="bot"))
        
        return SDUIResponse(
            session_id=str(new_conversation_id or "init"),
            branding=branding,
            components=final_components
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
