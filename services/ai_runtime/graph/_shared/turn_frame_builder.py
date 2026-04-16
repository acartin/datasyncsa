"""Deterministic generic turn-frame builder.

This shared builder only owns the vertical-agnostic frame used by the generic
verticals. Realtor-specific turn framing lives under ``graph/realtor``.
"""

from __future__ import annotations

from typing import Any

from services.ai_runtime.domain.contracts import TurnAnalysis
from services.ai_runtime.domain.state import (
    BaseGraphState,
    SCORING_FIELD_ALIASES,
    has_valid_lead_contact,
)
from services.ai_runtime.domain.turn_frame import (
    BaseTurnFrame,
    FramingKind,
    LeadCaptureContext,
    LeadSnapshot,
)
from services.ai_runtime.graph._shared.prompt_context import (
    summarize_memory_for_prompt,
    summarize_messages_for_prompt,
)

POLICY_FRAMINGS: dict[str, FramingKind] = {
    "inventory_probe": "policy_block",
}

_OUTPUT_TYPE_TO_FRAMING: dict[str, FramingKind] = {
    "appointment": "appointment_progress",
    "lead_capture": "lead_capture",
}

_LEAD_FIELD_CANONICAL_OVERRIDES: dict[str, str] = {
    "correo": "email",
    "numero": "telefono",
    "presupuesto_maximo": "presupuesto",
    "presupuesto_minimo": "presupuesto",
    "presupuesto_rango": "presupuesto",
}


def _turn_has_output_type(graph_state: BaseGraphState, target: str) -> bool:
    return any(
        str(item.get("type") or "").strip().lower() == target
        for item in graph_state.turn_outputs[-5:]
    )


