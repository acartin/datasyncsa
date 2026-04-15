"""Realtor-specific turn frame extensions.

Contains the realtor ``PropertySummary`` model, ``seen_properties`` helpers and
``RealtorTurnFrame``.  Universal turn-frame building blocks (``BaseTurnFrame``,
``LeadSnapshot``, ``LeadCaptureContext``, ``SearchContext``, ``FramingKind``)
live in ``services/ai_runtime/domain/turn_frame``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from services.ai_runtime.domain.turn_frame import BaseTurnFrame, SearchContext
from services.ai_runtime.graph.realtor.contracts import Property


# ---------------------------------------------------------------------------
# PropertySummary — compact property snapshot for the synthesizer
# ---------------------------------------------------------------------------

SEEN_PROPERTIES_CAP = 50

_POSITION_LABELS: dict[int, str] = {
    1: "La primera",
    2: "La segunda",
    3: "La tercera",
    4: "La cuarta",
}


class PropertySummary(BaseModel):
    """Lightweight property representation stored in ``seen_properties`` and
    serialized inside ``RealtorTurnFrame.visible_properties``."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    price: float
    currency: str
    province: str | None = None
    address: str | None = None
    bedrooms_clean: int = 0
    bathrooms_clean: float = 0
    garage_clean: int = 0
    sqm_clean: int | None = None
    has_image: bool = False
    public_url: str | None = None
    position_label: str | None = None
    added_turn: int = 0


def property_to_summary(
    prop: Property,
    *,
    position: int | None = None,
    total: int | None = None,
    added_turn: int = 0,
) -> PropertySummary:
    """Convert a full ``Property`` into a compact ``PropertySummary``."""

    label: str | None = None
    if position is not None and total is not None and total > 1:
        label = _POSITION_LABELS.get(position, f"La opcion {position}")

    return PropertySummary(
        id=prop.id,
        title=prop.title,
        price=prop.price,
        currency=prop.currency,
        province=prop.location.province,
        address=prop.address,
        bedrooms_clean=prop.features.bedrooms_clean,
        bathrooms_clean=prop.features.bathrooms_clean,
        garage_clean=prop.features.garage_clean,
        sqm_clean=prop.features.sqm_clean,
        has_image=bool(prop.media.primary_image_url or prop.media.image_urls),
        public_url=prop.meta.public_url,
        position_label=label,
        added_turn=added_turn,
    )


def merge_seen_properties(
    current: dict[str, Any],
    new_properties: list[Property],
    *,
    current_turn: int = 0,
) -> dict[str, Any]:
    """Merge *new_properties* into *current* applying the FIFO cap.

    Returns a plain ``dict`` (JSON-safe) suitable for LangGraph state updates.
    """

    merged: dict[str, PropertySummary] = {}
    for key, raw in current.items():
        if isinstance(raw, PropertySummary):
            merged[key] = raw
        elif isinstance(raw, dict):
            merged[key] = PropertySummary.model_validate(raw)

    for prop in new_properties:
        if prop.id not in merged:
            merged[prop.id] = property_to_summary(prop, added_turn=current_turn)

    if len(merged) > SEEN_PROPERTIES_CAP:
        sorted_keys = sorted(merged, key=lambda k: merged[k].added_turn)
        excess = len(merged) - SEEN_PROPERTIES_CAP
        for key in sorted_keys[:excess]:
            del merged[key]

    return {key: value.model_dump(mode="json") for key, value in merged.items()}


class RealtorTurnFrame(BaseTurnFrame):
    """Extended frame for the realtor vertical."""

    visible_properties: list[PropertySummary] = Field(default_factory=list)
    focused_property: PropertySummary | None = None

    search: SearchContext | None = None
    has_new_cards: bool = False
    cards_mode: str | None = None

    financial_result: dict[str, Any] | None = None

    comparison_scores: list[dict[str, Any]] = Field(default_factory=list)
