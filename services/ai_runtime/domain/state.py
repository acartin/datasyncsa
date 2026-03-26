"""Graph state contracts for generic and realtor assistants."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from services.ai_runtime.domain.contracts import (
    Appointment,
    BridgeName,
    ChatMessage,
    ConversationEntity,
    IntentDefinition,
    LeadExtracted,
    LeadPlaceholder,
    LeadScores,
    Property,
    TenantConfig,
    TurnAnalysis,
    Vertical,
)


class SearchFilters(BaseModel):
    ubicacion: str | None = None
    habitaciones: int | None = None
    banos: float | None = None
    garage: int | None = None
    precio_max: float | None = None
    precio_min: float | None = None
    currency: str | None = None
    provincia: str | None = None
    amenidades: list[str] = Field(default_factory=list)
    tipo: str | None = None
    operacion: str | None = None


class FinancialContext(BaseModel):
    property_id: str | None = None
    price: float | None = None
    currency: str | None = None
    prima: float | None = None
    plazo: int | None = None
    banco: str | None = None
    resultado: dict[str, Any] | None = None


class EscalationState(BaseModel):
    solicitada: bool = False
    motivo: str | None = None
    agente_asignado: str | None = None
    datos_capturados: dict[str, Any] = Field(default_factory=dict)


class LeadAdvisorState(BaseModel):
    lead_scores: LeadScores = Field(default_factory=LeadScores)
    lead_extracted: LeadExtracted = Field(default_factory=LeadExtracted)
    lead_completo: bool = False
    should_ask: bool = False
    field_to_ask: str | None = None


class MemoryLookupState(BaseModel):
    handled: bool = False
    key: str | None = None
    answer: str | None = None
    source: str | None = None


class ConversationMemoryState(BaseModel):
    entities: list[ConversationEntity] = Field(default_factory=list)
    last_lookup: MemoryLookupState = Field(default_factory=MemoryLookupState)


class BaseGraphState(BaseModel):
    """Shared state that exists from the first turn onward."""

    model_config = ConfigDict(extra="allow")

    session_id: str
    conversation_id: str
    user_id: str
    client_id: str
    vertical: Vertical
    bridge: BridgeName
    current_turn: int = 1
    messages: list[ChatMessage] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    tenant_config: TenantConfig
    resolved_references: list[dict[str, Any]] = Field(default_factory=list)
    pending_clarification: str | None = None
    clarification_attempts: int = 0
    intent_queue: list[IntentDefinition] = Field(default_factory=list)
    active_intent: IntentDefinition | None = None
    completed_intents: list[IntentDefinition] = Field(default_factory=list)
    turn_outputs: list[dict[str, Any]] = Field(default_factory=list)
    turn_analysis: TurnAnalysis | None = None
    cita: Appointment
    escalacion: EscalationState = Field(default_factory=EscalationState)
    lead_advisor: LeadAdvisorState = Field(default_factory=LeadAdvisorState)
    memory: ConversationMemoryState = Field(default_factory=ConversationMemoryState)
    lead: LeadPlaceholder = Field(default_factory=LeadPlaceholder)
    final_response: str | None = None


class GenericGraphState(BaseGraphState):
    """State for healthcare and legal tenants."""

    pass


class RealtorGraphState(BaseGraphState):
    """State for the full realtor graph."""

    search_filters: SearchFilters = Field(default_factory=SearchFilters)
    inventory: list[Property] = Field(default_factory=list)
    last_search_results: list[Property] = Field(default_factory=list)
    last_mentioned: Property | None = None
    active_comparison: list[str] = Field(default_factory=list)
    focus_scope: str | None = None
    search_attempts: int = 0
    cards_shown: list[str] = Field(default_factory=list)
    cards_mode: str | None = None
    render_mode: str | None = None
    ui_payload: dict[str, Any] | None = None
    financial_context: FinancialContext = Field(default_factory=FinancialContext)


def build_base_state(
    *,
    session_id: str,
    conversation_id: str,
    user_id: str,
    client_id: str,
    vertical: Vertical,
    bridge: BridgeName,
    tenant_config: TenantConfig,
    initial_message: str,
) -> BaseGraphState:
    """Bootstrap the canonical base state for a new session."""

    return BaseGraphState(
        session_id=session_id,
        conversation_id=conversation_id,
        user_id=user_id,
        client_id=client_id,
        vertical=vertical,
        bridge=bridge,
        capabilities=list(tenant_config.capabilities),
        tenant_config=tenant_config,
        messages=[ChatMessage(role="user", content=initial_message)],
        cita=Appointment(client_id=client_id),
    )
