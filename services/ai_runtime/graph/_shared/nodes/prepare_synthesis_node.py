"""Pre-synthesis frame builder node.

Builds the immutable ``TurnFrame`` and writes it to graph state so the
downstream ``synthesize`` node receives a fully pre-resolved context.
"""

from __future__ import annotations

import logging
from typing import Any

from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import BaseGraphState
from services.ai_runtime.graph.realtor.state.model import RealtorGraphState
from services.ai_runtime.graph._shared.turn_frame_builder import build_turn_frame

logger = logging.getLogger(__name__)


async def prepare_synthesis(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    """Build the immutable TurnFrame and write it to state for the synthesizer.

    If frame construction fails the exception propagates cleanly — no silent
    fallbacks.
    """

    del deps  # No I/O needed — purely deterministic
    graph_state: BaseGraphState
    if state.get("vertical") == "realtor":
        graph_state = RealtorGraphState.model_validate(state)
    else:
        graph_state = BaseGraphState.model_validate(state)

    try:
        turn_frame = build_turn_frame(graph_state)
    except Exception:
        logger.error("prepare_synthesis failed to build TurnFrame", exc_info=True)
        raise

    return {"turn_frame": turn_frame.model_dump(mode="json")}
