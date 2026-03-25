"""Deterministic shared routers."""

from __future__ import annotations

from services.ai_runtime.domain.state import BaseGraphState


def after_resolve_references(state: dict[str, object]) -> str:
    graph_state = BaseGraphState.model_validate(state)
    if graph_state.pending_clarification and graph_state.clarification_attempts < 3:
        return "ask_clarification"
    if graph_state.pending_clarification and graph_state.clarification_attempts >= 3:
        return "collect_lead_data"
    return "classify_intent"


def after_classify_intent(state: dict[str, object]) -> str:
    graph_state = BaseGraphState.model_validate(state)
    return "route_next_intent" if graph_state.intent_queue else "lead_advisor"


def after_check_queue(state: dict[str, object]) -> str:
    graph_state = BaseGraphState.model_validate(state)
    pending = [item for item in graph_state.intent_queue if item.status == "pending"]
    return "route_next_intent" if pending else "lead_advisor"

