"""Conversation bootstrap and orchestration helpers."""

from __future__ import annotations

from uuid import uuid4

from services.ai_runtime.config.tenant_loader import TenantLoader
from services.ai_runtime.domain.contracts import ChatMessage
from services.ai_runtime.domain.contracts import (
    ChatRequest,
    ChatResponse,
    InternalMemoryResetResponse,
    InternalSessionResetResponse,
)
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import (
    BaseGraphState,
    GenericGraphState,
    MemoryLookupState,
    RealtorGraphState,
    build_base_state,
)
from services.ai_runtime.graph.registry import GraphRegistry
from services.ai_runtime.runtime.turn_trace import (
    TurnTraceContext,
    activate_turn_trace,
    activate_latest_turn_state,
    deactivate_turn_trace,
    deactivate_latest_turn_state,
    summarize_state,
    utc_now_iso,
)


def _resolve_bridge(vertical: str, bridge: str | None) -> str:
    if bridge:
        return bridge
    return "property-bridge" if vertical == "realtor" else "generic-bridge"


def _build_components(final_state: BaseGraphState) -> list[dict[str, object]]:
    components: list[dict[str, object]] = []
    ui_payload = getattr(final_state, "ui_payload", None) or {}
    for card in ui_payload.get("property_cards", []):
        components.append(
            {
                "type": "property-card",
                "listing_id": card.get("property_id_internal"),
                "title": card.get("title"),
                "price": card.get("price"),
                "image_url": card.get("primary_image_url"),
                "public_url": card.get("public_url"),
                "city": card.get("province"),
                "neighborhood": card.get("province"),
            }
        )
    return components


def _reset_turn_scoped_state(base_state: BaseGraphState) -> None:
    """Clear fields that belong to a single turn while keeping session memory alive."""

    base_state.final_response = None
    base_state.pending_clarification = None
    base_state.clarification_attempts = 0
    base_state.resolved_references = []
    base_state.intent_queue = []
    base_state.active_intent = None
    base_state.completed_intents = []
    base_state.turn_outputs = []
    base_state.turn_analysis = None
    base_state.lead_advisor.should_ask = False
    base_state.lead_advisor.field_to_ask = None
    base_state.memory.last_lookup = MemoryLookupState()

    if isinstance(base_state, RealtorGraphState):
        base_state.render_mode = None
        base_state.cards_mode = None
        base_state.ui_payload = None
        base_state.search_attempts = 0


