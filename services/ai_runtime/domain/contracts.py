"""Canonical business contracts for the AI runtime."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


Vertical = Literal["realtor", "healthcare", "legal"]
BridgeName = Literal["property-bridge", "generic-bridge"]
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
AppointmentType = Literal["presencial", "visita", "videollamada"]


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
    metadata: dict[str, Any] = Field(default_factory=dict)


class PropertyFeatures(BaseModel):
    """Canonical normalized property feature set."""

    garage_clean: int
    bedrooms_clean: int
    bathrooms_clean: float
    sqm_clean: int | None = None
    lot_size_sqm: str | None = None
    year_built: str | None = None
    amenities: list[str] = Field(default_factory=list)
    is_featured: bool = False
    size_unit: str | None = None
    garage: str | None = None
    bedrooms: str | None = None
    bathrooms: str | None = None


class PropertyMedia(BaseModel):
    primary_image_url: str | None = None
    image_urls: list[str] = Field(default_factory=list)


class PropertyLocation(BaseModel):
    country: str | None = None
    province: str | None = None
    lat: float | None = None
    lng: float | None = None


class PropertyMeta(BaseModel):
    source_system: str | None = None
    source_property_ref: str | None = None
    ingested_at: datetime | None = None
    updated_at: datetime | None = None


class Property(BaseModel):
    """Canonical property contract v1.0."""

    model_config = ConfigDict(extra="forbid")

    property_id_internal: str
    client_id: str
    title: str
    description_html: str
    price: float
    currency: str
    address: str | None = None
    features: PropertyFeatures
    media: PropertyMedia = Field(default_factory=PropertyMedia)
    location: PropertyLocation = Field(default_factory=PropertyLocation)
    meta: PropertyMeta = Field(default_factory=PropertyMeta)


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


class Appointment(BaseModel):
    client_id: str
    id: str | None = None
    propiedad_id: str | None = None
    lead_id: str | None = None
    tipo: AppointmentType | None = None
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
    bridge: BridgeName
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


class TextToSQLResult(BaseModel):
    sql: str
    params: dict[str, Any] = Field(default_factory=dict)


class PropertyComparisonScore(BaseModel):
    property_id_internal: str
    score_total: float
    dimensions: dict[str, float] = Field(default_factory=dict)


class CardPayload(BaseModel):
    property_id_internal: str
    title: str
    price: float
    currency: str
    bedrooms_clean: int
    bathrooms_clean: float
    sqm_clean: int | None = None
    primary_image_url: str | None = None
    province: str | None = None


class MailDispatchResult(BaseModel):
    enviado: bool
    destinatarios: list[str] = Field(default_factory=list)
    error: str | None = None


class ChatRequest(BaseModel):
    """Canonical request that bridges send to the AI runtime."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    client_id: str = Field(validation_alias=AliasChoices("client_id", "clientId"))
    user_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("user_id", "userId"),
    )
    bridge: BridgeName | None = None
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
