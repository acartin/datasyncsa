"""Single-pass conversational turn analysis."""

from __future__ import annotations

import re
from typing import Any

from services.ai_runtime.config.geo_catalog import DEFAULT_COUNTRY_CODE, normalize_search_geo_filters
from services.ai_runtime.config.prompt_composer import compose
from services.ai_runtime.config.property_type_catalog import normalize_property_type
from services.ai_runtime.domain.contracts import (
    IntentDefinition,
    IntentPlanItem,
    Property,
    ReferenceDecision,
    TurnAnalysis,
)
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import BaseGraphState, RealtorGraphState, SearchFilters

INTERNAL_INTENTS = {"focus_property", "describe_result_set", "show_result_cards"}
DETAIL_ATTRIBUTE_PATTERNS: dict[str, re.Pattern[str]] = {
    "banos": re.compile(r"\b(bano|banos|baño|baños|servicio|servicios)\b", flags=re.IGNORECASE),
    "habitaciones": re.compile(r"\b(habitacion|habitaciones|cuarto|cuartos|dormitorio|dormitorios)\b", flags=re.IGNORECASE),
    "area": re.compile(r"\b(m2|mts|metros|metro|area|área|tamano|tamaño|terreno|lote)\b", flags=re.IGNORECASE),
    "precio": re.compile(r"\b(precio|precios|cuesta|cuestan|vale|valen|monto)\b", flags=re.IGNORECASE),
    "garage": re.compile(
        r"\b(garage|garaje|cochera|cocheras|estacionamiento|estacionamientos|parqueo|parqueos)\b",
        flags=re.IGNORECASE,
    ),
    "foto": re.compile(
        r"\b(foto|fotos|imagen|imagenes|imágenes|picture|pictures|ficha|fichas|anuncio|anuncios|card|cards|tarjeta|tarjetas)\b",
        flags=re.IGNORECASE,
    ),
}
DETAIL_QUERY_PATTERN = re.compile(
    r"\b(cuanto|cuantos|cuanta|cuantas|que|qué|cual|cuál|como|cómo)\b",
    flags=re.IGNORECASE,
)
PARKING_AMENITY_PATTERN = re.compile(
    r"\b(garage|garaje|cochera|cocheras|estacionamiento|estacionamientos|parqueo|parqueos)\b",
    flags=re.IGNORECASE,
)
NUMBER_WORDS = {
    "un": 1,
    "uno": 1,
    "una": 1,
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "seis": 6,
}
MEMORY_QUERY_PATTERN = re.compile(
    r"\b(como me llamo|cual es mi nombre|que edad tengo|cuantos anos tengo|cual era mi presupuesto|que presupuesto te dije|cual es mi correo|cual es mi email|cual es mi telefono|cual es mi numero|record[aá]s|recuerdas|te acord[aá]s)\b",
    flags=re.IGNORECASE,
)
MEMORY_STATEMENT_PATTERN = re.compile(
    r"\b(me llamo|mi nombre es|soy\s+[A-Za-zÁÉÍÓÚáéíóúÑñ]+|tengo\s+\d{1,3}\s+a(?:ñ|n)os|mi correo es|mi email es|mi telefono es|mi teléfono es|mi numero es|mi número es|mi presupuesto es)\b",
    flags=re.IGNORECASE,
)
INVENTORY_COUNT_PATTERN = re.compile(r"\b(cu[aá]nt[oa]s?|cantidad|total|n[uú]mero)\b", flags=re.IGNORECASE)
INVENTORY_NOUN_PATTERN = re.compile(
    r"\b(propiedades?|casas?|apartamentos?|condominios?|bodegas?|locales?|lotes?|terrenos?|inmuebles?)\b",
    flags=re.IGNORECASE,
)
AVERAGE_PRICE_PATTERN = re.compile(
    r"(\b(promedio|media|promedio general|ticket promedio)\b.*\b(precio|precios)\b)|(\b(precio|precios)\b.*\b(promedio|media|promedio general|ticket promedio)\b)",
    flags=re.IGNORECASE,
)
CURRENT_RESULT_REFERENCE_PATTERN = re.compile(
    r"\b(estas|esas|estos|esas opciones|estos resultados|las que me mostraste|las que me enseñaste|me mostraste|me enseñaste|de estas|de esas)\b",
    flags=re.IGNORECASE,
)
AFFIRMATIVE_TURN_PATTERN = re.compile(
    r"^\s*(si|sí|claro|dale|ok|okay|perfecto|de una|esta bien|está bien|me parece)\s*[.!?]*\s*$",
    flags=re.IGNORECASE,
)
COMPARE_INTENT_PATTERN = re.compile(
    r"\b(compara|compar[aá]|comparar|versus|vs\b|lado a lado|entre)\b",
    flags=re.IGNORECASE,
)
SEARCH_RESET_CUE_PATTERN = re.compile(
    r"\b(ahora mejor|m[aá]s bien|mas bien|en realidad|prefiero|cambiemos|mejor busco|mejor quiero)\b",
    flags=re.IGNORECASE,
)
SEARCH_INTENT_PATTERN = re.compile(
    r"\b(busco|buscar|quiero|quiero ver|ando buscando|necesito|me interesa)\b",
    flags=re.IGNORECASE,
)
NO_RESULTS_ASSISTANT_PATTERN = re.compile(
    r"\b(no encontr[eé]|no tengo resultados|sin resultados|no encontr[eé] casas|no encontr[eé] opciones)\b",
    flags=re.IGNORECASE,
)
RELAXATION_PROMPT_PATTERN = re.compile(
    r"\b(ampli[aeí]e?|abrir la b[uú]squeda|rango de precio|otra zona|la zona|criterios?)\b",
    flags=re.IGNORECASE,
)
COUNTRYWIDE_SCOPE_PATTERN = re.compile(
    r"\b(todo el pais|todo el país|en todo el pais|en todo el país|todo costa rica|en todo costa rica|a nivel nacional|cualquier zona|en cualquier zona)\b",
    flags=re.IGNORECASE,
)
COMPARE_ORDINAL_PATTERNS: tuple[tuple[int, re.Pattern[str]], ...] = (
    (1, re.compile(r"\b(primer[oa]?|primera)\b", flags=re.IGNORECASE)),
    (2, re.compile(r"\b(segund[oa]?|segunda)\b", flags=re.IGNORECASE)),
    (3, re.compile(r"\b(tercer[oa]?|tercera)\b", flags=re.IGNORECASE)),
    (4, re.compile(r"\b(cuart[oa]?|cuarta)\b", flags=re.IGNORECASE)),
)
LAST_COMPARE_PATTERN = re.compile(r"\b(ultim[oa]?|últim[oa]?|la ultima|la última)\b", flags=re.IGNORECASE)


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
    return {key: _normalize_value(value) for key, value in payload.items()}


