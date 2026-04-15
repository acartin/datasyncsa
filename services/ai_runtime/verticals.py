"""Explicit runtime vertical registry and response adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from services.ai_runtime.domain.contracts import FlowName, Vertical
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import BaseGraphState, GenericGraphState
from services.ai_runtime.graph.generic.graph import build_generic_graph
from services.ai_runtime.graph.realtor.graph import build_realtor_graph
from services.ai_runtime.graph.realtor.state.model import RealtorGraphState

GraphBuilder = Callable[[GraphDependencies], Any]
ComponentBuilder = Callable[[BaseGraphState], list[dict[str, object]]]


def _build_empty_components(_: BaseGraphState) -> list[dict[str, object]]:
    return []


def _build_realtor_components(final_state: BaseGraphState) -> list[dict[str, object]]:
    if not isinstance(final_state, RealtorGraphState):
        return []

    components: list[dict[str, object]] = []
    ui_payload = final_state.ui_payload or {}
    for card in ui_payload.get("property_cards", []):
        features = {
            "bedrooms_clean": card.get("bedrooms_clean"),
            "bathrooms_clean": card.get("bathrooms_clean"),
            "sqm_clean": card.get("sqm_clean"),
            "garage_clean": card.get("garage_clean"),
            "amenities": card.get("amenities") or [],
            "address": card.get("address"),
            "province": card.get("province"),
        }
        components.append(
            {
                "type": "property-card",
                "id": card.get("id"),
                "title": card.get("title"),
                "price": card.get("price"),
                "currency": card.get("currency"),
                "price_note": card.get("price_note"),
                "location": card.get("location") or card.get("address") or card.get("province"),
                "image_url": card.get("primary_image_url"),
                "image_urls": card.get("image_urls") or [],
                "photo_count": card.get("photo_count"),
                "public_url": card.get("public_url"),
                "tags": card.get("amenities") or [],
                "amenities": card.get("amenities") or [],
                "description": card.get("description"),
                "badge_main": card.get("badge_main"),
                "badge_sub": card.get("badge_sub"),
                "bedrooms_clean": card.get("bedrooms_clean"),
                "bathrooms_clean": card.get("bathrooms_clean"),
                "sqm_clean": card.get("sqm_clean"),
                "garage_clean": card.get("garage_clean"),
                "features": {
                    key: value
                    for key, value in features.items()
                    if value not in (None, "", [])
                },
                "city": card.get("province"),
                "neighborhood": card.get("province"),
            }
        )
    return components


@dataclass(frozen=True, slots=True)
class VerticalSpec:
    slug: Vertical
    default_flow: FlowName
    state_model: type[BaseGraphState]
    graph_builder: GraphBuilder
    component_builder: ComponentBuilder = _build_empty_components
    scoring_criteria: tuple[str, ...] = ()
    required_fields: tuple[str, ...] = ()


_VERTICAL_SPECS: dict[str, VerticalSpec] = {
    "realtor": VerticalSpec(
        slug="realtor",
        default_flow="realtor_flow",
        state_model=RealtorGraphState,
        graph_builder=build_realtor_graph,
        component_builder=_build_realtor_components,
        scoring_criteria=("apertura", "intencion", "urgencia", "match", "solvencia"),
        required_fields=(
            "nombre",
            "contacto",
            "presupuesto",
            "aprobacion",
            "fecha_preferida",
            "appointment_intent",
        ),
    ),
    "healthcare": VerticalSpec(
        slug="healthcare",
        default_flow="basic_flow",
        state_model=GenericGraphState,
        graph_builder=build_generic_graph,
        scoring_criteria=("apertura", "intencion", "emergencia", "match", "solvencia"),
        required_fields=("nombre", "contacto", "appointment_intent"),
    ),
    "legal": VerticalSpec(
        slug="legal",
        default_flow="basic_flow",
        state_model=GenericGraphState,
        graph_builder=build_generic_graph,
        scoring_criteria=("apertura", "intencion", "urgencia", "match", "solvencia"),
        required_fields=("nombre", "contacto", "appointment_intent"),
    ),
    "insurance": VerticalSpec(
        slug="insurance",
        default_flow="basic_flow",
        state_model=GenericGraphState,
        graph_builder=build_generic_graph,
        scoring_criteria=("apertura", "intencion", "urgencia", "match", "solvencia"),
        required_fields=("nombre", "contacto", "presupuesto", "appointment_intent"),
    ),
}


def get_vertical_spec(vertical: Vertical | str) -> VerticalSpec:
    normalized = str(vertical or "").strip().lower()
    spec = _VERTICAL_SPECS.get(normalized)
    if spec is None:
        raise ValueError(f"Unsupported runtime vertical={vertical!r}")
    return spec


def get_supported_verticals() -> tuple[str, ...]:
    return tuple(_VERTICAL_SPECS)
