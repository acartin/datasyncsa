"""Deterministic turn-frame builder.

Resolves **all** state interpretation before the synthesizer so the LLM only
has to *write*, never *interpret*.  Every function here is pure — no I/O, no
LLM calls.
"""

from __future__ import annotations

import logging
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
    SearchContext,
)
from services.ai_runtime.graph.realtor.contracts import Property
from services.ai_runtime.graph.realtor.state.model import RealtorGraphState
from services.ai_runtime.graph.realtor.turn_frame import (
    PropertySummary,
    RealtorTurnFrame,
    property_to_summary,
)
from services.ai_runtime.graph._shared.prompt_context import (
    summarize_memory_for_prompt,
    summarize_messages_for_prompt,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Framing constants
# ---------------------------------------------------------------------------

POLICY_FRAMINGS: dict[str, FramingKind] = {
    "inventory_probe": "policy_block",
}

_OUTPUT_TYPE_TO_FRAMING: dict[str, FramingKind] = {
    "property_focus": "property_focus",
    "property_selection": "property_selection",
    "comparison": "property_comparison",
    "result_set_detail": "result_set_detail",
    "recommendation": "recommendation",
    "financial_calc": "financial_calc",
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


# ---------------------------------------------------------------------------
# Visible properties
# ---------------------------------------------------------------------------

def _resolve_visible_properties(graph_state: RealtorGraphState) -> list[PropertySummary]:
    """Build the single consolidated list of properties the user can see.

    Priority: ``cards_shown`` resolved against ``seen_properties``, with a
    fallback to ``last_search_results`` + ``inventory`` for entries not yet in
    the accumulator.
    """

    # Build a lookup map — seen_properties first, then current-turn data
    prop_map: dict[str, Property] = {}
    for prop in [*graph_state.last_search_results, *graph_state.inventory]:
        prop_map[prop.id] = prop

    # Overlay with seen_properties (may contain cross-turn entries)
    seen_raw: dict[str, Any] = graph_state.seen_properties or {}
    for prop_id, raw in seen_raw.items():
        if prop_id in prop_map:
            continue  # current-turn data is fresher (full Property)
        # seen_properties stores PropertySummary dicts — we cannot upcast to
        # Property, but we can build a PropertySummary directly later.

    cards_shown = list(graph_state.cards_shown or [])
    if cards_shown:
        resolved: list[Property] = []
        resolved_ids: set[str] = set()
        for prop_id in cards_shown:
            prop = prop_map.get(str(prop_id))
            if prop and prop.id not in resolved_ids:
                resolved.append(prop)
                resolved_ids.add(prop.id)
            elif str(prop_id) in seen_raw and str(prop_id) not in resolved_ids:
                # Property only exists as a summary from a previous turn.
                # We can still surface it via PropertySummary.
                resolved_ids.add(str(prop_id))
        # Build summaries from full Property objects
        total = len(resolved)
        summaries = [
            property_to_summary(p, position=idx + 1, total=total)
            for idx, p in enumerate(resolved)
        ]
        # Append summary-only entries (from seen_properties, not in current results)
        for prop_id in cards_shown:
            pid = str(prop_id)
            if pid not in {s.id for s in summaries} and pid in seen_raw:
                raw_entry = seen_raw[pid]
                summary = (
                    raw_entry
                    if isinstance(raw_entry, PropertySummary)
                    else PropertySummary.model_validate(raw_entry)
                )
                pos = len(summaries) + 1
                total_with_extra = total + 1
                label = f"La opcion {pos}" if total_with_extra > 1 else None
                summaries.append(summary.model_copy(update={"position_label": label}))
        return summaries
    elif graph_state.last_search_results:
        props = list(graph_state.last_search_results[:4])
        total = len(props)
        return [
            property_to_summary(p, position=idx + 1, total=total)
            for idx, p in enumerate(props)
        ]

    return []


# ---------------------------------------------------------------------------
# Search context
# ---------------------------------------------------------------------------

def _resolve_search_context(graph_state: RealtorGraphState) -> SearchContext | None:
    """Extract search context from the current turn's outputs."""

    search_outputs = [
        item for item in graph_state.turn_outputs
        if str(item.get("type") or "").strip().lower() == "search"
    ]
    if not search_outputs:
        return None

    latest = search_outputs[-1]
    return SearchContext(
        requested_filters={
            k: v for k, v in (latest.get("requested_filters") or {}).items()
            if v not in (None, "", [])
        },
        effective_filters={
            k: v for k, v in (latest.get("effective_filters") or {}).items()
            if v not in (None, "", [])
        },
        relaxation_applied=bool(latest.get("relaxation_applied")),
        result_count=int(latest.get("count") or 0),
        attempt_count=len(search_outputs),
    )


# ---------------------------------------------------------------------------
# Lead capture context
# ---------------------------------------------------------------------------

def _resolve_lead_capture(graph_state: BaseGraphState) -> LeadCaptureContext:
    """Pre-resolve the lead-capture decision including appointment edge-cases."""

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


def _normalize_lead_field_key(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    normalized = SCORING_FIELD_ALIASES.get(normalized, normalized)
    return _LEAD_FIELD_CANONICAL_OVERRIDES.get(normalized, normalized)


def _compose_preferred_datetime(fecha: Any, hora: Any) -> str | None:
    fecha_text = str(fecha or "").strip()
    hora_text = str(hora or "").strip()
    combined = " ".join(part for part in (fecha_text, hora_text) if part).strip()
    return combined or None


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


def _turn_has_output_type(graph_state: BaseGraphState, target: str) -> bool:
    return any(
        str(item.get("type") or "").strip().lower() == target
        for item in graph_state.turn_outputs[-5:]
    )


# ---------------------------------------------------------------------------
# Narrative extraction
# ---------------------------------------------------------------------------

def _extract_primary_narrative(turn_outputs: list[dict[str, Any]]) -> str | None:
    """Return the narrative from the most relevant factual output."""

    for item in reversed(turn_outputs):
        output_type = str(item.get("type") or "").strip().lower()
        if output_type in _OUTPUT_TYPE_TO_FRAMING:
            narrative = str(item.get("narrative") or "").strip()
            if narrative:
                return narrative
    return None


def _extract_secondary_narratives(
    turn_outputs: list[dict[str, Any]],
    primary_type: str | None,
) -> list[str]:
    """Collect secondary narratives and RAG chunk texts."""

    narratives: list[str] = []
    for item in turn_outputs:
        output_type = str(item.get("type") or "").strip().lower()
        if output_type == primary_type:
            continue
        narrative = str(item.get("narrative") or "").strip()
        if narrative:
            narratives.append(narrative)

    # RAG chunks as text
    for item in turn_outputs:
        if str(item.get("type") or "").strip().lower() in {"rag_agencia", "rag_docs"}:
            for chunk in (item.get("chunks") or [])[:3]:
                text = str(chunk.get("content") or chunk.get("text") or "").strip()
                if text:
                    narratives.append(text)

    return narratives[:4]


def _extract_focused_property(
    turn_outputs: list[dict[str, Any]],
    prop_map: dict[str, Property],
) -> PropertySummary | None:
    """Extract the focused property from the turn's outputs."""

    for item in reversed(turn_outputs):
        output_type = str(item.get("type") or "").strip().lower()
        if output_type in {"property_focus", "property_selection", "recommendation"}:
            prop_data = item.get("property")
            if prop_data:
                try:
                    prop = Property.model_validate(prop_data)
                    return property_to_summary(prop)
                except Exception:
                    logger.warning("Failed to validate focused property from turn output")
    return None


# ---------------------------------------------------------------------------
# Framing resolution
# ---------------------------------------------------------------------------

def _resolve_framing(
    graph_state: BaseGraphState,
    search_context: SearchContext | None,
) -> FramingKind:
    """Determine the framing kind for the turn — fully deterministic."""

    analysis = graph_state.turn_analysis
    dialogue_act = analysis.dialogue_act if analysis else "unknown"

    # 1. Policy blocks
    if dialogue_act in POLICY_FRAMINGS:
        return POLICY_FRAMINGS[dialogue_act]

    # 2. Direct conversational acts
    if dialogue_act == "small_talk":
        return "small_talk"
    if dialogue_act == "reject_previous":
        return "reject_previous"
    if dialogue_act == "lead_capture":
        return "lead_capture"

    # 3. Turn outputs (most specific output wins)
    output_types = [
        str(item.get("type") or "").strip().lower()
        for item in graph_state.turn_outputs
    ]
    for output_type in reversed(output_types):
        if output_type in _OUTPUT_TYPE_TO_FRAMING:
            return _OUTPUT_TYPE_TO_FRAMING[output_type]

    # 4. Search
    if search_context is not None:
        if search_context.result_count == 0:
            return "no_results"
        if search_context.relaxation_applied:
            return "relaxed_match"
        return "exact_match"

    # 5. RAG
    if any(t in {"rag_agencia", "rag_docs"} for t in output_types):
        return "faq_answer"

    # 6. Confirm previous without new search
    if dialogue_act == "confirm_previous":
        return "confirm_continuation"

    # 7. Lead capture
    if "lead_capture" in output_types:
        return "lead_capture"

    if dialogue_act == "unknown":
        has_realtor_context = bool(
            getattr(graph_state, "cards_shown", None)
            or getattr(graph_state, "last_search_results", None)
            or getattr(graph_state, "seen_properties", None)
            or graph_state.memory.entities
        )
        return "generic_response" if has_realtor_context else "off_domain"

    return "generic_response"


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_turn_frame(graph_state: BaseGraphState) -> BaseTurnFrame:
    """Build the immutable TurnFrame for the synthesizer.

    This function is **purely deterministic** — no LLM calls, no I/O.
    """

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

    if isinstance(graph_state, RealtorGraphState):
        return _build_realtor_turn_frame(
            graph_state,
            analysis=analysis,
            user_message=user_message,
            recent_messages=recent,
            last_assistant_message=last_assistant,
            memory_summary=memory,
            lead_capture=lead_capture,
            lead_snapshot=lead_snapshot,
            rag_chunks=rag_chunks[:6],
            appointment_summary=appointment_summary,
        )

    # BaseTurnFrame for generic/healthcare/legal/insurance
    framing = _resolve_framing(graph_state, search_context=None)
    primary_narrative = _extract_primary_narrative(graph_state.turn_outputs)
    secondary_narratives = _extract_secondary_narratives(graph_state.turn_outputs, primary_type=None)

    return BaseTurnFrame(
        framing=framing,
        dialogue_act=analysis.dialogue_act,
        user_message=user_message,
        last_assistant_message=last_assistant,
        primary_narrative=primary_narrative,
        secondary_narratives=secondary_narratives,
        recent_messages=recent,
        memory_summary=memory,
        lead_capture=lead_capture,
        lead_snapshot=lead_snapshot,
        rag_chunks=rag_chunks[:6],
        appointment_summary=appointment_summary,
        capabilities=list(graph_state.capabilities),
    )


def _build_realtor_turn_frame(
    graph_state: RealtorGraphState,
    *,
    analysis: TurnAnalysis,
    user_message: str,
    recent_messages: list[dict[str, Any]],
    last_assistant_message: str | None,
    memory_summary: dict[str, Any],
    lead_capture: LeadCaptureContext,
    lead_snapshot: LeadSnapshot,
    rag_chunks: list[dict[str, Any]],
    appointment_summary: dict[str, Any] | None,
) -> RealtorTurnFrame:
    """Build the extended realtor turn frame."""

    search_context = _resolve_search_context(graph_state)
    visible_properties = _resolve_visible_properties(graph_state)

    output_types = [
        str(item.get("type") or "").strip().lower()
        for item in graph_state.turn_outputs
    ]
    has_new_cards = "search" in output_types and "render_cards" in output_types

    framing = _resolve_framing(graph_state, search_context)

    # Determine primary output type for narrative extraction
    primary_output_type: str | None = None
    for item in reversed(graph_state.turn_outputs):
        ot = str(item.get("type") or "").strip().lower()
        if ot in _OUTPUT_TYPE_TO_FRAMING:
            primary_output_type = ot
            break

    primary_narrative = _extract_primary_narrative(graph_state.turn_outputs)
    secondary_narratives = _extract_secondary_narratives(
        graph_state.turn_outputs, primary_output_type,
    )

    # Property map for focused property resolution
    prop_map: dict[str, Property] = {}
    for prop in [*graph_state.last_search_results, *graph_state.inventory]:
        prop_map[prop.id] = prop

    focused_property = _extract_focused_property(graph_state.turn_outputs, prop_map)

    # Financial result
    financial_result: dict[str, Any] | None = None
    for item in graph_state.turn_outputs:
        if str(item.get("type") or "").strip().lower() == "financial_calc":
            financial_result = item.get("result")

    # Comparison scores
    comparison_scores: list[dict[str, Any]] = []
    for item in graph_state.turn_outputs:
        if str(item.get("type") or "").strip().lower() == "comparison":
            comparison_scores = item.get("scores") or []

    return RealtorTurnFrame(
        framing=framing,
        dialogue_act=analysis.dialogue_act,
        user_message=user_message,
        last_assistant_message=last_assistant_message,
        primary_narrative=primary_narrative,
        secondary_narratives=secondary_narratives,
        recent_messages=recent_messages,
        memory_summary=memory_summary,
        lead_capture=lead_capture,
        lead_snapshot=lead_snapshot,
        rag_chunks=rag_chunks,
        appointment_summary=appointment_summary,
        capabilities=list(graph_state.capabilities),
        visible_properties=visible_properties,
        focused_property=focused_property,
        search=search_context,
        has_new_cards=has_new_cards,
        cards_mode=graph_state.cards_mode,
        financial_result=financial_result,
        comparison_scores=comparison_scores,
    )
