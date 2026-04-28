"""Single-pass conversational turn analysis."""

from __future__ import annotations

import re
from typing import Any

from services.ai_runtime.config.prompt_composer import compose
from services.ai_runtime.domain.contracts import (
    IntentDefinition,
    IntentPlanItem,
    ReferenceDecision,
    TurnAnalysis,
)
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import BaseGraphState
from services.ai_runtime.graph._shared.prompt_context import (
    summarize_message_for_prompt,
    summarize_messages_for_prompt,
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


def _policy_for_state(graph_state: BaseGraphState):
    from services.ai_runtime.verticals import get_vertical_spec

    return get_vertical_spec(graph_state.vertical).policy


def _item_id(item: dict[str, Any] | None) -> str:
    if not item:
        return ""
    return str(item.get("id") or "").strip()


def _coerce_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _item_price(item: dict[str, Any]) -> float:
    return _coerce_float(item.get("price"))


def _item_area(item: dict[str, Any]) -> float:
    return _coerce_float(item.get("area") or item.get("sqm_clean"))


def _item_is_featured(item: dict[str, Any]) -> bool:
    return bool(item.get("is_featured"))


def _item_matches_location(item: dict[str, Any], needle: str) -> bool:
    province = str(item.get("province") or "").lower()
    address = str(item.get("address") or "").lower()
    return needle in province or needle in address


def _select_reference_candidate(items: list[dict[str, Any]], decision: ReferenceDecision) -> dict[str, Any] | None:
    if not items:
        return None
    if decision.kind == "ORDINAL" and decision.ordinal_index:
        index = decision.ordinal_index - 1
        return items[index] if 0 <= index < len(items) else None
    if decision.kind == "BY_ATTRIBUTE":
        key = (decision.attribute_key or "").lower()
        if key == "cheapest":
            return min(items, key=_item_price)
        if key == "largest":
            return max(items, key=_item_area)
        if key == "featured":
            featured = [item for item in items if _item_is_featured(item)]
            return featured[0] if featured else None
    if decision.kind == "CONTEXT_LOCATION" and decision.location_hint:
        needle = decision.location_hint.lower()
        for item in items:
            if _item_matches_location(item, needle):
                return item
    return None


def _single_reference_resolution(
    visible_items: list[dict[str, Any]],
    focused_entity: dict[str, Any] | None,
) -> list[dict[str, Any]] | None:
    if len(visible_items) == 1:
        property_id = _item_id(visible_items[0])
        if property_id:
            return [{"kind": "property", "property_id": property_id}]
    focused_id = _item_id(focused_entity)
    if focused_id:
        return [{"kind": "property", "property_id": focused_id}]
    return None


async def _resolve_reference(
    graph_state: BaseGraphState,
    decision: ReferenceDecision,
    deps: GraphDependencies,
) -> tuple[list[dict[str, Any]], str | None]:
    policy = _policy_for_state(graph_state)
    visible_items = policy.resolve_visible_reference_items(graph_state)
    fallback_items = policy.resolve_reference_candidates(graph_state)
    focused_entity = policy.snapshot_focused_entity(graph_state)
    has_session_reference_context = bool(visible_items or fallback_items or focused_entity)
    single_reference = _single_reference_resolution(visible_items, focused_entity)

    if decision.kind == "NONE":
        return [], None
    if decision.kind == "AMBIGUOUS" or decision.confidence < 0.7:
        if single_reference:
            return single_reference, None
        return [], decision.clarification_target or "me ayudas a ubicar la referencia exacta"

    if decision.kind == "LAST_MENTIONED" and focused_entity:
        entity_id = _item_id(focused_entity)
        if entity_id:
            return [{"kind": "property", "property_id": entity_id}], None

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
            return [{"kind": "property", "property_id": _item_id(candidate)}], None
        if single_reference:
            return single_reference, None
        return [], decision.clarification_target or "me ayudas a ubicar cual de las opciones visibles queres decir"

    candidate = _select_reference_candidate(fallback_items, decision)
    if candidate:
        return [{"kind": "property", "property_id": _item_id(candidate)}], None
    if single_reference:
        return single_reference, None
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

    return list(_policy_for_state(graph_state).build_fallback_intent_plan(graph_state, analysis))


def _internal_intents_for_state(graph_state: BaseGraphState) -> set[str]:
    return set(_policy_for_state(graph_state).internal_intents())


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
    visible_count = len(_policy_for_state(graph_state).resolve_visible_reference_items(graph_state))
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


def _latest_user_metadata(graph_state: BaseGraphState) -> dict[str, Any]:
    if not graph_state.messages:
        return {}
    latest = graph_state.messages[-1]
    if getattr(latest, "role", None) != "user":
        return {}
    metadata = getattr(latest, "metadata", None)
    return dict(metadata or {})


async def analyze_turn(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    """Analyze the full turn once, then let deterministic code normalize and route the result."""

    from services.ai_runtime.verticals import get_vertical_spec

    vertical_spec = get_vertical_spec(state.get("vertical"))
    graph_state = vertical_spec.state_model.model_validate(state)
    policy = vertical_spec.policy
    quick_action_turn = policy.handle_quick_action(graph_state, _latest_user_metadata(graph_state))
    if quick_action_turn is not None:
        updates: dict[str, Any] = {
            "turn_analysis": quick_action_turn.analysis.model_dump(mode="json"),
            "resolved_references": list(quick_action_turn.resolved_references),
            "pending_clarification": None,
            "pending_decision": (
                quick_action_turn.pending_decision.model_dump(mode="json")
                if quick_action_turn.pending_decision
                else None
            ),
            "intent_queue": [],
            "active_intent": None,
        }
        if quick_action_turn.lead_advisor is not None:
            updates["lead_advisor"] = quick_action_turn.lead_advisor
        if quick_action_turn.cita is not None:
            updates["cita"] = quick_action_turn.cita
        if not quick_action_turn.pending_decision:
            updates["intent_queue"] = _build_intent_queue(
                graph_state,
                quick_action_turn.analysis,
                resolved_references=quick_action_turn.resolved_references,
            )
        return updates

    current_filters = policy.snapshot_search_context(graph_state)
    visible_result_snapshots = list(policy.resolve_visible_reference_items(graph_state)[:6])
    result_snapshots = list(policy.resolve_reference_candidates(graph_state)[:6])
    focused_entity_snapshot = policy.snapshot_focused_entity(graph_state)
    visible_reference_ids = [_item_id(item) for item in visible_result_snapshots if _item_id(item)]
    recent_messages = summarize_messages_for_prompt(graph_state.messages, limit=8)
    prompt = compose(
        "analyze_turn",
        graph_state.tenant_config,
        graph_state.vertical,
        {
            "message": summarize_message_for_prompt(graph_state.messages[-1]),
            "recent_messages": recent_messages,
            "last_assistant_message": next(
                (summarize_message_for_prompt(message) for message in reversed(graph_state.messages[:-1]) if message.role == "assistant"),
                None,
            ),
            "last_turn_dialogue_act": graph_state.last_turn_dialogue_act,
            "last_turn_output_types": list(graph_state.last_turn_output_types or []),
            "last_turn_search_summary": graph_state.last_turn_search_summary,
            "capabilities": graph_state.capabilities,
            "search_context": current_filters,
            "visible_reference_ids": visible_reference_ids,
            "visible_reference_items": visible_result_snapshots,
            "reference_candidates": result_snapshots,
            "focused_entity": focused_entity_snapshot,
            "memory_summary": {
                "entities": [item.model_dump(mode="json") for item in graph_state.memory.entities[-8:]],
                "lead_extracted": graph_state.lead_advisor.lead_extracted.model_dump(mode="json"),
            },
        },
        include_tone=False,
    )
    analysis = _sanitize_analysis(graph_state.messages[-1].content, await deps.llm.analyze_turn(prompt))
    analysis = _normalize_visible_reference_scope(graph_state, analysis)
    analysis, compare_target_ids = policy.apply_turn_policies(graph_state, analysis)
    pending_decision = policy.derive_pending_decision(graph_state, analysis)
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

    if analysis.dialogue_act in {"new_search", "refine_search"}:
        merged_filters = await policy.merge_filters(graph_state, analysis, deps)
        if merged_filters is not None:
            updates["search_filters"] = merged_filters
            if any(intent.get("type") == "buscar" for intent in updates["intent_queue"]):
                updates["search_attempts"] = 0
    return updates
