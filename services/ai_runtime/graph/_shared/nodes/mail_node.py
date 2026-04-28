"""Shared mail delivery node."""

from __future__ import annotations

from typing import Any

from services.ai_runtime.domain.contracts import TenantConfig
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import BaseGraphState
from services.ai_runtime.graph._shared.nodes.helpers import complete_active_intent
from services.ai_runtime.graph._shared.tools.mensajear import mensajear
from services.ai_runtime.runtime.turn_trace import build_traced_node


def build_mail_node(deps: GraphDependencies):
    async def _mail_impl(state: dict[str, Any], runtime_deps: GraphDependencies) -> dict[str, Any]:
        tenant_config = TenantConfig.model_validate(state["tenant_config"])
        graph_state = BaseGraphState.model_validate(state)
        result = await mensajear(
            dependencies=runtime_deps,
            client_id=state["client_id"],
            tipo="appointment_confirmation",
            destinatarios=[],
            datos_cita=state.get("cita", {}),
            tenant_config=tenant_config,
        )
        output = {"type": "mensajear", **result.model_dump(mode="json")}
        return {
            "turn_outputs": [*state.get("turn_outputs", []), output],
            **complete_active_intent(graph_state, output),
        }

    return build_traced_node("mensajear", _mail_impl, deps)
