"""Realtor search node."""

from __future__ import annotations

import logging
from typing import Any

from services.ai_runtime.config.prompt_composer import compose
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import RealtorGraphState, SearchFilters
from services.ai_runtime.graph._shared.nodes.helpers import complete_active_intent

logger = logging.getLogger(__name__)


def _relax_filters(filters: SearchFilters) -> SearchFilters:
    if filters.amenidades:
        return filters.model_copy(update={"amenidades": []})
    if filters.precio_max:
        return filters.model_copy(update={"precio_max": filters.precio_max * 1.1})
    if filters.precio_min:
        return filters.model_copy(update={"precio_min": filters.precio_min * 0.9})
    if filters.banos:
        return filters.model_copy(update={"banos": None})
    if filters.habitaciones:
        return filters.model_copy(update={"habitaciones": None})
    return filters


def _build_fallback_search_sql(graph_state: RealtorGraphState, filters: SearchFilters) -> tuple[str, dict[str, Any]]:
    clauses = ["SELECT * FROM searchable_properties WHERE client_id = :client_id"]
    params: dict[str, Any] = {"client_id": graph_state.client_id}

    if filters.provincia:
        params["provincia_like"] = f"%{filters.provincia.strip().lower()}%"
        clauses.append("AND searchable_text LIKE :provincia_like")
    if filters.ubicacion:
        params["ubicacion_like"] = f"%{filters.ubicacion.strip().lower()}%"
        clauses.append("AND searchable_text LIKE :ubicacion_like")
    if filters.habitaciones is not None:
        params["bedrooms"] = filters.habitaciones
        clauses.append("AND bedrooms_clean >= :bedrooms")
    if filters.banos is not None:
        params["bathrooms"] = filters.banos
        clauses.append("AND bathrooms_clean >= :bathrooms")
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
        params["tipo_like"] = f"%{filters.tipo.strip().lower()}%"
        clauses.append("AND LOWER(property_type_name) LIKE :tipo_like")
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
    filters = graph_state.search_filters
    if graph_state.search_attempts > 0:
        filters = _relax_filters(filters)
    prompt = compose(
        "text_to_sql",
        graph_state.tenant_config,
        graph_state.vertical,
        {
            "client_id": graph_state.client_id,
            "search_filters": filters.model_dump(mode="json"),
        },
        include_tone=False,
    )
    translation = await deps.llm.translate_text_to_sql(prompt)
    execution_mode = "llm_sql"
    sql_error: str | None = None
    try:
        results = await deps.property_repository.run_text_to_sql_query(
            client_id=graph_state.client_id,
            sql=translation.sql,
            params=translation.params,
        )
    except Exception as exc:
        logger.warning("search fallback activated after SQL execution error: %s", exc)
        fallback_sql, fallback_params = _build_fallback_search_sql(graph_state, filters)
        results = await deps.property_repository.run_text_to_sql_query(
            client_id=graph_state.client_id,
            sql=fallback_sql,
            params=fallback_params,
        )
        execution_mode = "fallback_sql"
        sql_error = repr(exc)

    output = {
        "type": "search",
        "count": len(results),
        "filters": filters.model_dump(mode="json"),
        "execution_mode": execution_mode,
    }
    if sql_error:
        output["sql_error"] = sql_error
    updates = {
        "search_filters": filters.model_dump(mode="json"),
        "last_search_results": [item.model_dump(mode="json") for item in results],
        "inventory": [item.model_dump(mode="json") for item in results],
        "search_attempts": graph_state.search_attempts + (1 if not results else 0),
        "turn_outputs": [*graph_state.turn_outputs, output],
    }
    if 0 < len(results) < 4:
        updates["render_mode"] = "text"
        updates |= complete_active_intent(graph_state, output)
    elif not results and updates["search_attempts"] >= 3:
        updates |= complete_active_intent(graph_state, output)
    return updates
