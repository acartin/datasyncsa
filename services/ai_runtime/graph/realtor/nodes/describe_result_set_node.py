"""Describe the currently visible result set for attribute-focused follow-up questions."""

from __future__ import annotations

import re
from typing import Any

from services.ai_runtime.domain.contracts import TurnAnalysis
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.graph._shared.nodes.helpers import complete_active_intent
from services.ai_runtime.graph.realtor.contracts import Property
from services.ai_runtime.graph.realtor.state.model import RealtorGraphState


def _format_number(value: float | int) -> str:
    numeric = float(value)
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.1f}".rstrip("0").rstrip(".")


def _format_money(value: float | int | None, currency: str | None) -> str | None:
    if value in (None, ""):
        return None
    amount = float(value)
    code = (currency or "").strip().upper()
    prefix = f"{code} " if code else ""
    formatted = f"{amount:,.0f}".replace(",", ".")
    return f"{prefix}{formatted}".strip()


def _parse_area(value: str | int | float | None) -> float | None:
    if value in (None, "", 0):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    raw = str(value).strip()
    if not raw:
        return None
    cleaned = re.sub(r"[^0-9.,]", "", raw)
    if not cleaned:
        return None

    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            normalized = cleaned.replace(".", "").replace(",", ".")
        else:
            normalized = cleaned.replace(",", "")
    elif cleaned.count(",") == 1 and len(cleaned.split(",")[-1]) == 3:
        normalized = cleaned.replace(",", "")
    elif cleaned.count(".") == 1 and len(cleaned.split(".")[-1]) == 3:
        normalized = cleaned.replace(".", "")
    else:
        normalized = cleaned.replace(",", ".")

    try:
        return float(normalized)
    except ValueError:
        return None


def _effective_area(property_item: Property) -> float | None:
    if property_item.features.sqm_clean:
        return float(property_item.features.sqm_clean)
    return _parse_area(property_item.features.lot_size_sqm)


def _load_displayed_properties(graph_state: RealtorGraphState) -> list[Property]:
    property_map = {
        item.id: item
        for item in [*graph_state.last_search_results, *graph_state.inventory]
    }

    selected: list[Property] = []
    if graph_state.cards_shown:
        for property_id in graph_state.cards_shown:
            item = property_map.get(property_id)
            if item and item.id not in {current.id for current in selected}:
                selected.append(item)
    elif graph_state.last_search_results:
        selected = list(graph_state.last_search_results[:3])
    return selected


def _label_for_index(index: int, total: int) -> str:
    if total == 2:
        return "La primera" if index == 1 else "La segunda"
    return f"La opción {index}"


def _format_attribute_value(property_item: Property, attribute_key: str) -> str | None:
    if attribute_key == "banos":
        bathrooms = property_item.features.bathrooms_clean
        if bathrooms > 0:
            return f"{_format_number(bathrooms)} baños"
        return None
    if attribute_key == "habitaciones":
        bedrooms = property_item.features.bedrooms_clean
        if bedrooms > 0:
            return f"{_format_number(bedrooms)} habitaciones"
        return None
    if attribute_key == "area":
        area = _effective_area(property_item)
        if area:
            return f"{_format_number(area)} m²"
        return None
    if attribute_key == "precio":
        return _format_money(property_item.price, property_item.currency)
    if attribute_key == "garage":
        garage = property_item.features.garage_clean
        if garage > 0:
            label = "estacionamiento" if int(garage) == 1 else "estacionamientos"
            return f"{_format_number(garage)} {label}"
        return None
    return None


def _build_result_set_detail_narrative(properties: list[Property], attribute_key: str) -> str:
    if not properties:
        return "Entendí la pregunta, pero en este momento no tengo resultados visibles para responderla con precisión."

    values = [_format_attribute_value(item, attribute_key) for item in properties]
    available = [(index + 1, value) for index, value in enumerate(values) if value]
    if not available:
        return "Entendí la pregunta, pero a estas opciones no les tengo ese dato suficientemente limpio todavía."

    if len(available) == len(properties):
        unique_values = {value for _, value in available}
        if len(unique_values) == 1 and len(properties) > 1:
            shared_value = next(iter(unique_values))
            intro = "Las dos opciones" if len(properties) == 2 else "Las opciones visibles"
            return f"{intro} tienen {shared_value}. Si querés, te cuento más de la que te interese."

    sentences: list[str] = []
    total = len(properties)
    for index, value in available:
        sentences.append(f"{_label_for_index(index, total)} tiene {value}")

    if len(sentences) == 1:
        body = sentences[0]
    elif len(sentences) == 2:
        body = " y ".join(sentences)
    else:
        body = "; ".join(sentences[:-1]) + f"; y {sentences[-1]}"
    return f"{body}. Si querés, profundizamos en la que más te interese."


async def describe_result_set(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    del deps
    graph_state = RealtorGraphState.model_validate(state)
    analysis = TurnAnalysis.model_validate(graph_state.turn_analysis or {})
    attribute_key = analysis.detail_attribute_key or "precio"
    properties = _load_displayed_properties(graph_state)
    narrative = _build_result_set_detail_narrative(properties, attribute_key)
    output = {
        "type": "result_set_detail",
        "attribute_key": attribute_key,
        "count": len(properties),
        "narrative": narrative,
    }
    return {
        "turn_outputs": [*graph_state.turn_outputs, output],
        **complete_active_intent(graph_state, output),
    }
