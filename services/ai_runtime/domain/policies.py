"""Vertical policy hooks for runtime behavior that is not universally shared."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from services.ai_runtime.domain.contracts import PendingDecision, TurnAnalysis
from services.ai_runtime.domain.state import BaseGraphState, LeadAdvisorState


@dataclass(frozen=True, slots=True)
class QuickActionResolution:
    """Normalized turn override produced by a vertical-owned quick action.

    The shared runtime treats this object as an already-interpreted turn:
    - ``analysis`` is the synthetic TurnAnalysis for the action
    - ``resolved_references`` contains any resolved entities the action points to
    - ``pending_decision`` optionally pauses the flow for a follow-up choice
    - ``lead_advisor`` / ``cita`` carry state patches owned by the vertical
    """

    analysis: TurnAnalysis
    resolved_references: list[dict[str, Any]] = field(default_factory=list)
    pending_decision: PendingDecision | None = None
    lead_advisor: dict[str, Any] | None = None
    cita: dict[str, Any] | None = None


class VerticalPolicy(Protocol):
    """Behavior hooks injected by each vertical into the shared runtime.

    Hooks must stay neutral from the perspective of ``graph/_shared``:
    - ``search context`` means whatever query/filter snapshot helps a vertical
      interpret a follow-up turn.
    - ``visible reference items`` are the entities the user can reasonably point
      at in the current turn, typically because they were just surfaced.
    - ``reference candidates`` are the broader current result set that can be
      reused when the user refers back to recent entities.
    - ``focused entity`` is the single entity currently in focus, if any.
    """

    def snapshot_search_context(
        self,
        graph_state: BaseGraphState,
    ) -> dict[str, Any]:
        ...

    def resolve_visible_reference_items(
        self,
        graph_state: BaseGraphState,
    ) -> list[dict[str, Any]]:
        ...

    def resolve_reference_candidates(
        self,
        graph_state: BaseGraphState,
    ) -> list[dict[str, Any]]:
        ...

    def snapshot_focused_entity(
        self,
        graph_state: BaseGraphState,
    ) -> dict[str, Any] | None:
        ...

    def handle_quick_action(
        self,
        graph_state: BaseGraphState,
        metadata: dict[str, Any],
    ) -> QuickActionResolution | None:
        ...

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

    def resolve_journey(
        self,
        graph_state: BaseGraphState,
    ) -> str | None:
        ...

    def progressive_field_plan(
        self,
        graph_state: BaseGraphState,
        lead_advisor_state: LeadAdvisorState,
    ) -> list[str]:
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

    def snapshot_search_context(self, graph_state):
        _ = graph_state
        return {}

    def resolve_visible_reference_items(self, graph_state):
        _ = graph_state
        return []

    def resolve_reference_candidates(self, graph_state):
        _ = graph_state
        return []

    def snapshot_focused_entity(self, graph_state):
        _ = graph_state
        return None

    def handle_quick_action(self, graph_state, metadata):
        _ = (graph_state, metadata)
        return None

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

    def resolve_journey(self, graph_state):
        _ = graph_state
        return None

    def progressive_field_plan(self, graph_state, lead_advisor_state):
        _ = graph_state
        completed = {
            str(item).strip().lower()
            for item in list(lead_advisor_state.completed_fields or [])
            if str(item).strip()
        }
        ordered: list[str] = []
        seen: set[str] = set()
        for field in list(lead_advisor_state.required_fields or lead_advisor_state.target_fields):
            normalized = str(field or "").strip().lower()
            if not normalized or normalized in completed or normalized in seen:
                continue
            ordered.append(normalized)
            seen.add(normalized)
        return ordered

    def extra_lead_sync(self, graph_state, lead_payload):
        return lead_payload

    def select_semantic_ctas(self, graph_state, *, channel, limit):
        _ = (graph_state, channel, limit)
        return []
