"""Single-pass conversational turn analysis."""

from __future__ import annotations

import re
from typing import Any

from services.ai_runtime.config.prompt_composer import compose
from services.ai_runtime.domain.contracts import (
    IntentDefinition,
    IntentPlanItem,
    Property,
    ReferenceDecision,
    TurnAnalysis,
)
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import BaseGraphState, RealtorGraphState, SearchFilters
from services.ai_runtime.graph.realtor.turn_policies import (
    REALTOR_INTERNAL_INTENTS,
    apply_realtor_turn_policies,
    build_realtor_fallback_intent_plan,
    derive_realtor_pending_decision,
    merge_realtor_filters,
)

MEMORY_QUERY_PATTERN = re.compile(
    r"\b(como me llamo|cual es mi nombre|que edad tengo|cuantos anos tengo|cual era mi presupuesto|que presupuesto te dije|cual es mi correo|cual es mi email|cual es mi telefono|cual es mi numero|record[aá]s|recuerdas|te acord[aá]s)\b",
    flags=re.IGNORECASE,
)
MEMORY_STATEMENT_PATTERN = re.compile(
    r"\b(me llamo|mi nombre es|soy\s+[A-Za-zÁÉÍÓÚáéíóúÑñ]+|tengo\s+\d{1,3}\s+a(?:ñ|n)os|mi correo es|mi email es|mi telefono es|mi teléfono es|mi numero es|mi número es|mi presupuesto es)\b",
    flags=re.IGNORECASE,
)
SHORT_NAME_STATEMENT_PATTERN = re.compile(
    r"^\s*(?:con|soy)\s+[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ'`.-]+(?:\s+[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ'`.-]+){0,3}\s*[\.\!\?]?\s*$"
)
VISIBLE_ORDINAL_PATTERNS = (
    (re.compile(r"\b(la|el)\s+primer[oa]\b", flags=re.IGNORECASE), 1),
    (re.compile(r"\b(la|el)\s+segund[oa]\b", flags=re.IGNORECASE), 2),
    (re.compile(r"\b(la|el)\s+tercer[oa]\b", flags=re.IGNORECASE), 3),
    (re.compile(r"\b(la|el)\s+cuart[oa]\b", flags=re.IGNORECASE), 4),
)


def _load_properties(raw_items: list[dict[str, Any]] | list[Property] | None) -> list[Property]:
    return [Property.model_validate(item) for item in raw_items or []]


def _visible_reference_items(graph_state: BaseGraphState) -> list[Property]:
    visible_ids = [str(item) for item in getattr(graph_state, "cards_shown", []) if item]
    if not visible_ids:
        return []
    search_items = _load_properties(getattr(graph_state, "last_search_results", []))
    inventory_items = _load_properties(getattr(graph_state, "inventory", []))
    by_id = {item.id: item for item in [*search_items, *inventory_items]}
    return [by_id[item_id] for item_id in visible_ids if item_id in by_id]


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


async def _resolve_reference(
    graph_state: BaseGraphState,
    decision: ReferenceDecision,
    deps: GraphDependencies,
) -> tuple[list[dict[str, Any]], str | None]:
    if decision.kind == "NONE":
        return [], None
    if decision.kind == "AMBIGUOUS" or decision.confidence < 0.7:
        return [], decision.clarification_target or "me ayudas a ubicar la referencia exacta"

    visible_items = _visible_reference_items(graph_state)
    search_items = _load_properties(getattr(graph_state, "last_search_results", []))
    inventory_items = _load_properties(getattr(graph_state, "inventory", []))
    fallback_items = search_items or inventory_items
    has_session_reference_context = bool(visible_items or fallback_items or getattr(graph_state, "last_mentioned", None))

    if decision.kind == "LAST_MENTIONED" and getattr(graph_state, "last_mentioned", None):
        property_item = Property.model_validate(graph_state.last_mentioned)
        return [{"kind": "property", "property_id": property_item.id}], None

    if decision.kind == "ANAPHORIC_HISTORY":
        history = await deps.conversation_repository.load_history(
            client_id=graph_state.client_id,
            user_id=graph_state.user_id,
            limit=5,
        )
        if history:
            return [{"kind": "history", "history_items": history}], None
        return [], decision.clarification_target or "a cual conversacion previa te referis"

    if decision.kind in {"ORDINAL", "LAST_MENTIONED", "BY_ATTRIBUTE", "CONTEXT_LOCATION"} and not has_session_reference_context:
        return [], decision.clarification_target or "me ayudas a ubicar la referencia exacta"

    if visible_items and decision.kind in {"ORDINAL", "BY_ATTRIBUTE", "CONTEXT_LOCATION"}:
        candidate = _select_reference_candidate(visible_items, decision)
        if candidate:
            return [{"kind": "property", "property_id": candidate.id}], None
        return [], decision.clarification_target or "me ayudas a ubicar cual de las opciones visibles queres decir"

    candidate = _select_reference_candidate(fallback_items, decision)
    if candidate:
        return [{"kind": "property", "property_id": candidate.id}], None
    return [], decision.clarification_target or "me ayudas a ubicar la referencia exacta"


