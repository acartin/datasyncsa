"""Final synthesis node."""

from __future__ import annotations

import re
from typing import Any

from services.ai_runtime.config.prompt_composer import compose
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import BaseGraphState, RealtorGraphState, has_valid_lead_contact
from services.ai_runtime.graph._shared.prompt_context import (
    summarize_lead_advisor_for_prompt,
    summarize_memory_for_prompt,
    summarize_message_for_prompt,
    summarize_messages_for_prompt,
    summarize_properties_for_prompt,
    summarize_property_for_prompt,
    summarize_turn_outputs_for_prompt,
)


FIELD_QUESTIONS = {
    "nombre": "Antes de seguir, con quien tengo el gusto?",
    "email": "Si te parece, compartime tu correo y te envio el resumen.",
    "telefono": "Si te queda bien, compartime tu telefono y te contacto por ahi.",
    "contacto": "Si queres, te dejo esto encaminado. Te queda mejor compartirme tu telefono o tu correo?",
    "presupuesto": "Para afinar mejor las opciones, en que rango de presupuesto te sentis comodo?",
    "aprobacion": "Ya tenes alguna aprobacion bancaria o prefieres que lo revisemos desde cero?",
    "preferencias": "Para ayudarte mejor, que zona o caracteristicas priorizas?",
    "fecha": "Para cuando te gustaria mover esto?",
    "fecha_preferida": "Para cuando te gustaria mover esto?",
    "tipo_cita": "Prefieres visita presencial, videollamada o una llamada rapida?",
    "appointment_intent": "Te gustaria que dejemos una cita coordinada para avanzar?",
    "cita": "Si te sirve, tambien te ayudo a dejar la cita encaminada. Te gustaria que la coordinemos?",
}

POLICY_RESPONSES = {
    "inventory_probe": (
        "Te puedo ayudar a buscar tu casa sonada, pero este tipo de consultas sobre inventario, totales o promedios del negocio no te las puedo responder. "
        "Si queres, con gusto te ayudo a encontrar opciones segun zona, presupuesto o tipo de propiedad."
    ),
}
_APPOINTMENT_CONFIRMATION_HINTS = (
    "agendada",
    "agendado",
    "confirmada",
    "confirmado",
    "queda agendada",
    "queda confirmada",
    "visita confirmada",
)
_TRAILING_INVERTED_QUESTION_BLOCK = re.compile(r"\s*¿[^?]*\?\s*$")
_TRAILING_PLAIN_QUESTION_BLOCK = re.compile(r"\s*[^¿?!.][^?]*\?\s*$")


def _serialize_messages(messages: list[Any], *, limit: int = 8) -> list[dict[str, Any]]:
    return summarize_messages_for_prompt(messages, limit=limit)


def _serialize_property(item: Any) -> dict[str, Any] | None:
    return summarize_property_for_prompt(item)


def _serialize_properties(items: list[Any], *, limit: int = 8) -> list[dict[str, Any]]:
    return summarize_properties_for_prompt(items, limit=limit)


def _last_assistant_message(messages: list[Any]) -> dict[str, Any] | None:
    for item in reversed(messages[:-1]):
        if getattr(item, "role", None) == "assistant":
            return summarize_message_for_prompt(item)
    return None


def _serialize_displayed_cards(graph_state: RealtorGraphState) -> list[dict[str, Any]]:
    property_map: dict[str, Any] = {}
    for item in [*graph_state.last_search_results, *graph_state.inventory]:
        property_map[item.id] = item

    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for property_id in graph_state.cards_shown:
        item = property_map.get(property_id)
        if not item or item.id in seen:
            continue
        serialized = summarize_property_for_prompt(item)
        if not serialized:
            continue
        selected.append(serialized)
        seen.add(item.id)
    return selected


