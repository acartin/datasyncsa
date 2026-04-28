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


def _policy_for_state(graph_state: BaseGraphState):
    from services.ai_runtime.verticals import get_vertical_spec

    return get_vertical_spec(graph_state.vertical).policy


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


def _generic_contact_field(pending: list[str]) -> str | None:
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
    return "contacto"


def _select_field_from_plan(
    *,
    pending: list[str],
    ordered_fields: list[str],
    appointment_intent: str | None,
) -> str | None:
    normalized_pending = {_normalize_field_key(item) for item in pending}
    normalized_intent = _normalize_field_key(appointment_intent)
    for candidate in ordered_fields:
        normalized = _normalize_field_key(candidate)
        if not normalized or normalized not in normalized_pending:
            continue
        if normalized == "tipo_cita" and normalized_intent != "positive":
            continue
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
    policy = _policy_for_state(graph_state)
    policy_journey = policy.resolve_journey(graph_state)
    policy_owned_progression = policy_journey is not None
    policy_plan = (
        list(policy.progressive_field_plan(graph_state, advisor_state))
        if policy_owned_progression
        else []
    )
    appointment_intent = advisor_state.lead_extracted.appointment_intent

    if current_turn_is_exposure and int(capture_exposure_count or 0) == 2 and "nombre" in pending:
        return "nombre"

    if (
        normalized_act == "calculate"
        and advisor_state.lead_extracted.presupuesto is not None
        and "aprobacion" in pending
    ):
        return "aprobacion"

    if normalized_act == "schedule":
        if policy_plan:
            scheduled_field = _select_field_from_plan(
                pending=pending,
                ordered_fields=policy_plan,
                appointment_intent=appointment_intent,
            )
            if scheduled_field:
                return scheduled_field
        generic_contact = _generic_contact_field(pending)
        if generic_contact:
            return generic_contact

    if normalized_suggested == "contacto":
        if policy_plan:
            planned_contact = _select_field_from_plan(
                pending=pending,
                ordered_fields=policy_plan,
                appointment_intent=appointment_intent,
            )
            if planned_contact in {"contacto", "email", "telefono"}:
                return planned_contact
        generic_contact = _generic_contact_field(pending)
        if generic_contact:
            return generic_contact

    normalized_pending = {_normalize_field_key(item) for item in pending}
    if (
        policy_plan
        and normalized_suggested in {"email", "telefono"}
        and "email" in normalized_pending
        and "telefono" in normalized_pending
    ):
        planned_contact = _select_field_from_plan(
            pending=pending,
            ordered_fields=policy_plan,
            appointment_intent=appointment_intent,
        )
        if planned_contact in {"email", "telefono"}:
            return planned_contact

    if normalized_suggested and normalized_suggested in pending:
        return normalized_suggested

    if profile and str(profile.prompt_template or "").strip() and policy_plan:
        planned_fallback = _select_field_from_plan(
            pending=pending,
            ordered_fields=policy_plan,
            appointment_intent=appointment_intent,
        )
        if planned_fallback:
            return planned_fallback

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
    current_turn_is_exposure = _turn_counts_as_case_exposure(graph_state)
    if current_turn_is_exposure:
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
        current_turn_is_exposure=current_turn_is_exposure,
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
