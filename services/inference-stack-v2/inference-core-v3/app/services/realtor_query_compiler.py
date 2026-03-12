from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class RealtorQueryCompiler:
    search_limit: int = 4

    def compile(self, *, client_id: str, plan: Dict[str, Any]) -> Dict[str, Any]:
        normalized = self._normalize_plan(plan)
        filters = normalized["filters"]
        search_text = normalized["search_text"]
        intent = normalized["intent"]
        operation = normalized["operation"]
        result_mode = normalized["result_mode"]
        sort_by = normalized["sort_by"]

        where_clauses = [
            f"client_id = '{self._escape_literal(client_id)}'",
            "COALESCE(price, 0) > 0",
        ]

        desired_location = filters.get("desired_location")
        if self._has_value(desired_location):
            where_clauses.append(
                self._or_group(
                    [
                        self._ilike("title", str(desired_location)),
                        self._ilike("COALESCE(features->>'address', '')", str(desired_location)),
                    ]
                )
            )

        property_type = filters.get("property_type")
        if self._has_value(property_type):
            where_clauses.append(self._text_term_group(str(property_type)))

        listing_intent = filters.get("listing_intent")
        if self._has_value(listing_intent):
            where_clauses.append(self._listing_intent_group(str(listing_intent)))

        bedrooms_min = self._numeric_value(filters.get("bedrooms_min"))
        if bedrooms_min is not None:
            where_clauses.append(f"{self._numeric_feature_expr('bedrooms_clean')} >= {bedrooms_min}")

        bathrooms_min = self._numeric_value(filters.get("bathrooms_min"))
        if bathrooms_min is not None:
            where_clauses.append(f"{self._numeric_feature_expr('bathrooms_clean')} >= {bathrooms_min}")

        garage_min = self._numeric_value(filters.get("garage_min"))
        if garage_min is not None:
            where_clauses.append(f"{self._numeric_feature_expr('garage')} >= {garage_min}")

        price_min = self._numeric_value(filters.get("price_min"))
        if price_min is not None:
            where_clauses.append(f"price >= {price_min}")

        price_max = self._numeric_value(filters.get("price_max"))
        if price_max is not None:
            where_clauses.append(f"price <= {price_max}")

        for term in search_text:
            if self._has_value(term):
                where_clauses.append(self._text_term_group(str(term)))

        where_sql = " AND ".join(clause for clause in where_clauses if clause)
        summary = normalized["search_summary"] or self._build_search_summary(filters, search_text)

        if operation == "price_range" or intent == "PROPERTY_PRICE_RANGE":
            sql = (
                "SELECT MIN(price) AS min_price, MAX(price) AS max_price, COUNT(*) AS count "
                "FROM lead_properties "
                f"WHERE {where_sql}"
            )
            return self._result_payload(intent, sql, summary, filters, result_mode)

        if operation == "inventory" or intent == "PROPERTY_INVENTORY":
            sql = (
                "SELECT COUNT(*) AS total "
                "FROM lead_properties "
                f"WHERE {where_sql}"
            )
            return self._result_payload(intent, sql, summary, filters, result_mode)

        order_sql = self._order_by_clause(sort_by)
        sql = (
            "SELECT id, client_id, title, description, features, price, public_url "
            "FROM lead_properties "
            f"WHERE {where_sql} "
            f"{order_sql} "
            f"LIMIT {int(self.search_limit)}"
        )
        return self._result_payload(intent, sql, summary, filters, result_mode)

    def _normalize_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        payload = plan if isinstance(plan, dict) else {}
        filters = payload.get("filters") if isinstance(payload.get("filters"), dict) else {}
        search_text_raw = payload.get("search_text")
        if isinstance(search_text_raw, list):
            search_text = [str(item).strip() for item in search_text_raw if str(item).strip()]
        elif isinstance(search_text_raw, str) and search_text_raw.strip():
            search_text = [search_text_raw.strip()]
        else:
            search_text = []

        intent = str(payload.get("intent") or "PROPERTY_SEARCH").strip().upper()
        operation = str(payload.get("operation") or "search").strip().lower()
        result_mode = str(payload.get("result_mode") or "show_cards").strip().lower()
        sort_by = str(payload.get("sort_by") or "relevant").strip().lower()
        search_summary = str(payload.get("search_summary") or "").strip() or None

        return {
            "intent": intent,
            "operation": operation,
            "result_mode": result_mode,
            "filters": filters,
            "search_text": search_text,
            "sort_by": sort_by,
            "search_summary": search_summary,
        }

    @staticmethod
    def _numeric_feature_expr(feature_key: str) -> str:
        return (
            "COALESCE(NULLIF(regexp_replace(COALESCE(features->>'%s', ''), '[^0-9.]', '', 'g'), ''), '0')::numeric"
            % feature_key
        )

    def _text_term_group(self, term: str) -> str:
        cleaned = str(term).strip()
        return self._or_group(
            [
                self._ilike("title", cleaned),
                self._ilike("description", cleaned),
                self._ilike("features::text", cleaned),
            ]
        )

    def _listing_intent_group(self, intent: str) -> str:
        normalized = str(intent or "").strip().lower()
        if normalized == "buy":
            terms = ["venta", "vender", "sale"]
        elif normalized == "rent":
            terms = ["renta", "alquiler", "alquilar", "rent"]
        else:
            terms = [normalized] if normalized else []
        return self._or_group([self._text_term_group(term) for term in terms if term])

    @staticmethod
    def _escape_literal(value: Any) -> str:
        return str(value).replace("'", "''")

    def _ilike(self, expression: str, value: str) -> str:
        escaped = self._escape_literal(value)
        return f"{expression} ILIKE '%{escaped}%'"

    @staticmethod
    def _or_group(parts: List[str]) -> str:
        normalized = [part for part in parts if part]
        if not normalized:
            return "(TRUE)"
        return "(" + " OR ".join(normalized) + ")"

    @staticmethod
    def _has_value(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        return True

    @staticmethod
    def _numeric_value(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return str(value)
        text = str(value).strip().replace(",", "")
        if not text:
            return None
        filtered = "".join(ch for ch in text if ch.isdigit() or ch == ".")
        if not filtered:
            return None
        return filtered

    @staticmethod
    def _order_by_clause(sort_by: str) -> str:
        if sort_by == "price_desc":
            return "ORDER BY price DESC NULLS LAST, id DESC"
        if sort_by == "newest":
            return "ORDER BY id DESC"
        return "ORDER BY price ASC NULLS LAST, id DESC"

    def _build_search_summary(self, filters: Dict[str, Any], search_text: List[str]) -> str:
        parts: List[str] = []
        property_type = filters.get("property_type")
        desired_location = filters.get("desired_location")
        bedrooms_min = filters.get("bedrooms_min")
        bathrooms_min = filters.get("bathrooms_min")
        garage_min = filters.get("garage_min")

        if self._has_value(property_type):
            parts.append(str(property_type).strip())
        else:
            parts.append("propiedades")

        if self._has_value(desired_location):
            parts.append(f"en {str(desired_location).strip()}")
        if self._has_value(bedrooms_min):
            parts.append(f"con al menos {bedrooms_min} habitaciones")
        if self._has_value(bathrooms_min):
            parts.append(f"con al menos {bathrooms_min} baños")
        if self._has_value(garage_min):
            parts.append(f"con cochera para {garage_min} carros")
        if search_text:
            parts.append("filtradas por " + ", ".join(search_text))

        summary = " ".join(parts).strip()
        return summary or "propiedades disponibles"

    @staticmethod
    def _result_payload(
        intent: str,
        sql: str,
        search_summary: str,
        filters: Dict[str, Any],
        result_mode: str,
    ) -> Dict[str, Any]:
        return {
            "intent": intent,
            "sql": sql,
            "search_summary": search_summary,
            "filters": filters,
            "result_mode": result_mode,
        }
