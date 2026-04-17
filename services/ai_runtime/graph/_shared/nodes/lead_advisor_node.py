"""Lead advisor node."""

from __future__ import annotations

from typing import Any

from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import (
    BaseGraphState,
    LeadAdvisorState,
    SCORING_FIELD_ALIASES,
    build_lead_advisor_state,
)
from services.ai_runtime.graph._shared.scoring_hybrid import enrich_lead_advisor_with_llm_scoring

EXPOSURE_OUTPUT_TYPES = {
    "search",
    "render_cards",
    "show_result_cards",
    "appointment",
    "property_focus",
    "property_selection",
    "result_set_detail",
}
FIELD_QUESTION_HINTS = {
    "nombre": ("nombre", "llamas", "gusto"),
    "email": ("correo", "email", "mail"),
    "telefono": ("telefono", "teléfono", "numero", "número"),
    "contacto": ("correo", "email", "telefono", "teléfono", "numero", "número"),
    "presupuesto": ("presupuesto", "rango", "monto"),
    "aprobacion": ("preaprob", "aprob", "prima", "banco", "hipotec"),
    "preferencias": ("zona", "caracter", "prefer", "buscas", "prioriz"),
    "fecha_preferida": ("cuando", "fecha", "mudar", "visitar"),
    "tipo_cita": ("visita", "videollamada", "llamada"),
    "appointment_intent": ("cita", "agendar", "coordinar"),
}
CAPTURE_ELIGIBLE_DIALOGUE_ACTS = {
    "new_search",
    "refine_search",
    "select_result",
    "ask_detail",
    "compare",
    "calculate",
    "schedule",
    "confirm_previous",
    "recommend",
}
CHANNEL_ALIASES = {
    "meta_whatsapp": "whatsapp",
    "whatsapp": "whatsapp",
    "meta_telegram": "telegram",
    "telegram": "telegram",
    "web_html": "webchat",
    "webchat": "webchat",
    "web": "webchat",
    "api": "webchat",
    "meta_ig": "instagram",
    "instagram": "instagram",
    "meta_messenger": "messenger",
    "messenger": "messenger",
}
REALTOR_PROGRESSIVE_DEFAULTS = {
    "sale": [
        "presupuesto",
        "aprobacion",
        "fecha_preferida",
        "appointment_intent",
        "tipo_cita",
        "contacto",
        "email",
        "telefono",
        "preferencias",
        "nombre",
    ],
    "rent": [
        "fecha_preferida",
        "presupuesto",
        "appointment_intent",
        "tipo_cita",
        "contacto",
        "email",
        "telefono",
        "preferencias",
        "nombre",
    ],
    "default": [
        "appointment_intent",
        "tipo_cita",
        "contacto",
        "email",
        "telefono",
        "presupuesto",
        "aprobacion",
        "fecha_preferida",
        "preferencias",
        "nombre",
    ],
}


def _compose_preferred_datetime(fecha: Any, hora: Any) -> str | None:
    fecha_text = str(fecha or "").strip()
    hora_text = str(hora or "").strip()
    combined = " ".join(part for part in (fecha_text, hora_text) if part).strip()
    return combined or None


