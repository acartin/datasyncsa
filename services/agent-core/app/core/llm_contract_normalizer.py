from __future__ import annotations

from typing import Any


def _unwrap_dict(raw: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, dict):
            return value
    return raw


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
                if fixed.get("top_k") is not None:
                    rag_payload["top_k"] = fixed.get("top_k")
                if fixed.get("filter_doc_type") is not None:
                    rag_payload["filter_doc_type"] = fixed.get("filter_doc_type")
                if rag_payload:
                    fixed["rag"] = rag_payload
            if tool_name == "realtor_sql" and "realtor_slots" not in fixed:
                if isinstance(fixed.get("slots"), dict):
                    fixed["realtor_slots"] = fixed.get("slots")
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
