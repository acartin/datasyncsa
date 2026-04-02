"""Deterministic shared routers."""

from __future__ import annotations

import re
import unicodedata

from services.ai_runtime.domain.contracts import TurnAnalysis
from services.ai_runtime.domain.state import BaseGraphState


_MEMORY_QUERY_PATTERNS = (
    r"\bcomo me llamo\b",
    r"\bcual es mi nombre\b",
    r"\bque edad tengo\b",
    r"\bcuantos anos tengo\b",
    r"\bcual era mi presupuesto\b",
    r"\bque presupuesto te dije\b",
    r"\bcual es mi correo\b",
    r"\bcual es mi email\b",
    r"\bcual es mi telefono\b",
    r"\bcual es mi numero\b",
    r"\brecord[aá]s\b",
    r"\brecuerdas\b",
    r"\bte acord[aá]s\b",
)


def _normalize_text(value: str) -> str:
    raw = unicodedata.normalize("NFKD", value or "")
    return "".join(char for char in raw if not unicodedata.combining(char)).lower().strip()


def _looks_like_memory_query(message: str) -> bool:
    normalized = _normalize_text(message)
    if not normalized:
        return False
    return any(re.search(pattern, normalized) for pattern in _MEMORY_QUERY_PATTERNS)


def after_analyze_turn(state: dict[str, object]) -> str:
    graph_state = BaseGraphState.model_validate(state)
    if graph_state.pending_decision and graph_state.clarification_attempts < 3:
        return "ask_clarification"
    if graph_state.pending_decision and graph_state.clarification_attempts >= 3:
        return "collect_lead_data"
    if graph_state.pending_clarification and graph_state.clarification_attempts < 3:
        return "ask_clarification"
    if graph_state.pending_clarification and graph_state.clarification_attempts >= 3:
        return "collect_lead_data"
    return "capture_memory_entities"


def after_capture_memory(state: dict[str, object]) -> str:
    graph_state = BaseGraphState.model_validate(state)
    analysis = TurnAnalysis.model_validate(graph_state.turn_analysis or {})
    latest_message = graph_state.messages[-1].content if graph_state.messages else ""
    if analysis.memory_lookup_key or analysis.dialogue_act == "memory_query" or _looks_like_memory_query(latest_message):
        return "memory_lookup"
    if analysis.dialogue_act == "inventory_probe":
        return "synthesize"
    return "route_next_intent" if graph_state.intent_queue else "lead_advisor"


def after_memory_lookup(state: dict[str, object]) -> str:
    graph_state = BaseGraphState.model_validate(state)
    analysis = TurnAnalysis.model_validate(graph_state.turn_analysis or {})
    if graph_state.memory.last_lookup.handled:
        return "end"
    if analysis.dialogue_act == "inventory_probe":
        return "synthesize"
    return "route_next_intent" if graph_state.intent_queue else "lead_advisor"


def after_check_queue(state: dict[str, object]) -> str:
    graph_state = BaseGraphState.model_validate(state)
    pending = [item for item in graph_state.intent_queue if item.status == "pending"]
    return "route_next_intent" if pending else "lead_advisor"
