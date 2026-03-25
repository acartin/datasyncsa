"""Reference resolution node."""

from __future__ import annotations

from typing import Any

from services.ai_runtime.config.prompt_composer import compose
from services.ai_runtime.domain.contracts import Property, ReferenceDecision
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import BaseGraphState


def _select_reference_candidate(items: list[Property], decision: ReferenceDecision) -> Property | None:
    if not items:
        return None
    if decision.kind == "ORDINAL" and decision.ordinal_index:
        index = decision.ordinal_index - 1
        return items[index] if 0 <= index < len(items) else None
    if decision.kind == "BY_ATTRIBUTE":
        key = (decision.attribute_key or "").lower()
        if key == "cheapest":
            return min(items, key=lambda item: item.price)
        if key == "largest":
            return max(items, key=lambda item: item.features.sqm_clean or 0)
        if key == "featured":
            featured = [item for item in items if item.features.is_featured]
            return featured[0] if featured else None
    if decision.kind == "CONTEXT_LOCATION" and decision.location_hint:
        needle = decision.location_hint.lower()
        for item in items:
            province = (item.location.province or "").lower()
            address = (item.address or "").lower()
            if needle in province or needle in address:
                return item
    return None


async def resolve_references(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    """Classify references with the LLM and resolve them to concrete entities in code."""

    graph_state = BaseGraphState.model_validate(state)
    prompt = compose(
        "reference_classifier",
        graph_state.tenant_config,
        graph_state.vertical,
        {
            "message": graph_state.messages[-1].model_dump(mode="json"),
            "last_mentioned": getattr(graph_state, "last_mentioned", None),
            "last_search_results": [item.model_dump(mode="json") for item in getattr(graph_state, "last_search_results", [])],
            "history_scope": {"client_id": graph_state.client_id, "user_id": graph_state.user_id},
        },
        include_tone=False,
    )
    decision = await deps.llm.classify_reference(prompt)
    if decision.kind == "NONE":
        return {"resolved_references": [], "pending_clarification": None}
    if decision.kind == "AMBIGUOUS" or decision.confidence < 0.7:
        return {
            "resolved_references": [],
            "pending_clarification": decision.clarification_target or "cual elemento queres decir",
        }

    items = [Property.model_validate(item) for item in state.get("last_search_results", [])]
    if not items:
        items = [Property.model_validate(item) for item in state.get("inventory", [])]
    has_session_reference_context = bool(items or state.get("last_mentioned"))

    if decision.kind in {"ORDINAL", "LAST_MENTIONED", "BY_ATTRIBUTE", "CONTEXT_LOCATION"} and not has_session_reference_context:
        return {"resolved_references": [], "pending_clarification": None}

    if decision.kind == "LAST_MENTIONED" and state.get("last_mentioned"):
        property_item = Property.model_validate(state["last_mentioned"])
        return {
            "resolved_references": [{"kind": "property", "property_id_internal": property_item.property_id_internal}],
            "pending_clarification": None,
        }

    if decision.kind == "ANAPHORIC_HISTORY":
        history = await deps.conversation_repository.load_history(
            client_id=graph_state.client_id,
            user_id=graph_state.user_id,
            limit=5,
        )
        if history:
            return {
                "resolved_references": [{"kind": "history", "history_items": history}],
                "pending_clarification": None,
            }
        return {
            "resolved_references": [],
            "pending_clarification": decision.clarification_target or "a cual conversacion previa te referis",
        }

    candidate = _select_reference_candidate(items, decision)
    if candidate:
        return {
            "resolved_references": [{"kind": "property", "property_id_internal": candidate.property_id_internal}],
            "pending_clarification": None,
        }
    return {
        "resolved_references": [],
        "pending_clarification": decision.clarification_target or "me ayudas a ubicar la referencia exacta",
    }
