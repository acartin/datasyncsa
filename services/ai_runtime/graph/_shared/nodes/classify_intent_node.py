"""Intent classification node."""

from __future__ import annotations

import re
from typing import Any

from services.ai_runtime.config.prompt_composer import compose
from services.ai_runtime.domain.contracts import IntentDefinition
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import BaseGraphState

INTERNAL_INTENTS = {"focus_property"}
COMPARE_SIGNAL_PATTERN = re.compile(
    r"\b(compara|compar[aá]|comparame|comparar|vs|versus|mejor entre|diferencia entre|lado a lado)\b",
    flags=re.IGNORECASE,
)
AFFIRMATIVE_TURN_PATTERN = re.compile(
    r"^\s*(si|sí|claro|dale|de una|ok|okay|perfecto|me interesa|por favor)\s*[.!]*\s*$",
    flags=re.IGNORECASE,
)
DESCRIBE_RESULTS_PATTERN = re.compile(
    r"(te\s+las\s+describa|te\s+los\s+describa|te\s+las\s+describo|te\s+los\s+describo|alguna\s+se\s+acerca\s+a\s+lo\s+que\s+buscas|te\s+cuente\s+m[aá]s\s+detalles|te\s+describa\s+las\s+opciones)",
    flags=re.IGNORECASE,
)


def _should_focus_selected_property(graph_state: BaseGraphState, detected: list[IntentDefinition]) -> bool:
    property_refs = [item for item in graph_state.resolved_references if item.get("kind") == "property"]
    if len(property_refs) != 1:
        return False
    if COMPARE_SIGNAL_PATTERN.search(graph_state.messages[-1].content):
        return False
    if not detected:
        return True
    return detected[0].type == "comparar"


def _should_reuse_search_results(graph_state: BaseGraphState, detected: list[IntentDefinition]) -> bool:
    if detected or graph_state.resolved_references:
        return False
    if not AFFIRMATIVE_TURN_PATTERN.search(graph_state.messages[-1].content):
        return False
    last_search_results = getattr(graph_state, "last_search_results", [])
    if not last_search_results:
        return False
    previous_assistant = next(
        (message.content for message in reversed(graph_state.messages[:-1]) if message.role == "assistant"),
        "",
    )
    return bool(DESCRIBE_RESULTS_PATTERN.search(previous_assistant))


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
    normalized_detected = [
        intent if isinstance(intent, IntentDefinition) else IntentDefinition.model_validate(intent)
        for intent in detected
    ]
    if _should_focus_selected_property(graph_state, normalized_detected):
        normalized_detected = [
            IntentDefinition(
                id="focus-property-0001",
                type="focus_property",
                priority=1,
                depends_on=[],
                condition={"requires_reference": "resolved_property"},
                skip_if_failed=False,
                status="pending",
                output=None,
            )
        ]
    elif _should_reuse_search_results(graph_state, normalized_detected):
        normalized_detected = [
            IntentDefinition(
                id="search-followup-0001",
                type="buscar",
                priority=1,
                depends_on=[],
                condition={"reuse_current_filters": True},
                skip_if_failed=False,
                status="pending",
                output=None,
            )
        ]
    allowed = []
    for intent_model in normalized_detected:
        if intent_model.type in graph_state.capabilities or intent_model.type in INTERNAL_INTENTS:
            allowed.append(intent_model)
    allowed.sort(key=lambda item: item.priority)
    limited = allowed[:4]
    return {
        "intent_queue": [intent.model_dump(mode="json") for intent in limited],
        "active_intent": None,
    }
