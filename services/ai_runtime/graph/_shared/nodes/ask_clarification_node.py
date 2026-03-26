"""Clarification node."""

from __future__ import annotations

from typing import Any

from services.ai_runtime.config.prompt_composer import compose
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import BaseGraphState


async def ask_clarification(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    """Ask a single clarification question and stop the turn."""

    graph_state = BaseGraphState.model_validate(state)
    prompt = compose(
        "clarification",
        graph_state.tenant_config,
        graph_state.vertical,
        {
            "pending_clarification": graph_state.pending_clarification,
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
        "turn_outputs": [*graph_state.turn_outputs, {"type": "clarification", "question": question}],
    }
