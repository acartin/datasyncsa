"""Realtor search node."""

from __future__ import annotations

import logging
from typing import Any

from services.ai_runtime.config.prompt_composer import compose
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.graph._shared.nodes.helpers import complete_active_intent
from services.ai_runtime.graph.realtor.adapters import get_realtor_adapters
from services.ai_runtime.graph.realtor.state.model import RealtorGraphState, SearchFilters
from services.ai_runtime.graph.realtor.turn_frame import merge_seen_properties

logger = logging.getLogger(__name__)


def _relax_filters_once(filters: SearchFilters) -> SearchFilters:
    if filters.amenidades:
        return filters.model_copy(update={"amenidades": []})
    if filters.precio_max:
        return filters.model_copy(update={"precio_max": filters.precio_max * 1.1})
    if filters.precio_min:
        return filters.model_copy(update={"precio_min": filters.precio_min * 0.9})
    if filters.garage:
        return filters.model_copy(update={"garage": None})
    if filters.banos:
        return filters.model_copy(update={"banos": None})
    if filters.habitaciones:
        return filters.model_copy(update={"habitaciones": None})
    return filters


def _build_effective_filters(requested_filters: SearchFilters, *, attempts: int) -> SearchFilters:
    effective = requested_filters
    for _ in range(max(0, attempts)):
        effective = _relax_filters_once(effective)
    return effective


def _match_scope(*, result_count: int, relaxation_applied: bool) -> str:
    if result_count <= 0:
        return "none"
    return "relaxed" if relaxation_applied else "exact"


def _build_fallback_search_sql(graph_state: RealtorGraphState, filters: SearchFilters) -> tuple[str, dict[str, Any]]:
    clauses = ["SELECT * FROM searchable_properties WHERE client_id = :client_id"]
    params: dict[str, Any] = {"client_id": graph_state.client_id}

    if filters.provincia:
        params["provincia_like"] = f"%{filters.provincia.strip().lower()}%"
        clauses.append("AND location_search_text LIKE :provincia_like")
    if filters.ubicacion:
        params["ubicacion_like"] = f"%{filters.ubicacion.strip().lower()}%"
        clauses.append("AND location_search_text LIKE :ubicacion_like")
    if filters.habitaciones is not None:
        params["bedrooms"] = filters.habitaciones
        clauses.append("AND bedrooms_clean >= :bedrooms")
    if filters.banos is not None:
        params["bathrooms"] = filters.banos
        clauses.append("AND bathrooms_clean >= :bathrooms")
    if filters.garage is not None:
        params["garage"] = filters.garage
        clauses.append("AND garage_clean >= :garage")
    if filters.precio_max is not None:
        params["price_max"] = filters.precio_max
        clauses.append("AND price <= :price_max")
    if filters.precio_min is not None:
        params["price_min"] = filters.precio_min
        clauses.append("AND price >= :price_min")
    if filters.currency:
        params["currency"] = filters.currency.strip().upper()
        clauses.append("AND currency = :currency")
    if filters.tipo:
        params["tipo_name"] = filters.tipo.strip().lower()
        clauses.append("AND LOWER(property_type_name) = :tipo_name")
    if filters.operacion:
        params["operacion_like"] = f"%{filters.operacion.strip().lower()}%"
        clauses.append("AND searchable_text LIKE :operacion_like")
    for index, amenidad in enumerate(filters.amenidades):
        cleaned = str(amenidad or "").strip().lower()
        if not cleaned:
            continue
        key = f"amenidad_like_{index}"
        params[key] = f"%{cleaned}%"
        clauses.append(f"AND searchable_text LIKE :{key}")

    clauses.append("ORDER BY price ASC LIMIT 12")
    return " ".join(clauses), params


async def search(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    graph_state = RealtorGraphState.model_validate(state)
    property_repository = get_realtor_adapters(deps).property_repository
    requested_filters = graph_state.search_filters
    effective_filters = _build_effective_filters(
        requested_filters,
        attempts=graph_state.search_attempts,
    )
    requested_dump = requested_filters.model_dump(mode="json")
    effective_dump = effective_filters.model_dump(mode="json")
    relaxation_applied = requested_dump != effective_dump
    prompt = compose(
        "text_to_sql",
        graph_state.tenant_config,
        graph_state.vertical,
        {
            "client_id": graph_state.client_id,
            "search_filters": effective_dump,
        },
        include_tone=False,
    )
    translation = await deps.llm.translate_text_to_sql(prompt)
    execution_mode = "llm_sql"
    sql_error: str | None = None
    try:
        results = await property_repository.run_text_to_sql_query(
            client_id=graph_state.client_id,
            sql=translation.sql,
            params=translation.params,
        )
    except Exception as exc:
        logger.warning("search fallback activated after SQL execution error: %s", exc)
        fallback_sql, fallback_params = _build_fallback_search_sql(graph_state, effective_filters)
        results = await property_repository.run_text_to_sql_query(
            client_id=graph_state.client_id,
            sql=fallback_sql,
            params=fallback_params,
        )
        execution_mode = "fallback_sql"
        sql_error = repr(exc)

    output = {
        "type": "search",
        "count": len(results),
        "filters": effective_dump,
        "requested_filters": requested_dump,
        "effective_filters": effective_dump,
        "relaxation_applied": relaxation_applied,
        "match_scope": _match_scope(result_count=len(results), relaxation_applied=relaxation_applied),
        "attempt_index": graph_state.search_attempts,
        "execution_mode": execution_mode,
    }
    if sql_error:
        output["sql_error"] = sql_error
    updates = {
        "search_filters": requested_dump,
        "effective_search_filters": effective_dump,
        "last_search_results": [item.model_dump(mode="json") for item in results],
        "inventory": [item.model_dump(mode="json") for item in results],
        "search_attempts": graph_state.search_attempts + (1 if not results else 0),
        "turn_outputs": [*graph_state.turn_outputs, output],
        "seen_properties": merge_seen_properties(
            graph_state.seen_properties,
            results,
            current_turn=graph_state.current_turn,
        ),
    }
    if not results:
        updates["cards_shown"] = []
        updates["last_mentioned"] = None
        updates["active_comparison"] = []
    if not results and updates["search_attempts"] >= 3:
        updates |= complete_active_intent(graph_state, output)
    return updates
