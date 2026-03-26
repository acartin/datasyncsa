"""Realtor property comparison node."""

from __future__ import annotations

from typing import Any

from services.ai_runtime.config.prompt_composer import compose
from services.ai_runtime.domain.contracts import Property
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import RealtorGraphState
from services.ai_runtime.graph._shared.nodes.helpers import complete_active_intent
from services.ai_runtime.graph.realtor.nodes.comparison_helpers import score_property


def _build_selection_narrative(property_item: Property) -> str:
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


async def compare_properties(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    graph_state = RealtorGraphState.model_validate(state)
    property_ids = graph_state.active_comparison or [
        reference["property_id_internal"]
        for reference in graph_state.resolved_references
        if reference.get("kind") == "property"
    ]
    properties = await deps.property_repository.load_properties_by_ids(
        client_id=graph_state.client_id,
        property_ids=property_ids,
    )
    if len(properties) == 1:
        selected = properties[0]
        output = {
            "type": "property_selection",
            "property": selected.model_dump(mode="json"),
            "narrative": _build_selection_narrative(selected),
        }
        return {
            "turn_outputs": [*graph_state.turn_outputs, output],
            "last_mentioned": selected.model_dump(mode="json"),
            **complete_active_intent(graph_state, output),
        }

    scores = [score_property(item) for item in properties]
    prompt = compose(
        "comparison_synthesizer",
        graph_state.tenant_config,
        graph_state.vertical,
        {
            "focus_scope": graph_state.focus_scope,
            "properties": [item.model_dump(mode="json") for item in properties],
            "scores": [item.model_dump(mode="json") for item in scores],
        },
    )
    narrative = await deps.llm.synthesize_response(prompt)
    output = {
        "type": "comparison",
        "scores": [item.model_dump(mode="json") for item in scores],
        "narrative": narrative,
    }
    return {
        "turn_outputs": [*graph_state.turn_outputs, output],
        **complete_active_intent(graph_state, output),
    }
