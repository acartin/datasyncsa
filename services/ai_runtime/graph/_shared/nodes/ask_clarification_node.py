"""Clarification node."""

from __future__ import annotations

from typing import Any

from services.ai_runtime.config.prompt_composer import compose
from services.ai_runtime.domain.contracts import PendingDecision
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import BaseGraphState
from services.ai_runtime.graph._shared.pending_decisions import render_pending_decision_question


async def ask_clarification(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    """Ask a single clarification question and stop the turn."""

    graph_state = BaseGraphState.model_validate(state)
    pending_decision = (
        PendingDecision.model_validate(graph_state.pending_decision)
        if graph_state.pending_decision
        else None
    )
    question = render_pending_decision_question(pending_decision)
    if not question:
        prompt = compose(
            "clarification",
            graph_state.tenant_config,
            graph_state.vertical,
            {
                "pending_clarification": graph_state.pending_clarification,
                "pending_decision": pending_decision.model_dump(mode="json") if pending_decision else None,
                "clarification_attempts": graph_state.clarification_attempts,
            },
            include_tone=True,
        )
        question = await deps.llm.synthesize_response(prompt)
    return {
        "clarification_attempts": graph_state.clarification_attempts + 1,
        "final_response": question,
        "messages": [
            *[message.model_dump(mode="json") for message in graph_state.messages],
            {"role": "assistant", "content": question},
        ],
        "turn_outputs": [
            *graph_state.turn_outputs,
            {
                "type": "clarification",
                "question": question,
                "pending_decision_kind": pending_decision.kind if pending_decision else None,
            },
        ],
    }
