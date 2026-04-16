"""Deterministic realtor turn-frame builder."""

from __future__ import annotations

import logging
from typing import Any

from services.ai_runtime.domain.contracts import TurnAnalysis
from services.ai_runtime.domain.turn_frame import LeadCaptureContext, LeadSnapshot, SearchContext
from services.ai_runtime.graph._shared.prompt_context import summarize_memory_for_prompt, summarize_messages_for_prompt
from services.ai_runtime.graph._shared.turn_frame_builder import (
    _extract_primary_narrative,
    _extract_secondary_narratives,
    _last_assistant_message,
    _resolve_framing,
    _resolve_lead_capture,
    _resolve_lead_snapshot,
    _turn_has_output_type,
)
from services.ai_runtime.graph.realtor.contracts import Property
from services.ai_runtime.graph.realtor.state.model import RealtorGraphState
from services.ai_runtime.graph.realtor.turn_frame import (
    PropertySummary,
    RealtorTurnFrame,
    property_to_summary,
)

logger = logging.getLogger(__name__)


def _resolve_visible_properties(graph_state: RealtorGraphState) -> list[PropertySummary]:
    prop_map: dict[str, Property] = {}
    for prop in [*graph_state.last_search_results, *graph_state.inventory]:
        prop_map[prop.id] = prop

    seen_raw: dict[str, Any] = graph_state.seen_properties or {}
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
                resolved_ids.add(str(prop_id))
        total = len(resolved)
        summaries = [
            property_to_summary(prop, position=index + 1, total=total)
            for index, prop in enumerate(resolved)
        ]
        for prop_id in cards_shown:
            pid = str(prop_id)
            if pid not in {summary.id for summary in summaries} and pid in seen_raw:
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

    if graph_state.last_search_results:
        props = list(graph_state.last_search_results[:4])
        total = len(props)
        return [
            property_to_summary(prop, position=index + 1, total=total)
            for index, prop in enumerate(props)
        ]

    return []


def _resolve_search_context(graph_state: RealtorGraphState) -> SearchContext | None:
    search_outputs = [
        item for item in graph_state.turn_outputs
        if str(item.get("type") or "").strip().lower() == "search"
    ]
    if not search_outputs:
        return None

    latest = search_outputs[-1]
    return SearchContext(
        requested_filters={
            key: value for key, value in (latest.get("requested_filters") or {}).items()
            if value not in (None, "", [])
        },
        effective_filters={
            key: value for key, value in (latest.get("effective_filters") or {}).items()
            if value not in (None, "", [])
        },
        relaxation_applied=bool(latest.get("relaxation_applied")),
        result_count=int(latest.get("count") or 0),
        attempt_count=len(search_outputs),
    )


def _extract_focused_property(
    turn_outputs: list[dict[str, Any]],
    prop_map: dict[str, Property],
) -> PropertySummary | None:
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


def build_realtor_turn_frame(graph_state: RealtorGraphState) -> RealtorTurnFrame:
    """Build the immutable realtor TurnFrame."""

    analysis: TurnAnalysis = graph_state.turn_analysis or TurnAnalysis()
    user_message = graph_state.messages[-1].content if graph_state.messages else ""
    recent_messages = summarize_messages_for_prompt(graph_state.messages, limit=6)
    last_assistant_message = _last_assistant_message(graph_state.messages)
    memory_summary = summarize_memory_for_prompt(graph_state.memory, entity_limit=6)
    lead_capture: LeadCaptureContext = _resolve_lead_capture(graph_state)
    lead_snapshot: LeadSnapshot = _resolve_lead_snapshot(graph_state)

    rag_chunks: list[dict[str, Any]] = []
    for item in graph_state.turn_outputs:
        if str(item.get("type") or "").strip().lower() in {"rag_agencia", "rag_docs"}:
            rag_chunks.extend(item.get("chunks") or [])

    appointment_summary: dict[str, Any] | None = None
    for item in graph_state.turn_outputs:
        if str(item.get("type") or "").strip().lower() == "appointment":
            appointment_summary = item.get("cita")

    search_context = _resolve_search_context(graph_state)
    visible_properties = _resolve_visible_properties(graph_state)
    output_types = [
        str(item.get("type") or "").strip().lower()
        for item in graph_state.turn_outputs
    ]
    has_new_cards = "search" in output_types and "render_cards" in output_types
    framing = _resolve_framing(graph_state)

    primary_output_type: str | None = None
    for item in reversed(graph_state.turn_outputs):
        output_type = str(item.get("type") or "").strip().lower()
        if output_type in {"property_focus", "property_selection", "comparison", "result_set_detail", "recommendation", "financial_calc", "appointment", "lead_capture"}:
            primary_output_type = output_type
            break

    prop_map: dict[str, Property] = {}
    for prop in [*graph_state.last_search_results, *graph_state.inventory]:
        prop_map[prop.id] = prop

    focused_property = _extract_focused_property(graph_state.turn_outputs, prop_map)

    financial_result: dict[str, Any] | None = None
    for item in graph_state.turn_outputs:
        if str(item.get("type") or "").strip().lower() == "financial_calc":
            financial_result = item.get("result")

    comparison_scores: list[dict[str, Any]] = []
    for item in graph_state.turn_outputs:
        if str(item.get("type") or "").strip().lower() == "comparison":
            comparison_scores = item.get("scores") or []

    return RealtorTurnFrame(
        framing=framing,
        dialogue_act=analysis.dialogue_act,
        user_message=user_message,
        last_assistant_message=last_assistant_message,
        primary_narrative=_extract_primary_narrative(graph_state.turn_outputs),
        secondary_narratives=_extract_secondary_narratives(graph_state.turn_outputs, primary_output_type),
        recent_messages=recent_messages,
        memory_summary=memory_summary,
        lead_capture=lead_capture,
        lead_snapshot=lead_snapshot,
        rag_chunks=rag_chunks[:6],
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
