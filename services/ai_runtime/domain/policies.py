"""Vertical policy hooks for runtime behavior that is not universally shared."""

from __future__ import annotations

from typing import Any, Protocol

from services.ai_runtime.domain.contracts import TurnAnalysis
from services.ai_runtime.domain.state import BaseGraphState


class VerticalPolicy(Protocol):
    """Behavior hooks injected by each vertical into the shared runtime."""

    async def merge_filters(
        self,
        graph_state: BaseGraphState,
        analysis: TurnAnalysis,
        deps: Any,
    ) -> dict[str, Any] | None:
        ...

    def apply_turn_policies(
        self,
        graph_state: BaseGraphState,
        analysis: TurnAnalysis,
    ) -> tuple[TurnAnalysis, list[str]]:
        ...

    def derive_pending_decision(
        self,
        graph_state: BaseGraphState,
        analysis: TurnAnalysis,
    ) -> Any | None:
        ...

    def build_fallback_intent_plan(
        self,
        graph_state: BaseGraphState,
        analysis: TurnAnalysis,
    ) -> list[Any]:
        ...

    def internal_intents(self) -> set[str]:
        ...

    def field_has_value(self, extracted: Any, field_key: str) -> bool | None:
        ...

    def extra_lead_sync(
        self,
        graph_state: BaseGraphState,
        lead_payload: dict[str, Any],
    ) -> dict[str, Any]:
        ...

    def select_semantic_ctas(
        self,
        graph_state: BaseGraphState,
        *,
        channel: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        ...


class NullVerticalPolicy:
    """No-op policy for verticals without extra runtime behavior."""

    async def merge_filters(self, graph_state, analysis, deps):
        return None

    def apply_turn_policies(self, graph_state, analysis):
        return analysis, []

    def derive_pending_decision(self, graph_state, analysis):
        return None

    def build_fallback_intent_plan(self, graph_state, analysis):
        return []

    def internal_intents(self):
        return set()

    def field_has_value(self, extracted, field_key):
        return None

    def extra_lead_sync(self, graph_state, lead_payload):
        return lead_payload

    def select_semantic_ctas(self, graph_state, *, channel, limit):
        _ = (graph_state, channel, limit)
        return []
