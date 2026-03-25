"""Graph registry for bridge and vertical selection."""

from __future__ import annotations

from services.ai_runtime.domain.contracts import BridgeName, Vertical
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.graph.generic.graph import build_generic_graph
from services.ai_runtime.graph.realtor.graph import build_realtor_graph


class GraphRegistry:
    """Select the correct LangGraph builder for the resolved tenant vertical."""

    def get_graph(self, vertical: Vertical, bridge: BridgeName, deps: GraphDependencies):
        if bridge == "property-bridge" and vertical != "realtor":
            raise ValueError("property-bridge solo puede usarse con vertical realtor")
        if bridge == "generic-bridge" and vertical == "realtor":
            raise ValueError("generic-bridge no puede usarse con vertical realtor")
        if vertical == "realtor":
            return build_realtor_graph(deps)
        return build_generic_graph(deps)
