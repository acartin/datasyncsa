"""Queue checkpoint node."""

from __future__ import annotations

from typing import Any

from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import BaseGraphState


async def check_queue(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    """No-op node used to centralize queue loop routing."""

    _ = deps
    BaseGraphState.model_validate(state)
    return {}
