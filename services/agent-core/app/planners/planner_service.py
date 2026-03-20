from __future__ import annotations

import re
from typing import Any, Dict

from pydantic import ValidationError

from app.core.config import settings
from app.core.llm_client import llm_service
from app.core.llm_contract_normalizer import normalize_router_decision
from app.core.prompt_service import prompt_service
from app.models.contracts import GoalType, ResponseMode, RouterDecision

_NAME_DECLARATION_RE = re.compile(
    r"\bme\s+llamo\s+([A-Za-zÁÉÍÓÚÑáéíóúñ][A-Za-zÁÉÍÓÚÑáéíóúñ'`\-]*)\b",
    re.IGNORECASE,
)
_NAME_RECALL_RE = re.compile(
    r"\brecuerd(?:as|a)\s+c[oó]mo\s+me\s+llamo\b",
    re.IGNORECASE,
)
_ROOMS_QUESTION_RE = re.compile(
    r"\bde\s+cu[aá]ntas?\s+habitaciones\s+son\b",
    re.IGNORECASE,
)
_PRICE_QUERY_RE = re.compile(
    r"\b(cu[aá]l|cual|que)\s+es\s+el\s+precio\b",
    re.IGNORECASE,
)
_REFERENCE_LAST_RE = re.compile(r"\b(la\s+[uú]ltima|ultima|última)\b", re.IGNORECASE)
_REFERENCE_FIRST_RE = re.compile(r"\b(la\s+primera|primera)\b", re.IGNORECASE)
_REFERENCE_SECOND_RE = re.compile(r"\b(la\s+segunda|segunda)\b", re.IGNORECASE)
_REFERENCE_THIRD_RE = re.compile(r"\b(la\s+tercera|tercera)\b", re.IGNORECASE)
_REFERENCE_PRONOUN_RE = re.compile(r"\b(esa|esta)\b", re.IGNORECASE)


def _coerce_card_list(context_snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    last_answer = context_snapshot.get("last_answer_envelope")
    if not isinstance(last_answer, dict):
        cards = []
    else:
        cards = last_answer.get("cards")
    if not isinstance(cards, list):
        cards = []
    if not cards:
        state = context_snapshot.get("conversation_state")
        if isinstance(state, dict):
            presentation_state = state.get("presentation_state")
            if isinstance(presentation_state, dict):
                fallback_cards = presentation_state.get("last_property_cards")
                if isinstance(fallback_cards, list):
                    cards = fallback_cards
    output: list[dict[str, Any]] = []
    for card in cards:
        if isinstance(card, dict) and card.get("card_type") == "property_card":
            output.append(card)
    return output


def _resolve_reference_index(query_text: str, cards: list[dict[str, Any]]) -> int | None:
    if not cards:
        return None
    if _REFERENCE_LAST_RE.search(query_text):
        return len(cards) - 1
    if _REFERENCE_FIRST_RE.search(query_text):
        return 0
    if _REFERENCE_SECOND_RE.search(query_text):
        return 1 if len(cards) >= 2 else None
    if _REFERENCE_THIRD_RE.search(query_text):
        return 2 if len(cards) >= 3 else None
    if _REFERENCE_PRONOUN_RE.search(query_text) and len(cards) >= 1:
        return len(cards) - 1
    return None


def _extract_known_name(context_snapshot: dict[str, Any]) -> str | None:
    state = context_snapshot.get("conversation_state")
    if isinstance(state, dict):
        profile_state = state.get("profile_state")
        if isinstance(profile_state, dict):
            value = str(profile_state.get("name") or "").strip()
            if value:
                return value

    history = context_snapshot.get("recent_history")
    if isinstance(history, list):
        for item in reversed(history):
            if not isinstance(item, dict):
                continue
            if str(item.get("role") or "").strip().lower() != "user":
                continue
            content = str(item.get("content") or "").strip()
            match = _NAME_DECLARATION_RE.search(content)
            if not match:
                continue
            value = str(match.group(1) or "").strip()
            if value:
                return value
    return None


def _force_answer(decision: RouterDecision, *, confidence_floor: float = 0.91) -> RouterDecision:
    return decision.model_copy(
        update={
            "goal": GoalType.answer,
            "tool_calls": [],
            "missing_slots": [],
            "clarify_message": None,
            "response_mode": ResponseMode.text_only,
            "confidence": max(float(decision.confidence), confidence_floor),
        }
    )


def _force_clarify(decision: RouterDecision, *, message: str, confidence_floor: float = 0.91) -> RouterDecision:
    return decision.model_copy(
        update={
            "goal": GoalType.clarify,
            "tool_calls": [],
            "missing_slots": [],
            "clarify_message": message,
            "response_mode": ResponseMode.text_only,
            "confidence": max(float(decision.confidence), confidence_floor),
        }
    )


def _apply_memory_reference_overrides(
    *,
    decision: RouterDecision,
    query_text: str,
    context_snapshot: dict[str, Any],
) -> RouterDecision:
    query = str(query_text or "").strip()
    if not query:
        return decision

    cards = _coerce_card_list(context_snapshot)
    known_name = _extract_known_name(context_snapshot)
    name_decl = _NAME_DECLARATION_RE.search(query)
    if name_decl:
        return _force_answer(decision)

    if _NAME_RECALL_RE.search(query) and known_name:
        return _force_answer(decision)

    has_reference = (
        _REFERENCE_LAST_RE.search(query)
        or _REFERENCE_FIRST_RE.search(query)
        or _REFERENCE_SECOND_RE.search(query)
        or _REFERENCE_THIRD_RE.search(query)
        or _REFERENCE_PRONOUN_RE.search(query)
    )
    if _ROOMS_QUESTION_RE.search(query) and not has_reference and len(cards) > 1:
        return _force_clarify(
            decision,
            message="¿Te refieres a la primera, segunda o última casa que te mostré?",
        )

    if _PRICE_QUERY_RE.search(query):
        reference_index = _resolve_reference_index(query, cards)
        if reference_index is not None and 0 <= reference_index < len(cards):
            price_display = str(cards[reference_index].get("price_display") or "").strip()
            if price_display:
                return _force_answer(decision)

    return decision


def _build_router_decision_schema() -> dict[str, Any]:
    try:
        schema = RouterDecision.model_json_schema(mode="validation")
        if isinstance(schema, dict):
            return schema
    except Exception:
        pass

    return {
        "type": "object",
        "required": ["goal", "confidence", "tool_calls", "missing_slots", "response_mode"],
        "properties": {
            "goal": {
                "type": "string",
                "enum": ["answer", "clarify", "rag", "realtor_search", "realtor_refine", "workflow"],
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "tool_calls": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["tool_name"],
                    "properties": {
                        "tool_name": {"type": "string", "enum": ["rag", "realtor_sql", "workflow"]},
                        "rag": {"type": ["object", "null"]},
                        "realtor_slots": {"type": ["object", "null"]},
                        "workflow": {"type": ["object", "null"]},
                    },
                },
            },
            "missing_slots": {"type": "array"},
            "clarify_message": {"type": ["string", "null"]},
            "response_mode": {"type": "string", "enum": ["text_only", "text_plus_cards"]},
        },
    }


