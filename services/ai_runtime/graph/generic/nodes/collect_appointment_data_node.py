"""Generic appointment collection node."""

from __future__ import annotations

from typing import Any

from services.ai_runtime.config.prompt_composer import compose
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import GenericGraphState, has_valid_lead_contact
from services.ai_runtime.graph._shared.nodes.helpers import complete_active_intent


async def collect_appointment_data(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    graph_state = GenericGraphState.model_validate(state)
    prompt = compose(
        "appointment_data_collector",
        graph_state.tenant_config,
        graph_state.vertical,
        {
            "messages": [message.model_dump(mode="json") for message in graph_state.messages[-6:]],
            "cita": graph_state.cita.model_dump(mode="json"),
        },
    )
    extracted = await deps.llm.extract_appointment_fields(prompt)
    cita = graph_state.cita.model_copy(
        update={
            **graph_state.cita.model_dump(mode="json"),
            **{key: value for key, value in extracted.items() if value not in (None, "", [])},
        }
    )
    contact_ok = has_valid_lead_contact(graph_state.lead_advisor.lead_extracted)
    cita.datos_completos = bool(cita.tipo and cita.fecha and cita.hora and contact_ok)
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
