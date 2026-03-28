"""Builder for the reduced generic LangGraph."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from services.ai_runtime.domain.state import GenericGraphState
from services.ai_runtime.domain.contracts import TenantConfig
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.graph._shared.nodes import (
    analyze_turn,
    ask_clarification,
    capture_memory_entities,
    check_queue,
    collect_lead_data,
    lead_advisor,
    memory_lookup,
    route_next_intent,
    synthesize,
)
from services.ai_runtime.graph._shared.nodes.helpers import complete_active_intent
from services.ai_runtime.graph._shared.routers.common import (
    after_analyze_turn,
    after_capture_memory,
    after_check_queue,
    after_memory_lookup,
)
from services.ai_runtime.graph._shared.tools.mensajear import mensajear
from services.ai_runtime.graph.generic.nodes.assign_agent_node import assign_agent
from services.ai_runtime.graph.generic.nodes.collect_appointment_data_node import collect_appointment_data
from services.ai_runtime.graph.generic.nodes.rag_agencia_node import rag_agencia
from services.ai_runtime.graph.generic.routers.routes import after_collect_appointment_data, after_route_next_intent
from services.ai_runtime.runtime.turn_trace import build_traced_node, build_traced_router


def _mail_node(deps: GraphDependencies):
    async def _mail_impl(state: dict, runtime_deps: GraphDependencies):
        tenant_config = TenantConfig.model_validate(state["tenant_config"])
        graph_state = GenericGraphState.model_validate(state)
        output = (
            await mensajear(
                dependencies=runtime_deps,
                client_id=state["client_id"],
                tipo="appointment_confirmation",
                destinatarios=[],
                datos_cita=state.get("cita", {}),
                tenant_config=tenant_config,
            )
        ).model_dump(mode="json")
        return {
            "turn_outputs": [*state.get("turn_outputs", []), {"type": "mensajear", **output}],
            **complete_active_intent(graph_state, {"type": "mensajear", **output}),
        }

    return build_traced_node("mensajear", _mail_impl, deps)


def build_generic_graph(deps: GraphDependencies):
    workflow = StateGraph(dict)
    workflow.add_node("analyze_turn", build_traced_node("analyze_turn", analyze_turn, deps))
    workflow.add_node("ask_clarification", build_traced_node("ask_clarification", ask_clarification, deps))
    workflow.add_node("capture_memory_entities", build_traced_node("capture_memory_entities", capture_memory_entities, deps))
    workflow.add_node("memory_lookup", build_traced_node("memory_lookup", memory_lookup, deps))
    workflow.add_node("route_next_intent", build_traced_node("route_next_intent", route_next_intent, deps))
    workflow.add_node("collect_lead_data", build_traced_node("collect_lead_data", collect_lead_data, deps))
    workflow.add_node("rag_agencia", build_traced_node("rag_agencia", rag_agencia, deps))
    workflow.add_node("collect_appointment_data", build_traced_node("collect_appointment_data", collect_appointment_data, deps))
    workflow.add_node("assign_agent", build_traced_node("assign_agent", assign_agent, deps))
    workflow.add_node("mensajear", _mail_node(deps))
    workflow.add_node("check_queue", build_traced_node("check_queue", check_queue, deps))
    workflow.add_node("lead_advisor", build_traced_node("lead_advisor", lead_advisor, deps))
    workflow.add_node("synthesize", build_traced_node("synthesize", synthesize, deps))

    workflow.add_edge(START, "analyze_turn")
    workflow.add_conditional_edges(
        "analyze_turn",
        build_traced_router("after_analyze_turn", after_analyze_turn, deps),
        {
            "ask_clarification": "ask_clarification",
            "collect_lead_data": "collect_lead_data",
            "capture_memory_entities": "capture_memory_entities",
        },
    )
    workflow.add_edge("ask_clarification", END)
    workflow.add_conditional_edges(
        "capture_memory_entities",
        build_traced_router("after_capture_memory", after_capture_memory, deps),
        {
            "memory_lookup": "memory_lookup",
            "route_next_intent": "route_next_intent",
            "lead_advisor": "lead_advisor",
            "synthesize": "synthesize",
        },
    )
    workflow.add_conditional_edges(
        "memory_lookup",
        build_traced_router("after_memory_lookup", after_memory_lookup, deps),
        {"route_next_intent": "route_next_intent", "lead_advisor": "lead_advisor", "end": END, "synthesize": "synthesize"},
    )
    workflow.add_edge("collect_lead_data", "synthesize")
    workflow.add_conditional_edges(
        "route_next_intent",
        build_traced_router("after_route_next_intent", after_route_next_intent, deps),
        {
            "rag_agencia": "rag_agencia",
            "collect_lead_data": "collect_lead_data",
            "collect_appointment_data": "collect_appointment_data",
            "mensajear": "mensajear",
            "lead_advisor": "lead_advisor",
        },
    )
    workflow.add_edge("rag_agencia", "check_queue")
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
