from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.models.contracts import GoalType
from app.graph.nodes import (
    answer_guardrail,
    clarify_response,
    execute_tools,
    hydrate_conversation_context,
    normalize_input,
    persist,
    plan_turn,
    policy_gate,
    synthesize,
)
from app.graph.state import AgentCoreState


def _route_after_policy_gate(state: AgentCoreState) -> str:
    gate = state.get("gate_result")
    decision = state.get("router_decision")

    if gate is None or not getattr(gate, "accepted", False):
        return "persist"
    if decision is not None and decision.goal == GoalType.clarify:
        return "clarify_response"
    return "execute_tools"


def _route_after_guardrail(state: AgentCoreState) -> str:
    guardrail = state.get("guardrail_result")
    if guardrail is None or not getattr(guardrail, "accepted", False):
        return "persist"
    return "persist"


def build_agent_graph():
    graph = StateGraph(AgentCoreState)

    graph.add_node("normalize_input", normalize_input)
    graph.add_node("hydrate_conversation_context", hydrate_conversation_context)
    graph.add_node("plan_turn", plan_turn)
    graph.add_node("policy_gate", policy_gate)
    graph.add_node("clarify_response", clarify_response)
    graph.add_node("execute_tools", execute_tools)
    graph.add_node("synthesize", synthesize)
    graph.add_node("answer_guardrail", answer_guardrail)
    graph.add_node("persist", persist)

    graph.add_edge(START, "normalize_input")
    graph.add_edge("normalize_input", "hydrate_conversation_context")
    graph.add_edge("hydrate_conversation_context", "plan_turn")
    graph.add_edge("plan_turn", "policy_gate")

    graph.add_conditional_edges(
        "policy_gate",
        _route_after_policy_gate,
        {
            "clarify_response": "clarify_response",
            "execute_tools": "execute_tools",
            "persist": "persist",
        },
    )

    graph.add_edge("clarify_response", "persist")
    graph.add_edge("execute_tools", "synthesize")
    graph.add_edge("synthesize", "answer_guardrail")
    graph.add_conditional_edges(
        "answer_guardrail",
        _route_after_guardrail,
        {
            "persist": "persist",
        },
    )

    graph.add_edge("persist", END)

    return graph.compile()


agent_graph = build_agent_graph()
