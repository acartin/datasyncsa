import os
import secrets
import logging
from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any

from app.api.schemas import (
    ExternalChatRequest,
    ExternalChatResponse,
    ExternalErrorResponse,
    EXTERNAL_ERROR_CODES,
)
from app.core.runtime_client import InferenceClient
from app.core.session_identity import (
    normalize_session_id,
    resolve_effective_session_id,
    resolve_request_session_id,
)
from app.core.vertical_router import GENERIC_RENDER_VERTICALS, vertical_router
from app.transformer.core import SDUITransformer
from app.transformer.realtor_policy import RealtorRendererPolicy
from app.transformer.generic_policy import GenericRendererPolicy
from app.session.manager import SessionManager
from app.core.feature_flags import feature_flags

logger = logging.getLogger("external_api")

router = APIRouter(prefix="/api/external/v1", tags=["external"])

inference_client = InferenceClient()
transformer = SDUITransformer()
session_manager = SessionManager()

vertical_router.register_strategy("realtor", "api", RealtorRendererPolicy(channel="api"))
for vertical_slug in GENERIC_RENDER_VERTICALS:
    vertical_router.register_strategy(
        vertical_slug,
        "api",
        GenericRendererPolicy(channel="api", vertical_slug=vertical_slug),
    )


def _assert_external_token(request: Request) -> None:
    """Valida token externo para API pública."""
    expected = (os.getenv("EXTERNAL_API_TOKEN") or "").strip()
    if not expected:
        logger.error("EXTERNAL_API_TOKEN is not configured")
        raise HTTPException(
            status_code=503,
            detail={
                "error": "External API auth is not configured",
                "code": "auth_not_configured",
            },
        )
    provided = (request.headers.get("X-External-Token") or "").strip()
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=401,
            detail={
                "error": "Unauthorized: invalid or missing X-External-Token header",
                "code": EXTERNAL_ERROR_CODES["UNAUTHORIZED"],
            },
        )


@router.post(
    "/chat",
    response_model=ExternalChatResponse,
    responses={
        400: {"model": ExternalErrorResponse, "description": "Invalid request"},
        401: {"model": ExternalErrorResponse, "description": "Unauthorized"},
        504: {"model": ExternalErrorResponse, "description": "Service timeout"},
        500: {"model": ExternalErrorResponse, "description": "Internal error"},
    },
)
async def external_chat(req: ExternalChatRequest, request: Request):
    """
    External API v1 chat endpoint.
    
    Contract:
    - Request: client_id (UUID), message_text (string), optional conversation_id
    - Response: conversation_id, answer, intent (optional), components (list), meta
    
    Example Request:
    ```json
    {
        "client_id": "64f357a0-98eb-44f1-9f41-6e615ed26180",
        "message_text": "Quiero ver casas en Escazu"
    }
    ```
    
    Example Response:
    ```json
    {
        "conversation_id": "9f579ceb-5f9e-45f7-8408-906f6a36e326",
        "answer": "Claro, te comparto opciones disponibles.",
        "intent": "property_search",
        "components": [
            {"type": "chat_text", "text": "Claro, te comparto opciones disponibles."}
        ],
        "meta": {
            "vertical": "realtor",
            "channel": "api"
        }
    }
    ```
    """
    if not feature_flags.EXTERNAL_API_V1_ENABLED:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "External API v1 is disabled",
                "code": "feature_disabled",
            },
        )
    
    _assert_external_token(request)
    
    client_id = str(req.client_id)
    channel = "api"
    channel_user_id = req.channel_user_id

    session_data = await session_manager.get_session_multichannel(
        client_id=client_id,
        channel=channel,
        channel_user_id=channel_user_id,
    )
    
    session_context = {
        "client_id": client_id,
        "session_id": resolve_request_session_id(
            incoming_session_id=normalize_session_id(req.session_id),
            stored_session_id=session_data.get("session_id"),
            incoming_conversation_id=str(req.conversation_id) if req.conversation_id else None,
            stored_conversation_id=session_data.get("conversation_id"),
        ),
        "conversation_id": str(req.conversation_id) if req.conversation_id else session_data.get("conversation_id"),
        "lead_id": session_data.get("lead_id"),
        "brand_project": session_data.get("brand_project"),
        "channel": channel,
        "channel_user_id": channel_user_id,
        "auth_user_id": req.auth_user_id,
    }
    
    if req.metadata:
        session_context.update(req.metadata)
    
    try:
        ai_response = await inference_client.chat(
            user_query=req.message_text,
            session=session_context,
        )
        
        new_session_id = normalize_session_id(ai_response.get("session_id")) or session_context.get("session_id")
        new_conversation_id = ai_response.get("conversation_id") or session_context.get("conversation_id")
        effective_session_id = resolve_effective_session_id(
            runtime_session_id=new_session_id,
            runtime_conversation_id=new_conversation_id,
            request_session_id=session_context.get("session_id"),
            request_conversation_id=session_context.get("conversation_id"),
        )
        resolved_lead_id = ai_response.get("lead_id") or session_context.get("lead_id")
        if new_session_id or new_conversation_id:
            await session_manager.upsert_session(
                client_id=client_id,
                channel=channel,
                channel_user_id=channel_user_id,
                data={
                    "session_id": effective_session_id if effective_session_id != "init" else None,
                    "conversation_id": new_conversation_id,
                    "lead_id": str(resolved_lead_id) if resolved_lead_id else None,
                    "brand_project": session_context.get("brand_project"),
                    "auth_user_id": session_context.get("auth_user_id"),
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
        
        policy_response = policy_handler.build_response(
            ai_text=ai_text,
            components=extracted_components,
            session_id=effective_session_id,
        )
        
        components = []
        for comp_data in policy_response.get("components", []):
            comp_type = comp_data.get("type")
            if comp_type == "chat":
                components.append({
                    "type": "chat_text",
                    "text": comp_data.get("text", ""),
                })
            elif comp_type == "property-card":
                components.append({
                    "type": "property_card",
                    "title": comp_data.get("title"),
                    "price": comp_data.get("price"),
                    "location": comp_data.get("location"),
                })
            elif comp_type == "property-grid":
                components.append({
                    "type": "property_grid",
                    "title": comp_data.get("title"),
                    "count": len(comp_data.get("properties", [])),
                })
            else:
                components.append({"type": comp_type})
        
        response_intent = ai_response.get("intent")
        if not response_intent:
            fallback_intent = ai_response.get("realtor_turn") or ai_response.get("realtorTurn")
            if isinstance(fallback_intent, dict):
                response_intent = (fallback_intent.get("intent") or "").lower()
        
        return ExternalChatResponse(
            conversation_id=str(new_conversation_id or "init"),
            answer=ai_text,
            intent=response_intent,
            components=components,
            meta={
                "vertical": vertical,
                "channel": channel,
            },
        )
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": str(e),
                "code": EXTERNAL_ERROR_CODES["VALIDATION_ERROR"],
            },
        )
    except TimeoutError as e:
        logger.error(f"Timeout error: {e}")
        raise HTTPException(
            status_code=504,
            detail={
                "error": "Service temporarily unavailable",
                "code": EXTERNAL_ERROR_CODES["TIMEOUT"],
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Internal error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal service error",
                "code": EXTERNAL_ERROR_CODES["INTERNAL_ERROR"],
            },
        )


@router.get("/health")
async def external_health():
    """Health check for external API."""
    return {"status": "operational", "version": "v1"}
