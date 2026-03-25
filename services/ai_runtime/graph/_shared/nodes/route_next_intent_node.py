"""Intent queue routing node."""

from __future__ import annotations

from typing import Any

from services.ai_runtime.config.prompt_composer import compose
from services.ai_runtime.domain.contracts import IntentDefinition
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import BaseGraphState


def _deterministic_condition_passes(state: BaseGraphState, condition: dict[str, Any] | None) -> bool | None:
    if not condition:
        return True
    if "requires_reference" in condition:
        return bool(state.resolved_references)
    if "min_search_results" in condition:
        return len(getattr(state, "last_search_results", [])) >= int(condition["min_search_results"])
    if "field_present" in condition:
        fields = state.lead_advisor.lead_extracted.model_dump()
        return fields.get(str(condition["field_present"])) is not None
    if condition.get("mode") == "lazy":
        return None
    return True


async def route_next_intent(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    """Pick the next executable intent using deterministic dependency checks."""

    graph_state = BaseGraphState.model_validate(state)
    queue = [IntentDefinition.model_validate(item) for item in graph_state.intent_queue]
    completed_ids = {item.id for item in graph_state.completed_intents if item.status == "done"}

    selected: IntentDefinition | None = None
    for intent in queue:
        if intent.status != "pending":
            continue
        if any(dependency not in completed_ids for dependency in intent.depends_on):
            continue
        condition_result = _deterministic_condition_passes(graph_state, intent.condition)
        if condition_result is None:
            prompt = compose(
                "lazy_condition_evaluator",
                graph_state.tenant_config,
                graph_state.vertical,
                {
                    "intent": intent.model_dump(mode="json"),
                    "turn_outputs": graph_state.turn_outputs,
                    "state": graph_state.model_dump(mode="json"),
                },
            )
            condition_result = await deps.llm.evaluate_lazy_condition(prompt)
        if not condition_result:
            if intent.skip_if_failed:
                intent.status = "skipped"
            continue
        intent.status = "running"
        selected = intent
        break

    return {
        "intent_queue": [intent.model_dump(mode="json") for intent in queue],
        "active_intent": selected.model_dump(mode="json") if selected else None,
    }