def _fallback_intent_plan(
    graph_state: BaseGraphState,
    analysis: TurnAnalysis,
    *,
    resolved_references: list[dict[str, Any]],
) -> list[IntentPlanItem]:
    if analysis.intent_plan:
        return list(analysis.intent_plan)

    has_property_reference = any(item.get("kind") == "property" for item in resolved_references)
    if analysis.dialogue_act in {"select_result", "ask_detail"} and has_property_reference:
        return [
            IntentPlanItem(
                type="focus_property",
                priority=1,
                depends_on=[],
                condition={"requires_reference": "resolved_property"},
                skip_if_failed=False,
            )
        ]

    if isinstance(graph_state, RealtorGraphState):
        return build_realtor_fallback_intent_plan(graph_state, analysis)
    return []


def _internal_intents_for_state(graph_state: BaseGraphState) -> set[str]:
    if isinstance(graph_state, RealtorGraphState):
        return set(REALTOR_INTERNAL_INTENTS)
    return set()


def _build_intent_queue(
    graph_state: BaseGraphState,
    analysis: TurnAnalysis,
    *,
    resolved_references: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    allowed_types = set(graph_state.capabilities) | _internal_intents_for_state(graph_state)
    ordered_plan = sorted(
        _fallback_intent_plan(graph_state, analysis, resolved_references=resolved_references),
        key=lambda item: item.priority,
    )[:4]
    normalized_plan = [item for item in ordered_plan if item.type in allowed_types]

    queue: list[IntentDefinition] = []
    ids_by_type: dict[str, str] = {}
    for index, item in enumerate(normalized_plan, start=1):
        intent_id = f"turn-{graph_state.current_turn:04d}-intent-{index:02d}-{item.type}"
        queue.append(
            IntentDefinition(
                id=intent_id,
                type=item.type,
                priority=item.priority,
                depends_on=[ids_by_type[name] for name in item.depends_on if name in ids_by_type],
                condition=item.condition,
                skip_if_failed=item.skip_if_failed,
                status="pending",
                output=None,
            )
        )
        ids_by_type.setdefault(item.type, intent_id)
    return [intent.model_dump(mode="json") for intent in queue]


def _sanitize_analysis(message: str, analysis: TurnAnalysis) -> TurnAnalysis:
    normalized_message = (message or "").strip()
    if analysis.dialogue_act in {"new_search", "refine_search"} and analysis.reference.kind == "CONTEXT_LOCATION":
        return analysis.model_copy(
            update={
                "reference": ReferenceDecision(kind="NONE", confidence=analysis.reference.confidence),
            }
        )
    if analysis.dialogue_act == "lead_capture" and analysis.memory_lookup_key:
        return analysis.model_copy(update={"memory_lookup_key": None})
    if not analysis.memory_lookup_key:
        return analysis
    if MEMORY_QUERY_PATTERN.search(normalized_message):
        return analysis
    if MEMORY_STATEMENT_PATTERN.search(normalized_message) or SHORT_NAME_STATEMENT_PATTERN.search(normalized_message):
        return analysis.model_copy(
            update={
                "dialogue_act": "lead_capture",
                "memory_lookup_key": None,
            }
        )
    return analysis


def _visible_ordinal_index(message: str, visible_count: int) -> int | None:
    if visible_count <= 0:
        return None
    normalized = (message or "").strip()
    if not normalized:
        return None
    if re.search(r"\bpen[úu]ltim[oa]\b", normalized, flags=re.IGNORECASE) and visible_count >= 2:
        return visible_count - 1
    if re.search(r"\b(la|el)\s+[úu]ltim[oa]\b", normalized, flags=re.IGNORECASE):
        return visible_count
    for pattern, ordinal in VISIBLE_ORDINAL_PATTERNS:
        if pattern.search(normalized):
            return ordinal if ordinal <= visible_count else None
    return None


def _normalize_visible_reference_scope(graph_state: BaseGraphState, analysis: TurnAnalysis) -> TurnAnalysis:
    visible_count = len(getattr(graph_state, "cards_shown", []) or [])
    if visible_count <= 0:
        return analysis
    reference = analysis.reference if isinstance(analysis.reference, ReferenceDecision) else ReferenceDecision.model_validate(analysis.reference)
    if reference.kind != "ORDINAL":
        return analysis
    normalized_ordinal = _visible_ordinal_index(graph_state.messages[-1].content, visible_count)
    if normalized_ordinal is None:
        return analysis
    return analysis.model_copy(
        update={
            "reference": reference.model_copy(update={"ordinal_index": normalized_ordinal}),
        }
    )


async def analyze_turn(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    """Analyze the full turn once, then let deterministic code normalize and route the result."""

    graph_state = (
        RealtorGraphState.model_validate(state)
        if state.get("vertical") == "realtor"
        else BaseGraphState.model_validate(state)
    )
    result_snapshots = []
    for item in getattr(graph_state, "last_search_results", [])[:6]:
        result_snapshots.append(
            {
                "id": item.id,
                "title": item.title,
                "price": item.price,
                "currency": item.currency,
                "province": item.location.province,
                "bedrooms_clean": item.features.bedrooms_clean,
                "bathrooms_clean": item.features.bathrooms_clean,
                "garage_clean": item.features.garage_clean,
                "sqm_clean": item.features.sqm_clean,
            }
        )
    last_mentioned = getattr(graph_state, "last_mentioned", None)
    last_mentioned_snapshot = (
        {
            "id": last_mentioned.id,
            "title": last_mentioned.title,
            "price": last_mentioned.price,
            "currency": last_mentioned.currency,
            "province": last_mentioned.location.province,
            "garage_clean": last_mentioned.features.garage_clean,
        }
        if last_mentioned
        else None
    )
    visible_result_snapshots = []
    for item in _visible_reference_items(graph_state)[:6]:
        visible_result_snapshots.append(
            {
                "id": item.id,
                "title": item.title,
                "price": item.price,
                "currency": item.currency,
                "province": item.location.province,
                "bedrooms_clean": item.features.bedrooms_clean,
                "bathrooms_clean": item.features.bathrooms_clean,
                "garage_clean": item.features.garage_clean,
                "sqm_clean": item.features.sqm_clean,
            }
        )
    recent_messages = [message.model_dump(mode="json") for message in graph_state.messages[-8:]]
    prompt = compose(
        "analyze_turn",
        graph_state.tenant_config,
        graph_state.vertical,
        {
            "message": graph_state.messages[-1].model_dump(mode="json"),
            "recent_messages": recent_messages,
            "last_assistant_message": next(
                (message.model_dump(mode="json") for message in reversed(graph_state.messages[:-1]) if message.role == "assistant"),
                None,
            ),
            "last_turn_dialogue_act": graph_state.last_turn_dialogue_act,
            "last_turn_output_types": list(graph_state.last_turn_output_types or []),
            "last_turn_search_summary": graph_state.last_turn_search_summary,
            "capabilities": graph_state.capabilities,
            "current_filters": getattr(graph_state, "search_filters", SearchFilters()).model_dump(mode="json"),
            "cards_shown": list(getattr(graph_state, "cards_shown", []) or []),
            "visible_cards": visible_result_snapshots,
            "last_search_results": result_snapshots,
            "last_mentioned": last_mentioned_snapshot,
            "memory_summary": {
                "entities": [item.model_dump(mode="json") for item in graph_state.memory.entities[-8:]],
                "lead_extracted": graph_state.lead_advisor.lead_extracted.model_dump(mode="json"),
            },
        },
        include_tone=False,
    )
    analysis = _sanitize_analysis(graph_state.messages[-1].content, await deps.llm.analyze_turn(prompt))
    analysis = _normalize_visible_reference_scope(graph_state, analysis)
    compare_target_ids: list[str] = []
    pending_decision = None
    if isinstance(graph_state, RealtorGraphState):
        analysis, compare_target_ids = apply_realtor_turn_policies(graph_state, analysis)
        pending_decision = derive_realtor_pending_decision(graph_state, analysis)
    decision = analysis.reference if isinstance(analysis.reference, ReferenceDecision) else ReferenceDecision.model_validate(analysis.reference)
    resolved_references, clarification_target = await _resolve_reference(graph_state, decision, deps)
    if compare_target_ids:
        resolved_references = [
            {"kind": "property", "property_id": property_id}
            for property_id in compare_target_ids
        ]
        clarification_target = None

    pending_clarification = analysis.clarification_target if analysis.needs_clarification else None
    if clarification_target:
        pending_clarification = clarification_target

    updates: dict[str, Any] = {
        "turn_analysis": analysis.model_dump(mode="json"),
        "resolved_references": resolved_references,
        "pending_clarification": pending_clarification,
        "pending_decision": pending_decision.model_dump(mode="json") if pending_decision else None,
        "intent_queue": [],
        "active_intent": None,
    }
    if compare_target_ids:
        updates["active_comparison"] = compare_target_ids
    if not pending_clarification and not pending_decision:
        updates["intent_queue"] = _build_intent_queue(
            graph_state,
            analysis,
            resolved_references=resolved_references,
        )

    if isinstance(graph_state, RealtorGraphState) and analysis.dialogue_act in {"new_search", "refine_search"}:
        updates["search_filters"] = await merge_realtor_filters(graph_state, analysis, deps)
        if any(intent.get("type") == "buscar" for intent in updates["intent_queue"]):
            updates["search_attempts"] = 0
    return updates
