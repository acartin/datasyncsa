"""Realtor cards rendering node."""

from __future__ import annotations

import re
from typing import Any

from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.graph._shared.nodes.helpers import complete_active_intent
from services.ai_runtime.graph.realtor.contracts import CardPayload, CardStat, Property
from services.ai_runtime.graph.realtor.state.model import RealtorGraphState
from services.ai_runtime.graph.realtor.turn_frame import merge_seen_properties

_LAND_TYPE_TOKENS = ("terreno", "lote", "lot", "land", "solar")


def _strip_html(value: str | None) -> str | None:
    if not value:
        return None
    text = re.sub(r"<[^>]+>", " ", value)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r"[^0-9.,]", "", str(value)).replace(",", ".")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _compact_number(value: Any) -> str | None:
    numeric = _normalize_number(value)
    if numeric is None:
        cleaned = _normalize_text(value)
        return cleaned or None
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.1f}".rstrip("0").rstrip(".")


def _area_value(value: Any) -> str | None:
    cleaned = re.sub(r"\b(m2|m²|sqm|sq\.?\s?m)\b", "", _normalize_text(value), flags=re.IGNORECASE)
    cleaned = cleaned.strip()
    if cleaned:
        return cleaned
    return _compact_number(value)


def _front_value(value: Any) -> str | None:
    cleaned = _normalize_text(value)
    if not cleaned:
        return None
    if re.search(r"[a-zA-Z]", cleaned):
        return cleaned
    compact = _compact_number(cleaned)
    if not compact:
        return None
    return f"{compact}m"


def _build_stat(icon: str, value: Any, label: str, *, formatter: Any | None = None) -> CardStat | None:
    formatted = formatter(value) if formatter else _normalize_text(value)
    if not formatted:
        return None
    return CardStat(icon=icon, value=formatted, label=label)


def _looks_like_land(item: Property) -> bool:
    hints = " ".join(
        filter(
            None,
            (
                item.title,
                item.features.property_type,
                item.features.land_use,
            ),
        )
    ).lower()
    if any(token in hints for token in _LAND_TYPE_TOKENS):
        return True
    return bool(item.features.lot_size_sqm) and item.features.bedrooms_clean <= 0 and item.features.bathrooms_clean <= 0


def _build_card_stats(item: Property) -> list[dict[str, str]]:
    stats: list[CardStat] = []
    is_land = _looks_like_land(item)

    if is_land:
        lot_area = _build_stat("area", item.features.lot_size_sqm or item.features.sqm_clean, "m² terreno", formatter=_area_value)
        frontage = _build_stat("front", item.features.front, "Frente", formatter=_front_value)
        land_use = _build_stat("use", item.features.land_use, "Uso suelo")
        for candidate in (lot_area, frontage, land_use):
            if candidate:
                stats.append(candidate)

    if not stats:
        bedrooms = item.features.bedrooms_clean if item.features.bedrooms_clean > 0 else None
        bathrooms = item.features.bathrooms_clean if item.features.bathrooms_clean > 0 else None
        built_area = item.features.sqm_clean or item.features.lot_size_sqm
        garage = item.features.garage_clean if item.features.garage_clean > 0 else None

        candidates = (
            _build_stat("bed", bedrooms, "Hab.", formatter=_compact_number),
            _build_stat("bath", bathrooms, "Baños", formatter=_compact_number),
            _build_stat(
                "area",
                built_area,
                "m² terreno" if item.features.lot_size_sqm and not item.features.sqm_clean else "m² constr.",
                formatter=_area_value,
            ),
            _build_stat("garage", garage, "Parqueos", formatter=_compact_number),
        )
        for candidate in candidates:
            if candidate:
                stats.append(candidate)
            if len(stats) >= 3:
                break

    return [item.model_dump(mode="json") for item in stats[:3]]


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
                lot_size_sqm=item.features.lot_size_sqm,
                front=item.features.front,
                land_use=item.features.land_use,
                property_type=item.features.property_type,
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
                stats=_build_card_stats(item),
            ).model_dump(mode="json")
        )
    return payload


async def render_cards(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    _ = deps
    graph_state = RealtorGraphState.model_validate(state)
    properties = [Property.model_validate(item) for item in graph_state.last_search_results]
    selected = properties[:3]
    mode = "gallery" if len(selected) > 1 else "single"
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
    if selected:
        updates["last_mentioned"] = selected[0].model_dump(mode="json")
    return updates
