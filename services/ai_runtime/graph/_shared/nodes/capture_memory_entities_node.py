"""Conversational memory extraction node."""

from __future__ import annotations

import re
from typing import Any

from services.ai_runtime.config.prompt_composer import compose
from services.ai_runtime.domain.contracts import ConversationEntity, LeadExtracted
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import BaseGraphState
from services.ai_runtime.graph._shared.prompt_context import (
    summarize_message_for_prompt,
    summarize_messages_for_prompt,
)


_MEMORY_SIGNAL_PATTERNS = (
    r"\bme llamo\b",
    r"\bmi nombre es\b",
    r"\bmi correo\b",
    r"\bmi email\b",
    r"\bcorreo\b",
    r"\bemail\b",
    r"\btelefono\b",
    r"\bteléfono\b",
    r"\bcelular\b",
    r"\bwhatsapp\b",
    r"\bpresupuesto\b",
    r"\baprobaci[oó]n\b",
    r"\bprefiero\b",
)

_PHONE_PATTERN = re.compile(r"(?:\+?\d[\d\s-]{6,}\d)")
_EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", flags=re.IGNORECASE)
_NUMBER_PATTERN = re.compile(r"-?\d+(?:[.,]\d+)?")
_NAME_PREFIX_PATTERN = re.compile(
    r"\b(?:me llamo|mi nombre es|mi nombre)\s+"
    r"(?P<name>[A-Za-zÁÉÍÓÚÑáéíóúñ'`.-]+(?:\s+[A-Za-zÁÉÍÓÚÑáéíóúñ'`.-]+){0,3})\b",
    flags=re.IGNORECASE,
)
_SHORT_NAME_PATTERN = re.compile(
    r"^\s*(?:con|soy)\s+"
    r"(?P<name>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ'`.-]+(?:\s+[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ'`.-]+){0,3})\s*[\.\!\?]?\s*$",
    flags=re.IGNORECASE,
)
_PERSON_NAME_TOKEN_PATTERN = re.compile(r"^[A-Za-zÁÉÍÓÚÑáéíóúñ'`.-]+$")
_SELF_IDENTIFICATION_MARKERS = (
    "me llamo",
    "mi nombre es",
    "mi nombre",
    "soy",
)
_SELF_IDENTIFICATION_BREAK_WORDS = {
    "y",
    "e",
    "o",
    "u",
    "pero",
    "porque",
    "que",
    "busco",
    "buscando",
    "quiero",
    "necesito",
    "ando",
    "estoy",
    "me",
    "mi",
    "para",
    "por",
    "con",
}
_SELF_IDENTIFICATION_LEADING_REJECT_WORDS = {
    "de",
    "del",
    "la",
    "las",
    "el",
    "los",
    "en",
    "un",
    "una",
}
_SELF_IDENTIFICATION_ROLE_WORDS = {
    "cliente",
    "inversionista",
    "agente",
    "asesor",
    "asesora",
    "interesado",
    "interesada",
    "comprador",
    "compradora",
    "vendedor",
    "vendedora",
}

_BASE_STRUCTURED_MEMORY_KEYS = {
    "nombre",
    "email",
    "correo",
    "telefono",
    "telefono_principal",
    "numero",
    "presupuesto",
    "presupuesto_minimo",
    "presupuesto_maximo",
    "presupuesto_rango",
    "aprobacion",
    "fecha_preferida",
    "tipo_cita",
    "appointment_intent",
    "preferencia",
    "preferencias",
}

_POSITIVE_APPOINTMENT_INTENT_VALUES = {"1", "positive", "si", "sí", "true", "yes"}
_NEGATIVE_APPOINTMENT_INTENT_VALUES = {"0", "false", "negative", "no"}
_ALLOWED_APPOINTMENT_INTENT_VALUES = {"positive", "negative", "uncertain"}


def _should_extract_memory(message: str) -> bool:
    normalized = (message or "").strip()
    if not normalized:
        return False
    if _EMAIL_PATTERN.search(normalized) or _PHONE_PATTERN.search(normalized):
        return True
    if _SHORT_NAME_PATTERN.search(normalized):
        return True
    if _extract_explicit_self_identification_name(normalized):
        return True
    lowered = normalized.lower()
    return any(re.search(pattern, lowered) for pattern in _MEMORY_SIGNAL_PATTERNS)


def _normalize_entity_key(value: str) -> str:
    cleaned = re.sub(r"\s+", "_", (value or "").strip().lower())
    return re.sub(r"[^a-z0-9_]+", "", cleaned)


