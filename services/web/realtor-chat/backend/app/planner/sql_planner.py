from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, List

from app.core.database import db_manager
from app.planner.models import SQLIntent, SQLPlan, SQLPlannerResult

logger = logging.getLogger("sql_planner")


class SQLPlanner:
    """LLM-based planner that classifies intent and produces SQL, then executes validated SELECTs.

    Flow:
    1. `plan()` builds a strict system prompt, sends user text + compact session context to the LLM,
       parses JSON output, and maps it to `SQLPlan`.
    2. `execute()` validates SQL safety (SELECT-only + tenant filter + forbidden tokens), executes SQL,
       and renders the same response behavior per intent (inventory, range, search).
    3. Session memory keeps compatibility keys and adds `planner_last_sql` for co-reference turns.
    """

    _SYSTEM_PROMPT_TEMPLATE = """
Eres un clasificador de intents y generador de SQL para un chatbot inmobiliario costarricense.
Recibes el mensaje del usuario y el historial reciente. Respondes ÚNICAMENTE con JSON válido.

SCHEMA:
TABLE lead_properties: id, client_id, title (TEXT), description (TEXT/HTML), features (JSONB), price (NUMERIC)
features JSONB: bedrooms_clean (INT), bathrooms_clean (FLOAT), sqm_clean (INT), lot_size_sqm (TEXT),
garage (TEXT), year_built (TEXT), address (TEXT), amenities (JSONB array), is_featured (BOOL)

REGLAS SQL:
- Solo SELECT. Nunca UPDATE, DELETE, INSERT, DROP.
- Siempre incluir WHERE client_id = {client_id}
- Siempre incluir filtro de precio publicado: COALESCE(price, 0) > 0
- Tabla objetivo: usar lead_properties (no lead_leads)
- Búsqueda estricta: filtrar SOLO contra title, description, features y price
- Location: usar ILIKE en title, description y features->>'address'
- Para PROPERTY_SEARCH/PROPERTY_INVENTORY devolver al menos: id, title, description, features
- Amenidades: features->'amenities' @> '["Nombre"]'::jsonb
- Numéricos en JSON: usar extractores robustos sobre *_clean y campo crudo:
  - dormitorios: COALESCE(NULLIF(regexp_replace(COALESCE(features->>'bedrooms_clean', features->>'bedrooms', ''), '[^0-9\\.]', '', 'g'), '')::numeric, 0)
  - banos: COALESCE(NULLIF(regexp_replace(COALESCE(features->>'bathrooms_clean', features->>'bathrooms', ''), '[^0-9\\.]', '', 'g'), '')::numeric, 0)
  - garage/carros: COALESCE(NULLIF(regexp_replace(COALESCE(features->>'garage_clean', features->>'garage', ''), '[^0-9\\.]', '', 'g'), '')::numeric, 0)
  - m2 construccion: COALESCE(NULLIF(regexp_replace(COALESCE(features->>'sqm_clean', ''), '[^0-9\\.]', '', 'g'), '')::numeric, 0)
- Cuando el usuario diga "al menos N", usa >= N sobre el extractor correspondiente.
- Default LIMIT: {search_limit}

OUTPUT FORMAT (siempre):
{
  "intent": "PROPERTY_SEARCH | PROPERTY_INVENTORY | PROPERTY_PRICE_RANGE | RAG | CLARIFICATION | NONE",
  "sql": "SELECT ... (solo si intent es PROPERTY_SEARCH, PROPERTY_INVENTORY o PROPERTY_PRICE_RANGE)",
  "clarification": "Pregunta al usuario (solo si intent = CLARIFICATION)",
  "reasoning": "Una línea explicando tu decisión"
}

INTENTS:
- PROPERTY_SEARCH: usuario quiere ver listados de propiedades
- PROPERTY_INVENTORY: usuario pregunta cuántas propiedades hay
- PROPERTY_PRICE_RANGE: usuario pregunta por rango de precios (usa MIN/MAX)
- Para rango de precio, puedes devolver filas con description y calcular min/max fuera de SQL
- RAG: pregunta general sobre bienes raíces, proceso de compra, legal, etc.
- CLARIFICATION: solo cuando sea imposible inferir una búsqueda útil con el mensaje actual + contexto reciente
- NONE: saludo, off-topic, irrelevante

COREFERENCES: usa session_data['planner_last_sql'] para resolver referencias como
"las más baratas de esas", "en Escazú" solo, "la que tiene piscina", "muéstramelas".
REGLA DE CONTEXTO OBLIGATORIA:
- No arrastres filtros previos por defecto.
- Solo reutiliza filtros de session_data['planner_last_sql'] cuando el mensaje actual sea una co-referencia explícita
  a resultados previos (ej: "de esas", "las mismas", "esas opciones", "refinar", "más baratas de esas").
- Si el usuario escribe una nueva búsqueda directa (ej: "en Heredia", "casas en San José", "apartamento en Escazú"),
  genera SQL nuevo solo con el mensaje actual y NO heredes garage/habitaciones/presupuesto anteriores.
""".strip()

    _INTENT_MAP = {
        "PROPERTY_SEARCH": SQLIntent.PROPERTY_SEARCH,
        "PROPERTY_INVENTORY": SQLIntent.PROPERTY_INVENTORY,
        "PROPERTY_PRICE_RANGE": SQLIntent.PROPERTY_PRICE_RANGE,
        "RAG": SQLIntent.NONE,
        "NONE": SQLIntent.NONE,
    }

    def __init__(self, search_limit: int = 4, llm_client: Any | None = None):
        self.search_limit = max(1, min(int(search_limit or 4), 12))
        self.llm_client = llm_client

    @staticmethod
    def _normalize(text: str) -> str:
        return (text or "").strip()

    def _build_system_prompt(self) -> str:
        return self._SYSTEM_PROMPT_TEMPLATE.replace("{search_limit}", str(self.search_limit))

    def _load_prompt_for_client_sync(self, client_id: str | None) -> str | None:
        if not client_id:
            return None
        conn = db_manager.get_connection()
        if not conn:
            return None
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT prompt_text
                    FROM lead_ai_prompts
                    WHERE is_active = TRUE
                      AND deleted_at IS NULL
                      AND (
                        (client_id::text = %s AND slug IN ('sql_planner_system', 'sql_planner'))
                        OR (client_id IS NULL AND slug IN ('sql_planner_system', 'sql_planner'))
                      )
                    ORDER BY
                      CASE WHEN client_id::text = %s THEN 0 ELSE 1 END,
                      CASE slug WHEN 'sql_planner_system' THEN 0 ELSE 1 END,
                      updated_at DESC
                    LIMIT 1
                    """,
                    (str(client_id), str(client_id)),
                )
                row = cur.fetchone() or {}
                prompt_text = row.get("prompt_text") if isinstance(row, dict) else None
                if isinstance(prompt_text, str) and prompt_text.strip():
                    return prompt_text.strip()
                return None
        except Exception as exc:
            logger.warning("SQLPlanner prompt lookup failed for client_id=%s: %s", client_id, exc)
            return None
        finally:
            try:
                conn.close()
            except Exception:
                pass

    async def _resolve_system_prompt(self, session_data: Dict[str, Any] | None) -> str:
        client_id = str((session_data or {}).get("client_id") or "").strip()
        if not client_id:
            return self._build_system_prompt()
        db_prompt = await asyncio.to_thread(self._load_prompt_for_client_sync, client_id)
        if db_prompt:
            return db_prompt.replace("{search_limit}", str(self.search_limit)).replace("{client_id}", client_id)
        return self._build_system_prompt()

    @staticmethod
    def _session_context(session_data: Dict[str, Any] | None) -> Dict[str, Any]:
        session_data = session_data or {}
        relevant = {
            "planner_last_property_query": session_data.get("planner_last_property_query"),
            "planner_last_sql": session_data.get("planner_last_sql"),
            "search_active": session_data.get("search_active"),
            "search_context": session_data.get("search_context"),
        }
        history = session_data.get("history") or session_data.get("messages")
        if isinstance(history, list):
            relevant["history_tail"] = history[-4:]
        return relevant

    @staticmethod
    def _parse_json_payload(raw: str) -> Dict[str, Any]:
        text = (raw or "").strip()
        if not text:
            raise ValueError("Empty LLM response")

        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
            text = re.sub(r"```$", "", text).strip()

        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]

        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("LLM response is not a JSON object")
        return parsed

    async def plan(self, user_text: str, session_data: Dict[str, Any]) -> SQLPlan:
        normalized = self._normalize(user_text)
        if not normalized:
            return SQLPlan(intent=SQLIntent.NONE, user_query=user_text, effective_query=None)

        if not self.llm_client:
            logger.warning("SQLPlanner plan() called without llm_client; falling back to NONE")
            return SQLPlan(intent=SQLIntent.NONE, user_query=user_text, effective_query=None)

        try:
            system_prompt = await self._resolve_system_prompt(session_data)
            user_payload = {
                "user_text": user_text,
                "session_data": self._session_context(session_data),
            }
            raw = await self.llm_client.complete(
                system=system_prompt,
                messages=[{"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}],
            )
            payload = self._parse_json_payload(raw)
        except Exception as exc:
            logger.exception("SQLPlanner LLM planning failed: %s", exc)
            return SQLPlan(intent=SQLIntent.NONE, user_query=user_text, effective_query=None)

        intent_raw = str(payload.get("intent") or "NONE").strip().upper()
        sql = payload.get("sql")
        clarification = payload.get("clarification")
        reasoning = payload.get("reasoning")
        if reasoning:
            logger.debug("SQLPlanner reasoning: %s", reasoning)

        if intent_raw == "CLARIFICATION":
            return SQLPlan(
                intent=SQLIntent.PROPERTY_SEARCH,
                user_query=user_text,
                effective_query=None,
                needs_clarification=True,
                clarification_message=(clarification or "¿Me confirmas zona, presupuesto o tipo de propiedad?"),
            )

        intent = self._INTENT_MAP.get(intent_raw, SQLIntent.NONE)
        if intent == SQLIntent.NONE:
            return SQLPlan(intent=SQLIntent.NONE, user_query=user_text, effective_query=None)

        if not isinstance(sql, str) or not sql.strip():
            logger.warning("SQLPlanner received property intent without SQL. intent=%s", intent_raw)
            return SQLPlan(intent=SQLIntent.NONE, user_query=user_text, effective_query=None)

        return SQLPlan(
            intent=intent,
            user_query=user_text,
            effective_query=sql.strip(),
        )

    @staticmethod
    def _location_suffix(filters: Dict[str, Any]) -> str:
        location = (filters or {}).get("location")
        if not location:
            return ""
        normalized = str(location).strip()
        if not normalized:
            return ""
        return f" en {normalized.title()}"

    @staticmethod
    def _fmt_money(value: float | None) -> str:
        if value is None:
            return "N/D"
        return f"${value:,.0f}"

    def _materialize_sql(self, sql: str, client_id: str, user_query: str = "") -> str:
        safe_client_id = str(client_id).replace("'", "''")
        materialized = (sql or "").strip()
        materialized = re.sub(r"(?i)\blead_leads\b", "lead_properties", materialized)
        materialized = re.sub(r"(?i)\blead_propierties\b", "lead_properties", materialized)
        materialized = materialized.replace("{client_id}", f"'{safe_client_id}'")
        materialized = materialized.replace("__CLIENT_ID__", f"'{safe_client_id}'")
        materialized = materialized.replace("{search_limit}", str(self.search_limit))
        # Normalize fragile direct casts generated by LLM to robust numeric extractors over JSON text fields.
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
        # Force tenant scoping to the runtime client_id even if the model guessed another value.
        materialized = re.sub(
            r"(?i)\bclient_id\s*=\s*(?:'[^']*'|[0-9a-zA-Z_-]+)",
            f"client_id = '{safe_client_id}'",
            materialized,
        )
        if re.search(r"(?i)\bwhere\b", materialized):
            if not re.search(r"(?i)\bprice\s*>\s*0\b", materialized) and not re.search(
                r"(?i)\bcoalesce\s*\(\s*price\s*,\s*0\s*\)\s*>\s*0\b", materialized
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
                materialized = (
                    f"{materialized[:idx]} WHERE COALESCE(price, 0) > 0 {materialized[idx:]}"
                )
            else:
                materialized = f"{materialized} WHERE COALESCE(price, 0) > 0"
        materialized = materialized.rstrip(";").strip()
        return materialized

    def _validate_sql(self, sql: str, client_id: str) -> bool:
        sql_upper = (sql or "").strip().upper()
        if not sql_upper.startswith("SELECT"):
            return False

        compact_sql = sql_upper.replace(" ", "")
        compact_sql = compact_sql.replace("\n", "").replace("\t", "")
        if "CLIENT_ID=" not in compact_sql:
            return False

        if ";" in sql_upper:
            return False

        # Enforce strict search surface: only title/description/features (+ id/client_id) in query text.
        forbidden_columns = ["ADDRESS_CITY", "ADDRESS_STATE", "BEDROOMS", "BATHROOMS", "AREA_SQM"]
        if any(col in sql_upper for col in forbidden_columns):
            return False

        if "PRICE" not in sql_upper:
            return False
        if "COALESCE(PRICE,0)>0" not in compact_sql and "PRICE>0" not in compact_sql:
            return False

        forbidden = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "TRUNCATE", "--", ";--"]
        return not any(word in sql_upper for word in forbidden)

    def _run_sql_sync(self, sql: str) -> List[Dict[str, Any]]:
        conn = db_manager.get_connection()
        if not conn:
            return []
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall() or []
                return list(rows)
        except Exception as exc:
            logger.error("SQL execution error in planner: %s", exc)
            return []
        finally:
            try:
                conn.close()
            except Exception:
                pass

    async def _run_sql(self, sql: str) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self._run_sql_sync, sql)

    @staticmethod
    def _to_number(raw: Any) -> float | None:
        if raw is None:
            return None
        if isinstance(raw, (int, float)):
            return float(raw)
        text = str(raw).strip()
        if not text:
            return None
        cleaned = re.sub(r"[^\d.,]", "", text)
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

    def _extract_price_from_description(self, description: str) -> float | None:
        if not description:
            return None
        matches = re.findall(r"(?:USD|US\$|\$|₡)\s*([\d\.,]+)", description, flags=re.IGNORECASE)
        for match in matches:
            parsed = self._to_number(match)
            if parsed is not None and parsed > 0:
                return parsed
        return None

    def _extract_price_from_row(self, row: Dict[str, Any]) -> float | None:
        direct_price = self._to_number(row.get("price"))
        if direct_price is not None and direct_price > 0:
            return direct_price
        return self._extract_price_from_description(str(row.get("description") or ""))

    def _get_images_map(self, property_ids: List[str]) -> Dict[str, str]:
        clean_ids = [str(pid).strip() for pid in property_ids if str(pid).strip()]
        if not clean_ids:
            return {}
        conn = db_manager.get_connection()
        if not conn:
            return {}
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT property_id::text AS property_id, original_url
                    FROM lead_property_images
                    WHERE property_id::text = ANY(%s)
                    ORDER BY property_id::text, sort_order
                    """,
                    (clean_ids,),
                )
                rows = cur.fetchall() or []
            images: Dict[str, str] = {}
            for row in rows:
                pid = str(row.get("property_id") or "").strip()
                url = row.get("original_url")
                if not pid or not url:
                    continue
                images.setdefault(pid, str(url))
            return images
        except Exception as exc:
            logger.warning("SQLPlanner image lookup failed: %s", exc)
            return {}
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _rows_to_property_components(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        row_ids = [str(row.get("id")) for row in rows if isinstance(row, dict) and row.get("id") is not None]
        images_map = self._get_images_map(row_ids)
        components: List[Dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            features = row.get("features") if isinstance(row.get("features"), dict) else {}
            amenities = features.get("amenities") if isinstance(features.get("amenities"), list) else []

            price = self._extract_price_from_row(row) or 0.0
            location = (features.get("address") or "").strip() if isinstance(features.get("address"), str) else None
            property_id = str(row.get("id")) if row.get("id") is not None else None

            card = {
                "type": "property-card",
                "id": property_id,
                "title": str(row.get("title") or "Propiedad Disponible"),
                "price": float(price),
                "location": location,
                "image_url": images_map.get(property_id or ""),
                "features": {
                    "bedrooms": int(self._to_number(features.get("bedrooms_clean")) or 0),
                    "bathrooms": float(self._to_number(features.get("bathrooms_clean")) or 0),
                    "sqm": int(self._to_number(features.get("sqm_clean")) or 0),
                },
                "tags": [str(a) for a in amenities[:5]],
            }
            components.append(card)
        return components

    @staticmethod
    def _extract_count(rows: List[Dict[str, Any]]) -> int:
        if not rows:
            return 0
        row = rows[0] if isinstance(rows[0], dict) else {}
        for key in ("count", "total", "qty", "cantidad"):
            value = row.get(key)
            if value is not None:
                try:
                    return int(value)
                except Exception:
                    continue
        return len(rows)

    def _extract_price_stats(self, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not rows:
            return {"count": 0, "min_price": None, "max_price": None}

        first = rows[0] if isinstance(rows[0], dict) else {}
        count = self._extract_count(rows)

        min_price = self._to_number(first.get("min_price") if isinstance(first, dict) else None)
        max_price = self._to_number(first.get("max_price") if isinstance(first, dict) else None)

        if min_price is None or max_price is None:
            prices = [self._extract_price_from_row(row) for row in rows if isinstance(row, dict)]
            prices = [p for p in prices if p is not None]
            if prices:
                min_price = min_price if min_price is not None else min(prices)
                max_price = max_price if max_price is not None else max(prices)
                count = max(count, len(prices))

        return {"count": int(count), "min_price": min_price, "max_price": max_price}

    def _build_inventory_details_sql(self, inventory_sql: str) -> str:
        normalized = (inventory_sql or "").strip()
        match = re.search(r"\bFROM\b", normalized, flags=re.IGNORECASE)
        if not match:
            return ""

        tail = normalized[match.start() :]
        tail = re.sub(r"\bLIMIT\s+\d+\s*$", "", tail, flags=re.IGNORECASE)
        return (
            "SELECT id, title, description, features "
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

    async def execute(
        self,
        plan: SQLPlan,
        client_id: str,
        transformer,
    ) -> SQLPlannerResult:
        if plan.needs_clarification:
            return SQLPlannerResult(
                handled=True,
                answer_override=plan.clarification_message,
            )

        if plan.intent == SQLIntent.NONE:
            return SQLPlannerResult(handled=False)

        sql = self._materialize_sql(plan.effective_query or "", client_id, user_query=plan.user_query)
        if not sql or not self._validate_sql(sql, client_id):
            logger.warning("SQLPlanner blocked unsafe/invalid SQL. intent=%s", plan.intent)
            return SQLPlannerResult(handled=False)

        location_suffix = ""
        session_updates = {
            "planner_last_property_query": plan.user_query,
            "planner_last_sql": sql,
            "search_active": True,
            "search_context": {
                "intent": plan.intent.value if hasattr(plan.intent, "value") else str(plan.intent),
                "last_user_query": plan.user_query,
                "last_sql": sql,
            },
        }

        if plan.intent == SQLIntent.PROPERTY_PRICE_RANGE:
            rows = await self._run_sql(sql)
            stats = self._extract_price_stats(rows)
            count = int(stats.get("count") or 0)
            if count <= 0:
                return SQLPlannerResult(
                    handled=True,
                    answer_override=(
                        f"No tengo propiedades disponibles{location_suffix} para calcular un rango de precios en este momento."
                    ),
                    session_updates=session_updates,
                )

            return SQLPlannerResult(
                handled=True,
                answer_override=(
                    f"Actualmente tengo {count} propiedades con precio publicado{location_suffix}. "
                    f"El rango de precios va desde {self._fmt_money(stats.get('min_price'))} "
                    f"hasta {self._fmt_money(stats.get('max_price'))}. "
                    "Si quieres, te las filtro por presupuesto o por habitaciones."
                ),
                session_updates=session_updates,
            )

        if plan.intent == SQLIntent.PROPERTY_INVENTORY:
            rows = await self._run_sql(sql)
            total_matches = self._extract_count(rows)

            if total_matches > self.search_limit:
                return SQLPlannerResult(
                    handled=True,
                    answer_override=(
                        f"Si, tengo {total_matches} propiedades{location_suffix}. "
                        "Dime si tienes preferencia de precio, habitaciones o zona, "
                        "o si prefieres que te muestre todas."
                    ),
                    session_updates=session_updates,
                )

            if total_matches <= 0:
                return SQLPlannerResult(
                    handled=True,
                    answer_override=(
                        f"No tengo propiedades disponibles{location_suffix} en este momento. "
                        "Si quieres, te muestro opciones en zonas cercanas o en otro rango de precio."
                    ),
                    session_updates=session_updates,
                )

            details_sql = self._build_inventory_details_sql(sql)
            details_rows: List[Dict[str, Any]] = []
            if details_sql and self._validate_sql(details_sql, client_id):
                details_rows = await self._run_sql(details_sql)
            components = self._rows_to_property_components(details_rows)

            return SQLPlannerResult(
                handled=True,
                answer_override=(
                    f"Si, tengo {total_matches} propiedades{location_suffix}. "
                    "Te las muestro y, si quieres, luego las filtramos por precio, habitaciones o presupuesto."
                ),
                components=components,
                session_updates=session_updates,
            )

        if plan.intent == SQLIntent.PROPERTY_SEARCH:
            rows = await self._run_sql(sql)
            components = self._rows_to_property_components(rows)
            if not components:
                return SQLPlannerResult(
                    handled=True,
                    answer_override=(
                        f"No encontré propiedades{location_suffix} con ese criterio ahora mismo. "
                        "Si quieres, te propongo zonas cercanas o ajustamos el presupuesto."
                    ),
                    session_updates=session_updates,
                )

            total_matches = len(components)
            count_sql = self._build_count_sql(sql)
            if count_sql and self._validate_sql(count_sql, client_id):
                count_rows = await self._run_sql(count_sql)
                total_matches = self._extract_count(count_rows)

            visible_components = components[:3]
            visible_count = len(visible_components)
            if total_matches > visible_count:
                return SQLPlannerResult(
                    handled=True,
                    answer_override=(
                        "Te he mostrado solo 3 propiedades, pero tengo más. "
                        "Si me das más detalles, podemos refinar la búsqueda."
                    ),
                    components=visible_components,
                    session_updates=session_updates,
                )
            return SQLPlannerResult(
                handled=True,
                components=visible_components,
                session_updates=session_updates,
            )

        return SQLPlannerResult(handled=False)
