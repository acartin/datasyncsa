"""Intent classification node."""

from __future__ import annotations

from typing import Any

from services.ai_runtime.config.prompt_composer import compose
from services.ai_runtime.domain.contracts import IntentDefinition
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import BaseGraphState


async def classify_intent(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    """Detect every supported intent for the message and keep only tenant-enabled capabilities."""

    graph_state = BaseGraphState.model_validate(state)
    prompt = compose(
        "intent_detector",
        graph_state.tenant_config,
        graph_state.vertical,
        {
            "message": graph_state.messages[-1].model_dump(mode="json"),
            "capabilities": graph_state.capabilities,
            "resolved_references": graph_state.resolved_references,
            "turn_outputs": graph_state.turn_outputs,
        },
    )
    detected = await deps.llm.detect_intents(prompt)
    allowed = []
    for intent in detected:
        intent_model = intent if isinstance(intent, IntentDefinition) else IntentDefinition.model_validate(intent)
        if intent_model.type in graph_state.capabilities:
            allowed.append(intent_model)
    allowed.sort(key=lambda item: item.priority)
    limited = allowed[:4]
    return {
        "intent_queue": [intent.model_dump(mode="json") for intent in limited],
        "active_intent": None,
    }