def _extract_garage_filter_from_message(message: str) -> int | None:
    normalized = (message or "").strip().lower()
    if not normalized or not PARKING_AMENITY_PATTERN.search(normalized):
        return None
    explicit_match = re.search(
        r"\b(\d+|un|uno|una|dos|tres|cuatro|cinco|seis)\s+(garage|garaje|cochera|cocheras|estacionamiento|estacionamientos|parqueo|parqueos)\b",
        normalized,
    )
    if explicit_match:
        raw_value = explicit_match.group(1)
        if raw_value.isdigit():
            return int(raw_value)
        return NUMBER_WORDS.get(raw_value)
    return 1


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

    items = [Property.model_validate(item) for item in getattr(graph_state, "last_search_results", [])]
    if not items:
        items = [Property.model_validate(item) for item in getattr(graph_state, "inventory", [])]
    has_session_reference_context = bool(items or getattr(graph_state, "last_mentioned", None))

    if decision.kind == "LAST_MENTIONED" and getattr(graph_state, "last_mentioned", None):
        property_item = Property.model_validate(graph_state.last_mentioned)
        return [{"kind": "property", "property_id_internal": property_item.property_id_internal}], None

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

    candidate = _select_reference_candidate(items, decision)
    if candidate:
        return [{"kind": "property", "property_id_internal": candidate.property_id_internal}], None
    return [], decision.clarification_target or "me ayudas a ubicar la referencia exacta"


