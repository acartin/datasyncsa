"""Deterministic geographic catalog normalization for search filters."""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

DEFAULT_COUNTRY_CODE = "CR"
_CATALOG_DIR = Path(__file__).with_name("geo")


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


@lru_cache(maxsize=8)
def _load_catalog(country_code: str = DEFAULT_COUNTRY_CODE) -> dict[str, Any]:
    path = _CATALOG_DIR / f"{country_code.lower()}.json"
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=8)
def _build_indexes(country_code: str = DEFAULT_COUNTRY_CODE) -> dict[str, Any]:
    catalog = _load_catalog(country_code)
    provinces_by_key: dict[str, dict[str, Any]] = {}
    province_entries: list[tuple[str, dict[str, Any]]] = []
    province_name_keys: set[str] = set()

    for region in catalog.get("regions", []):
        keys = {_normalize_text(region.get("name"))}
        keys.update(_normalize_text(alias) for alias in region.get("aliases", []) if alias)
        for key in {item for item in keys if item}:
            provinces_by_key[key] = region
            province_entries.append((key, region))
            province_name_keys.add(key)

    localities_by_key: dict[str, dict[str, Any]] = {}
    locality_entries: list[tuple[str, dict[str, Any]]] = []
    for locality in catalog.get("localities", []):
        keys = {_normalize_text(locality.get("name"))}
        keys.update(_normalize_text(alias) for alias in locality.get("aliases", []) if alias)
        for key in {item for item in keys if item}:
            localities_by_key[key] = locality
            if key not in province_name_keys:
                locality_entries.append((key, locality))

    province_entries.sort(key=lambda item: len(item[0]), reverse=True)
    locality_entries.sort(key=lambda item: len(item[0]), reverse=True)
    return {
        "provinces_by_key": provinces_by_key,
        "province_entries": province_entries,
        "localities_by_key": localities_by_key,
        "locality_entries": locality_entries,
    }


def resolve_geo_value(value: str | None, *, country_code: str = DEFAULT_COUNTRY_CODE) -> dict[str, str] | None:
    normalized = _normalize_text(value)
    if not normalized:
        return None
    indexes = _build_indexes(country_code)
    locality = indexes["localities_by_key"].get(normalized)
    if locality:
        return {
            "scope": "locality",
            "ubicacion": locality["name"],
            "provincia": locality["province_name"],
        }
    province = indexes["provinces_by_key"].get(normalized)
    if province:
        return {
            "scope": "province",
            "ubicacion": None,
            "provincia": province["name"],
        }
    return None


def detect_geo_from_message(message: str | None, *, country_code: str = DEFAULT_COUNTRY_CODE) -> dict[str, str] | None:
    normalized = _normalize_text(message)
    if not normalized:
        return None

    indexes = _build_indexes(country_code)
    for key, locality in indexes["locality_entries"]:
        if _contains_phrase(normalized, key):
            return {
                "scope": "locality",
                "ubicacion": locality["name"],
                "provincia": locality["province_name"],
            }

    for key, province in indexes["province_entries"]:
        if _contains_phrase(normalized, key):
            return {
                "scope": "province",
                "ubicacion": None,
                "provincia": province["name"],
            }

    return None


def normalize_search_geo_filters(
    filters: dict[str, Any],
    *,
    message: str | None,
    country_code: str = DEFAULT_COUNTRY_CODE,
) -> dict[str, Any]:
    normalized_filters = {**filters}

    explicit_geo = detect_geo_from_message(message, country_code=country_code)
    if explicit_geo:
        normalized_filters["provincia"] = explicit_geo["provincia"]
        if explicit_geo["scope"] == "locality":
            normalized_filters["ubicacion"] = explicit_geo["ubicacion"]
        else:
            current_location = normalized_filters.get("ubicacion")
            resolved_location = resolve_geo_value(str(current_location), country_code=country_code) if current_location else None
            if resolved_location and resolved_location["provincia"] != explicit_geo["provincia"]:
                normalized_filters["ubicacion"] = None
        return normalized_filters

    current_location = normalized_filters.get("ubicacion")
    resolved_location = resolve_geo_value(str(current_location), country_code=country_code) if current_location else None
    if resolved_location:
        normalized_filters["ubicacion"] = resolved_location["ubicacion"]
        normalized_filters["provincia"] = resolved_location["provincia"]
        return normalized_filters

    current_province = normalized_filters.get("provincia")
    resolved_province = resolve_geo_value(str(current_province), country_code=country_code) if current_province else None
    if resolved_province:
        normalized_filters["provincia"] = resolved_province["provincia"]
        if resolved_province["scope"] == "locality":
            normalized_filters["ubicacion"] = resolved_province["ubicacion"]

    return normalized_filters