def _allowed_structured_memory_keys(_: BaseGraphState) -> set[str]:
    return set(_BASE_STRUCTURED_MEMORY_KEYS)


def _infer_value_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "object"
    return "string"


def _coerce_budget_value(value: Any) -> float | None:
    if value in (None, "", []):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = _NUMBER_PATTERN.search(value.replace(",", ""))
        if not match:
            return None
        try:
            return float(match.group(0).replace(",", "."))
        except ValueError:
            return None
    if isinstance(value, dict):
        for key in ("max", "min", "value", "amount"):
            candidate = _coerce_budget_value(value.get(key))
            if candidate is not None:
                return candidate
        lower = _coerce_budget_value(value.get("desde"))
        upper = _coerce_budget_value(value.get("hasta"))
        if lower is not None and upper is not None:
            return (lower + upper) / 2
    return None


def _normalize_person_name(value: str | None) -> str | None:
    cleaned = re.sub(r"\s+", " ", (value or "").strip(" .,!?:;"))
    if not cleaned:
        return None
    if len(cleaned) > 80:
        return None
    if any(char.isdigit() for char in cleaned):
        return None
    return cleaned


def _extract_name_after_self_identification_marker(text: str) -> str | None:
    remainder = text.lstrip(" ,:;-")
    if not remainder:
        return None

    candidate_tokens: list[str] = []
    for raw_token in remainder.split():
        token = raw_token.strip(" ,.!?;:()[]{}\"'")
        lowered = token.lower()
        if not token:
            if candidate_tokens:
                break
            continue
        if lowered in _SELF_IDENTIFICATION_BREAK_WORDS:
            break
        if not _PERSON_NAME_TOKEN_PATTERN.fullmatch(token):
            break
        candidate_tokens.append(token)
        if len(candidate_tokens) >= 4:
            break

    if not candidate_tokens:
        return None
    if candidate_tokens[0].lower() in _SELF_IDENTIFICATION_LEADING_REJECT_WORDS:
        return None
    if len(candidate_tokens) == 1 and candidate_tokens[0].lower() in _SELF_IDENTIFICATION_ROLE_WORDS:
        return None
    return _normalize_person_name(" ".join(candidate_tokens))


def _extract_explicit_self_identification_name(message: str) -> str | None:
    text = re.sub(r"\s+", " ", (message or "").strip())
    if not text:
        return None

    lowered = text.lower()
    for marker in _SELF_IDENTIFICATION_MARKERS:
        search_start = 0
        while True:
            index = lowered.find(marker, search_start)
            if index < 0:
                break
            candidate = _extract_name_after_self_identification_marker(text[index + len(marker) :])
            if candidate:
                return candidate
            search_start = index + len(marker)
    return None


def _extract_name_fallback(message: str) -> str | None:
    text = (message or "").strip()
    if not text:
        return None
    prefixed = _NAME_PREFIX_PATTERN.search(text)
    if prefixed:
        return _normalize_person_name(prefixed.group("name"))
    short = _SHORT_NAME_PATTERN.search(text)
    if short:
        return _normalize_person_name(short.group("name"))
    return _extract_explicit_self_identification_name(text)


def _normalize_appointment_intent(value: Any) -> str | None:
    if value in (None, "", []):
        return None
    if isinstance(value, bool):
        return "positive" if value else "negative"
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    if normalized in _POSITIVE_APPOINTMENT_INTENT_VALUES:
        return "positive"
    if normalized in _NEGATIVE_APPOINTMENT_INTENT_VALUES:
        return "negative"
    if normalized in _ALLOWED_APPOINTMENT_INTENT_VALUES:
        return normalized
    return "uncertain"


def _merge_canonical_fields(current: LeadExtracted, payload: dict[str, Any]) -> LeadExtracted:
    merged = current.model_dump(mode="json")
    negative_appointment_intent = False
    for key, value in payload.items():
        if key not in merged:
            continue
        if key == "appointment_intent":
            normalized = _normalize_appointment_intent(value)
            if normalized is None:
                continue
            merged[key] = normalized
            negative_appointment_intent = normalized == "negative"
            continue
        if value in (None, "", []):
            continue
        if key == "presupuesto":
            coerced = _coerce_budget_value(value)
            if coerced is not None:
                merged[key] = coerced
            continue
        if key == "preferencias":
            merged[key] = list(dict.fromkeys([*merged.get(key, []), *[item for item in value if item]]))
            continue
        merged[key] = value
    if negative_appointment_intent:
        merged["tipo_cita"] = None
    return LeadExtracted.model_validate(merged)