def _normalize_field_key(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    return SCORING_FIELD_ALIASES.get(normalized, normalized)


def _coerce_budget_hint(value: Any) -> float | None:
    if value in (None, "", []):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return None
    if isinstance(value, dict):
        for key in ("max", "hasta", "value", "amount"):
            candidate = _coerce_budget_hint(value.get(key))
            if candidate is not None:
                return candidate
        for key in ("min", "desde"):
            candidate = _coerce_budget_hint(value.get(key))
            if candidate is not None:
                return candidate
    return None


def _sync_lead_extracted_from_state(graph_state: BaseGraphState, advisor_state: LeadAdvisorState) -> LeadAdvisorState:
    from services.ai_runtime.verticals import get_vertical_spec

    payload = advisor_state.lead_extracted.model_dump(mode="json")

    latest_entities: dict[str, Any] = {}
    for entity in reversed(graph_state.memory.entities):
        key = _normalize_field_key(getattr(entity, "key", None))
        if not key or key in latest_entities:
            continue
        latest_entities[key] = entity.value

    if not payload.get("nombre") and latest_entities.get("nombre"):
        payload["nombre"] = latest_entities["nombre"]
    if not payload.get("email") and latest_entities.get("email"):
        payload["email"] = latest_entities["email"]
    if not payload.get("telefono") and latest_entities.get("telefono"):
        payload["telefono"] = latest_entities["telefono"]
    if not payload.get("aprobacion") and latest_entities.get("aprobacion"):
        payload["aprobacion"] = latest_entities["aprobacion"]
    if not payload.get("fecha_preferida") and latest_entities.get("fecha_preferida"):
        payload["fecha_preferida"] = latest_entities["fecha_preferida"]
    if not payload.get("tipo_cita") and latest_entities.get("tipo_cita"):
        payload["tipo_cita"] = latest_entities["tipo_cita"]

    if payload.get("presupuesto") is None:
        for key in ("presupuesto", "presupuesto_maximo", "presupuesto_rango", "presupuesto_minimo"):
            candidate = _coerce_budget_hint(latest_entities.get(key))
            if candidate is not None:
                payload["presupuesto"] = candidate
                break

    payload = get_vertical_spec(graph_state.vertical).policy.extra_lead_sync(graph_state, payload)

    if not payload.get("tipo_cita") and graph_state.cita.tipo:
        payload["tipo_cita"] = str(graph_state.cita.tipo)

    if not payload.get("fecha_preferida"):
        preferred_datetime = _compose_preferred_datetime(graph_state.cita.fecha, graph_state.cita.hora)
        if preferred_datetime:
            payload["fecha_preferida"] = preferred_datetime

    if (
        not payload.get("appointment_intent")
        and (
            graph_state.cita.tipo
            or graph_state.cita.fecha
            or graph_state.cita.hora
            or graph_state.cita.propiedad_id
        )
    ):
        payload["appointment_intent"] = "positive"

    if _normalize_field_key(payload.get("appointment_intent")) == "negative":
        payload["tipo_cita"] = None

    synchronized = advisor_state.model_copy(
        update={
            "lead_extracted": advisor_state.lead_extracted.model_validate(payload),
        }
    )
    return build_lead_advisor_state(graph_state.tenant_config, synchronized)


def _pending_fields(advisor_state: LeadAdvisorState) -> list[str]:
    required_fields = list(advisor_state.required_fields or advisor_state.target_fields)
    completed = set(advisor_state.completed_fields or [])
    pending = [field for field in required_fields if field not in completed]
    if _normalize_field_key(advisor_state.lead_extracted.appointment_intent) == "negative":
        pending = [field for field in pending if _normalize_field_key(field) != "tipo_cita"]
    return pending


def _normalize_channel(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    return CHANNEL_ALIASES.get(raw, raw)


def _resolve_current_channel(graph_state: BaseGraphState) -> str:
    for message in reversed(graph_state.messages):
        if str(getattr(message, "role", "")).strip().lower() != "user":
            continue
        metadata = getattr(message, "metadata", None)
        if not isinstance(metadata, dict):
            continue
        for key in ("channel", "platform"):
            normalized = _normalize_channel(metadata.get(key))
            if normalized:
                return normalized
    return "webchat"


def _resolve_realtor_journey(graph_state: BaseGraphState) -> str:
    if str(graph_state.vertical).strip().lower() != "realtor":
        return "default"

    candidates: list[str] = []
    search_filters = getattr(graph_state, "search_filters", None)
    if search_filters is not None:
        candidates.append(str(getattr(search_filters, "operacion", "") or ""))
    effective_filters = getattr(graph_state, "effective_search_filters", None)
    if effective_filters is not None:
        candidates.append(str(getattr(effective_filters, "operacion", "") or ""))

    for candidate in candidates:
        normalized = candidate.strip().lower()
        if not normalized:
            continue
        if any(token in normalized for token in ("alquiler", "renta", "rent", "arrendar")):
            return "rent"
        if any(token in normalized for token in ("venta", "comprar", "compra", "sale", "buy")):
            return "sale"
    return "default"


def _resolve_contact_field(
    *,
    graph_state: BaseGraphState,
    advisor_state: LeadAdvisorState,
    pending: list[str],
) -> str | None:
    normalized_pending = {_normalize_field_key(item) for item in pending}
    has_email = "email" in normalized_pending
    has_phone = "telefono" in normalized_pending

    if not has_email and not has_phone:
        if "contacto" in normalized_pending:
            return "contacto"
        return None
    if has_phone and not has_email:
        return "telefono"
    if has_email and not has_phone:
        return "email"

    profile = advisor_state.scoring_profile
    scoring_contract = dict(profile.scoring_contract or {}) if profile else {}
    progressive = scoring_contract.get("progressive_profile")
    contact_policy: Any = None
    if isinstance(progressive, dict):
        contact_policy = progressive.get("contact_policy")

    policy_name = "channel_aware"
    channel = _resolve_current_channel(graph_state)
    if isinstance(contact_policy, str):
        policy_name = contact_policy.strip().lower() or policy_name
    elif isinstance(contact_policy, dict):
        default_policy = str(contact_policy.get("default") or "").strip().lower()
        by_channel = contact_policy.get("by_channel")
        if not isinstance(by_channel, dict):
            by_channel = contact_policy.get("channels")
        channel_policy = ""
        if isinstance(by_channel, dict):
            channel_policy = str(by_channel.get(channel) or "").strip().lower()
            if channel_policy:
                policy_name = channel_policy
        if not channel_policy and default_policy:
            policy_name = default_policy

    if policy_name in {"phone_first", "prefer_phone", "whatsapp_first"}:
        return "telefono"
    if policy_name in {"email_first", "prefer_email"}:
        return "email"
    if channel in {"whatsapp", "telegram"}:
        return "telefono"
    return "email"


def _resolve_realtor_progressive_order(
    *,
    graph_state: BaseGraphState,
    advisor_state: LeadAdvisorState,
) -> list[str]:
    journey = _resolve_realtor_journey(graph_state)
    profile = advisor_state.scoring_profile
    scoring_contract = dict(profile.scoring_contract or {}) if profile else {}
    progressive = scoring_contract.get("progressive_profile")
    journey_orders: dict[str, Any] = {}
    if isinstance(progressive, dict):
        raw_orders = progressive.get("journey_field_orders")
        if isinstance(raw_orders, dict):
            journey_orders = raw_orders

    sequence = journey_orders.get(journey)
    if not isinstance(sequence, list):
        sequence = journey_orders.get("default")
    if not isinstance(sequence, list):
        sequence = REALTOR_PROGRESSIVE_DEFAULTS.get(journey, REALTOR_PROGRESSIVE_DEFAULTS["default"])

    resolved: list[str] = []
    for item in sequence:
        if not isinstance(item, str):
            continue
        normalized = _normalize_field_key(item)
        if normalized:
            resolved.append(normalized)
    return resolved


def _select_realtor_progressive_fallback(
    *,
    graph_state: BaseGraphState,
    advisor_state: LeadAdvisorState,
    pending: list[str],
    dialogue_act: str | None,
) -> str | None:
    if str(graph_state.vertical).strip().lower() != "realtor":
        return None

    normalized_act = str(dialogue_act or "").strip().lower()
    if normalized_act not in CAPTURE_ELIGIBLE_DIALOGUE_ACTS:
        return None

    normalized_pending = {_normalize_field_key(item) for item in pending}
    appointment_intent = _normalize_field_key(advisor_state.lead_extracted.appointment_intent)
    ordered_fields = _resolve_realtor_progressive_order(
        graph_state=graph_state,
        advisor_state=advisor_state,
    )

    for candidate in ordered_fields:
        if candidate == "contacto":
            resolved_contact = _resolve_contact_field(
                graph_state=graph_state,
                advisor_state=advisor_state,
                pending=pending,
            )
            if resolved_contact and _normalize_field_key(resolved_contact) in normalized_pending:
                return resolved_contact
            continue
        if candidate not in normalized_pending:
            continue
        if candidate == "tipo_cita" and appointment_intent != "positive":
            continue
        return candidate

    if "email" in normalized_pending and "telefono" in normalized_pending:
        return _resolve_contact_field(
            graph_state=graph_state,
            advisor_state=advisor_state,
            pending=pending,
        )
    for item in pending:
        normalized = _normalize_field_key(item)
        if normalized in normalized_pending:
            return normalized
    return None


def _select_field_to_ask(
    graph_state: BaseGraphState,
    advisor_state: LeadAdvisorState,
    *,
    suggested_field: str | None,
    dialogue_act: str | None,
    capture_exposure_count: int,
    current_turn_is_exposure: bool,
) -> str | None:
    pending = _pending_fields(advisor_state)
    if not pending:
        return None

    normalized_act = str(dialogue_act or "").strip().lower()
    if normalized_act in {"small_talk", "unknown", "memory_query", "reject_previous", "lead_capture"}:
        return None
    if int(capture_exposure_count or 0) < 2:
        return None

    profile = advisor_state.scoring_profile
    normalized_suggested = _normalize_field_key(suggested_field)
    if current_turn_is_exposure and int(capture_exposure_count or 0) == 2 and "nombre" in pending:
        return "nombre"

    if (
        normalized_act == "calculate"
        and advisor_state.lead_extracted.presupuesto is not None
        and "aprobacion" in pending
    ):
        return "aprobacion"

    if normalized_act == "schedule":
        if str(graph_state.vertical).strip().lower() == "realtor":
            if "appointment_intent" in pending:
                return "appointment_intent"
            if _normalize_field_key(advisor_state.lead_extracted.appointment_intent) == "positive" and "tipo_cita" in pending:
                return "tipo_cita"
            schedule_contact = _resolve_contact_field(
                graph_state=graph_state,
                advisor_state=advisor_state,
                pending=pending,
            )
            if schedule_contact:
                return schedule_contact
        else:
            if "email" in pending and "telefono" in pending:
                return "contacto"
            if "email" in pending:
                return "email"
            if "telefono" in pending:
                return "telefono"

    if normalized_suggested == "contacto":
        if str(graph_state.vertical).strip().lower() == "realtor":
            suggested_contact = _resolve_contact_field(
                graph_state=graph_state,
                advisor_state=advisor_state,
                pending=pending,
            )
            if suggested_contact:
                return suggested_contact
        else:
            if "email" in pending and "telefono" in pending:
                return "contacto"
            if "email" in pending:
                return "email"
            if "telefono" in pending:
                return "telefono"
    if (
        str(graph_state.vertical).strip().lower() == "realtor"
        and normalized_suggested in {"email", "telefono"}
        and "email" in pending
        and "telefono" in pending
    ):
        policy_contact = _resolve_contact_field(
            graph_state=graph_state,
            advisor_state=advisor_state,
            pending=pending,
        )
        if policy_contact:
            return policy_contact
    if normalized_suggested and normalized_suggested in pending:
        return normalized_suggested

    # Si el tenant ya tiene prompt de scoring activo, usa fallback determinista realtor antes de abortar.
    if profile and str(profile.prompt_template or "").strip():
        return _select_realtor_progressive_fallback(
            graph_state=graph_state,
            advisor_state=advisor_state,
            pending=pending,
            dialogue_act=normalized_act,
        )

    # Fallback legacy solo para tenants sin scoring prompt activo.
    if normalized_act not in CAPTURE_ELIGIBLE_DIALOGUE_ACTS:
        return None
    return pending[0]


def _output_counts_as_case_exposure(item: dict[str, Any]) -> bool:
    output_type = str(item.get("type") or "").strip().lower()
    if output_type not in EXPOSURE_OUTPUT_TYPES:
        return False
    if output_type in {"search", "render_cards", "show_result_cards"}:
        try:
            return int(item.get("count") or 0) > 0
        except (TypeError, ValueError):
            return False
    return True


def _turn_counts_as_case_exposure(graph_state: BaseGraphState) -> bool:
    return any(_output_counts_as_case_exposure(item) for item in graph_state.turn_outputs)


def _question_from_profile(advisor_state: LeadAdvisorState, field_key: str | None) -> str | None:
    if not field_key or not advisor_state.scoring_profile:
        return None
    normalized_field = _normalize_field_key(field_key)
    for field in advisor_state.scoring_profile.extraction_fields:
        if _normalize_field_key(field.key) != normalized_field:
            continue
        question = str(field.question or "").strip()
        if question:
            return question
    return None


def _question_matches_field(field_key: str | None, question: str | None) -> bool:
    normalized_field = _normalize_field_key(field_key)
    normalized_question = str(question or "").strip().lower()
    if not normalized_field or not normalized_question:
        return False
    hints = FIELD_QUESTION_HINTS.get(normalized_field, ())
    if not hints:
        return True
    return any(hint in normalized_question for hint in hints)


def _resolve_question_to_ask(
    advisor_state: LeadAdvisorState,
    *,
    field_to_ask: str | None,
    suggested_question: str | None,
) -> str | None:
    if not field_to_ask:
        return None
    # Precedence: dynamic prompt hint -> schema wording -> synthesize fallback.
    prompt_question = str(suggested_question or "").strip()
    if prompt_question and _question_matches_field(field_to_ask, prompt_question):
        return prompt_question
    return _question_from_profile(advisor_state, field_to_ask)


async def lead_advisor(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    """Evaluate the next best lead question using prompt output plus deterministic guardrails."""

    graph_state = BaseGraphState.model_validate(state)
    advisor_state = build_lead_advisor_state(graph_state.tenant_config, graph_state.lead_advisor)
    advisor_state = _sync_lead_extracted_from_state(graph_state, advisor_state)
    capture_exposure_count = int(advisor_state.capture_exposure_count or 0)
    if _turn_counts_as_case_exposure(graph_state):
        capture_exposure_count += 1
        advisor_state = advisor_state.model_copy(update={"capture_exposure_count": capture_exposure_count})
    enriched_advisor, scoring_output, slot_hints = await enrich_lead_advisor_with_llm_scoring(
        graph_state,
        advisor_state,
        deps,
    )
    advisor_state = build_lead_advisor_state(graph_state.tenant_config, enriched_advisor)
    dialogue_act = graph_state.turn_analysis.dialogue_act if graph_state.turn_analysis else None
    suggested_field = (slot_hints or {}).get("suggested_field") if slot_hints else None
    suggested_question = (slot_hints or {}).get("suggested_question") if slot_hints else None
    field_to_ask = _select_field_to_ask(
        graph_state,
        advisor_state,
        suggested_field=suggested_field,
        dialogue_act=dialogue_act,
        capture_exposure_count=capture_exposure_count,
        current_turn_is_exposure=_turn_counts_as_case_exposure(graph_state),
    )
    question_to_ask = _resolve_question_to_ask(
        advisor_state,
        field_to_ask=field_to_ask,
        suggested_question=suggested_question,
    )
    updated_state = LeadAdvisorState.model_validate(
        advisor_state.model_dump(mode="json")
    ).model_copy(
        update={
            "capture_exposure_count": capture_exposure_count,
            "should_ask": field_to_ask is not None,
            "field_to_ask": field_to_ask,
            "question_to_ask": question_to_ask or None,
        }
    )
    updates: dict[str, Any] = {"lead_advisor": updated_state.model_dump(mode="json")}
    if scoring_output:
        updates["turn_outputs"] = [*graph_state.turn_outputs, scoring_output]
    return updates
