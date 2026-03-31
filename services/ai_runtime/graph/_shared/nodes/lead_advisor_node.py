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


def _normalize_field_key(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    return SCORING_FIELD_ALIASES.get(normalized, normalized)


def _pending_fields(advisor_state: LeadAdvisorState) -> list[str]:
    required_fields = list(advisor_state.required_fields or advisor_state.target_fields)
    completed = set(advisor_state.completed_fields or [])
    pending = [field for field in required_fields if field not in completed]
    if _normalize_field_key(advisor_state.lead_extracted.appointment_intent) == "negative":
        pending = [field for field in pending if _normalize_field_key(field) != "tipo_cita"]
    return pending


def _select_field_to_ask(
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

    normalized_suggested = _normalize_field_key(suggested_field)
    if current_turn_is_exposure and int(capture_exposure_count or 0) == 2 and "nombre" in pending:
        return "nombre"

    if normalized_suggested == "contacto":
        if "email" in pending and "telefono" in pending:
            return "contacto"
        if "email" in pending:
            return "email"
        if "telefono" in pending:
            return "telefono"
    if normalized_suggested and normalized_suggested in pending:
        return normalized_suggested

    # Si el tenant ya tiene prompt de scoring activo, la politica conversacional debe venir de slot_hints.
    profile = advisor_state.scoring_profile
    if profile and str(profile.prompt_template or "").strip():
        return None

    # Fallback legacy solo para tenants sin scoring prompt activo.
    if normalized_act not in {
        "new_search",
        "refine_search",
        "select_result",
        "ask_detail",
        "compare",
        "calculate",
        "schedule",
        "confirm_previous",
        "recommend",
    }:
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
