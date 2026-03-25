"""Shared helper functions for state updates."""

from __future__ import annotations

from typing import Any

from services.ai_runtime.domain.contracts import IntentDefinition
from services.ai_runtime.domain.state import BaseGraphState


def complete_active_intent(state: BaseGraphState, output: dict[str, Any]) -> dict[str, Any]:
    """Move the active intent from running to done and snapshot its output."""

    if not state.active_intent:
        return {}
    completed = state.active_intent.model_copy(update={"status": "done", "output": output})
    queue = []
    for item in state.intent_queue:
        intent = item if isinstance(item, IntentDefinition) else IntentDefinition.model_validate(item)
        queue.append(completed if intent.id == completed.id else intent)
    return {
        "intent_queue": [intent.model_dump(mode="json") for intent in queue],
        "completed_intents": [
            *[intent.model_dump(mode="json") for intent in state.completed_intents],
            completed.model_dump(mode="json"),
        ],
        "active_intent": None,
    }

