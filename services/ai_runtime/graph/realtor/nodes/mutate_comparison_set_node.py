"""Realtor comparison-set mutation node."""

from __future__ import annotations

from typing import Any

from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import RealtorGraphState
from services.ai_runtime.graph._shared.nodes.helpers import complete_active_intent


async def mutate_comparison_set(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    _ = deps
    graph_state = RealtorGraphState.model_validate(state)
    operation = (graph_state.active_intent.output or {}).get("operation", "REPLACE") if graph_state.active_intent else "REPLACE"
    property_ids = [
        reference["property_id_internal"]
        for reference in graph_state.resolved_references
        if reference.get("kind") == "property" and reference.get("property_id_internal")
    ]
    current = list(graph_state.active_comparison)
    if operation == "ADD":
        updated = list(dict.fromkeys([*current, *property_ids]))
    elif operation == "REMOVE":
        updated = [item for item in current if item not in property_ids]
    else:
        updated = property_ids
    output = {"type": "comparison_set", "operation": operation, "property_ids": updated}
    return {
        "active_comparison": updated,
        "turn_outputs": [*graph_state.turn_outputs, output],
        **complete_active_intent(graph_state, output),
    }
