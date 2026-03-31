"""Graph state contracts for generic and realtor assistants."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from services.ai_runtime.domain.contracts import (
    Appointment,
    ChatMessage,
    ConversationEntity,
    FlowName,
    IntentDefinition,
    LeadExtracted,
    LeadPlaceholder,
    LeadScores,
    PendingDecision,
    Property,
    ScoringProfile,
    TenantConfig,
    TurnAnalysis,
    Vertical,
)


DEFAULT_SCORING_CRITERIA_BY_VERTICAL: dict[str, list[str]] = {
    "realtor": ["apertura", "intencion", "urgencia", "match", "solvencia"],
    "healthcare": ["apertura", "intencion", "emergencia", "match", "solvencia"],
    "legal": ["apertura", "intencion", "urgencia", "match", "solvencia"],
    "insurance": ["apertura", "intencion", "urgencia", "match", "solvencia"],
}
DEFAULT_REQUIRED_FIELDS_BY_VERTICAL: dict[str, list[str]] = {
    "realtor": ["nombre", "contacto", "presupuesto", "aprobacion", "fecha_preferida", "appointment_intent"],
    "healthcare": ["nombre", "contacto", "appointment_intent"],
    "legal": ["nombre", "contacto", "appointment_intent"],
    "insurance": ["nombre", "contacto", "presupuesto", "appointment_intent"],
}
SCORING_CRITERION_ALIASES: dict[str, tuple[str, ...]] = {
    "apertura": ("apertura", "engagement", "engage", "openness"),
    "intencion": ("intencion", "intent", "purchase_intent"),
    "urgencia": ("urgencia", "timeline", "urgency", "emergencia", "plazo"),
    "match": ("match", "fit"),
    "solvencia": ("solvencia", "finance", "financial", "affordability"),
}
SCORING_FIELD_ALIASES: dict[str, str] = {
    "extracted_name": "nombre",
    "name": "nombre",
    "full_name": "nombre",
    "extracted_email": "email",
    "correo": "email",
    "mail": "email",
    "extracted_phone": "telefono",
    "phone": "telefono",
    "telefono_principal": "telefono",
    "budget": "presupuesto",
    "timeline": "fecha_preferida",
    "date_preferred": "fecha_preferida",
    "extracted_preferred_date": "fecha_preferida",
    "appointment_date": "fecha_preferida",
    "extracted_approval": "aprobacion",
    "extracted_budget": "presupuesto",
    "extracted_preference": "preferencias",
    "extracted_preferences": "preferencias",
    "extracted_appointment_type": "tipo_cita",
    "extracted_appointment_intent": "appointment_intent",
    "appointment_type": "tipo_cita",
    "schedule_intent": "appointment_intent",
}
_EMAIL_CONTACT_PATTERN = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", flags=re.IGNORECASE)


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
    capture_exposure_count: int = 0
    should_ask: bool = False
    field_to_ask: str | None = None
    question_to_ask: str | None = None
    scoring_profile: ScoringProfile | None = None
    criteria_scores: dict[str, float] = Field(default_factory=dict)
    criteria_reasons: dict[str, str] = Field(default_factory=dict)
    scoring_reasoning: str | None = None
    scoring_confidence: float | None = None
    scoring_last_updated_turn: int | None = None
    target_criteria: list[str] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    target_fields: list[str] = Field(default_factory=list)
    completed_fields: list[str] = Field(default_factory=list)


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
    flow: FlowName
    current_turn: int = 1
    messages: list[ChatMessage] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    tenant_config: TenantConfig
    resolved_references: list[dict[str, Any]] = Field(default_factory=list)
    pending_clarification: str | None = None
    pending_decision: PendingDecision | None = None
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
    """State shared today by healthcare, legal, and insurance tenants."""

    pass


class RealtorGraphState(BaseGraphState):
    """State for the full realtor graph."""

    search_filters: SearchFilters = Field(default_factory=SearchFilters)
    effective_search_filters: SearchFilters | None = None
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


def is_valid_contact_email(value: str | None) -> bool:
    if not value:
        return False
    return bool(_EMAIL_CONTACT_PATTERN.match(value.strip()))


def is_valid_contact_phone(value: str | None) -> bool:
    if not value:
        return False
    digits = re.sub(r"\D", "", value)
    return 8 <= len(digits) <= 15


def has_valid_lead_contact(extracted: LeadExtracted) -> bool:
    return is_valid_contact_email(extracted.email) or is_valid_contact_phone(extracted.telefono)


def _normalize_criterion_key(key: str) -> str:
    return str(key or "").strip().lower()


def _normalize_field_key(key: str) -> str:
    normalized = str(key or "").strip().lower()
    return SCORING_FIELD_ALIASES.get(normalized, normalized)


def _default_scoring_profile(vertical: Vertical) -> ScoringProfile:
    criteria = [
        {"key": key, "display_order": index}
        for index, key in enumerate(DEFAULT_SCORING_CRITERIA_BY_VERTICAL.get(vertical, []), start=1)
    ]
    extraction_fields = [
        {"key": key, "required": True}
        for key in DEFAULT_REQUIRED_FIELDS_BY_VERTICAL.get(vertical, [])
    ]
    return ScoringProfile(criteria=criteria, extraction_fields=extraction_fields)


def _resolve_scoring_profile(tenant_config: TenantConfig) -> ScoringProfile:
    profile = tenant_config.scoring_profile or _default_scoring_profile(tenant_config.vertical)
    criteria = []
    for item in profile.criteria:
        key = _normalize_criterion_key(item.key)
        if not key:
            continue
        criteria.append(item.model_copy(update={"key": key}))
    extraction_fields = []
    for item in profile.extraction_fields:
        key = _normalize_field_key(item.key)
        if not key:
            continue
        extraction_fields.append(item.model_copy(update={"key": key}))
    return profile.model_copy(
        update={
            "criteria": criteria,
            "extraction_fields": extraction_fields,
        }
    )


def _build_criteria_order(profile: ScoringProfile, vertical: Vertical) -> list[str]:
    ordered = sorted(
        [item for item in profile.criteria if _normalize_criterion_key(item.key)],
        key=lambda item: int(item.display_order or 0),
    )
    keys = []
    seen: set[str] = set()
    for item in ordered:
        key = _normalize_criterion_key(item.key)
        if key in seen:
            continue
        seen.add(key)
        keys.append(key)
    if keys:
        return keys
    return list(DEFAULT_SCORING_CRITERIA_BY_VERTICAL.get(vertical, []))


def _build_required_fields(profile: ScoringProfile, vertical: Vertical) -> list[str]:
    explicit = [_normalize_field_key(item.key) for item in profile.extraction_fields if bool(item.required)]
    fallback = [_normalize_field_key(item.key) for item in profile.extraction_fields]
    candidates = explicit or fallback or DEFAULT_REQUIRED_FIELDS_BY_VERTICAL.get(vertical, [])
    normalized: list[str] = []
    seen: set[str] = set()
    for key in candidates:
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        normalized.append(key)
    return normalized


def _legacy_scores_from_dynamic(criteria_scores: dict[str, float]) -> LeadScores:
    def _pick(*aliases: str) -> float:
        for key in aliases:
            normalized = _normalize_criterion_key(key)
            if normalized in criteria_scores:
                return float(criteria_scores[normalized])
        return 0.0

    return LeadScores(
        apertura=_pick(*SCORING_CRITERION_ALIASES["apertura"]),
        intencion=_pick(*SCORING_CRITERION_ALIASES["intencion"]),
        urgencia=_pick(*SCORING_CRITERION_ALIASES["urgencia"]),
        match=_pick(*SCORING_CRITERION_ALIASES["match"]),
        solvencia=_pick(*SCORING_CRITERION_ALIASES["solvencia"]),
    )


def _dynamic_scores_from_legacy(criteria_order: list[str], lead_scores: LeadScores) -> dict[str, float]:
    legacy = {
        "apertura": float(lead_scores.apertura),
        "intencion": float(lead_scores.intencion),
        "urgencia": float(lead_scores.urgencia),
        "match": float(lead_scores.match),
        "solvencia": float(lead_scores.solvencia),
        "emergencia": float(lead_scores.urgencia),
    }

    alias_to_canonical: dict[str, str] = {}
    for canonical, aliases in SCORING_CRITERION_ALIASES.items():
        for alias in aliases:
            normalized = _normalize_criterion_key(alias)
            if normalized:
                alias_to_canonical[normalized] = canonical
    alias_to_canonical.setdefault("emergencia", "urgencia")

    resolved: dict[str, float] = {}
    for raw_key in criteria_order:
        key = _normalize_criterion_key(raw_key)
        canonical = alias_to_canonical.get(key, key)
        resolved[key] = float(legacy.get(canonical, legacy.get(key, 0.0)))
    return resolved


def _field_has_value(extracted: LeadExtracted, field_key: str) -> bool:
    key = _normalize_field_key(field_key)
    if key == "contacto":
        return has_valid_lead_contact(extracted)
    if key == "nombre":
        return bool(extracted.nombre)
    if key == "email":
        return is_valid_contact_email(extracted.email)
    if key == "telefono":
        return is_valid_contact_phone(extracted.telefono)
    if key == "presupuesto":
        return extracted.presupuesto is not None
    if key == "aprobacion":
        return bool(extracted.aprobacion)
    if key == "fecha_preferida":
        return bool(extracted.fecha_preferida)
    if key == "tipo_cita":
        return bool(extracted.tipo_cita)
    if key == "appointment_intent":
        return bool(extracted.appointment_intent)
    value = getattr(extracted, key, None)
    if isinstance(value, list):
        return bool(value)
    return value not in (None, "")


def build_lead_advisor_state(
    tenant_config: TenantConfig,
    previous: LeadAdvisorState | None = None,
) -> LeadAdvisorState:
    profile = _resolve_scoring_profile(tenant_config)
    criteria_order = _build_criteria_order(profile, tenant_config.vertical)
    previous_dynamic_scores = dict((previous.criteria_scores if previous else {}) or {})
    previous_reasons = dict((previous.criteria_reasons if previous else {}) or {})
    if not previous_dynamic_scores and previous:
        previous_dynamic_scores = _dynamic_scores_from_legacy(criteria_order, previous.lead_scores)
    criteria_scores = {
        key: float(previous_dynamic_scores.get(key, 0.0))
        for key in criteria_order
    }
    criteria_reasons = {
        key: str(previous_reasons.get(key) or "").strip()
        for key in criteria_order
        if str(previous_reasons.get(key) or "").strip()
    }
    lead_extracted = previous.lead_extracted if previous else LeadExtracted()
    required_fields = _build_required_fields(profile, tenant_config.vertical)
    completed_fields = [field for field in required_fields if _field_has_value(lead_extracted, field)]
    lead_complete = bool(required_fields) and len(completed_fields) >= len(required_fields)
    return LeadAdvisorState(
        lead_scores=_legacy_scores_from_dynamic(criteria_scores),
        lead_extracted=lead_extracted,
        lead_completo=lead_complete,
        capture_exposure_count=int(previous.capture_exposure_count or 0) if previous else 0,
        should_ask=bool(previous.should_ask) if previous else False,
        field_to_ask=previous.field_to_ask if previous else None,
        question_to_ask=previous.question_to_ask if previous else None,
        scoring_profile=profile,
        criteria_scores=criteria_scores,
        criteria_reasons=criteria_reasons,
        scoring_reasoning=(previous.scoring_reasoning if previous else None),
        scoring_confidence=(previous.scoring_confidence if previous else None),
        scoring_last_updated_turn=(previous.scoring_last_updated_turn if previous else None),
        target_criteria=list(criteria_order),
        required_fields=list(required_fields),
        target_fields=list(required_fields),
        completed_fields=completed_fields,
    )


def build_base_state(
    *,
    session_id: str,
    conversation_id: str,
    user_id: str,
    client_id: str,
    vertical: Vertical,
    flow: FlowName,
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
        flow=flow,
        capabilities=list(tenant_config.capabilities),
        tenant_config=tenant_config,
        messages=[ChatMessage(role="user", content=initial_message)],
        cita=Appointment(client_id=client_id),
        lead_advisor=build_lead_advisor_state(tenant_config),
    )
