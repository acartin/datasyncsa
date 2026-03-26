"""Routers specific to the realtor graph."""

from __future__ import annotations

from services.ai_runtime.domain.state import RealtorGraphState


def after_route_next_intent(state: dict[str, object]) -> str:
    graph_state = RealtorGraphState.model_validate(state)
    if not graph_state.active_intent:
        return "lead_advisor"
    mapping = {
        "buscar": "search",
        "describe_result_set": "describe_result_set",
        "show_result_cards": "show_result_cards",
        "focus_property": "focus_property",
        "calcular": "financial_calc",
        "comparar": "compare_properties",
        "mutar_comparacion": "mutate_comparison_set",
        "agendar": "collect_appointment_data",
        "rag_agencia": "rag_agencia",
        "rag_docs": "rag_documents",
        "escalar": "collect_lead_data",
        "recomendar": "llm_recommend",
        "mensajear": "mensajear",
    }
    return mapping.get(graph_state.active_intent.type, "lead_advisor")


def after_search(state: dict[str, object]) -> str:
    graph_state = RealtorGraphState.model_validate(state)
    count = len(graph_state.last_search_results)
    if count == 0 and graph_state.search_attempts < 3:
        return "search"
    if count == 0 and graph_state.search_attempts >= 3:
        return "lead_advisor"
    return "render_cards"


def after_render_cards(state: dict[str, object]) -> str:
    _ = RealtorGraphState.model_validate(state)
    return "check_queue"


def after_collect_appointment_data(state: dict[str, object]) -> str:
    graph_state = RealtorGraphState.model_validate(state)
    return "assign_agent" if getattr(graph_state.cita, "datos_completos", False) else "synthesize"
