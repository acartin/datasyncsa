"""Single-pass conversational turn analysis."""

from __future__ import annotations

import re
from typing import Any

from services.ai_runtime.config.prompt_composer import compose
from services.ai_runtime.domain.contracts import (
    IntentDefinition,
    IntentPlanItem,
    PendingDecision,
    ReferenceDecision,
    TurnAnalysis,
)
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import BaseGraphState, build_lead_advisor_state
from services.ai_runtime.graph._shared.prompt_context import summarize_message_for_prompt, summarize_messages_for_prompt

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


def _coerce_property_dict(raw_item: Any) -> dict[str, Any] | None:
    if raw_item is None:
        return None
    if isinstance(raw_item, dict):
        return raw_item
    model_dump = getattr(raw_item, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json")
    return None


def _load_properties(raw_items: list[Any] | None) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for raw_item in raw_items or []:
        item = _coerce_property_dict(raw_item)
        if item:
            items.append(item)
    return items


def _prop_get(item: dict[str, Any], *path: str) -> Any:
    current: Any = item
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _prop_id(item: dict[str, Any]) -> str:
    return str(item.get("id") or "").strip()


def _prop_price(item: dict[str, Any]) -> float:
    try:
        return float(item.get("price") or 0)
    except (TypeError, ValueError):
        return 0.0


def _prop_area(item: dict[str, Any]) -> float:
    try:
        return float(_prop_get(item, "features", "sqm_clean") or 0)
    except (TypeError, ValueError):
        return 0.0


def _prop_is_featured(item: dict[str, Any]) -> bool:
    return bool(_prop_get(item, "features", "is_featured"))


def _property_snapshot(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "price": item.get("price"),
        "currency": item.get("currency"),
        "province": _prop_get(item, "location", "province"),
        "bedrooms_clean": _prop_get(item, "features", "bedrooms_clean"),
        "bathrooms_clean": _prop_get(item, "features", "bathrooms_clean"),
        "garage_clean": _prop_get(item, "features", "garage_clean"),
        "sqm_clean": _prop_get(item, "features", "sqm_clean"),
    }


def _dump_search_filters(graph_state: BaseGraphState) -> dict[str, Any]:
    raw_filters = getattr(graph_state, "search_filters", None)
    if raw_filters is None:
        return {}
    if isinstance(raw_filters, dict):
        return raw_filters
    model_dump = getattr(raw_filters, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json")
    return {}


def _visible_reference_items(graph_state: BaseGraphState) -> list[dict[str, Any]]:
    visible_ids = [str(item) for item in getattr(graph_state, "cards_shown", []) if item]
    if not visible_ids:
        return []
    search_items = _load_properties(getattr(graph_state, "last_search_results", []))
    inventory_items = _load_properties(getattr(graph_state, "inventory", []))
    by_id = {_prop_id(item): item for item in [*search_items, *inventory_items] if _prop_id(item)}
    return [by_id[item_id] for item_id in visible_ids if item_id in by_id]


def _select_reference_candidate(items: list[dict[str, Any]], decision: ReferenceDecision) -> dict[str, Any] | None:
    if not items:
        return None
    if decision.kind == "ORDINAL" and decision.ordinal_index:
        index = decision.ordinal_index - 1
        return items[index] if 0 <= index < len(items) else None
    if decision.kind == "BY_ATTRIBUTE":
        key = (decision.attribute_key or "").lower()
        if key == "cheapest":
            return min(items, key=_prop_price)
        if key == "largest":
            return max(items, key=_prop_area)
        if key == "featured":
            featured = [item for item in items if _prop_is_featured(item)]
            return featured[0] if featured else None
    if decision.kind == "CONTEXT_LOCATION" and decision.location_hint:
        needle = decision.location_hint.lower()
        for item in items:
            province = str(_prop_get(item, "location", "province") or "").lower()
            address = str(item.get("address") or "").lower()
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
        last_mentioned = _coerce_property_dict(getattr(graph_state, "last_mentioned", None))
        property_id = _prop_id(last_mentioned or {})
        if property_id:
            return [{"kind": "property", "property_id": property_id}], None

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
            return [{"kind": "property", "property_id": _prop_id(candidate)}], None
        return [], decision.clarification_target or "me ayudas a ubicar cual de las opciones visibles queres decir"

    candidate = _select_reference_candidate(fallback_items, decision)
    if candidate:
        return [{"kind": "property", "property_id": _prop_id(candidate)}], None
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


def _latest_user_metadata(graph_state: BaseGraphState) -> dict[str, Any]:
    if not graph_state.messages:
        return {}
    latest = graph_state.messages[-1]
    if getattr(latest, "role", None) != "user":
        return {}
    metadata = getattr(latest, "metadata", None)
    return dict(metadata or {})


def _single_intent(
    intent_type: str,
    *,
    condition: dict[str, Any] | None = None,
) -> list[IntentPlanItem]:
    return [
        IntentPlanItem(
            type=intent_type,
            priority=1,
            depends_on=[],
            condition=condition,
            skip_if_failed=False,
        )
    ]


def _property_references_from_quick_action(
    graph_state: BaseGraphState,
    metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    candidate_ids: list[str] = []
    for key in ("target_property_id", "property_id"):
        value = str(metadata.get(key) or "").strip()
        if value:
            candidate_ids.append(value)

    if not candidate_ids:
        last_mentioned = _coerce_property_dict(getattr(graph_state, "last_mentioned", None))
        property_id = _prop_id(last_mentioned or {})
        if property_id:
            candidate_ids.append(property_id)

    if not candidate_ids:
        visible_items = _visible_reference_items(graph_state)
        if visible_items:
            candidate_ids.append(_prop_id(visible_items[0]))

    if not candidate_ids:
        search_items = _load_properties(getattr(graph_state, "last_search_results", []))
        if search_items:
            candidate_ids.append(_prop_id(search_items[0]))

    references: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate_id in candidate_ids:
        normalized = str(candidate_id or "").strip()
        if not normalized or normalized in seen:
            continue
        references.append({"kind": "property", "property_id": normalized})
        seen.add(normalized)
    return references


def _lead_advisor_with_positive_intent(graph_state: BaseGraphState) -> dict[str, Any] | None:
    current_intent = str(graph_state.lead_advisor.lead_extracted.appointment_intent or "").strip().lower()
    if current_intent == "positive":
        return None
    updated_extracted = graph_state.lead_advisor.lead_extracted.model_copy(
        update={"appointment_intent": "positive"}
    )
    updated_advisor = graph_state.lead_advisor.model_copy(update={"lead_extracted": updated_extracted})
    return build_lead_advisor_state(
        graph_state.tenant_config,
        updated_advisor,
    ).model_dump(mode="json")


def _schedule_cita_update(
    graph_state: BaseGraphState,
    references: list[dict[str, Any]],
) -> dict[str, Any] | None:
    property_id = next(
        (
            str(item.get("property_id") or "").strip()
            for item in references
            if item.get("kind") == "property" and str(item.get("property_id") or "").strip()
        ),
        "",
    )
    cita_updates: dict[str, Any] = {}
    if not str(graph_state.cita.tipo or "").strip():
        cita_updates["tipo"] = "visita"
    if property_id and not str(graph_state.cita.propiedad_id or "").strip():
        cita_updates["propiedad_id"] = property_id
    if not cita_updates:
        return None
    return graph_state.cita.model_copy(update=cita_updates).model_dump(mode="json")


def _quick_action_turn(graph_state: BaseGraphState) -> dict[str, Any] | None:
    metadata = _latest_user_metadata(graph_state)
    action_id = str(metadata.get("action_id") or "").strip().lower()
    if not action_id:
        return None

    default_reference = ReferenceDecision(kind="NONE", confidence=1.0)
    property_references = _property_references_from_quick_action(graph_state, metadata)

    if action_id == "interest_yes":
        return {
            "analysis": TurnAnalysis(
                dialogue_act="select_result",
                confidence=1.0,
                reference=default_reference,
                intent_plan=_single_intent("focus_property", condition={"requires_reference": "resolved_property"}),
            ),
            "resolved_references": property_references,
            "pending_decision": None,
            "lead_advisor": _lead_advisor_with_positive_intent(graph_state),
            "cita": None,
        }

    if action_id == "show_next":
        return {
            "analysis": TurnAnalysis(
                dialogue_act="confirm_previous",
                confidence=1.0,
                reference=default_reference,
                intent_plan=_single_intent("show_result_cards", condition={"min_search_results": 1}),
                reuse_current_filters=True,
            ),
            "resolved_references": [],
            "pending_decision": None,
            "lead_advisor": None,
            "cita": None,
        }

    if action_id == "schedule_visit":
        return {
            "analysis": TurnAnalysis(
                dialogue_act="schedule",
                confidence=1.0,
                reference=default_reference,
                intent_plan=_single_intent("agendar"),
            ),
            "resolved_references": property_references,
            "pending_decision": None,
            "lead_advisor": _lead_advisor_with_positive_intent(graph_state),
            "cita": _schedule_cita_update(graph_state, property_references),
        }

    if action_id == "ask_financing":
        return {
            "analysis": TurnAnalysis(
                dialogue_act="calculate",
                confidence=1.0,
                reference=default_reference,
                intent_plan=_single_intent("calcular"),
            ),
            "resolved_references": property_references,
            "pending_decision": None,
            "lead_advisor": None,
            "cita": None,
        }

    if action_id == "human_handoff":
        return {
            "analysis": TurnAnalysis(
                dialogue_act="lead_capture",
                confidence=1.0,
                reference=default_reference,
                intent_plan=_single_intent("escalar"),
            ),
            "resolved_references": property_references,
            "pending_decision": None,
            "lead_advisor": _lead_advisor_with_positive_intent(graph_state),
            "cita": None,
        }

    refinement_questions = {
        "reject_current": (
            "quick_refine_choice",
            "Perfecto. ¿Qué querés ajustar primero: precio, zona o tipo de propiedad?",
            ["precio", "zona", "tipo de propiedad"],
        ),
        "ask_price": (
            "quick_refine_price",
            "Perfecto. ¿Qué presupuesto máximo te gustaría manejar?",
            [],
        ),
        "ask_zone": (
            "quick_refine_zone",
            "Claro. ¿Qué zona te gustaría explorar ahora?",
            [],
        ),
        "ask_property_type": (
            "quick_refine_type",
            "Perfecto. ¿Qué tipo de propiedad preferís ver?",
            [],
        ),
        "ask_size_needs": (
            "quick_refine_size",
            "Claro. ¿Buscás más habitaciones, más baños o más metros cuadrados?",
            [],
        ),
        "ask_budget_fit": (
            "quick_refine_budget_fit",
            "Entiendo. ¿Hasta qué monto te gustaría bajar el presupuesto?",
            [],
        ),
        "ask_upgrade": (
            "quick_refine_upgrade",
            "Perfecto. ¿Querés subir presupuesto, ver más metros o más habitaciones?",
            [],
        ),
        "ask_features": (
            "quick_refine_features",
            "Claro. ¿Qué querés mantener sí o sí en la siguiente opción: zona, presupuesto o habitaciones?",
            ["zona", "presupuesto", "habitaciones"],
        ),
        "save_followup": (
            "quick_followup_contact",
            "Perfecto. ¿A qué correo o WhatsApp te la envío luego?",
            [],
        ),
    }
    if action_id in refinement_questions:
        kind, question, options = refinement_questions[action_id]
        return {
            "analysis": TurnAnalysis(
                dialogue_act="refine_search",
                confidence=1.0,
                reference=default_reference,
            ),
            "resolved_references": property_references,
            "pending_decision": PendingDecision(
                kind=kind,
                question=question,
                options=options,
                metadata={"source": "quick_action", "action_id": action_id},
            ),
            "lead_advisor": None,
            "cita": None,
        }

    return None


async def analyze_turn(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    """Analyze the full turn once, then let deterministic code normalize and route the result."""

    from services.ai_runtime.verticals import get_vertical_spec

    vertical_spec = get_vertical_spec(state.get("vertical"))
    graph_state = vertical_spec.state_model.model_validate(state)
    policy = vertical_spec.policy
    quick_action_turn = _quick_action_turn(graph_state)
    if quick_action_turn is not None:
        analysis = quick_action_turn["analysis"]
        pending_decision = quick_action_turn["pending_decision"]
        updates: dict[str, Any] = {
            "turn_analysis": analysis.model_dump(mode="json"),
            "resolved_references": quick_action_turn["resolved_references"],
            "pending_clarification": None,
            "pending_decision": pending_decision.model_dump(mode="json") if pending_decision else None,
            "intent_queue": [],
            "active_intent": None,
        }
        if quick_action_turn.get("lead_advisor") is not None:
            updates["lead_advisor"] = quick_action_turn["lead_advisor"]
        if quick_action_turn.get("cita") is not None:
            updates["cita"] = quick_action_turn["cita"]
        if not pending_decision:
            updates["intent_queue"] = _build_intent_queue(
                graph_state,
                analysis,
                resolved_references=quick_action_turn["resolved_references"],
            )
        return updates

    result_snapshots = []
    for item in getattr(graph_state, "last_search_results", [])[:6]:
        item_data = _coerce_property_dict(item)
        if item_data:
            result_snapshots.append(_property_snapshot(item_data))
    last_mentioned = getattr(graph_state, "last_mentioned", None)
    last_mentioned_data = _coerce_property_dict(last_mentioned)
    last_mentioned_snapshot = (
        {
            "id": last_mentioned_data.get("id"),
            "title": last_mentioned_data.get("title"),
            "price": last_mentioned_data.get("price"),
            "currency": last_mentioned_data.get("currency"),
            "province": _prop_get(last_mentioned_data, "location", "province"),
            "garage_clean": _prop_get(last_mentioned_data, "features", "garage_clean"),
        }
        if last_mentioned_data
        else None
    )
    visible_result_snapshots = []
    for item in _visible_reference_items(graph_state)[:6]:
        visible_result_snapshots.append(_property_snapshot(item))
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
            "current_filters": _dump_search_filters(graph_state),
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
