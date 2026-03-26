"""Focus a single resolved property without forcing comparison."""

from __future__ import annotations

from typing import Any

from services.ai_runtime.domain.contracts import Property
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import RealtorGraphState
from services.ai_runtime.graph._shared.nodes.helpers import complete_active_intent


def _build_focus_narrative(property_item: Property) -> str:
    details: list[str] = []
    if property_item.features.bedrooms_clean > 0:
        details.append(f"{property_item.features.bedrooms_clean} habitaciones")
    if property_item.features.bathrooms_clean > 0:
        details.append(f"{property_item.features.bathrooms_clean:g} baños")
    if property_item.features.sqm_clean:
        details.append(f"{property_item.features.sqm_clean} m²")

    summary = ", ".join(details[:3])
    if summary:
        return (
            f"Perfecto, te referís a {property_item.title}. "
            f"Esta opción tiene {summary}. "
            "Si querés, te cuento más detalles, te ayudo a calcular una cuota o la comparamos con la otra."
        )
    return (
        f"Perfecto, te referís a {property_item.title}. "
        "Si querés, te cuento más detalles, te ayudo a calcular una cuota o la comparamos con la otra."
    )


async def focus_property(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    graph_state = RealtorGraphState.model_validate(state)
    property_ids = [
        reference["property_id_internal"]
        for reference in graph_state.resolved_references
        if reference.get("kind") == "property"
    ]
    properties = await deps.property_repository.load_properties_by_ids(
        client_id=graph_state.client_id,
        property_ids=property_ids,
    )
    if not properties:
        output = {
            "type": "property_focus",
            "narrative": "Entendí cuál opción señalaste, pero no pude recuperar sus datos en este momento.",
        }
        return {
            "turn_outputs": [*graph_state.turn_outputs, output],
            **complete_active_intent(graph_state, output),
        }

    selected = properties[0]
    output = {
        "type": "property_focus",
        "property": selected.model_dump(mode="json"),
        "narrative": _build_focus_narrative(selected),
    }
    return {
        "turn_outputs": [*graph_state.turn_outputs, output],
        "last_mentioned": selected.model_dump(mode="json"),
        **complete_active_intent(graph_state, output),
    }
