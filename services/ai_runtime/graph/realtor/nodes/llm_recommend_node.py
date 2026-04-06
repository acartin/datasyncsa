"""Realtor recommendation node."""

from __future__ import annotations

from typing import Any

from services.ai_runtime.config.prompt_composer import compose
from services.ai_runtime.domain.contracts import Property
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import RealtorGraphState
from services.ai_runtime.graph._shared.nodes.helpers import complete_active_intent
from services.ai_runtime.graph._shared.prompt_context import (
    summarize_properties_for_prompt,
    summarize_property_for_prompt,
)
from services.ai_runtime.graph.realtor.nodes.comparison_helpers import score_property


def _select_visible_properties(graph_state: RealtorGraphState) -> list[Property]:
    property_map = {
        item.id: item
        for item in [*graph_state.last_search_results, *graph_state.inventory]
    }
    if graph_state.cards_shown:
        selected: list[Property] = []
        seen: set[str] = set()
        for property_id in graph_state.cards_shown:
            item = property_map.get(property_id)
            if not item or item.id in seen:
                continue
            selected.append(item)
            seen.add(item.id)
        if selected:
            return selected
    return [Property.model_validate(item.model_dump(mode="json")) for item in graph_state.last_search_results[:4]]


def _extract_explicit_preferences(graph_state: RealtorGraphState) -> dict[str, Any]:
    filters = graph_state.search_filters.model_dump(mode="json")
    explicit_filters = {
        key: value
        for key, value in filters.items()
        if value not in (None, "", [], {})
    }
    lead = graph_state.lead_advisor.lead_extracted.model_dump(mode="json")
    explicit_lead = {
        key: value
        for key, value in lead.items()
        if value not in (None, "", [], {})
    }
    preferences = {
        "search_filters": explicit_filters,
        "lead_data": explicit_lead,
        "has_explicit_preferences": bool(explicit_filters or explicit_lead),
    }
    return preferences


async def llm_recommend(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    graph_state = RealtorGraphState.model_validate(state)
    properties = _select_visible_properties(graph_state)
    if not properties:
        output = {
            "type": "recommendation",
            "narrative": "Puedo recomendarte mejor apenas tenga opciones activas para comparar.",
        }
        return {
            "turn_outputs": [*graph_state.turn_outputs, output],
            **complete_active_intent(graph_state, output),
        }
    scores = [score_property(item) for item in properties]
    recommended_score = max(scores, key=lambda item: item.score_total)
    recommended_property = next(
        item for item in properties if item.id == recommended_score.property_id
    )
    prompt = compose(
        "recommendation",
        graph_state.tenant_config,
        graph_state.vertical,
        {
            "visible_properties": summarize_properties_for_prompt(
                properties,
                limit=len(properties),
                include_description_excerpt=True,
            ),
            "scores": [item.model_dump(mode="json") for item in scores],
            "recommended_property": summarize_property_for_prompt(
                recommended_property,
                include_description_excerpt=True,
            ),
            "recommended_score": recommended_score.model_dump(mode="json"),
            "explicit_preferences": _extract_explicit_preferences(graph_state),
        },
    )
    narrative = await deps.llm.redact_recommendation(prompt)
    output = {
        "type": "recommendation",
        "property": recommended_property.model_dump(mode="json"),
        "scores": [item.model_dump(mode="json") for item in scores],
        "narrative": narrative,
    }
    return {
        "turn_outputs": [*graph_state.turn_outputs, output],
        "last_mentioned": recommended_property.model_dump(mode="json"),
        **complete_active_intent(graph_state, output),
    }