class ConversationRuntime:
    """Coordinates tenant loading, state hydration, graph execution, and persistence."""

    def __init__(
        self,
        *,
        tenant_loader: TenantLoader,
        graph_registry: GraphRegistry,
        dependencies: GraphDependencies,
    ):
        self.tenant_loader = tenant_loader
        self.graph_registry = graph_registry
        self.dependencies = dependencies

    async def handle_turn(self, request: ChatRequest) -> ChatResponse:
        tenant_config = await self.tenant_loader.load(request.client_id)
        bridge = _resolve_bridge(tenant_config.vertical, request.bridge)
        user_id = (
            request.user_id
            or str(request.metadata.get("channel_user_id") or "")
            or str(request.metadata.get("user_id") or "")
            or str(request.metadata.get("lead_id") or "")
            or f"anonymous:{request.client_id}"
        )
        session_id = request.session_id or str(uuid4())
        conversation_id = request.conversation_id or str(uuid4())
        existing_payload = await self.dependencies.session_store.get_state(request.client_id, session_id)

        if existing_payload:
            state_cls = RealtorGraphState if tenant_config.vertical == "realtor" else GenericGraphState
            base_state = state_cls.model_validate(existing_payload)
            base_state.tenant_config = tenant_config
            base_state.capabilities = list(tenant_config.capabilities)
            base_state.vertical = tenant_config.vertical
            base_state.bridge = bridge
            base_state.user_id = user_id
            _reset_turn_scoped_state(base_state)
            base_state.current_turn += 1
            base_state.messages.append(ChatMessage(role="user", content=request.message))
            conversation_id = base_state.conversation_id
        else:
            state = build_base_state(
                session_id=session_id,
                conversation_id=conversation_id,
                user_id=user_id,
                client_id=request.client_id,
                vertical=tenant_config.vertical,
                bridge=bridge,
                tenant_config=tenant_config,
                initial_message=request.message,
            )
            if tenant_config.vertical == "realtor":
                base_state = RealtorGraphState.model_validate(state.model_dump())
            else:
                base_state = GenericGraphState.model_validate(state.model_dump())
            _reset_turn_scoped_state(base_state)
            conversation_id = base_state.conversation_id

        trace_context = TurnTraceContext(
            trace_id=str(uuid4()),
            client_id=request.client_id,
            session_id=session_id,
            conversation_id=conversation_id,
            vertical=tenant_config.vertical,
            bridge=bridge,
            turn=base_state.current_turn,
            user_id=user_id,
            user_message=request.message,
            started_at=utc_now_iso(),
        )
        token = activate_turn_trace(trace_context)
        state_token = activate_latest_turn_state(base_state.model_dump(mode="json"))
        self.dependencies.trace_store.start_turn(
            trace_context,
            request_metadata=request.metadata,
            state_summary=summarize_state(base_state.model_dump(mode="json")),
        )
        graph = self.graph_registry.get_graph(tenant_config.vertical, bridge, self.dependencies)
        try:
            final_payload = await graph.ainvoke(base_state.model_dump(mode="json"))
            final_state = (
                RealtorGraphState.model_validate(final_payload)
                if tenant_config.vertical == "realtor"
                else GenericGraphState.model_validate(final_payload)
            )
            components = _build_components(final_state)
            rag_outputs = [
                item
                for item in final_state.turn_outputs
                if item.get("type") in {"rag_agencia", "rag_docs"}
            ]
            sources = [chunk for output in rag_outputs for chunk in output.get("chunks", [])]
            await self.dependencies.session_store.set_state(
                request.client_id,
                session_id,
                final_state.model_dump(mode="json"),
                tenant_config.redis_ttl_seconds,
            )
            response = ChatResponse(
                session_id=session_id,
                conversation_id=conversation_id,
                client_id=request.client_id,
                vertical=tenant_config.vertical,
                answer=final_state.final_response or "",
                components=components,
                sources=sources,
                ui_payload=getattr(final_state, "ui_payload", None),
                render_mode=getattr(final_state, "render_mode", None),
                cards_mode=getattr(final_state, "cards_mode", None),
                escalated=final_state.escalacion.solicitada,
                scoring_status="disabled",
                metadata={"bridge": bridge, "turn": final_state.current_turn, "trace_id": trace_context.trace_id},
            )
            self.dependencies.trace_store.finish_turn(
                status="completed",
                final_state_summary=summarize_state(final_state.model_dump(mode="json")),
                response_payload=response.model_dump(mode="json"),
            )
            return response
        except Exception as exc:
            self.dependencies.trace_store.finish_turn(
                status="failed",
                final_state_summary=summarize_state(base_state.model_dump(mode="json")),
                error=repr(exc),
            )
            raise
        finally:
            deactivate_latest_turn_state(state_token)
            deactivate_turn_trace(token)

    async def reset_client_memory(self, client_id: str) -> InternalMemoryResetResponse:
        conversations_deleted = await self.dependencies.session_store.delete_by_client(client_id)
        cache_keys_deleted = 0
        cache_keys_deleted += await self.dependencies.lead_store.delete_by_client(client_id)
        cache_keys_deleted += await self.dependencies.tenant_cache.delete_client_runtime(client_id)
        return InternalMemoryResetResponse(
            client_id=client_id,
            conversations_deleted=conversations_deleted,
            cache_keys_deleted=cache_keys_deleted,
        )

    async def reset_session_memory(self, client_id: str, session_id: str) -> InternalSessionResetResponse:
        state_deleted = await self.dependencies.session_store.delete_session(client_id, session_id)
        lead_deleted = await self.dependencies.lead_store.delete_session(client_id, session_id)
        trace_result = self.dependencies.trace_store.delete_session(client_id, session_id)
        return InternalSessionResetResponse(
            client_id=client_id,
            session_id=session_id,
            state_deleted=state_deleted,
            lead_deleted=lead_deleted,
            trace_deleted=bool(trace_result.get("deleted")),
        )
