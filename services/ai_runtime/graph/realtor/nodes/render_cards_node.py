"""Realtor cards rendering node."""

from __future__ import annotations

from typing import Any

from services.ai_runtime.domain.contracts import CardPayload, Property
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import RealtorGraphState
from services.ai_runtime.graph._shared.nodes.helpers import complete_active_intent


async def render_cards(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    _ = deps
    graph_state = RealtorGraphState.model_validate(state)
    properties = [Property.model_validate(item) for item in graph_state.last_search_results]
    interest = graph_state.lead_advisor.lead_scores.intencion
    spotlight = graph_state.search_attempts <= 1 and interest < 5
    selected = properties[:2] if spotlight else properties[:4]
    payload = [
        CardPayload(
            property_id_internal=item.property_id_internal,
            title=item.title,
            price=item.price,
            currency=item.currency,
            bedrooms_clean=item.features.bedrooms_clean,
            bathrooms_clean=item.features.bathrooms_clean,
            sqm_clean=item.features.sqm_clean,
            primary_image_url=item.media.primary_image_url,
            province=item.location.province,
        ).model_dump(mode="json")
        for item in selected
    ]
    output = {"type": "render_cards", "mode": "spotlight" if spotlight else "gallery", "count": len(payload)}
    return {
        "cards_shown": [item["property_id_internal"] for item in payload],
        "cards_mode": "spotlight" if spotlight else "gallery",
        "render_mode": "cards",
        "ui_payload": {"property_cards": payload},
        "turn_outputs": [*graph_state.turn_outputs, output],
        **complete_active_intent(graph_state, output),
    }
