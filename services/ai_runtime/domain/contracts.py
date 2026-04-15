"""Canonical business contracts for the AI runtime.

These contracts are vertical-agnostic. Realtor-specific types live in
``services/ai_runtime/graph/realtor/contracts`` and must not leak here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


Vertical = Literal["realtor", "healthcare", "legal", "insurance"]
FlowName = Literal["realtor_flow", "basic_flow"]
DialogueAct = Literal[
    "new_search",
    "refine_search",
    "inventory_probe",
    "select_result",
    "confirm_previous",
    "reject_previous",
    "ask_detail",
    "compare",
    "calculate",
    "schedule",
    "faq",
    "document_query",
    "memory_query",
    "lead_capture",
    "recommend",
    "small_talk",
    "unknown",
]
DetailScope = Literal["current_result_set", "resolved_reference"]
ReferenceKind = Literal[
    "ORDINAL",
    "LAST_MENTIONED",
    "BY_ATTRIBUTE",
    "CONTEXT_LOCATION",
    "ANAPHORIC_HISTORY",
    "AMBIGUOUS",
    "NONE",
]
IntentStatus = Literal["pending", "running", "done", "failed", "skipped"]
MemoryEntityStatus = Literal["explicit", "inferred", "confirmed"]
MemoryEntityValueType = Literal["string", "number", "boolean", "list", "object"]


class ChatMessage(BaseModel):
    """Normalized chat message used inside the graph state."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    created_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TenantBusinessProfile(BaseModel):
    """Editable tenant configuration loaded from PostgreSQL."""

    model_config = ConfigDict(extra="allow")

    name: str
    phones: list[str] = Field(default_factory=list)
    email: str | None = None
    operation_zones: list[str] = Field(default_factory=list)
    commissions: dict[str, Any] = Field(default_factory=dict)
    appointment_policy: dict[str, Any] = Field(default_factory=dict)
    schedules: dict[str, Any] = Field(default_factory=dict)


class ScoringCriterionConfig(BaseModel):
    """One scoring dimension configured for a tenant model."""

    model_config = ConfigDict(extra="ignore")

    key: str
    label: str | None = None
    weight: float = 1.0
    min_score: float = 0
    max_score: float = 10
    display_order: int = 0


class ScoringFieldConfig(BaseModel):
    """One extraction/capture field expected by the active scoring prompt."""

    model_config = ConfigDict(extra="ignore")

    key: str
    value_type: str = "string"
    required: bool = False
    question: str | None = None


class ScoringProfile(BaseModel):
    """Tenant scoring profile resolved from scoring model + prompt metadata."""

    model_config = ConfigDict(extra="ignore")

    vertical_id: int | None = None
    model_id: str | None = None
    model_version: int | None = None
    prompt_id: str | None = None
    prompt_version: int | None = None
    prompt_template: str | None = None
    criteria: list[ScoringCriterionConfig] = Field(default_factory=list)
    extraction_fields: list[ScoringFieldConfig] = Field(default_factory=list)
    scoring_contract: dict[str, Any] = Field(default_factory=dict)


class TenantConfig(BaseModel):
    """Runtime tenant configuration cached for the full session."""

    model_config = ConfigDict(extra="allow")

    client_id: str
    vertical: Vertical
    bot_name: str = "Datasyncsa AI"
    tone_prompt: str = ""
    capabilities: list[str] = Field(default_factory=list)
    redis_ttl_seconds: int = 3600
    business: TenantBusinessProfile
    scoring_profile: ScoringProfile | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LeadPlaceholder(BaseModel):
    """Placeholder lead contract for v1."""

    model_config = ConfigDict(protected_namespaces=())

    _status: str = "pending"
    _version: int = 0


class LeadScores(BaseModel):
    apertura: float = 0
    intencion: float = 0
    urgencia: float = 0
    match: float = 0
    solvencia: float = 0


class LeadExtracted(BaseModel):
    nombre: str | None = None
    email: str | None = None
    telefono: str | None = None
    presupuesto: float | None = None
    aprobacion: str | None = None
    preferencias: list[str] = Field(default_factory=list)
    fecha_preferida: str | None = None
    tipo_cita: str | None = None
    appointment_intent: str | None = None


class ConversationEntity(BaseModel):
    """Durable conversational fact extracted from user turns."""

    model_config = ConfigDict(extra="forbid")

    key: str
    value: Any
    value_type: MemoryEntityValueType = "string"
    confidence: float = 0
    source_turn: int | None = None
    source_text: str | None = None
    status: MemoryEntityStatus = "explicit"


class Appointment(BaseModel):
    client_id: str
    id: str | None = None
    reference_id: str | None = None
    lead_id: str | None = None
    tipo: str | None = None
    fecha: str | None = None
    hora: str | None = None
    agente_asignado: str | None = None
    confirmada: bool = False
    datos_completos: bool = False
    notas: str | None = None


