"""Builder for the full realtor LangGraph."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from services.ai_runtime.domain.contracts import TenantConfig
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import RealtorGraphState
from services.ai_runtime.graph._shared.nodes import (
    ask_clarification,
    check_queue,
    classify_intent,
    collect_lead_data,
    lead_advisor,
    resolve_references,
    route_next_intent,
    synthesize,
)
from services.ai_runtime.graph._shared.nodes.helpers import complete_active_intent
from services.ai_runtime.graph._shared.routers.common import after_check_queue, after_classify_intent, after_resolve_references
from services.ai_runtime.graph._shared.tools.mensajear import mensajear
from services.ai_runtime.graph.realtor.nodes.assign_agent_node import assign_agent
from services.ai_runtime.graph.realtor.nodes.collect_appointment_data_node import collect_appointment_data
from services.ai_runtime.graph.realtor.nodes.compare_properties_node import compare_properties
from services.ai_runtime.graph.realtor.nodes.extract_search_filters_node import extract_search_filters
from services.ai_runtime.graph.realtor.nodes.llm_recommend_node import llm_recommend
from services.ai_runtime.graph.realtor.nodes.mutate_comparison_set_node import mutate_comparison_set
from services.ai_runtime.graph.realtor.nodes.rag_agencia_node import rag_agencia
from services.ai_runtime.graph.realtor.nodes.rag_documents_node import rag_documents
from services.ai_runtime.graph.realtor.nodes.render_cards_node import render_cards
from services.ai_runtime.graph.realtor.nodes.search_node import search
from services.ai_runtime.graph.realtor.routers.routes import (
    after_collect_appointment_data,
    after_render_cards,
    after_route_next_intent,
    after_search,
)
from services.ai_runtime.graph.realtor.tools.financial_calc import financial_calc
from services.ai_runtime.runtime.turn_trace import build_traced_node, build_traced_router


def _mail_node(deps: GraphDependencies):
    async def _mail_impl(state: dict, runtime_deps: GraphDependencies):
        tenant_config = TenantConfig.model_validate(state["tenant_config"])
        graph_state = RealtorGraphState.model_validate(state)
        result = await mensajear(
            dependencies=runtime_deps,
            client_id=state["client_id"],
            tipo="appointment_confirmation",
            destinatarios=[],
            datos_cita=state.get("cita", {}),
            tenant_config=tenant_config,
        )
        output = {"type": "mensajear", **result.model_dump(mode="json")}
        return {
            "turn_outputs": [*state.get("turn_outputs", []), output],
            **complete_active_intent(graph_state, output),
        }

    return build_traced_node("mensajear", _mail_impl, deps)


def build_realtor_graph(deps: GraphDependencies):
    workflow = StateGraph(dict)
    workflow.add_node("resolve_references", build_traced_node("resolve_references", resolve_references, deps))
    workflow.add_node("ask_clarification", build_traced_node("ask_clarification", ask_clarification, deps))
    workflow.add_node("classify_intent", build_traced_node("classify_intent", classify_intent, deps))
    workflow.add_node("route_next_intent", build_traced_node("route_next_intent", route_next_intent, deps))
    workflow.add_node("extract_search_filters", build_traced_node("extract_search_filters", extract_search_filters, deps))
    workflow.add_node("search", build_traced_node("search", search, deps))
    workflow.add_node("render_cards", build_traced_node("render_cards", render_cards, deps))
    workflow.add_node("financial_calc", build_traced_node("financial_calc", financial_calc, deps))
    workflow.add_node("compare_properties", build_traced_node("compare_properties", compare_properties, deps))
    workflow.add_node("mutate_comparison_set", build_traced_node("mutate_comparison_set", mutate_comparison_set, deps))
    workflow.add_node("collect_appointment_data", build_traced_node("collect_appointment_data", collect_appointment_data, deps))
    workflow.add_node("assign_agent", build_traced_node("assign_agent", assign_agent, deps))
    workflow.add_node("rag_agencia", build_traced_node("rag_agencia", rag_agencia, deps))
    workflow.add_node("rag_documents", build_traced_node("rag_documents", rag_documents, deps))
    workflow.add_node("collect_lead_data", build_traced_node("collect_lead_data", collect_lead_data, deps))
    workflow.add_node("llm_recommend", build_traced_node("llm_recommend", llm_recommend, deps))
    workflow.add_node("mensajear", _mail_node(deps))
    workflow.add_node("check_queue", build_traced_node("check_queue", check_queue, deps))
    workflow.add_node("lead_advisor", build_traced_node("lead_advisor", lead_advisor, deps))
    workflow.add_node("synthesize", build_traced_node("synthesize", synthesize, deps))

    workflow.add_edge(START, "resolve_references")
    workflow.add_conditional_edges(
        "resolve_references",
        build_traced_router("after_resolve_references", after_resolve_references, deps),
        {
            "ask_clarification": "ask_clarification",
            "collect_lead_data": "collect_lead_data",
            "classify_intent": "classify_intent",
        },
    )
    workflow.add_edge("ask_clarification", END)
    workflow.add_edge("collect_lead_data", "synthesize")
    workflow.add_conditional_edges(
        "classify_intent",
        build_traced_router("after_classify_intent", after_classify_intent, deps),
        {"route_next_intent": "route_next_intent", "lead_advisor": "lead_advisor"},
    )
    workflow.add_conditional_edges(
        "route_next_intent",
        build_traced_router("after_route_next_intent", after_route_next_intent, deps),
        {
            "extract_search_filters": "extract_search_filters",
            "financial_calc": "financial_calc",
            "compare_properties": "compare_properties",
            "mutate_comparison_set": "mutate_comparison_set",
            "collect_appointment_data": "collect_appointment_data",
            "rag_agencia": "rag_agencia",
            "rag_documents": "rag_documents",
            "collect_lead_data": "collect_lead_data",
            "llm_recommend": "llm_recommend",
            "mensajear": "mensajear",
            "lead_advisor": "lead_advisor",
        },
    )
    workflow.add_edge("extract_search_filters", "search")
    workflow.add_conditional_edges(
        "search",
        build_traced_router("after_search", after_search, deps),
        {"search": "search", "lead_advisor": "lead_advisor", "check_queue": "check_queue", "render_cards": "render_cards"},
    )
    workflow.add_conditional_edges(
        "render_cards",
        build_traced_router("after_render_cards", after_render_cards, deps),
        {"check_queue": "check_queue"},
    )
    workflow.add_edge("financial_calc", "check_queue")
    workflow.add_edge("compare_properties", "check_queue")
    workflow.add_edge("mutate_comparison_set", "check_queue")
    workflow.add_edge("rag_agencia", "check_queue")
    workflow.add_edge("rag_documents", "check_queue")
    workflow.add_edge("llm_recommend", "check_queue")
    workflow.add_conditional_edges(
        "collect_appointment_data",
        build_traced_router("after_collect_appointment_data", after_collect_appointment_data, deps),
        {"assign_agent": "assign_agent", "synthesize": "synthesize"},
    )
    workflow.add_edge("assign_agent", "mensajear")
    workflow.add_edge("mensajear", "check_queue")
    workflow.add_conditional_edges(
        "check_queue",
        build_traced_router("after_check_queue", after_check_queue, deps),
        {"route_next_intent": "route_next_intent", "lead_advisor": "lead_advisor"},
    )
    workflow.add_edge("lead_advisor", "synthesize")
    workflow.add_edge("synthesize", END)
    return workflow.compile()
