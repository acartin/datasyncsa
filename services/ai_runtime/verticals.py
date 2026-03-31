"""Explicit runtime vertical registry and response adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from services.ai_runtime.domain.contracts import FlowName, Vertical
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import BaseGraphState, GenericGraphState, RealtorGraphState
from services.ai_runtime.graph.generic.graph import build_generic_graph
from services.ai_runtime.graph.realtor.graph import build_realtor_graph

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
        components.append(
            {
                "type": "property-card",
                "listing_id": card.get("property_id_internal"),
                "title": card.get("title"),
                "price": card.get("price"),
                "image_url": card.get("primary_image_url"),
                "public_url": card.get("public_url"),
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


_VERTICAL_SPECS: dict[str, VerticalSpec] = {
    "realtor": VerticalSpec(
        slug="realtor",
        default_flow="realtor_flow",
        state_model=RealtorGraphState,
        graph_builder=build_realtor_graph,
        component_builder=_build_realtor_components,
    ),
    "healthcare": VerticalSpec(
        slug="healthcare",
        default_flow="basic_flow",
        state_model=GenericGraphState,
        graph_builder=build_generic_graph,
    ),
    "legal": VerticalSpec(
        slug="legal",
        default_flow="basic_flow",
        state_model=GenericGraphState,
        graph_builder=build_generic_graph,
    ),
    "insurance": VerticalSpec(
        slug="insurance",
        default_flow="basic_flow",
        state_model=GenericGraphState,
        graph_builder=build_generic_graph,
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
