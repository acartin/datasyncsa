"""Realtor recommendation node."""

from __future__ import annotations

from typing import Any

from services.ai_runtime.config.prompt_composer import compose
from services.ai_runtime.domain.contracts import Property
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import RealtorGraphState
from services.ai_runtime.graph._shared.nodes.helpers import complete_active_intent
from services.ai_runtime.graph.realtor.nodes.comparison_helpers import score_property


async def llm_recommend(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    graph_state = RealtorGraphState.model_validate(state)
    properties = [Property.model_validate(item) for item in graph_state.last_search_results[:4]]
    scores = [score_property(item) for item in properties]
    prompt = compose(
        "recommendation",
        graph_state.tenant_config,
        graph_state.vertical,
        {
            "properties": [item.model_dump(mode="json") for item in properties],
            "scores": [item.model_dump(mode="json") for item in scores],
            "lead": graph_state.lead_advisor.lead_extracted.model_dump(mode="json"),
        },
    )
    narrative = await deps.llm.redact_recommendation(prompt)
    output = {
        "type": "recommendation",
        "scores": [item.model_dump(mode="json") for item in scores],
        "narrative": narrative,
    }
    return {
        "turn_outputs": [*graph_state.turn_outputs, output],
        **complete_active_intent(graph_state, output),
    }
