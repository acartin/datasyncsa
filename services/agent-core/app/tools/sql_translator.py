from __future__ import annotations

from typing import Any

from app.tools.canonical_property_contract import canonical_feature_keys

_PROPERTY_TYPE_SEARCH_TERMS: dict[str, tuple[str, ...]] = {
    "house": ("house", "casa", "hogar"),
    "apartment": ("apartment", "apartamento", "apto", "departamento", "depa"),
    "land": ("land", "terreno", "lote", "lot"),
    "office": ("office", "oficina"),
}


class SlotsToSqlTranslator:
    def compile(self, *, tenant_id: str, slots: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        city = str((slots or {}).get("city") or "").strip()
        property_type = str((slots or {}).get("property_type") or "").strip()
        min_rooms = (slots or {}).get("min_rooms")
        max_rooms = (slots or {}).get("max_rooms")
        min_bathrooms = (slots or {}).get("min_bathrooms")
        max_bathrooms = (slots or {}).get("max_bathrooms")
        min_garage = (slots or {}).get("min_garage")
        max_garage = (slots or {}).get("max_garage")
        min_area = (slots or {}).get("min_area_m2")
        max_area = (slots or {}).get("max_area_m2")
        neighborhood = str((slots or {}).get("neighborhood") or "").strip()
        features = (slots or {}).get("features") or []

        feature_keys = canonical_feature_keys()
        address_key = feature_keys["address"]
        bedrooms_key = feature_keys["bedrooms_clean"]
        bathrooms_key = feature_keys["bathrooms_clean"]
        garage_key = feature_keys["garage_clean"]
        sqm_key = feature_keys["sqm_clean"]

        where_clauses = [
            "p.client_id = :client_id",
            "p.deleted_at IS NULL",
            "COALESCE(p.price, 0) > 0",
        ]
        params: dict[str, Any] = {"client_id": tenant_id}

        if city:
            _append_text_filter(
                where_clauses=where_clauses,
                params=params,
                param_name="city_q",
                value=city,
                address_feature_key=address_key,
            )
        if property_type:
            _append_property_type_filter(
                where_clauses=where_clauses,
                params=params,
                value=property_type,
                address_feature_key=address_key,
            )
        if neighborhood:
            _append_text_filter(
                where_clauses=where_clauses,
                params=params,
                param_name="neighborhood_q",
                value=neighborhood,
                address_feature_key=address_key,
            )

        bedrooms_expr = _json_number_expr("p.features", bedrooms_key)
        bathrooms_expr = _json_number_expr("p.features", bathrooms_key)
        garage_expr = _json_number_expr("p.features", garage_key)
        sqm_expr = _json_number_expr("p.features", sqm_key)

        if min_rooms is not None:
            where_clauses.append(f"{bedrooms_expr} >= :min_rooms")
            params["min_rooms"] = int(min_rooms)
        if max_rooms is not None:
            where_clauses.append(f"{bedrooms_expr} <= :max_rooms")
            params["max_rooms"] = int(max_rooms)
        if min_bathrooms is not None:
            where_clauses.append(f"{bathrooms_expr} >= :min_bathrooms")
            params["min_bathrooms"] = float(min_bathrooms)
        if max_bathrooms is not None:
            where_clauses.append(f"{bathrooms_expr} <= :max_bathrooms")
            params["max_bathrooms"] = float(max_bathrooms)
        if min_garage is not None:
            where_clauses.append(f"{garage_expr} >= :min_garage")
            params["min_garage"] = int(min_garage)
        if max_garage is not None:
            where_clauses.append(f"{garage_expr} <= :max_garage")
            params["max_garage"] = int(max_garage)
        if min_area is not None:
            where_clauses.append(f"{sqm_expr} >= :min_area_m2")
            params["min_area_m2"] = float(min_area)
        if max_area is not None:
            where_clauses.append(f"{sqm_expr} <= :max_area_m2")
            params["max_area_m2"] = float(max_area)

        normalized_features = [str(item).strip().lower() for item in features if str(item).strip()]
        for idx, value in enumerate(normalized_features):
            _append_text_filter(
                where_clauses=where_clauses,
                params=params,
                param_name=f"feature_{idx}",
                value=value,
                address_feature_key=address_key,
            )

        clauses = " AND ".join(where_clauses)
        sql = (
            "SELECT "
            "p.id AS listing_id, "
            "p.title, "
            "COALESCE(p.description, '') AS description_html, "
            "COALESCE(p.address_street, '') AS address_street, "
            "COALESCE(p.price, 0) AS price, "
            "COALESCE(p.currency_id, 'USD') AS currency, "
            "COALESCE(p.features::text, '{}') AS features_json, "
            "COALESCE(img.image_urls, '[]'::jsonb) AS image_urls, "
            "p.public_url AS listing_url "
            "FROM lead_properties p "
            "LEFT JOIN LATERAL ("
            "  SELECT jsonb_agg(i.original_url ORDER BY i.is_main DESC, i.sort_order ASC, i.created_at ASC) AS image_urls "
            "  FROM lead_property_images i "
            "  WHERE i.property_id = p.id"
            ") img ON TRUE "
            f"WHERE {clauses} "
            f"ORDER BY {bedrooms_expr} DESC, COALESCE(p.price, 0) DESC "
            "LIMIT 20"
        )
        return sql, params


def _append_property_type_filter(
    *,
    where_clauses: list[str],
    params: dict[str, Any],
    value: str,
    address_feature_key: str,
) -> None:
    terms = _property_type_terms(value)
    if not terms:
        return
    term_clauses: list[str] = []
    for idx, term in enumerate(terms):
        param_name = f"property_type_q_{idx}"
        params[param_name] = f"%{term}%"
        term_clauses.append(_text_filter_clause(param_name=param_name, address_feature_key=address_feature_key))
    where_clauses.append("(" + " OR ".join(term_clauses) + ")")


def _append_text_filter(
    *,
    where_clauses: list[str],
    params: dict[str, Any],
    param_name: str,
    value: str,
    address_feature_key: str,
) -> None:
    params[param_name] = f"%{value.lower()}%"
    where_clauses.append(_text_filter_clause(param_name=param_name, address_feature_key=address_feature_key))


def _text_filter_clause(*, param_name: str, address_feature_key: str) -> str:
    return (
        "("
        f"LOWER(COALESCE(p.title, '')) LIKE :{param_name} OR "
        f"LOWER(COALESCE(p.description, '')) LIKE :{param_name} OR "
        f"LOWER(COALESCE(p.address_street, '')) LIKE :{param_name} OR "
        f"LOWER(COALESCE(p.features->>'{address_feature_key}', '')) LIKE :{param_name} OR "
        f"LOWER(COALESCE(p.features::text, '')) LIKE :{param_name}"
        ")"
    )


def _property_type_terms(value: str) -> list[str]:
    token = value.strip().lower()
    if not token:
        return []
    terms = _PROPERTY_TYPE_SEARCH_TERMS.get(token, (token,))
    unique: list[str] = []
    seen: set[str] = set()
    for term in terms:
        cleaned = str(term).strip().lower()
        if not cleaned or cleaned in seen:
            continue
        unique.append(cleaned)
        seen.add(cleaned)
    return unique


def _json_number_expr(json_column: str, feature_key: str) -> str:
    return (
        f"COALESCE(NULLIF(regexp_replace({json_column}->>'{feature_key}', '[^0-9\\\\.]', '', 'g'), ''), '0')::numeric"
    )


slots_to_sql = SlotsToSqlTranslator()
