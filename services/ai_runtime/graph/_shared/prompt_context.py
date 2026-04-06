"""Compact serializers for prompt context payloads."""

from __future__ import annotations

import re
from typing import Any


_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
_WHITESPACE_PATTERN = re.compile(r"\s+")


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return dict(value)
    return {}


def _collapse_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return _WHITESPACE_PATTERN.sub(" ", text)


def _truncate_text(value: Any, max_chars: int) -> str:
    text = _collapse_text(value)
    if len(text) <= max_chars:
        return text
    if max_chars <= 3:
        return text[:max_chars]
    return f"{text[: max_chars - 3].rstrip()}..."


def _description_excerpt(value: Any, max_chars: int) -> str:
    plain_text = _HTML_TAG_PATTERN.sub(" ", str(value or ""))
    return _truncate_text(plain_text, max_chars)


def summarize_message_for_prompt(message: Any, *, max_chars: int | None = None) -> dict[str, Any]:
    payload = _as_dict(message)
    content = _collapse_text(payload.get("content"))
    if max_chars is not None:
        content = _truncate_text(content, max_chars)
    compact: dict[str, Any] = {
        "role": payload.get("role"),
        "content": content,
    }
    metadata = payload.get("metadata")
    if metadata:
        compact["metadata"] = metadata
    return compact


def summarize_messages_for_prompt(
    messages: list[Any],
    *,
    limit: int,
    max_chars: int | None = None,
) -> list[dict[str, Any]]:
    return [summarize_message_for_prompt(item, max_chars=max_chars) for item in messages[-limit:]]


def summarize_property_for_prompt(
    property_item: Any,
    *,
    include_description_excerpt: bool = False,
    description_chars: int = 280,
) -> dict[str, Any] | None:
    payload = _as_dict(property_item)
    if not payload:
        return None

    features = _as_dict(payload.get("features"))
    media = _as_dict(payload.get("media"))
    location = _as_dict(payload.get("location"))
    meta = _as_dict(payload.get("meta"))
    compact: dict[str, Any] = {
        "id": payload.get("id"),
        "title": payload.get("title"),
        "price": payload.get("price"),
        "currency": payload.get("currency"),
        "address": payload.get("address"),
        "country": location.get("country"),
        "province": location.get("province"),
        "bedrooms_clean": features.get("bedrooms_clean"),
        "bathrooms_clean": features.get("bathrooms_clean"),
        "garage_clean": features.get("garage_clean"),
        "sqm_clean": features.get("sqm_clean"),
        "lot_size_sqm": features.get("lot_size_sqm"),
        "year_built": features.get("year_built"),
        "amenities": list(features.get("amenities") or [])[:8],
        "is_featured": features.get("is_featured"),
        "primary_image_url": media.get("primary_image_url"),
        "public_url": meta.get("public_url"),
    }
    if include_description_excerpt:
        excerpt = _description_excerpt(payload.get("description_html"), description_chars)
        if excerpt:
            compact["description_excerpt"] = excerpt
    return {key: value for key, value in compact.items() if value not in (None, "", [], {})}


def summarize_properties_for_prompt(
    properties: list[Any],
    *,
    limit: int,
    include_description_excerpt: bool = False,
    description_chars: int = 280,
) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for item in properties[:limit]:
        serialized = summarize_property_for_prompt(
            item,
            include_description_excerpt=include_description_excerpt,
            description_chars=description_chars,
        )
        if serialized:
            compact.append(serialized)
    return compact


def summarize_memory_for_prompt(memory_state: Any, *, entity_limit: int = 8) -> dict[str, Any]:
    payload = _as_dict(memory_state)
    entities = []
    for item in list(payload.get("entities") or [])[-entity_limit:]:
        entity_payload = _as_dict(item)
        entities.append(
            {
                key: entity_payload.get(key)
                for key in ("key", "value", "status", "value_type", "source_turn")
                if entity_payload.get(key) not in (None, "", [], {})
            }
        )
    compact = {
        "entities": entities,
        "last_lookup": _as_dict(payload.get("last_lookup")),
    }
    return {key: value for key, value in compact.items() if value not in (None, "", [], {})}


