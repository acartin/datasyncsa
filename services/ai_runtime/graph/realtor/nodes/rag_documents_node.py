"""Realtor documents RAG node."""

from __future__ import annotations

from typing import Any

from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.graph._shared.nodes.helpers import complete_active_intent
from services.ai_runtime.graph.realtor.state.model import RealtorGraphState


async def rag_documents(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    graph_state = RealtorGraphState.model_validate(state)
    chunks = await deps.documents_rag_repository.search(
        client_id=graph_state.client_id,
        query_embedding=[0.0],
        query_text=graph_state.messages[-1].content,
        limit=5,
    )
    output = {"type": "rag_docs", "chunks": chunks}
    return {
        "turn_outputs": [*graph_state.turn_outputs, output],
        **complete_active_intent(graph_state, output),
    }
