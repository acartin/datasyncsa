"""Routers specific to the reduced generic graph."""

from __future__ import annotations

from services.ai_runtime.domain.state import GenericGraphState


def after_route_next_intent(state: dict[str, object]) -> str:
    graph_state = GenericGraphState.model_validate(state)
    if not graph_state.active_intent:
        return "lead_advisor"
    mapping = {
        "rag_agencia": "rag_agencia",
        "escalar": "collect_lead_data",
        "captura_lead": "collect_lead_data",
        "agendar": "collect_appointment_data",
        "mensajear": "mensajear",
    }
    return mapping.get(graph_state.active_intent.type, "lead_advisor")


def after_collect_appointment_data(state: dict[str, object]) -> str:
    graph_state = GenericGraphState.model_validate(state)
    return "assign_agent" if getattr(graph_state.cita, "datos_completos", False) else "synthesize"