_ROUTER_DECISION_SCHEMA = _build_router_decision_schema()


class PlannerService:
    async def run(
        self,
        *,
        raw_input: Dict[str, Any],
        normalized_input: Dict[str, Any],
        history: list[Dict[str, Any]],
        conversation_id: str | None = None,
        lead_id: str | None = None,
    ) -> RouterDecision:
        tenant_id = str(raw_input.get("tenant_id") or raw_input.get("clientId") or "default").strip()
        vertical = str(raw_input.get("vertical") or normalized_input.get("vertical") or "generic").strip()
        channel = str(raw_input.get("channel") or "web_html").strip()
        conversation_token = str(
            conversation_id
            or raw_input.get("conversationId")
            or raw_input.get("conversation_id")
            or ""
        ).strip()
        lead_token = str(
            lead_id
            or raw_input.get("leadId")
            or raw_input.get("lead_id")
            or ""
        ).strip()

        prompts = await prompt_service.resolve_prompts(
            tenant_id=tenant_id,
            vertical=vertical,
            channel=channel,
        )

        context_snapshot = normalized_input.get("context_snapshot")
        if not isinstance(context_snapshot, dict):
            context_snapshot = {}
        context_snapshot = {
            **context_snapshot,
            "conversation_summary": normalized_input.get("conversation_summary", ""),
            "vertical": vertical,
            "conversation_state": normalized_input.get("conversation_state", {}),
            "last_user_turn": normalized_input.get("last_user_turn", ""),
        }

        payload = {
            "query_text": raw_input.get("queryText") or raw_input.get("text") or "",
            "history": history[-10:],
            "normalized_input": normalized_input,
            "context_snapshot": context_snapshot,
            "state_json": context_snapshot.get("conversation_state") or {},
            "router_decision_schema": _ROUTER_DECISION_SCHEMA,
            "tenant_id": tenant_id,
            "channel": channel,
            "contract": {
                "goal": "answer|clarify|rag|realtor_search|realtor_refine|workflow",
                "confidence": "float 0..1",
                "tool_calls": "optional tool calls",
                "missing_slots": "list",
                "clarify_message": "required when goal=clarify",
                "response_mode": "text_only|text_plus_cards",
            },
        }

        raw = await llm_service.generate_json(
            system_instruction=prompts.planner_system_prompt,
            payload=payload,
            temperature=0.1,
            max_output_tokens=settings.llm_max_output_tokens,
            trace_context={
                "conversation_id": conversation_token,
                "lead_id": lead_token or None,
                "tenant_id": tenant_id,
                "channel": channel,
                "vertical": vertical,
                "component": "planner",
                "operation": "router_decision",
                "history_turns": len(history),
            },
        )
        normalized = normalize_router_decision(raw)

        try:
            decision = RouterDecision.model_validate(normalized)
            return _apply_memory_reference_overrides(
                decision=decision,
                query_text=str(payload.get("query_text") or ""),
                context_snapshot=context_snapshot,
            )
        except ValidationError as exc:
            raise ValueError(f"planner_output_invalid:{exc}") from exc


planner_service = PlannerService()