def _normalize_lead_field_key(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    normalized = SCORING_FIELD_ALIASES.get(normalized, normalized)
    return _LEAD_FIELD_CANONICAL_OVERRIDES.get(normalized, normalized)


def _compose_preferred_datetime(fecha: Any, hora: Any) -> str | None:
    fecha_text = str(fecha or "").strip()
    hora_text = str(hora or "").strip()
    combined = " ".join(part for part in (fecha_text, hora_text) if part).strip()
    return combined or None


def _resolve_lead_capture(graph_state: BaseGraphState) -> LeadCaptureContext:
    advisor = graph_state.lead_advisor
    contact_ok = has_valid_lead_contact(advisor.lead_extracted)
    lead_name_known = bool(str(advisor.lead_extracted.nombre or "").strip())

    appointment_context = (
        _turn_has_output_type(graph_state, "appointment")
        or bool(
            graph_state.cita.tipo
            or graph_state.cita.fecha
            or graph_state.cita.hora
            or graph_state.cita.propiedad_id
        )
        or (
            graph_state.turn_analysis is not None
            and graph_state.turn_analysis.dialogue_act == "schedule"
        )
    )
    appointment_pending_contact = (
        appointment_context
        and not bool(graph_state.cita.confirmada)
        and not contact_ok
    )

    return LeadCaptureContext(
        should_ask=bool(advisor.should_ask),
        field_to_ask=advisor.field_to_ask,
        question_to_ask=advisor.question_to_ask,
        lead_name_known=lead_name_known,
        has_valid_contact=contact_ok,
        appointment_pending_contact=appointment_pending_contact,
    )


def _resolve_lead_snapshot(graph_state: BaseGraphState) -> LeadSnapshot:
    extracted = graph_state.lead_advisor.lead_extracted.model_dump(mode="json")
    cita = graph_state.cita

    if not extracted.get("tipo_cita") and cita.tipo:
        extracted["tipo_cita"] = str(cita.tipo)

    if not extracted.get("fecha_preferida"):
        preferred_datetime = _compose_preferred_datetime(cita.fecha, cita.hora)
        if preferred_datetime:
            extracted["fecha_preferida"] = preferred_datetime

    if (
        not extracted.get("appointment_intent")
        and (cita.tipo or cita.fecha or cita.hora or cita.propiedad_id)
    ):
        extracted["appointment_intent"] = "positive"

    newly_captured_fields: list[str] = []
    seen_fields: set[str] = set()
    for entity in reversed(graph_state.memory.entities):
        if int(entity.source_turn or 0) != int(graph_state.current_turn):
            continue
        normalized_key = _normalize_lead_field_key(entity.key)
        if not normalized_key or normalized_key in seen_fields:
            continue
        seen_fields.add(normalized_key)
        newly_captured_fields.append(normalized_key)

    if _turn_has_output_type(graph_state, "appointment"):
        for key, value in (
            ("appointment_intent", extracted.get("appointment_intent")),
            ("tipo_cita", extracted.get("tipo_cita")),
            ("fecha_preferida", extracted.get("fecha_preferida")),
        ):
            if value and key not in seen_fields:
                seen_fields.add(key)
                newly_captured_fields.append(key)

    return LeadSnapshot(
        nombre=str(extracted.get("nombre") or "").strip() or None,
        email=str(extracted.get("email") or "").strip() or None,
        telefono=str(extracted.get("telefono") or "").strip() or None,
        presupuesto=(
            float(extracted["presupuesto"])
            if extracted.get("presupuesto") not in (None, "", [])
            else None
        ),
        aprobacion=str(extracted.get("aprobacion") or "").strip() or None,
        preferencias=[
            str(item).strip()
            for item in (extracted.get("preferencias") or [])
            if str(item).strip()
        ],
        fecha_preferida=str(extracted.get("fecha_preferida") or "").strip() or None,
        tipo_cita=str(extracted.get("tipo_cita") or "").strip() or None,
        appointment_intent=str(extracted.get("appointment_intent") or "").strip() or None,
        newly_captured_fields=newly_captured_fields,
    )


def _extract_primary_narrative(turn_outputs: list[dict[str, Any]]) -> str | None:
    for item in reversed(turn_outputs):
        output_type = str(item.get("type") or "").strip().lower()
        if output_type in _OUTPUT_TYPE_TO_FRAMING:
            narrative = str(item.get("narrative") or "").strip()
            if narrative:
                return narrative
    return None


def _extract_secondary_narratives(turn_outputs: list[dict[str, Any]], primary_type: str | None) -> list[str]:
    narratives: list[str] = []
    for item in turn_outputs:
        output_type = str(item.get("type") or "").strip().lower()
        if output_type == primary_type:
            continue
        narrative = str(item.get("narrative") or "").strip()
        if narrative:
            narratives.append(narrative)

    for item in turn_outputs:
        if str(item.get("type") or "").strip().lower() in {"rag_agencia", "rag_docs"}:
            for chunk in (item.get("chunks") or [])[:3]:
                text = str(chunk.get("content") or chunk.get("text") or "").strip()
                if text:
                    narratives.append(text)

    return narratives[:4]


def _resolve_framing(graph_state: BaseGraphState) -> FramingKind:
    analysis = graph_state.turn_analysis
    dialogue_act = analysis.dialogue_act if analysis else "unknown"

    if dialogue_act in POLICY_FRAMINGS:
        return POLICY_FRAMINGS[dialogue_act]
    if dialogue_act == "small_talk":
        return "small_talk"
    if dialogue_act == "reject_previous":
        return "reject_previous"
    if dialogue_act == "lead_capture":
        return "lead_capture"

    output_types = [
        str(item.get("type") or "").strip().lower()
        for item in graph_state.turn_outputs
    ]
    for output_type in reversed(output_types):
        if output_type in _OUTPUT_TYPE_TO_FRAMING:
            return _OUTPUT_TYPE_TO_FRAMING[output_type]
    if any(t in {"rag_agencia", "rag_docs"} for t in output_types):
        return "faq_answer"
    if dialogue_act == "confirm_previous":
        return "confirm_continuation"
    if dialogue_act == "unknown":
        return "generic_response" if graph_state.memory.entities else "off_domain"
    return "generic_response"


def _last_assistant_message(messages: list[Any]) -> str | None:
    for item in reversed(messages[:-1] if len(messages) > 1 else []):
        role = getattr(item, "role", None)
        if isinstance(item, dict):
            role = item.get("role")
        content = getattr(item, "content", None)
        if isinstance(item, dict):
            content = item.get("content")
        if role == "assistant" and content:
            return str(content).strip()
    return None


def build_turn_frame(graph_state: BaseGraphState) -> BaseTurnFrame:
    """Build the immutable generic TurnFrame for non-realtor verticals."""

    analysis = graph_state.turn_analysis or TurnAnalysis()
    user_message = graph_state.messages[-1].content if graph_state.messages else ""
    recent = summarize_messages_for_prompt(graph_state.messages, limit=6)
    last_assistant = _last_assistant_message(graph_state.messages)
    memory = summarize_memory_for_prompt(graph_state.memory, entity_limit=6)
    lead_capture = _resolve_lead_capture(graph_state)
    lead_snapshot = _resolve_lead_snapshot(graph_state)

    rag_chunks: list[dict[str, Any]] = []
    for item in graph_state.turn_outputs:
        if str(item.get("type") or "").strip().lower() in {"rag_agencia", "rag_docs"}:
            rag_chunks.extend(item.get("chunks") or [])

    appointment_summary: dict[str, Any] | None = None
    for item in graph_state.turn_outputs:
        if str(item.get("type") or "").strip().lower() == "appointment":
            appointment_summary = item.get("cita")

    primary_output_type: str | None = None
    for item in reversed(graph_state.turn_outputs):
        output_type = str(item.get("type") or "").strip().lower()
        if output_type in _OUTPUT_TYPE_TO_FRAMING:
            primary_output_type = output_type
            break

    return BaseTurnFrame(
        framing=_resolve_framing(graph_state),
        dialogue_act=analysis.dialogue_act,
        user_message=user_message,
        last_assistant_message=last_assistant,
        primary_narrative=_extract_primary_narrative(graph_state.turn_outputs),
        secondary_narratives=_extract_secondary_narratives(graph_state.turn_outputs, primary_output_type),
        recent_messages=recent,
        memory_summary=memory,
        lead_capture=lead_capture,
        lead_snapshot=lead_snapshot,
        rag_chunks=rag_chunks[:6],
        appointment_summary=appointment_summary,
        capabilities=list(graph_state.capabilities),
    )
