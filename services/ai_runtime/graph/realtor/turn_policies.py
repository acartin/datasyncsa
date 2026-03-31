"""Realtor-only turn normalization and fallback planning helpers."""

from __future__ import annotations

import re
from typing import Any

from services.ai_runtime.config.geo_catalog import DEFAULT_COUNTRY_CODE, normalize_search_geo_filters
from services.ai_runtime.config.property_type_catalog import normalize_property_type
from services.ai_runtime.domain.contracts import IntentPlanItem, PendingDecision, ReferenceDecision, TurnAnalysis
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import RealtorGraphState, SearchFilters

REALTOR_INTERNAL_INTENTS = {"focus_property", "describe_result_set", "show_result_cards"}
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
RELAXATION_PRICE_OPTION_PATTERN = re.compile(
    r"\b(precio|presupuesto|monto|rango)\b",
    flags=re.IGNORECASE,
)
RELAXATION_ZONE_OPTION_PATTERN = re.compile(
    r"\b(zona|ubicacion|ubicación|provincia|sector|area|área|otra zona)\b",
    flags=re.IGNORECASE,
)
RELAXATION_CRITERIA_OPTION_PATTERN = re.compile(
    r"\b(criterio|criterios|filtro|filtros|otro criterio|otros criterios)\b",
    flags=re.IGNORECASE,
)


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


async def merge_realtor_filters(
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


def build_realtor_fallback_intent_plan(
    graph_state: RealtorGraphState,
    analysis: TurnAnalysis,
) -> list[IntentPlanItem]:
    if analysis.dialogue_act not in {"new_search", "refine_search", "confirm_previous"}:
        return []
    if analysis.dialogue_act == "confirm_previous" and _assistant_requested_search_relaxation(graph_state):
        return []
    has_search_context = bool(
        analysis.filters_delta
        or analysis.reuse_current_filters
        or graph_state.search_filters.model_dump(exclude_none=True)
    )
    if not has_search_context:
        return []
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


def _filters_delta_has_values(analysis: TurnAnalysis) -> bool:
    if not isinstance(analysis.filters_delta, dict):
        return False
    for value in analysis.filters_delta.values():
        normalized = _normalize_value(value)
        if normalized is None:
            continue
        if normalized == "":
            continue
        if normalized == []:
            continue
        if normalized == {}:
            continue
        return True
    return False


def _has_actionable_search_update(analysis: TurnAnalysis) -> bool:
    if analysis.dialogue_act in {"new_search", "refine_search"}:
        return True
    if analysis.reuse_current_filters:
        return True
    if _filters_delta_has_values(analysis):
        return True
    return any(item.type == "buscar" for item in analysis.intent_plan)


def _extract_search_relaxation_option(message: str) -> str | None:
    normalized = (message or "").strip()
    if not normalized:
        return None

    hits: list[str] = []
    if RELAXATION_PRICE_OPTION_PATTERN.search(normalized):
        hits.append("price")
    if RELAXATION_ZONE_OPTION_PATTERN.search(normalized):
        hits.append("zone")
    if RELAXATION_CRITERIA_OPTION_PATTERN.search(normalized):
        hits.append("criteria")
    if len(hits) != 1:
        return None
    return hits[0]


def _build_search_relaxation_pending_decision(
    graph_state: RealtorGraphState,
    *,
    kind: str,
) -> PendingDecision:
    filters = graph_state.search_filters.model_dump(mode="json", exclude_none=True)
    metadata = {
        "ubicacion": filters.get("ubicacion"),
        "provincia": filters.get("provincia"),
        "precio_max": filters.get("precio_max"),
        "precio_min": filters.get("precio_min"),
        "currency": filters.get("currency"),
        "tipo": filters.get("tipo"),
    }
    return PendingDecision(
        kind=kind,
        reason="search_relaxation_required",
        options=["precio", "zona", "criterios"] if kind == "search_relaxation_choice" else [],
        metadata=metadata,
    )


def derive_realtor_pending_decision(
    graph_state: RealtorGraphState,
    analysis: TurnAnalysis,
) -> PendingDecision | None:
    if not _assistant_requested_search_relaxation(graph_state):
        return None

    latest_message = graph_state.messages[-1].content
    selected_option = _extract_search_relaxation_option(latest_message)
    if selected_option == "price":
        return _build_search_relaxation_pending_decision(
            graph_state,
            kind="search_relaxation_price_value",
        )
    if selected_option == "zone":
        return _build_search_relaxation_pending_decision(
            graph_state,
            kind="search_relaxation_zone_value",
        )
    if selected_option == "criteria":
        return _build_search_relaxation_pending_decision(
            graph_state,
            kind="search_relaxation_custom_value",
        )

    if _has_actionable_search_update(analysis):
        return None
    if analysis.dialogue_act not in {"confirm_previous", "ask_detail", "unknown", "small_talk"}:
        return None
    return _build_search_relaxation_pending_decision(
        graph_state,
        kind="search_relaxation_choice",
    )


def apply_realtor_turn_policies(
    graph_state: RealtorGraphState,
    analysis: TurnAnalysis,
) -> tuple[TurnAnalysis, list[str]]:
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
    return analysis, compare_target_ids


def _detect_detail_attribute(message: str) -> str | None:
    normalized = (message or "").strip()
    if not normalized:
        return None
    for key, pattern in DETAIL_ATTRIBUTE_PATTERNS.items():
        if pattern.search(normalized):
            return key
    return None


def _last_assistant_message(graph_state: RealtorGraphState) -> str:
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


def _assistant_requested_search_relaxation(graph_state: RealtorGraphState) -> bool:
    assistant_message = _last_assistant_message(graph_state)
    if not assistant_message:
        return False
    return bool(
        NO_RESULTS_ASSISTANT_PATTERN.search(assistant_message)
        and RELAXATION_PROMPT_PATTERN.search(assistant_message)
    )


def _coerce_result_set_detail(
    graph_state: RealtorGraphState,
    analysis: TurnAnalysis,
) -> TurnAnalysis:
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
    if not detail_attribute or detail_attribute == "foto":
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
    graph_state: RealtorGraphState,
    analysis: TurnAnalysis,
) -> TurnAnalysis:
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
    graph_state: RealtorGraphState,
    analysis: TurnAnalysis,
) -> TurnAnalysis:
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
    graph_state: RealtorGraphState,
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
    graph_state: RealtorGraphState,
    analysis: TurnAnalysis,
) -> TurnAnalysis:
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
    graph_state: RealtorGraphState,
    analysis: TurnAnalysis,
) -> TurnAnalysis:
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
    graph_state: RealtorGraphState,
    analysis: TurnAnalysis,
) -> list[str]:
    if analysis.dialogue_act != "compare" or analysis.needs_clarification:
        return []
    return _extract_compare_target_ids(graph_state, graph_state.messages[-1].content)


def _coerce_inventory_probe(
    graph_state: RealtorGraphState,
    analysis: TurnAnalysis,
) -> TurnAnalysis:
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