async def _merge_realtor_filters(
    graph_state: RealtorGraphState,
    analysis: TurnAnalysis,
    deps: GraphDependencies,
) -> dict[str, Any]:
    available_property_types = await deps.property_repository.load_property_types()
    base_filters = (
        SearchFilters().model_dump(mode="json")
        if analysis.dialogue_act == "new_search"
        else graph_state.search_filters.model_dump(mode="json")
    )
    delta = analysis.filters_delta if isinstance(analysis.filters_delta, dict) else {}
    for key, value in _normalize_payload(delta).items():
        if key not in base_filters:
            continue
        if value is None and analysis.dialogue_act != "new_search":
            continue
        base_filters[key] = value

    country_code = str(graph_state.tenant_config.metadata.get("country_code") or DEFAULT_COUNTRY_CODE)
    base_filters = normalize_search_geo_filters(
        base_filters,
        message=graph_state.messages[-1].content,
        country_code=country_code,
    )
    if COUNTRYWIDE_SCOPE_PATTERN.search(graph_state.messages[-1].content):
        base_filters["ubicacion"] = None
        base_filters["provincia"] = None
    base_filters["tipo"] = normalize_property_type(
        base_filters.get("tipo"),
        message=graph_state.messages[-1].content,
        available_types=available_property_types,
    )
    inferred_garage = _extract_garage_filter_from_message(graph_state.messages[-1].content)
    if inferred_garage is not None:
        base_filters["garage"] = inferred_garage
        base_filters["amenidades"] = [
            item
            for item in (base_filters.get("amenidades") or [])
            if not PARKING_AMENITY_PATTERN.search(str(item))
        ]
    return SearchFilters.model_validate(base_filters).model_dump(mode="json")


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

    if isinstance(graph_state, RealtorGraphState) and analysis.dialogue_act in {"new_search", "refine_search", "confirm_previous"}:
        if analysis.dialogue_act == "confirm_previous" and _assistant_requested_search_relaxation(graph_state):
            return []
        has_search_context = bool(analysis.filters_delta or analysis.reuse_current_filters or graph_state.search_filters.model_dump(exclude_none=True))
        if has_search_context:
            condition = {"reuse_current_filters": True} if analysis.reuse_current_filters else None
            return [
                IntentPlanItem(
                    type="buscar",
                    priority=1,
                    depends_on=[],
                    condition=condition,
                    skip_if_failed=False,
                )
            ]
    return []


