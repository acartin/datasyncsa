"""Pre-synthesis frame builder node.

Builds the immutable ``TurnFrame`` and writes it to graph state so the
downstream ``synthesize`` node receives a fully pre-resolved context.
"""

from __future__ import annotations

import logging
from typing import Any

from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import BaseGraphState

logger = logging.getLogger(__name__)


async def prepare_synthesis(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    """Build the immutable TurnFrame and write it to state for the synthesizer.

    If frame construction fails the exception propagates cleanly — no silent
    fallbacks.
    """

    del deps  # No I/O needed — purely deterministic
    from services.ai_runtime.verticals import get_vertical_spec

    vertical_spec = get_vertical_spec(state.get("vertical"))
    graph_state: BaseGraphState = vertical_spec.state_model.model_validate(state)

    try:
        turn_frame = vertical_spec.turn_frame_builder(graph_state)
    except Exception:
        logger.error("prepare_synthesis failed to build TurnFrame", exc_info=True)
        raise

    return {"turn_frame": turn_frame.model_dump(mode="json")}
