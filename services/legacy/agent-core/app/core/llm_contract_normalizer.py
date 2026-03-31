from __future__ import annotations

from typing import Any
import unicodedata


_REALTOR_SLOT_KEYS = {
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
}

_PROPERTY_TYPE_ALIASES = {
    "apartment": "apartment",
    "apartamento": "apartment",
    "apto": "apartment",
    "departamento": "apartment",
    "depa": "apartment",
    "house": "house",
    "casa": "house",
    "hogar": "house",
    "land": "land",
    "terreno": "land",
    "lote": "land",
    "lot": "land",
    "office": "office",
    "oficina": "office",
}


def _unwrap_dict(raw: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, dict):
            return value
    return raw


def _normalize_token(value: str) -> str:
    base = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in base if not unicodedata.combining(ch)).strip().lower()


def _normalize_realtor_slots(slots: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(slots)
    property_type = normalized.get("property_type")
    if isinstance(property_type, str):
        alias = _PROPERTY_TYPE_ALIASES.get(_normalize_token(property_type))
        if alias:
            normalized["property_type"] = alias
    if "features" in normalized:
        raw_features = normalized.get("features")
        if raw_features is None:
            normalized["features"] = []
        elif isinstance(raw_features, str):
            token = raw_features.strip()
            normalized["features"] = [token] if token else []
        elif isinstance(raw_features, list):
            normalized["features"] = [
                str(item).strip()
                for item in raw_features
                if str(item).strip()
            ]
        else:
            normalized["features"] = []
    return normalized


def _extract_realtor_slots(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    candidate: dict[str, Any] = value
    if isinstance(value.get("realtor_slots"), dict):
        candidate = value.get("realtor_slots")  # type: ignore[assignment]
    elif isinstance(value.get("slots"), dict):
        candidate = value.get("slots")  # type: ignore[assignment]

    slots = {key: candidate.get(key) for key in _REALTOR_SLOT_KEYS if key in candidate}
    slots = _normalize_realtor_slots(slots)
    return slots or None


def normalize_router_decision(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Structural normalization only.
    Does not repair business decisions or infer missing fields.
    """
    if not isinstance(raw, dict):
        return {}
    normalized = _unwrap_dict(raw, ("RouterDecision", "router_decision"))
    if not isinstance(normalized, dict):
        return {}

    tool_calls_raw = normalized.get("tool_calls")
    if isinstance(tool_calls_raw, list):
        fixed_calls: list[dict[str, Any]] = []
        for call in tool_calls_raw:
            if not isinstance(call, dict):
                continue
            fixed = dict(call)
            if "tool_name" not in fixed and "name" in fixed:
                fixed["tool_name"] = fixed.get("name")
            tool_name = str(fixed.get("tool_name") or "").strip().lower()
            if tool_name == "rag" and "rag" not in fixed:
                rag_payload = {}
                if fixed.get("query_text") is not None:
                    rag_payload["query_text"] = fixed.get("query_text")
                if fixed.get("query") is not None and "query_text" not in rag_payload:
                    rag_payload["query_text"] = fixed.get("query")
                if fixed.get("rag_query") is not None and "query_text" not in rag_payload:
                    rag_payload["query_text"] = fixed.get("rag_query")
                if fixed.get("queryText") is not None and "query_text" not in rag_payload:
                    rag_payload["query_text"] = fixed.get("queryText")
                if fixed.get("ragQuery") is not None and "query_text" not in rag_payload:
                    rag_payload["query_text"] = fixed.get("ragQuery")
                if fixed.get("top_k") is not None:
                    rag_payload["top_k"] = fixed.get("top_k")
                if fixed.get("filter_doc_type") is not None:
                    rag_payload["filter_doc_type"] = fixed.get("filter_doc_type")
                if rag_payload:
                    fixed["rag"] = rag_payload
            if tool_name == "realtor_sql" and "realtor_slots" not in fixed:
                realtor_slots = None
                if isinstance(fixed.get("slots"), dict):
                    realtor_slots = _extract_realtor_slots(fixed.get("slots"))
                if realtor_slots is None and isinstance(fixed.get("parameters"), dict):
                    realtor_slots = _extract_realtor_slots(fixed.get("parameters"))
                if realtor_slots is None and isinstance(fixed.get("params"), dict):
                    realtor_slots = _extract_realtor_slots(fixed.get("params"))
                if realtor_slots is not None:
                    fixed["realtor_slots"] = realtor_slots
            elif tool_name == "realtor_sql" and isinstance(fixed.get("realtor_slots"), dict):
                fixed["realtor_slots"] = _normalize_realtor_slots(fixed["realtor_slots"])
            if tool_name == "workflow" and "workflow" not in fixed:
                if isinstance(fixed.get("params"), dict):
                    fixed["workflow"] = {
                        "workflow_name": str(fixed.get("workflow_name") or fixed.get("name") or "").strip(),
                        "params": fixed.get("params") or {},
                    }
            fixed_calls.append(fixed)
        normalized["tool_calls"] = fixed_calls

    return normalized


def normalize_synthesizer_output(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Structural normalization only.
    Does not coerce invalid types or fabricate evidence.
    """
    if not isinstance(raw, dict):
        return {}
    return _unwrap_dict(raw, ("SynthesizerOutput", "synthesizer_output"))