class SessionRecord(BaseModel):
    client_id: str
    session_id: str
    user_id: str
    vertical: Vertical
    flow: FlowName
    created_at: datetime | None = None
    last_active: datetime | None = None
    turno_actual: int = 0
    estado: str = "active"
    resumen: str | None = None


class AgentRecord(BaseModel):
    client_id: str
    id: str
    nombre: str
    email: str | None = None
    telefono: str | None = None
    zonas: list[str] = Field(default_factory=list)
    activo: bool = True


class IntentDefinition(BaseModel):
    """Queue item produced by the intent classifier."""

    model_config = ConfigDict(extra="forbid")

    id: str
    type: str
    priority: int
    depends_on: list[str] = Field(default_factory=list)
    condition: dict[str, Any] | None = None
    skip_if_failed: bool = False
    status: IntentStatus = "pending"
    output: dict[str, Any] | None = None


class IntentPlanItem(BaseModel):
    """Structured intent plan returned by analyze_turn before runtime IDs/status are assigned."""

    model_config = ConfigDict(extra="forbid")

    type: str
    priority: int
    depends_on: list[str] = Field(default_factory=list)
    condition: dict[str, Any] | None = None
    skip_if_failed: bool = False


class ReferenceDecision(BaseModel):
    """Structured output from the reference classifier prompt."""

    model_config = ConfigDict(extra="forbid")

    kind: ReferenceKind
    confidence: float = 0
    ordinal_index: int | None = None
    attribute_key: str | None = None
    location_hint: str | None = None
    history_hint: str | None = None
    clarification_target: str | None = None


class TurnAnalysis(BaseModel):
    """Structured understanding of a single user turn."""

    model_config = ConfigDict(extra="forbid")

    dialogue_act: DialogueAct = "unknown"
    confidence: float = 0
    needs_clarification: bool = False
    clarification_target: str | None = None
    reference: ReferenceDecision = Field(default_factory=lambda: ReferenceDecision(kind="NONE", confidence=0))
    intent_plan: list[IntentPlanItem] = Field(default_factory=list)
    filters_delta: dict[str, Any] = Field(default_factory=dict)
    memory_lookup_key: str | None = None
    reuse_current_filters: bool = False
    detail_scope: DetailScope | None = None
    detail_attribute_key: str | None = None


class PendingDecision(BaseModel):
    """Structured decision the user still needs to make before the flow can continue."""

    model_config = ConfigDict(extra="forbid")

    kind: str
    reason: str | None = None
    question: str | None = None
    options: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TextToSQLResult(BaseModel):
    sql: str
    params: dict[str, Any] = Field(default_factory=dict)


class MailDispatchResult(BaseModel):
    enviado: bool
    destinatarios: list[str] = Field(default_factory=list)
    error: str | None = None


class ChatRequest(BaseModel):
    """Canonical request sent to the AI runtime."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    client_id: str = Field(validation_alias=AliasChoices("client_id", "clientId"))
    user_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("user_id", "userId"),
    )
    flow: FlowName | None = None
    message: str = Field(validation_alias=AliasChoices("message", "query_text", "queryText", "text"))
    session_id: str | None = Field(default=None, validation_alias=AliasChoices("session_id", "sessionId"))
    conversation_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("conversation_id", "conversationId"),
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("metadata", "user_metadata", "userMetadata"),
    )


class ChatResponse(BaseModel):
    """Canonical response returned by the AI runtime."""

    model_config = ConfigDict(populate_by_name=True)

    session_id: str
    conversation_id: str
    client_id: str
    vertical: Vertical
    answer: str
    components: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    ui_payload: dict[str, Any] | None = None
    render_mode: str | None = None
    cards_mode: str | None = None
    escalated: bool = False
    scoring_status: str = "disabled"
    metadata: dict[str, Any] = Field(default_factory=dict)


class InternalMemoryResetRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    client_id: str = Field(validation_alias=AliasChoices("client_id", "clientId"))
    reason: str | None = None


class InternalMemoryResetResponse(BaseModel):
    status: str = "ok"
    client_id: str
    conversations_deleted: int
    cache_keys_deleted: int = 0


class InternalSessionResetRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    client_id: str = Field(validation_alias=AliasChoices("client_id", "clientId"))
    session_id: str = Field(validation_alias=AliasChoices("session_id", "sessionId"))
    reason: str | None = None


class InternalSessionResetResponse(BaseModel):
    status: str = "ok"
    client_id: str
    session_id: str
    state_deleted: bool = False
    lead_deleted: bool = False
    trace_deleted: bool = False
