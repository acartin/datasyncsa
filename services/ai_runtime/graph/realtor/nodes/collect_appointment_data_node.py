"""Realtor appointment collection node."""

from __future__ import annotations

from typing import Any

from services.ai_runtime.config.prompt_composer import compose
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import has_valid_lead_contact
from services.ai_runtime.graph._shared.nodes.helpers import complete_active_intent
from services.ai_runtime.graph._shared.prompt_context import (
    summarize_messages_for_prompt,
    summarize_property_for_prompt,
)
from services.ai_runtime.graph.realtor.state.model import RealtorGraphState


def _grounded_property_ids(graph_state: RealtorGraphState) -> set[str]:
    grounded: set[str] = set()
    for reference in graph_state.resolved_references:
        if str(reference.get("kind") or "").strip().lower() != "property":
            continue
        property_id = str(reference.get("property_id") or "").strip()
        if property_id:
            grounded.add(property_id)
    focused_id = str(getattr(graph_state.last_mentioned, "id", "") or "").strip()
    if focused_id:
        grounded.add(focused_id)
    return grounded


async def collect_appointment_data(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    graph_state = RealtorGraphState.model_validate(state)
    prompt = compose(
        "appointment_data_collector",
        graph_state.tenant_config,
        graph_state.vertical,
        {
            "messages": summarize_messages_for_prompt(graph_state.messages, limit=6),
            "cita": graph_state.cita.model_dump(mode="json"),
            "resolved_references": graph_state.resolved_references,
            "last_mentioned": summarize_property_for_prompt(
                graph_state.last_mentioned,
                include_description_excerpt=True,
            ),
        },
    )
    extracted = await deps.llm.extract_appointment_fields(prompt)
    updates = {key: value for key, value in extracted.items() if value not in (None, "", [])}
    grounded_property_ids = _grounded_property_ids(graph_state)
    extracted_property_id = str(updates.get("propiedad_id") or "").strip()
    if extracted_property_id and grounded_property_ids and extracted_property_id not in grounded_property_ids:
        updates.pop("propiedad_id", None)
        extracted_property_id = ""
    if "propiedad_id" not in updates and graph_state.last_mentioned:
        updates["propiedad_id"] = graph_state.last_mentioned.id
    cita = graph_state.cita.model_copy(update={**graph_state.cita.model_dump(mode="json"), **updates})
    contact_ok = has_valid_lead_contact(graph_state.lead_advisor.lead_extracted)
    cita.datos_completos = bool(cita.tipo and cita.propiedad_id and cita.fecha and cita.hora and contact_ok)
    output = {"type": "appointment", "cita": cita.model_dump(mode="json")}
    completion = {} if cita.datos_completos else complete_active_intent(graph_state, output)
    updates_payload: dict[str, Any] = {
        "cita": cita.model_dump(mode="json"),
        "turn_outputs": [*graph_state.turn_outputs, output],
        **completion,
    }
    if cita.tipo and cita.fecha and cita.hora and str(cita.propiedad_id or "").strip() in grounded_property_ids and not contact_ok:
        updates_payload["lead_advisor"] = graph_state.lead_advisor.model_copy(
            update={"should_ask": True, "field_to_ask": "contacto"}
        ).model_dump(mode="json")
    return updates_payload
