"""Extract and normalize realtor search filters before SQL translation."""

from __future__ import annotations

from typing import Any

from services.ai_runtime.config.prompt_composer import compose
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import RealtorGraphState, SearchFilters


def _normalize_value(value: Any) -> Any:
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned.lower() in {"", "null", "none", "n/a"}:
            return None
        return cleaned
    if isinstance(value, list):
        normalized_items: list[Any] = []
        for item in value:
            normalized = _normalize_value(item)
            if normalized is not None:
                normalized_items.append(normalized)
        return normalized_items
    return value


def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in payload.items():
        normalized[key] = _normalize_value(value)
    return normalized


async def extract_search_filters(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    graph_state = RealtorGraphState.model_validate(state)
    prompt = compose(
        "search_filter_extractor",
        graph_state.tenant_config,
        graph_state.vertical,
        {
            "message": graph_state.messages[-1].content,
            "current_filters": graph_state.search_filters.model_dump(mode="json"),
            "resolved_references": graph_state.resolved_references,
        },
        include_tone=False,
    )
    extracted = await deps.llm.extract_search_filters(prompt)
    payload = extracted.get("search_filters") if isinstance(extracted, dict) else {}
    if not isinstance(payload, dict):
        payload = {}

    current_filters = graph_state.search_filters.model_dump(mode="json")
    merged_filters = {**current_filters}
    for key, value in _normalize_payload(payload).items():
        if key in current_filters:
            merged_filters[key] = value

    normalized_filters = SearchFilters.model_validate(merged_filters)
    return {
        "search_filters": normalized_filters.model_dump(mode="json"),
        "search_attempts": 0,
    }
