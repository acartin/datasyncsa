"""Realtor-specific runtime policy hooks."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from services.ai_runtime.domain.contracts import TurnAnalysis
from services.ai_runtime.domain.policies import VerticalPolicy
from services.ai_runtime.domain.state import BaseGraphState
from services.ai_runtime.graph.realtor.state.model import RealtorGraphState
from services.ai_runtime.graph.realtor.turn_policies import (
    REALTOR_INTERNAL_INTENTS,
    apply_realtor_turn_policies,
    build_realtor_fallback_intent_plan,
    derive_realtor_pending_decision,
    merge_realtor_filters,
)

_NEGATIVE_APPOINTMENT_PATTERNS = (
    re.compile(
        r"\bno\s+(?:quiero|deseo|necesito)\s+(?:agendar|agenda|coordinar|cita|visita|visitar)\b"
    ),
    re.compile(
        r"\b(?:por\s+ahora|todavia|aun)\s+no\s+(?:quiero\s+)?(?:agendar|coordinar|cita|visita|visitar)\b"
    ),
    re.compile(r"\bprefiero\s+no\s+(?:agendar|coordinar|cita|visita|visitar)\b"),
)


def _normalize_text(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    return "".join(char for char in raw if not unicodedata.combining(char))


def _latest_user_message(graph_state: BaseGraphState) -> str:
    for message in reversed(graph_state.messages):
        if str(getattr(message, "role", "")).strip().lower() != "user":
            continue
        content = str(getattr(message, "content", "")).strip()
        if content:
            return content
    return ""


def _has_explicit_negative_appointment_intent(message: str) -> bool:
    normalized = _normalize_text(message)
    if not normalized:
        return False
    return any(pattern.search(normalized) for pattern in _NEGATIVE_APPOINTMENT_PATTERNS)


def _coerce_realtor_state(graph_state: BaseGraphState) -> RealtorGraphState:
    if isinstance(graph_state, RealtorGraphState):
        return graph_state
    return RealtorGraphState.model_validate(graph_state.model_dump(mode="json"))


class RealtorPolicy(VerticalPolicy):
    async def merge_filters(
        self,
        graph_state: BaseGraphState,
        analysis: TurnAnalysis,
        deps: Any,
    ) -> dict[str, Any] | None:
        return await merge_realtor_filters(_coerce_realtor_state(graph_state), analysis, deps)

    def apply_turn_policies(
        self,
        graph_state: BaseGraphState,
        analysis: TurnAnalysis,
    ) -> tuple[TurnAnalysis, list[str]]:
        return apply_realtor_turn_policies(_coerce_realtor_state(graph_state), analysis)

    def derive_pending_decision(
        self,
        graph_state: BaseGraphState,
        analysis: TurnAnalysis,
    ) -> Any | None:
        return derive_realtor_pending_decision(_coerce_realtor_state(graph_state), analysis)

    def build_fallback_intent_plan(
        self,
        graph_state: BaseGraphState,
        analysis: TurnAnalysis,
    ) -> list[Any]:
        return build_realtor_fallback_intent_plan(_coerce_realtor_state(graph_state), analysis)

    def internal_intents(self) -> set[str]:
        return set(REALTOR_INTERNAL_INTENTS)

    def field_has_value(self, extracted: Any, field_key: str) -> bool | None:
        return None

    def extra_lead_sync(
        self,
        graph_state: BaseGraphState,
        lead_payload: dict[str, Any],
    ) -> dict[str, Any]:
        payload = dict(lead_payload)
        realtor_state = _coerce_realtor_state(graph_state)
        if payload.get("presupuesto") is None:
            candidate = realtor_state.search_filters.precio_max or realtor_state.search_filters.precio_min
            if candidate is not None:
                payload["presupuesto"] = float(candidate)

        # Guardrail realtor: explicit "no quiero agendar" style turns must
        # persist as appointment_intent=negative even if LLM extraction omits it.
        if _has_explicit_negative_appointment_intent(_latest_user_message(realtor_state)):
            payload["appointment_intent"] = "negative"
            payload["tipo_cita"] = None
        return payload

    def select_semantic_ctas(
        self,
        graph_state: BaseGraphState,
        *,
        channel: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        _ = channel
        from services.ai_runtime.graph.realtor.cta_selector import select_realtor_card_ctas

        return select_realtor_card_ctas(_coerce_realtor_state(graph_state), limit=limit)
