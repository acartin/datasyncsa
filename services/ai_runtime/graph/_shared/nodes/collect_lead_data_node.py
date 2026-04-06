"""Lead capture node."""

from __future__ import annotations

from typing import Any

from services.ai_runtime.config.prompt_composer import compose
from services.ai_runtime.domain.contracts import AgentRecord
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import BaseGraphState
from services.ai_runtime.graph._shared.nodes.helpers import complete_active_intent
from services.ai_runtime.graph._shared.prompt_context import summarize_messages_for_prompt


async def collect_lead_data(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    """Collect one lead field conversationally and prepare escalation data if needed."""

    graph_state = BaseGraphState.model_validate(state)
    prompt = compose(
        "lead_data_collector",
        graph_state.tenant_config,
        graph_state.vertical,
        {
            "messages": summarize_messages_for_prompt(graph_state.messages, limit=6),
            "lead_extracted": graph_state.lead_advisor.lead_extracted.model_dump(mode="json"),
            "active_intent": graph_state.active_intent.model_dump(mode="json") if graph_state.active_intent else None,
        },
    )
    extracted = await deps.llm.extract_lead_fields(prompt)
    merged = graph_state.lead_advisor.lead_extracted.model_copy(
        update={
            **graph_state.lead_advisor.lead_extracted.model_dump(mode="json"),
            **{key: value for key, value in extracted.items() if value not in (None, "", [])},
        }
    )
    assigned_agent: AgentRecord | None = None
    zone = graph_state.tenant_config.business.operation_zones[0] if graph_state.tenant_config.business.operation_zones else None
    if zone:
        assigned_agent = await deps.agent_repository.assign_for_zone(client_id=graph_state.client_id, zone=zone)
    escalation_payload = graph_state.escalacion.model_copy(
        update={
            "solicitada": graph_state.escalacion.solicitada or (graph_state.active_intent and graph_state.active_intent.type == "escalar"),
            "agente_asignado": assigned_agent.id if assigned_agent else graph_state.escalacion.agente_asignado,
            "datos_capturados": merged.model_dump(mode="json"),
        }
    )
    output = {"type": "lead_capture", "fields": merged.model_dump(mode="json")}
    return {
        "lead_advisor": graph_state.lead_advisor.model_copy(update={"lead_extracted": merged}).model_dump(mode="json"),
        "escalacion": escalation_payload.model_dump(mode="json"),
        "turn_outputs": [*graph_state.turn_outputs, output],
        **complete_active_intent(graph_state, output),
    }