def _build_intent_queue(
    graph_state: BaseGraphState,
    analysis: TurnAnalysis,
    *,
    resolved_references: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    allowed_types = set(graph_state.capabilities) | INTERNAL_INTENTS
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


def _detect_detail_attribute(message: str) -> str | None:
    normalized = (message or "").strip()
    if not normalized:
        return None
    for key, pattern in DETAIL_ATTRIBUTE_PATTERNS.items():
        if pattern.search(normalized):
            return key
    return None


def _last_assistant_message(graph_state: BaseGraphState) -> str:
    for message in reversed(graph_state.messages[:-1]):
        if message.role == "assistant":
            return message.content
    return ""


def _ordered_compare_candidates(graph_state: RealtorGraphState) -> list[str]:
    candidates: list[str] = []
    for property_id in graph_state.cards_shown:
        if property_id not in candidates:
            candidates.append(property_id)
    for item in graph_state.last_search_results:
        if item.property_id_internal not in candidates:
            candidates.append(item.property_id_internal)
    for item in graph_state.inventory:
        if item.property_id_internal not in candidates:
            candidates.append(item.property_id_internal)
    return candidates


def _extract_compare_target_ids(graph_state: RealtorGraphState, message: str) -> list[str]:
    if not message.strip():
        return []
    ordered_candidates = _ordered_compare_candidates(graph_state)
    if len(ordered_candidates) < 2:
        return []

    hits: list[tuple[int, int]] = []
    for ordinal_index, pattern in COMPARE_ORDINAL_PATTERNS:
        for match in pattern.finditer(message):
            hits.append((match.start(), ordinal_index))
    for match in LAST_COMPARE_PATTERN.finditer(message):
        hits.append((match.start(), len(ordered_candidates)))

    if len(hits) < 2:
        return []

    seen_indices: set[int] = set()
    ordered_indices: list[int] = []
    for _, ordinal_index in sorted(hits, key=lambda item: item[0]):
        if ordinal_index < 1 or ordinal_index > len(ordered_candidates):
            continue
        if ordinal_index in seen_indices:
            continue
        seen_indices.add(ordinal_index)
        ordered_indices.append(ordinal_index)

    if len(ordered_indices) < 2:
        return []
    return [ordered_candidates[index - 1] for index in ordered_indices[:4]]


def _extract_single_ordinal_index(graph_state: RealtorGraphState, message: str) -> int | None:
    normalized = (message or "").strip()
    if not normalized or COMPARE_INTENT_PATTERN.search(normalized):
        return None

    ordered_candidates = _ordered_compare_candidates(graph_state)
    if not ordered_candidates:
        return None

    hits: list[tuple[int, int]] = []
    for ordinal_index, pattern in COMPARE_ORDINAL_PATTERNS:
        for match in pattern.finditer(normalized):
            hits.append((match.start(), ordinal_index))
    for match in LAST_COMPARE_PATTERN.finditer(normalized):
        hits.append((match.start(), len(ordered_candidates)))

    if not hits:
        return None

    ordered_indices: list[int] = []
    seen: set[int] = set()
    for _, ordinal_index in sorted(hits, key=lambda item: item[0]):
        if ordinal_index < 1 or ordinal_index > len(ordered_candidates):
            continue
        if ordinal_index in seen:
            continue
        ordered_indices.append(ordinal_index)
        seen.add(ordinal_index)

    if len(ordered_indices) != 1:
        return None
    return ordered_indices[0]


def _assistant_requested_search_relaxation(graph_state: BaseGraphState) -> bool:
    assistant_message = _last_assistant_message(graph_state)
    if not assistant_message:
        return False
    return bool(
        NO_RESULTS_ASSISTANT_PATTERN.search(assistant_message)
        and RELAXATION_PROMPT_PATTERN.search(assistant_message)
    )


def _coerce_result_set_detail(
    graph_state: BaseGraphState,
    analysis: TurnAnalysis,
) -> TurnAnalysis:
    if not isinstance(graph_state, RealtorGraphState):
        return analysis
    latest_message = graph_state.messages[-1].content
    if analysis.dialogue_act not in {"ask_detail", "unknown"}:
        return analysis
    if analysis.dialogue_act == "unknown" and not DETAIL_QUERY_PATTERN.search(latest_message):
        return analysis
    if not (graph_state.cards_shown or graph_state.last_search_results):
        return analysis

    reference_kind = analysis.reference.kind
    if reference_kind in {"ORDINAL", "LAST_MENTIONED", "BY_ATTRIBUTE", "ANAPHORIC_HISTORY", "AMBIGUOUS"}:
        return analysis
    if reference_kind == "CONTEXT_LOCATION" and (analysis.reference.location_hint or "").lower() not in {
        "",
        "last_search_results",
        "current_results",
        "cards_shown",
    }:
        return analysis

    detail_attribute = analysis.detail_attribute_key or _detect_detail_attribute(latest_message)
    if not detail_attribute:
        return analysis
    if detail_attribute == "foto":
        return analysis

    return analysis.model_copy(
        update={
            "needs_clarification": False,
            "clarification_target": None,
            "reference": ReferenceDecision(kind="NONE", confidence=max(analysis.reference.confidence, 0.85)),
            "intent_plan": [
                IntentPlanItem(
                    type="describe_result_set",
                    priority=1,
                    depends_on=[],
                    condition={"min_search_results": 1},
                    skip_if_failed=False,
                )
            ],
            "detail_scope": "current_result_set",
            "detail_attribute_key": detail_attribute,
        }
    )


def _coerce_visual_request(
    graph_state: BaseGraphState,
    analysis: TurnAnalysis,
) -> TurnAnalysis:
    if not isinstance(graph_state, RealtorGraphState):
        return analysis
    if analysis.dialogue_act not in {"ask_detail", "unknown"}:
        return analysis
    if not (graph_state.last_search_results or graph_state.cards_shown):
        return analysis
    latest_message = graph_state.messages[-1].content
    if not DETAIL_ATTRIBUTE_PATTERNS["foto"].search(latest_message):
        return analysis
    return analysis.model_copy(
        update={
            "dialogue_act": "ask_detail",
            "needs_clarification": False,
            "clarification_target": None,
            "reference": ReferenceDecision(kind="NONE", confidence=max(analysis.reference.confidence, 0.85)),
            "intent_plan": [
                IntentPlanItem(
                    type="show_result_cards",
                    priority=1,
                    depends_on=[],
                    condition={"min_search_results": 1},
                    skip_if_failed=False,
                )
            ],
            "detail_scope": "current_result_set",
            "detail_attribute_key": "foto",
        }
    )


def _coerce_single_ordinal_selection(
    graph_state: BaseGraphState,
    analysis: TurnAnalysis,
) -> TurnAnalysis:
    if not isinstance(graph_state, RealtorGraphState):
        return analysis
    if analysis.dialogue_act not in {"unknown", "ask_detail", "select_result"}:
        return analysis
    if not (graph_state.cards_shown or graph_state.last_search_results or graph_state.inventory):
        return analysis

    ordinal_index = _extract_single_ordinal_index(graph_state, graph_state.messages[-1].content)
    if ordinal_index is None:
        return analysis

    return analysis.model_copy(
        update={
            "dialogue_act": "select_result",
            "confidence": max(analysis.confidence, 0.92),
            "needs_clarification": False,
            "clarification_target": None,
            "reference": ReferenceDecision(kind="ORDINAL", confidence=0.98, ordinal_index=ordinal_index),
            "intent_plan": [
                IntentPlanItem(
                    type="focus_property",
                    priority=1,
                    depends_on=[],
                    condition={"requires_reference": "resolved_property"},
                    skip_if_failed=False,
                )
            ],
            "detail_scope": None,
            "detail_attribute_key": None,
        }
    )


def _coerce_affirmative_after_no_results(
    graph_state: BaseGraphState,
    analysis: TurnAnalysis,
) -> TurnAnalysis:
    if analysis.dialogue_act != "unknown":
        return analysis

    latest_message = graph_state.messages[-1].content.strip()
    if not AFFIRMATIVE_TURN_PATTERN.match(latest_message):
        return analysis
    if not _assistant_requested_search_relaxation(graph_state):
        return analysis

    return analysis.model_copy(
        update={
            "dialogue_act": "confirm_previous",
            "confidence": max(analysis.confidence, 0.9),
            "needs_clarification": False,
            "clarification_target": None,
            "reference": ReferenceDecision(kind="NONE", confidence=0.99),
            "intent_plan": [],
            "reuse_current_filters": False,
            "detail_scope": None,
            "detail_attribute_key": None,
        }
    )


def _coerce_search_restart(
    graph_state: BaseGraphState,
    analysis: TurnAnalysis,
) -> TurnAnalysis:
    if not isinstance(graph_state, RealtorGraphState):
        return analysis
    if analysis.dialogue_act not in {"refine_search", "unknown"}:
        return analysis

    latest_message = graph_state.messages[-1].content.strip()
    if not latest_message:
        return analysis
    if not SEARCH_RESET_CUE_PATTERN.search(latest_message):
        return analysis
    if not SEARCH_INTENT_PATTERN.search(latest_message):
        return analysis
    if not analysis.filters_delta:
        return analysis

    return analysis.model_copy(
        update={
            "dialogue_act": "new_search",
            "confidence": max(analysis.confidence, 0.9),
            "needs_clarification": False,
            "clarification_target": None,
            "reference": ReferenceDecision(kind="NONE", confidence=max(analysis.reference.confidence, 0.95)),
            "reuse_current_filters": False,
            "detail_scope": None,
            "detail_attribute_key": None,
        }
    )


def _coerce_countrywide_scope(
    graph_state: BaseGraphState,
    analysis: TurnAnalysis,
) -> TurnAnalysis:
    if not isinstance(graph_state, RealtorGraphState):
        return analysis

    latest_message = graph_state.messages[-1].content.strip()
    if not latest_message or not COUNTRYWIDE_SCOPE_PATTERN.search(latest_message):
        return analysis
    if analysis.dialogue_act not in {"confirm_previous", "refine_search", "unknown"}:
        return analysis
    if not graph_state.search_filters.model_dump(exclude_none=True):
        return analysis

    return analysis.model_copy(
        update={
            "dialogue_act": "refine_search",
            "confidence": max(analysis.confidence, 0.9),
            "needs_clarification": False,
            "clarification_target": None,
            "reference": ReferenceDecision(kind="NONE", confidence=max(analysis.reference.confidence, 0.95)),
            "intent_plan": [
                IntentPlanItem(
                    type="buscar",
                    priority=1,
                    depends_on=[],
                    condition=None,
                    skip_if_failed=False,
                )
            ],
            "reuse_current_filters": False,
            "detail_scope": None,
            "detail_attribute_key": None,
        }
    )


def _coerce_compare_visible_targets(
    graph_state: BaseGraphState,
    analysis: TurnAnalysis,
) -> list[str]:
    if not isinstance(graph_state, RealtorGraphState):
        return []
    if analysis.dialogue_act != "compare":
        return []
    if analysis.needs_clarification:
        return []
    return _extract_compare_target_ids(graph_state, graph_state.messages[-1].content)


def _sanitize_analysis(message: str, analysis: TurnAnalysis) -> TurnAnalysis:
    normalized_message = (message or "").strip()
    if analysis.dialogue_act in {"new_search", "refine_search"} and analysis.reference.kind == "CONTEXT_LOCATION":
        return analysis.model_copy(
            update={
                "reference": ReferenceDecision(kind="NONE", confidence=analysis.reference.confidence),
            }
        )
    if not analysis.memory_lookup_key:
        return analysis
    if MEMORY_QUERY_PATTERN.search(normalized_message):
        return analysis
    if MEMORY_STATEMENT_PATTERN.search(normalized_message):
        return analysis.model_copy(
            update={
                "dialogue_act": "lead_capture",
                "memory_lookup_key": None,
            }
        )
    return analysis


def _coerce_inventory_probe(
    graph_state: BaseGraphState,
    analysis: TurnAnalysis,
) -> TurnAnalysis:
    if not isinstance(graph_state, RealtorGraphState):
        return analysis
    latest_message = graph_state.messages[-1].content.strip()
    if not latest_message:
        return analysis
    normalized = latest_message.lower()
    if CURRENT_RESULT_REFERENCE_PATTERN.search(normalized):
        return analysis
    if DETAIL_ATTRIBUTE_PATTERNS["banos"].search(normalized) or DETAIL_ATTRIBUTE_PATTERNS["habitaciones"].search(normalized):
        return analysis
    if DETAIL_ATTRIBUTE_PATTERNS["garage"].search(normalized) or DETAIL_ATTRIBUTE_PATTERNS["area"].search(normalized):
        return analysis
    has_inventory_noun = bool(INVENTORY_NOUN_PATTERN.search(normalized))
    if not has_inventory_noun:
        return analysis
    has_count_metric = bool(INVENTORY_COUNT_PATTERN.search(normalized))
    has_average_price = bool(AVERAGE_PRICE_PATTERN.search(normalized))
    if not (has_count_metric or has_average_price):
        return analysis
    return analysis.model_copy(
        update={
            "dialogue_act": "inventory_probe",
            "needs_clarification": False,
            "clarification_target": None,
            "reference": ReferenceDecision(kind="NONE", confidence=max(analysis.reference.confidence, 0.95)),
            "intent_plan": [],
            "filters_delta": {},
            "reuse_current_filters": False,
            "detail_scope": None,
            "detail_attribute_key": None,
            "memory_lookup_key": None,
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
                "property_id_internal": item.property_id_internal,
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
            "property_id_internal": last_mentioned.property_id_internal,
            "title": last_mentioned.title,
            "price": last_mentioned.price,
            "currency": last_mentioned.currency,
            "province": last_mentioned.location.province,
            "garage_clean": last_mentioned.features.garage_clean,
        }
        if last_mentioned
        else None
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
            "capabilities": graph_state.capabilities,
            "current_filters": getattr(graph_state, "search_filters", SearchFilters()).model_dump(mode="json"),
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
    analysis = _coerce_inventory_probe(graph_state, analysis)
    analysis = _coerce_search_restart(graph_state, analysis)
    analysis = _coerce_countrywide_scope(graph_state, analysis)
    analysis = _coerce_affirmative_after_no_results(graph_state, analysis)
    analysis = _coerce_single_ordinal_selection(graph_state, analysis)
    analysis = _coerce_visual_request(graph_state, analysis)
    analysis = _coerce_result_set_detail(graph_state, analysis)
    compare_target_ids = _coerce_compare_visible_targets(graph_state, analysis)
    if compare_target_ids:
        analysis = analysis.model_copy(
            update={
                "needs_clarification": False,
                "clarification_target": None,
                "reference": ReferenceDecision(kind="NONE", confidence=1.0),
            }
        )
    decision = analysis.reference if isinstance(analysis.reference, ReferenceDecision) else ReferenceDecision.model_validate(analysis.reference)
    resolved_references, clarification_target = await _resolve_reference(graph_state, decision, deps)
    if compare_target_ids:
        resolved_references = [
            {"kind": "property", "property_id_internal": property_id}
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
        "intent_queue": [],
        "active_intent": None,
    }
    if compare_target_ids:
        updates["active_comparison"] = compare_target_ids
    if not pending_clarification:
        updates["intent_queue"] = _build_intent_queue(
            graph_state,
            analysis,
            resolved_references=resolved_references,
        )

    if isinstance(graph_state, RealtorGraphState) and analysis.dialogue_act in {"new_search", "refine_search"}:
        updates["search_filters"] = await _merge_realtor_filters(graph_state, analysis, deps)
        if any(intent.get("type") == "buscar" for intent in updates["intent_queue"]):
            updates["search_attempts"] = 0
    return updates
