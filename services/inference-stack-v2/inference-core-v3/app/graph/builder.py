from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, StateGraph

from app.graph import nodes
from app.models.agent_state import AgentState


logger = logging.getLogger("inference-core-v3.graph")


def build_realtor_subgraph():
    graph = StateGraph(AgentState)
    graph.add_node("realtor_turn_planner", nodes.realtor_turn_planner_node)
    graph.add_node("realtor_search_transition_judge", nodes.realtor_search_transition_judge_node)
    graph.add_node("realtor_filter_carryover_guard", nodes.realtor_filter_carryover_guard_node)
    graph.add_node("realtor_query_compiler", nodes.realtor_query_compiler_node)
    graph.add_node("shown_results_reference_resolver", nodes.shown_results_reference_resolver_node)
    graph.add_node("realtor_context_resolver", nodes.realtor_context_resolver_node)
    graph.add_node("realtor_tool_executor", nodes.realtor_tool_executor_node)
    graph.add_node("lead_followup_planner", nodes.lead_followup_planner_node)
    graph.add_node("answer_synthesizer", nodes.answer_synthesizer_node)

    graph.set_entry_point("realtor_turn_planner")
    graph.add_conditional_edges(
        "realtor_turn_planner",
        nodes.select_realtor_compiler_route,
        {
            "realtor_search_transition_judge": "realtor_search_transition_judge",
            "shown_results_reference_resolver": "shown_results_reference_resolver",
            "realtor_context_resolver": "realtor_context_resolver",
            "lead_followup_planner": "lead_followup_planner",
        },
    )
    graph.add_edge("realtor_search_transition_judge", "realtor_filter_carryover_guard")
    graph.add_edge("realtor_filter_carryover_guard", "realtor_query_compiler")
    graph.add_edge("realtor_query_compiler", "realtor_tool_executor")
    graph.add_edge("shown_results_reference_resolver", "lead_followup_planner")
    graph.add_edge("realtor_context_resolver", "lead_followup_planner")
    graph.add_edge("realtor_tool_executor", "lead_followup_planner")
    graph.add_edge("lead_followup_planner", "answer_synthesizer")
    graph.add_edge("answer_synthesizer", END)
    return graph.compile()


def build_generic_subgraph():
    graph = StateGraph(AgentState)
    graph.add_node("generic_turn_planner", nodes.generic_turn_planner_node)
    graph.add_node("generic_tool_executor", nodes.generic_tool_executor_node)
    graph.add_node("lead_followup_planner", nodes.lead_followup_planner_node)
    graph.add_node("answer_synthesizer", nodes.answer_synthesizer_node)

    graph.set_entry_point("generic_turn_planner")
    graph.add_conditional_edges(
        "generic_turn_planner",
        nodes.select_generic_executor_route,
        {
            "generic_tool_executor": "generic_tool_executor",
            "lead_followup_planner": "lead_followup_planner",
        },
    )
    graph.add_edge("generic_tool_executor", "lead_followup_planner")
    graph.add_edge("lead_followup_planner", "answer_synthesizer")
    graph.add_edge("answer_synthesizer", END)
    return graph.compile()


def build_workflow_subgraph():
    graph = StateGraph(AgentState)
    graph.add_node("workflow_planner", nodes.workflow_planner_node)
    graph.add_node("workflow_executor", nodes.workflow_executor_node)
    graph.add_node("lead_followup_planner", nodes.lead_followup_planner_node)
    graph.add_node("answer_synthesizer", nodes.answer_synthesizer_node)

    graph.set_entry_point("workflow_planner")
    graph.add_edge("workflow_planner", "workflow_executor")
    graph.add_edge("workflow_executor", "lead_followup_planner")
    graph.add_edge("lead_followup_planner", "answer_synthesizer")
    graph.add_edge("answer_synthesizer", END)
    return graph.compile()


def build_graph() -> StateGraph:
    realtor_subgraph = build_realtor_subgraph()
    generic_subgraph = build_generic_subgraph()
    workflow_subgraph = build_workflow_subgraph()

    async def dispatch_subgraph(state: AgentState) -> dict[str, Any]:
        subgraph_key = str(state.get("active_vertical_subgraph") or "generic_subgraph").strip()
        if subgraph_key == "realtor_subgraph":
            return await realtor_subgraph.ainvoke(state)
        if subgraph_key == "workflow_subgraph":
            return await workflow_subgraph.ainvoke(state)
        return await generic_subgraph.ainvoke(state)

    graph = StateGraph(AgentState)
    graph.add_node("load_request", nodes.load_request)
    graph.add_node("load_tenant_runtime", nodes.load_tenant_runtime)
    graph.add_node("load_conversation_memory", nodes.load_conversation_memory)
    graph.add_node("load_live_lead_state", nodes.load_live_lead_state)
    graph.add_node("route_turn", nodes.route_turn)
    graph.add_node("dispatch_subgraph", dispatch_subgraph)
    graph.add_node("persist_memory", nodes.persist_memory)
    graph.add_node("enqueue_side_effects", nodes.enqueue_side_effects)
    graph.add_node("return_response", nodes.return_response)

    graph.set_entry_point("load_request")
    graph.add_edge("load_request", "load_tenant_runtime")
    graph.add_edge("load_tenant_runtime", "load_conversation_memory")
    graph.add_edge("load_conversation_memory", "load_live_lead_state")
    graph.add_edge("load_live_lead_state", "route_turn")
    graph.add_edge("route_turn", "dispatch_subgraph")
    graph.add_edge("dispatch_subgraph", "persist_memory")
    graph.add_edge("persist_memory", "enqueue_side_effects")
    graph.add_edge("enqueue_side_effects", "return_response")
    graph.add_edge("return_response", END)
    return graph


class V3FlowGraph:
    def __init__(self) -> None:
        self.graph = build_graph().compile()

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        logger.debug("Running v3 graph for client=%s", state.get("raw_request", {}).get("client_id"))
        return await self.graph.ainvoke(state)