def summarize_lead_advisor_for_prompt(lead_advisor: Any) -> dict[str, Any]:
    payload = _as_dict(lead_advisor)
    if not payload:
        return {}
    criteria_reasons = {
        str(key): _truncate_text(value, 240)
        for key, value in dict(payload.get("criteria_reasons") or {}).items()
        if str(value or "").strip()
    }
    compact = {
        "lead_extracted": _as_dict(payload.get("lead_extracted")),
        "lead_completo": payload.get("lead_completo"),
        "capture_exposure_count": payload.get("capture_exposure_count"),
        "should_ask": payload.get("should_ask"),
        "field_to_ask": payload.get("field_to_ask"),
        "question_to_ask": _truncate_text(payload.get("question_to_ask"), 240)
        if str(payload.get("question_to_ask") or "").strip()
        else None,
        "criteria_scores": dict(payload.get("criteria_scores") or {}),
        "criteria_reasons": criteria_reasons,
        "scoring_reasoning": _truncate_text(payload.get("scoring_reasoning"), 320)
        if str(payload.get("scoring_reasoning") or "").strip()
        else None,
        "scoring_confidence": payload.get("scoring_confidence"),
        "scoring_last_updated_turn": payload.get("scoring_last_updated_turn"),
        "required_fields": list(payload.get("required_fields") or []),
        "completed_fields": list(payload.get("completed_fields") or []),
        "target_criteria": list(payload.get("target_criteria") or []),
    }
    return {key: value for key, value in compact.items() if value not in (None, "", [], {})}


def summarize_turn_outputs_for_prompt(turn_outputs: list[dict[str, Any]], *, limit: int = 8) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for item in turn_outputs[-limit:]:
        output_type = str(item.get("type") or "").strip().lower()
        payload: dict[str, Any]
        if output_type == "search":
            payload = {
                "type": item.get("type"),
                "count": item.get("count"),
                "match_scope": item.get("match_scope"),
                "filters": item.get("filters"),
                "requested_filters": item.get("requested_filters"),
                "effective_filters": item.get("effective_filters"),
                "relaxation_applied": item.get("relaxation_applied"),
                "attempt_index": item.get("attempt_index"),
                "execution_mode": item.get("execution_mode"),
            }
        elif output_type in {"recommendation", "property_selection", "property_focus"}:
            payload = {
                "type": item.get("type"),
                "property": summarize_property_for_prompt(item.get("property")),
                "narrative": _truncate_text(item.get("narrative"), 320)
                if str(item.get("narrative") or "").strip()
                else None,
            }
        elif output_type == "comparison":
            payload = {
                "type": item.get("type"),
                "scores": item.get("scores"),
                "narrative": _truncate_text(item.get("narrative"), 320)
                if str(item.get("narrative") or "").strip()
                else None,
            }
        elif output_type == "lead_scoring":
            payload = {
                "type": item.get("type"),
                "scores": item.get("scores"),
                "updated_fields": item.get("updated_fields"),
                "slot_hints": item.get("slot_hints"),
                "guardrails_applied": item.get("guardrails_applied"),
                "reasoning": _truncate_text(item.get("reasoning"), 240)
                if str(item.get("reasoning") or "").strip()
                else None,
                "confidence": item.get("confidence"),
            }
        elif output_type == "appointment":
            payload = {
                "type": item.get("type"),
                "cita": item.get("cita"),
            }
        elif output_type == "clarification":
            payload = {
                "type": item.get("type"),
                "question": _truncate_text(item.get("question"), 240)
                if str(item.get("question") or "").strip()
                else None,
            }
        elif output_type == "lead_capture":
            payload = {
                "type": item.get("type"),
                "fields": item.get("fields"),
            }
        else:
            payload = {
                key: value
                for key, value in item.items()
                if key == "type" or not isinstance(value, (dict, list))
            }
        compact.append({key: value for key, value in payload.items() if value not in (None, "", [], {})})
    return compact
