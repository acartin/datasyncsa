"""Realtor cards rendering node."""

from __future__ import annotations

import re
from typing import Any

from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.graph._shared.nodes.helpers import complete_active_intent
from services.ai_runtime.graph.realtor.contracts import CardPayload, Property
from services.ai_runtime.graph.realtor.state.model import RealtorGraphState
from services.ai_runtime.graph.realtor.turn_frame import merge_seen_properties


def _strip_html(value: str | None) -> str | None:
    if not value:
        return None
    text = re.sub(r"<[^>]+>", " ", value)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def build_card_payload(properties: list[Property]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for item in properties:
        image_urls = list(item.media.image_urls or [])
        if not image_urls and item.media.primary_image_url:
            image_urls = [item.media.primary_image_url]
        location = item.address or item.location.province
        payload.append(
            CardPayload(
                id=item.id,
                title=item.title,
                price=item.price,
                currency=item.currency,
                bedrooms_clean=item.features.bedrooms_clean,
                bathrooms_clean=item.features.bathrooms_clean,
                sqm_clean=item.features.sqm_clean,
                garage_clean=item.features.garage_clean,
                location=location,
                address=item.address,
                primary_image_url=item.media.primary_image_url,
                image_urls=image_urls,
                photo_count=len(image_urls),
                public_url=item.meta.public_url,
                province=item.location.province,
                amenities=list(item.features.amenities or [])[:8],
                description=_strip_html(item.description_html),
                price_note="Precio publicado",
                badge_main="Destacada" if item.features.is_featured else None,
            ).model_dump(mode="json")
        )
    return payload


async def render_cards(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    _ = deps
    graph_state = RealtorGraphState.model_validate(state)
    properties = [Property.model_validate(item) for item in graph_state.last_search_results]
    if len(properties) == 1:
        selected = properties[:1]
        mode = "single"
    else:
        interest = graph_state.lead_advisor.lead_scores.intencion
        spotlight = graph_state.search_attempts <= 1 and interest < 5
        selected = properties[:2] if spotlight else properties[:4]
        mode = "spotlight" if spotlight else "gallery"
    payload = build_card_payload(selected)
    output = {"type": "render_cards", "mode": mode, "count": len(payload)}
    updates = {
        "cards_shown": [item["id"] for item in payload],
        "cards_mode": mode,
        "render_mode": "cards",
        "ui_payload": {"property_cards": payload},
        "turn_outputs": [*graph_state.turn_outputs, output],
        "seen_properties": merge_seen_properties(
            graph_state.seen_properties,
            selected,
            current_turn=graph_state.current_turn,
        ),
        **complete_active_intent(graph_state, output),
    }
    if len(selected) == 1:
        updates["last_mentioned"] = selected[0].model_dump(mode="json")
    return updates
