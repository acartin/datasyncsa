from __future__ import annotations

from typing import Any

from app.models.contracts import (
    AnswerEnvelope,
    GoalType,
    ResponseMode,
    RouterDecision,
    SynthesizerOutput,
    ToolName,
    ToolResult,
)

_ALLOWED_SLOTS = (
    "city",
    "property_type",
    "min_price",
    "max_price",
    "min_rooms",
    "max_rooms",
    "min_bathrooms",
    "max_bathrooms",
    "min_garage",
    "max_garage",
    "min_area_m2",
    "max_area_m2",
    "neighborhood",
    "features",
)

_ALLOWED_QUERY_KINDS = {
    "answer",
    "clarify",
    "rag",
    "realtor_search",
    "realtor_refine",
    "workflow",
}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    output: list[str] = []
    for item in value:
        token = str(item or "").strip()
        if token:
            output.append(token)
    return output


def _as_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _as_int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _as_property_cards(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    cards: list[dict[str, Any]] = []
    for item in value:
        if hasattr(item, "model_dump"):
            item = item.model_dump(mode="json")
        if not isinstance(item, dict):
            continue
        if str(item.get("card_type") or "").strip() != "property_card":
            continue
        cards.append(dict(item))
    return cards


def _normalize_slots(raw_slots: dict[str, Any]) -> dict[str, Any]:
    slots: dict[str, Any] = {
        "city": None,
        "property_type": None,
        "min_price": None,
        "max_price": None,
        "min_rooms": None,
        "max_rooms": None,
        "min_bathrooms": None,
        "max_bathrooms": None,
        "min_garage": None,
        "max_garage": None,
        "min_area_m2": None,
        "max_area_m2": None,
        "neighborhood": None,
        "features": [],
    }
    for key in _ALLOWED_SLOTS:
        if key not in raw_slots:
            continue
        value = raw_slots.get(key)
        if key == "features":
            slots[key] = _as_str_list(value)
            continue
        slots[key] = value
    return slots


def _count_turns(history: list[dict[str, Any]]) -> tuple[int, int]:
    user_turns = 0
    assistant_turns = 0
    for entry in history:
        if not isinstance(entry, dict):
            continue
        role = str(entry.get("role") or "").strip().lower()
        content = str(entry.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            user_turns += 1
        elif role == "assistant":
            assistant_turns += 1
    return user_turns, assistant_turns


def normalize_conversation_state(
    *,
    raw_state: dict[str, Any] | None,
    history: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    source = dict(raw_state or {})
    history_items = history if isinstance(history, list) else []
    user_turns, assistant_turns = _count_turns(history_items)

    search_state_raw = _as_dict(source.get("search_state"))
    legacy_active_search = _as_dict(source.get("active_search"))
    slots_source = _as_dict(search_state_raw.get("active_slots"))
    if not slots_source:
        slots_source = legacy_active_search
    if "rooms" in slots_source and "min_rooms" not in slots_source and "max_rooms" not in slots_source:
        slots_source["min_rooms"] = slots_source.get("rooms")
        slots_source["max_rooms"] = slots_source.get("rooms")

    pending_state_raw = _as_dict(source.get("pending_state"))
    progression_raw = _as_dict(source.get("lead_progression_state"))
    presentation_raw = _as_dict(source.get("presentation_state"))

    last_query_kind = str(search_state_raw.get("last_query_kind") or "").strip().lower()
    if last_query_kind not in _ALLOWED_QUERY_KINDS:
        last_query_kind = None

    fields_collected = _as_dict(progression_raw.get("fields_collected"))
    normalized: dict[str, Any] = dict(source)
    normalized["search_state"] = {
        "active_slots": _normalize_slots(slots_source),
        "last_total_found": _as_int_or_none(search_state_raw.get("last_total_found")),
        "last_listing_ids": _as_str_list(search_state_raw.get("last_listing_ids")),
        "last_query_kind": last_query_kind,
    }
    normalized["pending_state"] = {
        "pending_clarification": bool(pending_state_raw.get("pending_clarification")),
        "pending_reference_target": str(pending_state_raw.get("pending_reference_target") or "").strip() or None,
        "pending_reset_offer_city": str(pending_state_raw.get("pending_reset_offer_city") or "").strip() or None,
    }
    normalized["lead_progression_state"] = {
        "user_turn_count": _as_int(progression_raw.get("user_turn_count"), default=user_turns),
        "assistant_turn_count": _as_int(progression_raw.get("assistant_turn_count"), default=assistant_turns),
        "capture_attempt_count": _as_int(progression_raw.get("capture_attempt_count"), default=0),
        "last_capture_field": str(progression_raw.get("last_capture_field") or "").strip() or None,
        "last_capture_turn": _as_int_or_none(progression_raw.get("last_capture_turn")),
        "fields_collected": {
            "name": bool(fields_collected.get("name")),
            "email": bool(fields_collected.get("email")),
            "phone": bool(fields_collected.get("phone")),
            "budget": bool(fields_collected.get("budget")),
            "urgency": bool(fields_collected.get("urgency")),
            "appointment_window": bool(fields_collected.get("appointment_window")),
        },
    }
    normalized["presentation_state"] = {
        "last_response_mode": (
            str(presentation_raw.get("last_response_mode") or "").strip()
            if str(presentation_raw.get("last_response_mode") or "").strip() in {"text_only", "text_plus_cards"}
            else None
        ),
        "last_needs_cards": bool(presentation_raw.get("last_needs_cards")),
        "cards_shown_ever": bool(presentation_raw.get("cards_shown_ever")),
        "last_property_cards": _as_property_cards(presentation_raw.get("last_property_cards")),
    }
    # Backward-compat alias used by older payloads.
    legacy_alias = dict(normalized["search_state"]["active_slots"])
    if "rooms" in legacy_active_search:
        legacy_alias["rooms"] = legacy_active_search.get("rooms")
    if "bathrooms" in legacy_active_search:
        legacy_alias["bathrooms"] = legacy_active_search.get("bathrooms")
    if "garage" in legacy_active_search:
        legacy_alias["garage"] = legacy_active_search.get("garage")
    normalized["active_search"] = legacy_alias
    return normalized


def resolve_response_mode(
    *,
    decision: RouterDecision,
    tool_results: list[ToolResult] | None = None,
) -> ResponseMode:
    if decision.goal == GoalType.clarify:
        return ResponseMode.text_only

    has_realtor_call = any(call.tool_name == ToolName.realtor_sql for call in decision.tool_calls)
    has_realtor_result = False
    if isinstance(tool_results, list):
        for result in tool_results:
            if result.realtor is not None:
                has_realtor_result = True
                break

    if decision.goal in {GoalType.realtor_search, GoalType.realtor_refine} and (has_realtor_call or has_realtor_result):
        return ResponseMode.text_plus_cards
    if has_realtor_call:
        return ResponseMode.text_plus_cards
    return ResponseMode.text_only


def enforce_decision_response_mode(decision: RouterDecision) -> RouterDecision:
    resolved_mode = resolve_response_mode(decision=decision, tool_results=None)
    if decision.response_mode == resolved_mode:
        return decision
    return decision.model_copy(update={"response_mode": resolved_mode})


def advance_conversation_state(
    *,
    current_state: dict[str, Any] | None,
    decision: RouterDecision,
    tool_results: list[ToolResult],
    envelope: AnswerEnvelope,
    synthesizer_output: SynthesizerOutput,
    user_turn_text: str,
) -> dict[str, Any]:
    state = normalize_conversation_state(raw_state=current_state, history=[])
    search_state = _as_dict(state.get("search_state"))
    progression_state = _as_dict(state.get("lead_progression_state"))
    pending_state = _as_dict(state.get("pending_state"))
    presentation_state = _as_dict(state.get("presentation_state"))

    if decision.goal in {GoalType.realtor_search, GoalType.realtor_refine}:
        for tool_call in decision.tool_calls:
            if tool_call.tool_name == ToolName.realtor_sql and tool_call.realtor_slots is not None:
                search_state["active_slots"] = _normalize_slots(tool_call.realtor_slots.model_dump(mode="json"))
                break

    search_state["last_query_kind"] = decision.goal.value
    pending_state["pending_clarification"] = decision.goal == GoalType.clarify
    if decision.goal == GoalType.clarify:
        pending_state["pending_reference_target"] = None
        pending_state["pending_reset_offer_city"] = None

    for result in tool_results:
        if result.status != "ok" or result.realtor is None:
            continue
        search_state["last_total_found"] = int(result.realtor.total_found)
        search_state["last_listing_ids"] = [
            listing.listing_id
            for listing in result.realtor.listings
            if str(listing.listing_id).strip()
        ]
        search_state["active_slots"] = _normalize_slots(result.realtor.slots_used.model_dump(mode="json"))

    presentation_state["last_response_mode"] = envelope.response_mode.value
    presentation_state["last_needs_cards"] = bool(synthesizer_output.needs_cards)
    presentation_state["cards_shown_ever"] = bool(presentation_state.get("cards_shown_ever")) or bool(envelope.cards)
    previous_property_cards = _as_property_cards(presentation_state.get("last_property_cards"))
    current_property_cards = _as_property_cards(envelope.cards)
    presentation_state["last_property_cards"] = current_property_cards or previous_property_cards

    if str(user_turn_text or "").strip():
        progression_state["user_turn_count"] = _as_int(progression_state.get("user_turn_count"), default=0) + 1
    progression_state["assistant_turn_count"] = _as_int(progression_state.get("assistant_turn_count"), default=0) + 1

    state["search_state"] = search_state
    state["pending_state"] = pending_state
    state["lead_progression_state"] = progression_state
    state["presentation_state"] = presentation_state
    state["active_search"] = dict(_as_dict(search_state.get("active_slots")))
    return state
