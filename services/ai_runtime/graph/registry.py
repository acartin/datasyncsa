"""Graph registry for flow and vertical selection."""

from __future__ import annotations

from services.ai_runtime.domain.contracts import FlowName, Vertical
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.verticals import get_vertical_spec


class GraphRegistry:
    """Select the correct LangGraph builder for the resolved tenant vertical."""

    def get_graph(self, vertical: Vertical, flow: FlowName, deps: GraphDependencies):
        spec = get_vertical_spec(vertical)
        if flow != spec.default_flow:
            raise ValueError(
                f"{flow} no puede usarse con vertical {vertical}; flow esperado={spec.default_flow}"
            )
        return spec.graph_builder(deps)
