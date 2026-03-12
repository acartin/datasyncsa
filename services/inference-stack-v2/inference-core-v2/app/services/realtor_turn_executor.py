from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession


logger = logging.getLogger("inference-core-v2.realtor-turn-executor")


class RealtorTurnExecutor:
    """Executes validated realtor SQL and returns structured facts/components."""

    def __init__(self, db_session: AsyncSession, search_limit: int = 4):
        self.db_session = db_session
        self.search_limit = max(1, min(int(search_limit or 4), 12))

    async def execute(
        self,
        *,
        realtor_turn: Optional[Dict[str, Any]],
        user_query: str,
        client_id: UUID,
    ) -> Dict[str, Any]:
        payload = self._normalize_realtor_turn_payload(realtor_turn)
        intent = payload["intent"]
        search_summary = payload.get("search_summary")
        filters = payload.get("filters") or {}

        if intent not in {"PROPERTY_SEARCH", "PROPERTY_INVENTORY", "PROPERTY_PRICE_RANGE"}:
            return {
                "handled": False,
                "components": [],
                "facts": {},
                "search_state": {},
            }

        sql = self._materialize_sql(payload.get("sql") or "", str(client_id))
        if not sql or not self._validate_sql(sql, str(client_id)):
            logger.warning("Blocked unsafe/invalid realtor SQL. intent=%s", intent)
            return {
                "handled": True,
                "status": "execution_error",
                "operation": intent,
                "components": [],
                "facts": {
                    "search_summary": search_summary,
                    "error_code": "INVALID_SQL",
                },
                "search_state": {
                    "planner_last_property_query": user_query,
                    "planner_last_sql": sql,
                    "intent": intent,
                    "search_summary": search_summary,
                    "filters": filters,
                },
            }

        search_state = {
            "planner_last_property_query": user_query,
            "planner_last_sql": sql,
            "intent": intent,
            "search_summary": search_summary,
            "filters": filters,
        }

        if intent == "PROPERTY_PRICE_RANGE":
            rows = await self._run_sql(sql)
            stats = self._extract_price_stats(rows)
            count = int(stats.get("count") or 0)
            if count <= 0:
                return {
                    "handled": True,
                    "status": "empty",
                    "operation": intent,
                    "components": [],
                    "facts": {
                        "count": 0,
                        "search_summary": search_summary,
                    },
                    "search_state": search_state,
                }
            return {
                "handled": True,
                "status": "results",
                "operation": intent,
                "components": [],
                "facts": {
                    "count": count,
                    "min_price": stats.get("min_price"),
                    "max_price": stats.get("max_price"),
                    "search_summary": search_summary,
                },
                "search_state": search_state,
            }

        if intent == "PROPERTY_INVENTORY":
            rows = await self._run_sql(sql)
            total_matches = self._extract_count(rows)

            if total_matches <= 0:
                return {
                    "handled": True,
                    "status": "empty",
                    "operation": intent,
                    "components": [],
                    "facts": {
                        "total_matches": 0,
                        "visible_count": 0,
                        "search_summary": search_summary,
                    },
                    "search_state": search_state,
                }

            if total_matches > self.search_limit:
                return {
                    "handled": True,
                    "status": "results",
                    "operation": intent,
                    "components": [],
                    "facts": {
                        "total_matches": total_matches,
                        "visible_count": 0,
                        "search_summary": search_summary,
                    },
                    "search_state": search_state,
                }

            details_sql = self._build_inventory_details_sql(sql)
            details_rows: List[Dict[str, Any]] = []
            if details_sql and self._validate_sql(details_sql, str(client_id)):
                details_rows = await self._run_sql(details_sql)

            components = self._rows_to_property_components(details_rows)
            return {
                "handled": True,
                "status": "results",
                "operation": intent,
                "components": components,
                "facts": {
                    "total_matches": total_matches,
                    "visible_count": len(components),
                    "search_summary": search_summary,
                },
                "search_state": search_state,
            }

        rows = await self._run_sql(sql)
        components = await self._rows_to_property_components(rows)
        if not components:
            return {
                "handled": True,
                "status": "empty",
                "operation": intent,
                "components": [],
                "facts": {
                    "total_matches": 0,
                    "visible_count": 0,
                    "search_summary": search_summary,
                },
                "search_state": search_state,
            }

        total_matches = len(components)
        count_sql = self._build_count_sql(sql)
        if count_sql and self._validate_sql(count_sql, str(client_id)):
            count_rows = await self._run_sql(count_sql)
            total_matches = self._extract_count(count_rows)

        visible_components = components[:3]
        visible_count = len(visible_components)
        return {
            "handled": True,
            "status": "results",
            "operation": intent,
            "components": visible_components,
            "facts": {
                "total_matches": total_matches,
                "visible_count": visible_count,
                "search_summary": search_summary,
            },
            "search_state": search_state,
        }

    @staticmethod
    def _normalize_realtor_turn_payload(raw_payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        payload = raw_payload or {}
        if not isinstance(payload, dict):
            payload = {}

        intent = str(payload.get("intent") or "NONE").strip().upper()
        if intent not in {
            "PROPERTY_SEARCH",
            "PROPERTY_INVENTORY",
            "PROPERTY_PRICE_RANGE",
            "RAG",
            "CLARIFICATION",
            "NONE",
        }:
            intent = "NONE"

        sql = payload.get("sql")
        if sql is not None:
            sql = str(sql).strip() or None

        search_summary = payload.get("search_summary")
        if search_summary is not None:
            search_summary = str(search_summary).strip() or None

        filters = payload.get("filters")
        if isinstance(filters, dict):
            allowed_filter_keys = {
                "desired_location",
                "property_type",
                "bedrooms_min",
                "bathrooms_min",
                "garage_min",
                "price_min",
                "price_max",
                "listing_intent",
            }
            normalized_filters: Dict[str, Any] = {}
            for key, value in filters.items():
                if key not in allowed_filter_keys or value is None:
                    continue
                if isinstance(value, str):
                    cleaned = value.strip()
                    if not cleaned:
                        continue
                    normalized_filters[key] = cleaned
                else:
                    normalized_filters[key] = value
        else:
            normalized_filters = {}

        return {
            "intent": intent,
            "sql": sql,
            "search_summary": search_summary,
            "filters": normalized_filters,
        }

    def _materialize_sql(self, sql: str, client_id: str) -> str:
        safe_client_id = str(client_id).replace("'", "''")
        materialized = (sql or "").strip()
        materialized = re.sub(r"(?i)\blead_leads\b", "lead_properties", materialized)
        materialized = re.sub(r"(?i)\blead_propierties\b", "lead_properties", materialized)
        materialized = materialized.replace("{client_id}", f"'{safe_client_id}'")
        materialized = materialized.replace("__CLIENT_ID__", f"'{safe_client_id}'")
        materialized = materialized.replace("{search_limit}", str(self.search_limit))

        numeric_rewrites = [
            (
                r"(?i)\(\s*features->>'garage'\s*\)\s*::\s*int\b",
                "COALESCE(NULLIF(regexp_replace(COALESCE(features->>'garage_clean', features->>'garage', ''), '[^0-9\\.]', '', 'g'), '')::numeric, 0)",
            ),
            (
                r"(?i)\(\s*features->>'bedrooms_clean'\s*\)\s*::\s*int\b",
                "COALESCE(NULLIF(regexp_replace(COALESCE(features->>'bedrooms_clean', features->>'bedrooms', ''), '[^0-9\\.]', '', 'g'), '')::numeric, 0)",
            ),
            (
                r"(?i)\(\s*features->>'bathrooms_clean'\s*\)\s*::\s*(?:float|double precision|numeric)\b",
                "COALESCE(NULLIF(regexp_replace(COALESCE(features->>'bathrooms_clean', features->>'bathrooms', ''), '[^0-9\\.]', '', 'g'), '')::numeric, 0)",
            ),
            (
                r"(?i)\(\s*features->>'sqm_clean'\s*\)\s*::\s*int\b",
                "COALESCE(NULLIF(regexp_replace(COALESCE(features->>'sqm_clean', ''), '[^0-9\\.]', '', 'g'), '')::numeric, 0)",
            ),
        ]
        for pattern, replacement in numeric_rewrites:
            materialized = re.sub(pattern, replacement, materialized)

        materialized = re.sub(
            r"(?i)\bclient_id\s*=\s*(?:'[^']*'|[0-9a-zA-Z_-]+)",
            f"client_id = '{safe_client_id}'",
            materialized,
        )

        if re.search(r"(?i)\bwhere\b", materialized):
            if not re.search(r"(?i)\bprice\s*>\s*0\b", materialized) and not re.search(
                r"(?i)\bcoalesce\s*\(\s*price\s*,\s*0\s*\)\s*>\s*0\b",
                materialized,
            ):
                materialized = re.sub(
                    r"(?i)\bwhere\b",
                    "WHERE COALESCE(price, 0) > 0 AND ",
                    materialized,
                    count=1,
                )
        else:
            order_or_limit = re.search(r"(?i)\b(order\s+by|limit)\b", materialized)
            if order_or_limit:
                idx = order_or_limit.start()
                materialized = f"{materialized[:idx]} WHERE COALESCE(price, 0) > 0 {materialized[idx:]}"
            else:
                materialized = f"{materialized} WHERE COALESCE(price, 0) > 0"

        return materialized.rstrip(";").strip()

    @staticmethod
    def _validate_sql(sql: str, client_id: str) -> bool:
        sql_upper = (sql or "").strip().upper()
        if not sql_upper.startswith("SELECT"):
            return False

        compact_sql = re.sub(r"\s+", "", sql_upper)
        normalized_client = str(client_id).upper().replace("'", "")
        if f"CLIENT_ID='{normalized_client}'" not in compact_sql:
            return False

        if ";" in sql_upper:
            return False

        if "LEAD_PROPERTIES" not in sql_upper:
            return False

        if "PRICE" not in sql_upper:
            return False
        if "COALESCE(PRICE,0)>0" not in compact_sql and "PRICE>0" not in compact_sql:
            return False

        forbidden = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "TRUNCATE", "--", ";--"]
        return not any(word in sql_upper for word in forbidden)

    async def _run_sql(self, sql: str) -> List[Dict[str, Any]]:
        try:
            result = await self.db_session.execute(text(sql))
            return [dict(row) for row in result.mappings().all()]
        except Exception as exc:
            logger.error("Realtor SQL execution error: %s", exc)
            try:
                await self.db_session.rollback()
            except Exception:
                logger.exception("Failed to rollback realtor SQL transaction after execution error")
            return []

    @staticmethod
    def _to_number(raw: Any) -> Optional[float]:
        if raw is None:
            return None
        if isinstance(raw, (int, float)):
            return float(raw)

        text_value = str(raw).strip()
        if not text_value:
            return None
        cleaned = re.sub(r"[^\d.,]", "", text_value)
        if not cleaned:
            return None
        if "," in cleaned and "." in cleaned:
            cleaned = cleaned.replace(",", "")
        elif "," in cleaned:
            cleaned = cleaned.replace(",", "")
        try:
            return float(cleaned)
        except ValueError:
            return None

    def _extract_price_from_description(self, description: str) -> Optional[float]:
        if not description:
            return None
        matches = re.findall(r"(?:USD|US\\$|\\$|₡)\\s*([\\d\\.,]+)", description, flags=re.IGNORECASE)
        for match in matches:
            parsed = self._to_number(match)
            if parsed is not None and parsed > 0:
                return parsed
        return None

    def _extract_price_from_row(self, row: Dict[str, Any]) -> Optional[float]:
        direct_price = self._to_number(row.get("price"))
        if direct_price is not None and direct_price > 0:
            return direct_price
        return self._extract_price_from_description(str(row.get("description") or ""))

    async def _get_images_map(self, property_ids: List[str]) -> Dict[str, str]:
        clean_ids = [str(pid).strip() for pid in property_ids if str(pid).strip()]
        if not clean_ids:
            return {}

        try:
            query = text(
                """
                SELECT property_id::text AS property_id, original_url
                FROM lead_property_images
                WHERE property_id IN :property_ids
                  AND original_url IS NOT NULL
                  AND original_url <> ''
                ORDER BY sort_order ASC NULLS LAST, id ASC
                """
            ).bindparams(bindparam("property_ids", expanding=True))
            result = await self.db_session.execute(query, {"property_ids": clean_ids})
            rows = result.mappings().all()
        except Exception as exc:
            logger.warning("Realtor image lookup failed: %s", exc)
            try:
                await self.db_session.rollback()
            except Exception:
                logger.exception("Failed to rollback realtor SQL transaction after image lookup error")
            return {}

        images: Dict[str, str] = {}
        for row in rows:
            property_id = str(row.get("property_id") or "").strip()
            original_url = str(row.get("original_url") or "").strip()
            if property_id and original_url and property_id not in images:
                images[property_id] = original_url
        return images

    @staticmethod
    def _parse_features(raw: Any) -> Dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        return {}

    @staticmethod
    def _location_from_features(features: Dict[str, Any], title: str) -> Optional[str]:
        address = str(features.get("address") or "").strip()
        if address:
            return address
        return title.strip() or None

    async def _rows_to_property_components(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not rows:
            return []

        image_lookup_ids: List[str] = []
        normalized_rows: List[tuple[Dict[str, Any], Dict[str, Any], Optional[float], str, str]] = []
        for row in rows:
            features = self._parse_features(row.get("features"))
            price = self._extract_price_from_row(row)
            row_uuid = str(row.get("id") or "").strip()
            public_id = str(features.get("property_id_internal") or row_uuid).strip()
            if row_uuid:
                image_lookup_ids.append(row_uuid)
            normalized_rows.append((row, features, price, row_uuid, public_id))

        images_map = await self._get_images_map(image_lookup_ids)

        components: List[Dict[str, Any]] = []
        for row, features, price, row_uuid, public_id in normalized_rows:
            location = self._location_from_features(features, str(row.get("title") or ""))
            bedrooms = self._to_number(features.get("bedrooms_clean") or features.get("bedrooms"))
            bathrooms = self._to_number(features.get("bathrooms_clean") or features.get("bathrooms"))
            garage = self._to_number(features.get("garage_clean") or features.get("garage"))
            sqm = self._to_number(features.get("sqm_clean"))

            feature_map: Dict[str, Any] = {}
            if bedrooms is not None:
                feature_map["bedrooms"] = int(bedrooms) if bedrooms.is_integer() else bedrooms
            if bathrooms is not None:
                feature_map["bathrooms"] = int(bathrooms) if bathrooms.is_integer() else bathrooms
            if garage is not None:
                feature_map["garage"] = int(garage) if garage.is_integer() else garage
            if sqm is not None:
                feature_map["sqm"] = int(sqm) if sqm.is_integer() else sqm

            components.append(
                {
                    "type": "property-card",
                    "id": public_id or row_uuid,
                    "title": str(row.get("title") or "Propiedad"),
                    "price": float(price or 0),
                    "location": location,
                    "image_url": images_map.get(row_uuid or "", None),
                    "features": feature_map,
                    "tags": [],
                }
            )

        return components

    @staticmethod
    def _extract_count(rows: List[Dict[str, Any]]) -> int:
        if not rows:
            return 0
        row = rows[0] or {}
        for key in ("total", "count", "count(*)"):
            value = row.get(key)
            if value is not None:
                try:
                    return int(value)
                except Exception:
                    continue
        try:
            first_value = next(iter(row.values()))
            return int(first_value)
        except Exception:
            return 0

    def _extract_price_stats(self, rows: List[Dict[str, Any]]) -> Dict[str, Optional[float]]:
        if not rows:
            return {"count": 0, "min_price": None, "max_price": None}
        row = rows[0] or {}
        count = self._extract_count(rows)
        min_price = self._to_number(row.get("min_price"))
        max_price = self._to_number(row.get("max_price"))
        return {
            "count": count,
            "min_price": min_price,
            "max_price": max_price,
        }

    def _fmt_money(self, value: Any) -> str:
        amount = self._to_number(value)
        if amount is None:
            return "USD N/D"
        return f"USD {amount:,.0f}"

    def _build_inventory_details_sql(self, inventory_sql: str) -> str:
        normalized = (inventory_sql or "").strip()
        match = re.search(r"\bFROM\b", normalized, flags=re.IGNORECASE)
        if not match:
            return ""

        tail = normalized[match.start() :]
        tail = re.sub(r"\bLIMIT\s+\d+\s*$", "", tail, flags=re.IGNORECASE)
        return (
            "SELECT id, title, description, features, price "
            f"{tail} "
            "ORDER BY id DESC "
            f"LIMIT {self.search_limit}"
        )

    @staticmethod
    def _build_count_sql(base_sql: str) -> str:
        normalized = (base_sql or "").strip()
        from_match = re.search(r"\bFROM\b", normalized, flags=re.IGNORECASE)
        if not from_match:
            return ""
        tail = normalized[from_match.start() :]
        tail = re.sub(r"(?is)\bORDER\s+BY\b.+$", "", tail).strip()
        tail = re.sub(r"(?is)\bLIMIT\s+\d+\b", "", tail).strip()
        return f"SELECT COUNT(*) AS total {tail}"