def _build_search_strategy(graph_state: RealtorGraphState) -> dict[str, Any] | None:
    search_outputs = [item for item in graph_state.turn_outputs if item.get("type") == "search"]
    if not search_outputs:
        return None

    latest = search_outputs[-1]
    exact_attempt = next((item for item in search_outputs if not item.get("relaxation_applied")), None)
    return {
        "requested_filters": graph_state.search_filters.model_dump(mode="json"),
        "effective_filters": (
            graph_state.effective_search_filters.model_dump(mode="json")
            if graph_state.effective_search_filters
            else latest.get("effective_filters")
        ),
        "relaxation_applied": bool(latest.get("relaxation_applied")),
        "match_scope": latest.get("match_scope"),
        "exact_result_count": exact_attempt.get("count") if exact_attempt else None,
        "final_result_count": latest.get("count"),
        "attempt_count": len(search_outputs),
    }


def _build_context(graph_state: BaseGraphState) -> dict[str, Any]:
    context: dict[str, Any] = {
        "current_message": summarize_message_for_prompt(graph_state.messages[-1]),
        "recent_messages": _serialize_messages(graph_state.messages),
        "last_assistant_message": _last_assistant_message(graph_state.messages),
        "turn_analysis": graph_state.turn_analysis.model_dump(mode="json") if graph_state.turn_analysis else None,
        "turn_outputs": summarize_turn_outputs_for_prompt(graph_state.turn_outputs),
        "turn_output_types": [str(item.get("type")) for item in graph_state.turn_outputs],
        "lead_advisor": summarize_lead_advisor_for_prompt(graph_state.lead_advisor),
        "memory": summarize_memory_for_prompt(graph_state.memory),
        "render_mode": getattr(graph_state, "render_mode", None),
        "cards_mode": getattr(graph_state, "cards_mode", None),
        "capabilities": graph_state.capabilities,
    }

    if isinstance(graph_state, RealtorGraphState):
        context.update(
            {
                "search_filters": graph_state.search_filters.model_dump(mode="json"),
                "effective_search_filters": (
                    graph_state.effective_search_filters.model_dump(mode="json")
                    if graph_state.effective_search_filters
                    else None
                ),
                "search_strategy": _build_search_strategy(graph_state),
                "displayed_cards": _serialize_displayed_cards(graph_state),
                "last_search_results_preview": _serialize_properties(graph_state.last_search_results, limit=6),
                "inventory_preview": _serialize_properties(graph_state.inventory, limit=6),
                "last_mentioned": _serialize_property(graph_state.last_mentioned),
                "active_comparison": list(graph_state.active_comparison),
                "ui_payload": graph_state.ui_payload,
                "search_attempts": graph_state.search_attempts,
            }
        )

    return context


def _turn_has_appointment_output(graph_state: BaseGraphState) -> bool:
    for item in graph_state.turn_outputs[-3:]:
        if str(item.get("type") or "").strip().lower() == "appointment":
            return True
    return False


def _looks_like_appointment_confirmation(answer: str) -> bool:
    lowered = re.sub(r"\s+", " ", (answer or "").strip().lower())
    return any(hint in lowered for hint in _APPOINTMENT_CONFIRMATION_HINTS)


def _strip_trailing_question_blocks(answer: str) -> str:
    text = str(answer or "").strip()
    while True:
        updated = re.sub(_TRAILING_INVERTED_QUESTION_BLOCK, "", text).strip()
        if updated == text:
            break
        text = updated
    while text.endswith("?"):
        updated = re.sub(_TRAILING_PLAIN_QUESTION_BLOCK, "", text).strip()
        if updated == text:
            break
        text = updated
    return re.sub(r"\s{2,}", " ", text).strip()


def _ensure_sentence_ending(text: str) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""
    if cleaned[-1] in ".!?":
        return cleaned
    return f"{cleaned}."


