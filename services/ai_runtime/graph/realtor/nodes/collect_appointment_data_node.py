"""Realtor appointment collection node."""

from __future__ import annotations

from typing import Any

from services.ai_runtime.config.prompt_composer import compose
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import RealtorGraphState, has_valid_lead_contact
from services.ai_runtime.graph._shared.nodes.helpers import complete_active_intent


async def collect_appointment_data(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    graph_state = RealtorGraphState.model_validate(state)
    prompt = compose(
        "appointment_data_collector",
        graph_state.tenant_config,
        graph_state.vertical,
        {
            "messages": [message.model_dump(mode="json") for message in graph_state.messages[-6:]],
            "cita": graph_state.cita.model_dump(mode="json"),
            "resolved_references": graph_state.resolved_references,
            "last_mentioned": graph_state.last_mentioned.model_dump(mode="json") if graph_state.last_mentioned else None,
        },
    )
    extracted = await deps.llm.extract_appointment_fields(prompt)
    updates = {key: value for key, value in extracted.items() if value not in (None, "", [])}
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
    if cita.tipo and cita.fecha and cita.hora and not contact_ok:
        updates_payload["lead_advisor"] = graph_state.lead_advisor.model_copy(
            update={"should_ask": True, "field_to_ask": "contacto"}
        ).model_dump(mode="json")
    return updates_payload