def _build_promoted_entities(
    canonical_fields: dict[str, Any],
    *,
    previous_fields: dict[str, Any],
    source_turn: int,
    source_text: str,
    existing_keys: set[str],
) -> list[ConversationEntity]:
    promoted: list[ConversationEntity] = []
    for key in ("nombre", "email", "telefono", "presupuesto", "aprobacion", "fecha_preferida", "tipo_cita"):
        value = canonical_fields.get(key)
        normalized_key = _normalize_entity_key(key)
        if value in (None, "", []) or normalized_key in existing_keys or previous_fields.get(key) == value:
            continue
        promoted.append(
            ConversationEntity(
                key=normalized_key,
                value=value,
                value_type=_infer_value_type(value),
                confidence=0.9,
                source_turn=source_turn,
                source_text=source_text,
                status="explicit",
            )
        )
    return promoted


def _merge_entities(existing: list[ConversationEntity], incoming: list[ConversationEntity]) -> list[ConversationEntity]:
    merged: dict[str, ConversationEntity] = {_normalize_entity_key(item.key): item for item in existing}
    for entity in incoming:
        key = _normalize_entity_key(entity.key)
        current = merged.get(key)
        if current and current.value == entity.value:
            continue
        merged[key] = entity
    return list(merged.values())


async def capture_memory_entities(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    """Extract durable user facts into state memory and canonical lead fields."""

    graph_state = BaseGraphState.model_validate(state)
    latest_message = graph_state.messages[-1].content
    if not _should_extract_memory(latest_message):
        return {}

    prompt = compose(
        "memory_entity_extractor",
        graph_state.tenant_config,
        graph_state.vertical,
        {
            "message": summarize_message_for_prompt(graph_state.messages[-1]),
            "messages": summarize_messages_for_prompt(graph_state.messages, limit=6),
            "canonical_fields": graph_state.lead_advisor.lead_extracted.model_dump(mode="json"),
            "existing_entities": [
                {
                    key: entity.model_dump(mode="json").get(key)
                    for key in ("key", "value", "status", "value_type", "source_turn")
                    if entity.model_dump(mode="json").get(key) not in (None, "", [], {})
                }
                for entity in graph_state.memory.entities[-12:]
            ],
        },
        include_tone=False,
    )
    payload = await deps.llm.extract_memory_entities(prompt)
    canonical_payload = payload.get("canonical_fields", {}) if isinstance(payload, dict) else {}
    entities_payload = payload.get("entities", []) if isinstance(payload, dict) else []
    if not isinstance(canonical_payload, dict):
        canonical_payload = {}
    if not isinstance(entities_payload, list):
        entities_payload = []
    if not canonical_payload.get("nombre"):
        fallback_name = _extract_name_fallback(latest_message)
        if fallback_name:
            canonical_payload["nombre"] = fallback_name

    merged_lead = _merge_canonical_fields(graph_state.lead_advisor.lead_extracted, canonical_payload)
    allowed_keys = _allowed_structured_memory_keys(graph_state)

    parsed_entities: list[ConversationEntity] = []
    for item in entities_payload:
        if not isinstance(item, dict):
            continue
        key = _normalize_entity_key(str(item.get("key") or ""))
        value = item.get("value")
        if not key or key not in allowed_keys or value in (None, "", []):
            continue
        try:
            parsed_entities.append(
                ConversationEntity.model_validate(
                    {
                        **item,
                        "key": key,
                        "value_type": item.get("value_type") or _infer_value_type(value),
                        "source_turn": graph_state.current_turn,
                        "source_text": item.get("source_text") or latest_message,
                        "status": item.get("status") or "explicit",
                    }
                )
            )
        except Exception:
            continue

    if not canonical_payload and not parsed_entities:
        return {}

    existing_keys = {_normalize_entity_key(item.key) for item in parsed_entities}
    parsed_entities.extend(
        _build_promoted_entities(
            canonical_payload,
            previous_fields=graph_state.lead_advisor.lead_extracted.model_dump(mode="json"),
            source_turn=graph_state.current_turn,
            source_text=latest_message,
            existing_keys=existing_keys,
        )
    )

    merged_entities = _merge_entities(graph_state.memory.entities, parsed_entities)
    return {
        "lead_advisor": graph_state.lead_advisor.model_copy(update={"lead_extracted": merged_lead}).model_dump(mode="json"),
        "memory": graph_state.memory.model_copy(update={"entities": merged_entities}).model_dump(mode="json"),
    }