def _resolve_lead_prompt_for_synthesis(
    *,
    answer: str,
    lead_should_ask: bool,
    lead_field_to_ask: str | None,
    lead_question_to_ask: str | None,
    appointment_pending_contact: bool,
    lead_name_known: bool,
) -> tuple[str, str | None, str | None]:
    resolved_answer = answer
    forced_field_to_ask: str | None = None
    if appointment_pending_contact and lead_name_known:
        forced_field_to_ask = "contacto"
        if _looks_like_appointment_confirmation(resolved_answer):
            resolved_answer = "Perfecto, ya tengo la fecha y la hora. Para dejar la cita confirmada, compartime tu telefono o tu correo."
    elif appointment_pending_contact and not lead_name_known and _looks_like_appointment_confirmation(resolved_answer):
        resolved_answer = "Perfecto, puedo ayudarte a coordinar la visita de esa opcion."

    field_to_ask = lead_field_to_ask if lead_should_ask and lead_field_to_ask else None
    if forced_field_to_ask:
        field_to_ask = forced_field_to_ask

    question_to_ask = None
    if field_to_ask:
        question_to_ask = str(lead_question_to_ask or "").strip() or FIELD_QUESTIONS.get(field_to_ask)
    return resolved_answer, field_to_ask, question_to_ask


async def synthesize(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    """Render the final user-facing answer from structured turn context."""

    graph_state = (
        RealtorGraphState.model_validate(state)
        if state.get("vertical") == "realtor"
        else BaseGraphState.model_validate(state)
    )
    dialogue_act = graph_state.turn_analysis.dialogue_act if graph_state.turn_analysis else None
    if dialogue_act in POLICY_RESPONSES:
        answer = POLICY_RESPONSES[dialogue_act]
    else:
        prompt = compose(
            "synthesis_prompt",
            graph_state.tenant_config,
            graph_state.vertical,
            _build_context(graph_state),
            include_tone=True,
        )
        answer = await deps.llm.synthesize_response(prompt)

    contact_ok = has_valid_lead_contact(graph_state.lead_advisor.lead_extracted)
    appointment_context = (
        _turn_has_appointment_output(graph_state)
        or bool(graph_state.cita.tipo or graph_state.cita.fecha or graph_state.cita.hora or graph_state.cita.propiedad_id)
        or dialogue_act == "schedule"
    )
    appointment_pending_contact = (
        appointment_context
        and not bool(graph_state.cita.confirmada)
        and not contact_ok
    )
    lead_name_known = bool(str(graph_state.lead_advisor.lead_extracted.nombre or "").strip())
    answer, field_to_ask, question_to_ask = _resolve_lead_prompt_for_synthesis(
        answer=answer,
        lead_should_ask=bool(graph_state.lead_advisor.should_ask),
        lead_field_to_ask=graph_state.lead_advisor.field_to_ask,
        lead_question_to_ask=graph_state.lead_advisor.question_to_ask,
        appointment_pending_contact=appointment_pending_contact,
        lead_name_known=lead_name_known,
    )

    if field_to_ask:
        if question_to_ask:
            answer_body = _strip_trailing_question_blocks(answer)
            if answer_body:
                answer = f"{_ensure_sentence_ending(answer_body)} {question_to_ask}".strip()
            else:
                answer = question_to_ask

    messages = [*graph_state.messages, {"role": "assistant", "content": answer}]
    lead_advisor = graph_state.lead_advisor
    if (
        bool(lead_advisor.should_ask) != bool(field_to_ask)
        or lead_advisor.field_to_ask != field_to_ask
        or str(lead_advisor.question_to_ask or "").strip() != str(question_to_ask or "").strip()
    ):
        lead_advisor = lead_advisor.model_copy(
            update={
                "should_ask": bool(field_to_ask),
                "field_to_ask": field_to_ask,
                "question_to_ask": question_to_ask,
            }
        )
    await deps.worker_dispatcher.fire_and_forget(
        "lead_worker",
        {
            "client_id": graph_state.client_id,
            "session_id": graph_state.session_id,
            "state": graph_state.model_dump(mode="json"),
        },
    )
    return {
        "final_response": answer,
        "messages": messages,
        "lead_advisor": lead_advisor.model_dump(mode="json"),
        "turn_outputs": [*graph_state.turn_outputs],
    }
