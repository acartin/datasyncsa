"""Generic assign-agent node."""

from __future__ import annotations

from typing import Any

from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import GenericGraphState
from services.ai_runtime.graph._shared.nodes.helpers import complete_active_intent


async def assign_agent(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    graph_state = GenericGraphState.model_validate(state)
    zone = graph_state.tenant_config.business.operation_zones[0] if graph_state.tenant_config.business.operation_zones else None
    agent = await deps.agent_repository.assign_for_zone(client_id=graph_state.client_id, zone=zone)
    if not agent:
        return {}
    cita = graph_state.cita.model_copy(update={"agente_asignado": agent.id, "confirmada": True})
    escalacion = graph_state.escalacion.model_copy(update={"agente_asignado": agent.id})
    output = {"type": "agent_assignment", "agent_id": agent.id}
    return {
        "cita": cita.model_dump(mode="json"),
        "escalacion": escalacion.model_dump(mode="json"),
        "turn_outputs": [*graph_state.turn_outputs, output],
        **complete_active_intent(graph_state, output),
    }
