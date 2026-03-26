"""Deterministic normalization of conversational property types against DB types."""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    stripped = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(ch for ch in stripped if not unicodedata.combining(ch))
    lowered = ascii_text.lower()
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _contains_phrase(haystack: str, phrase: str) -> bool:
    if not haystack or not phrase:
        return False
    pattern = rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])"
    return re.search(pattern, haystack) is not None


_TYPE_HINTS: dict[str, list[str]] = {
    "casa": ["casa", "house", "hogar", "residencia", "casa de habitacion"],
    "apartamento": ["apartamento", "condominio", "apartment", "condo"],
    "terreno": ["lote", "terreno", "land", "lot", "propiedad"],
    "local": ["local", "local comercial", "commercial", "commercial space"],
    "oficina": ["oficina", "office"],
    "bodega": ["bodega", "warehouse", "industrial"],
    "finca": ["quinta", "finca", "villa", "farm"],
}


def _canonical_group(raw_value: str | None) -> str | None:
    normalized = _normalize_text(raw_value)
    if not normalized:
        return None
    for group, hints in _TYPE_HINTS.items():
        if any(_contains_phrase(normalized, _normalize_text(hint)) for hint in hints):
            return group
    return None


def _preferred_db_type(group: str, available_types: list[str]) -> str | None:
    normalized_types = [(_normalize_text(item), item) for item in available_types]

    preferences: dict[str, list[str]] = {
        "casa": ["casa", "house"],
        "apartamento": ["apartamento", "apartment"],
        "terreno": ["lote", "terreno", "land"],
        "local": ["local", "commercial"],
        "oficina": ["oficina", "office"],
        "bodega": ["bodega", "industrial"],
        "finca": ["quinta", "finca", "villa"],
    }

    for preferred in preferences.get(group, []):
        preferred_norm = _normalize_text(preferred)
        for normalized_name, original_name in normalized_types:
            if preferred_norm and preferred_norm in normalized_name:
                return original_name
    return None


def normalize_property_type(
    value: str | None,
    *,
    message: str | None,
    available_types: Iterable[str],
) -> str | None:
    types = [item for item in available_types if item]
    if not types:
        return value

    normalized_map = {_normalize_text(item): item for item in types}

    raw_value = value or ""
    normalized_value = _normalize_text(raw_value)
    if normalized_value in normalized_map:
        return normalized_map[normalized_value]

    message_group = _canonical_group(message)
    value_group = _canonical_group(raw_value)
    chosen_group = value_group or message_group
    if not chosen_group:
        return value

    preferred = _preferred_db_type(chosen_group, types)
    return preferred or value
