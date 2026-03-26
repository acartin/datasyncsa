"""Show cards for the current result set on explicit visual requests."""

from __future__ import annotations

from typing import Any

from services.ai_runtime.domain.contracts import Property, TurnAnalysis
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import RealtorGraphState
from services.ai_runtime.graph._shared.nodes.helpers import complete_active_intent
from services.ai_runtime.graph.realtor.nodes.render_cards_node import build_card_payload


def _select_properties(graph_state: RealtorGraphState) -> list[Property]:
    property_map = {
        item.property_id_internal: item
        for item in [*graph_state.last_search_results, *graph_state.inventory]
    }
    if graph_state.cards_shown:
        selected: list[Property] = []
        for property_id in graph_state.cards_shown:
            item = property_map.get(property_id)
            if item and item.property_id_internal not in {current.property_id_internal for current in selected}:
                selected.append(item)
        if selected:
            return selected
    if graph_state.last_search_results:
        return list(graph_state.last_search_results[:2])
    return []


def _build_narrative(properties: list[Property]) -> str:
    if not properties:
        return "Entendí que querés ver la ficha, pero en este momento no tengo una propiedad activa para mostrártela."
    if len(properties) == 1:
        property_item = properties[0]
        has_image = bool(property_item.media.primary_image_url or property_item.media.image_urls)
        if has_image:
            return f"Te la muestro por acá: {property_item.title}."
        return f"Te dejo la ficha de {property_item.title}. En este registro no tengo una foto cargada todavía."
    has_any_image = any(item.media.primary_image_url or item.media.image_urls for item in properties)
    if has_any_image:
        return "Te muestro las opciones por acá para que las puedas revisar mejor."
    return "Te dejo las fichas de estas opciones. En este registro no tengo fotos cargadas todavía."


async def show_result_cards(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    del deps
    graph_state = RealtorGraphState.model_validate(state)
    analysis = TurnAnalysis.model_validate(graph_state.turn_analysis or {})
    properties = _select_properties(graph_state)
    payload = build_card_payload(properties)
    narrative = _build_narrative(properties)
    mode = "single" if len(payload) <= 1 else "gallery"

    output = {
        "type": "show_result_cards",
        "mode": mode,
        "count": len(payload),
        "narrative": narrative,
    }
    updates: dict[str, Any] = {
        "turn_outputs": [*graph_state.turn_outputs, output],
        "render_mode": "cards" if payload else "text",
        "cards_mode": mode if payload else None,
        "ui_payload": {"property_cards": payload} if payload else None,
        "cards_shown": [item["property_id_internal"] for item in payload],
        **complete_active_intent(graph_state, output),
    }
    if len(properties) == 1 and analysis.detail_attribute_key == "foto":
        updates["last_mentioned"] = properties[0].model_dump(mode="json")
    return updates
