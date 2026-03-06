import os
import re
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger("database")

class DatabaseManager:
    def __init__(self):
        self.host = os.getenv("DB_HOST", "postgres")
        self.port = int(os.getenv("DB_PORT", "5432"))
        self.database = os.getenv("DB_NAME") or os.getenv("DB_DATABASE", "agentic")
        self.user = os.getenv("DB_USER") or os.getenv("DB_USERNAME", "postgres")
        self.password = os.getenv("DB_PASS") or os.getenv("DB_PASSWORD", "")
        self._conn = None

    def get_connection(self):
        try:
            conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                cursor_factory=RealDictCursor
            )
            return conn
        except Exception as e:
            logger.error(f"❌ Database connection error: {e}")
            return None

    def get_property(self, property_id):
        conn = self.get_connection()
        if not conn: return None
        try:
            with conn.cursor() as cur:
                # Get property details
                cur.execute("SELECT * FROM lead_properties WHERE id = %s", (property_id,))
                prop = cur.fetchone()
                if not prop: return None
                
                # Get images
                cur.execute("SELECT original_url FROM lead_property_images WHERE property_id = %s ORDER BY sort_order", (property_id,))
                images = cur.fetchall()
                prop['images'] = [img['original_url'] for img in images]
                
                return prop
        except Exception as e:
            logger.error(f"Error fetching property {property_id}: {e}")
            return None

    @staticmethod
    def _parse_money_value(raw: str) -> Optional[float]:
        if not raw:
            return None
        cleaned = re.sub(r"[^\d.,]", "", raw)
        if not cleaned:
            return None
        if "," in cleaned and "." in cleaned:
            cleaned = cleaned.replace(",", "")
        elif "," in cleaned and "." not in cleaned:
            cleaned = cleaned.replace(",", "")
        try:
            return float(cleaned)
        except ValueError:
            return None

    @classmethod
    def _extract_property_filters(cls, query_text: str) -> Dict[str, Any]:
        text = (query_text or "").strip().lower()
        result: Dict[str, Any] = {
            "location": None,
            "min_price": None,
            "max_price": None,
            "bedrooms_min": None,
            "bathrooms_min": None,
            "terms": [],
        }
        if not text:
            return result

        location_match = re.search(r"(?:en|zona\s+de|por)\s+([a-záéíóúñ\s]{3,60})", text)
        if location_match:
            location = re.sub(r"\s+", " ", location_match.group(1)).strip()
            location = re.split(r"\b(?:hasta|desde|con|y|para|por)\b", location, maxsplit=1)[0].strip(" ,.?")
            if location:
                result["location"] = location

        max_match = re.search(r"(?:hasta|max(?:imo)?|menos\s+de|tope\s+de)\s*\$?\s*([\d\.,]+)", text)
        if max_match:
            result["max_price"] = cls._parse_money_value(max_match.group(1))

        min_match = re.search(r"(?:desde|min(?:imo)?|mas\s+de|más\s+de)\s*\$?\s*([\d\.,]+)", text)
        if min_match:
            result["min_price"] = cls._parse_money_value(min_match.group(1))

        bedrooms_match = re.search(r"(\d+)\s*(?:hab(?:itaciones?)?|cuartos?|dormitorios?)", text)
        if bedrooms_match:
            result["bedrooms_min"] = float(bedrooms_match.group(1))

        bathrooms_match = re.search(r"(\d+(?:[\.,]\d+)?)\s*(?:baños?|banos?)", text)
        if bathrooms_match:
            result["bathrooms_min"] = cls._parse_money_value(bathrooms_match.group(1))

        stopwords = {
            "quiero", "buscar", "busco", "casa", "casas", "apartamento", "apartamentos", "propiedad",
            "propiedades", "en", "con", "para", "por", "del", "las", "los", "una", "uno", "un",
            "de", "la", "el", "y", "o", "que", "ver", "mostrar", "me", "porfavor", "favor",
            "cuantas", "cuántas", "tienes", "tienen", "manejas", "cuantos", "cuántos",
        }
        tokens = re.findall(r"[a-záéíóúñ0-9]{3,}", text)
        terms = [t for t in tokens if t not in stopwords][:4]
        result["terms"] = terms
        return result

    @staticmethod
    def _normalized_like_expression(field_sql: str) -> str:
        return (
            "translate(lower(COALESCE(" + field_sql + ", '')), 'áéíóúüñ', 'aeiouun') "
            "LIKE translate(lower(%s), 'áéíóúüñ', 'aeiouun')"
        )

    def _append_text_match_clause(
        self,
        where: List[str],
        params: List[Any],
        like_value: str,
        fields: List[str],
    ) -> None:
        clauses: List[str] = []
        for field_sql in fields:
            clauses.append(self._normalized_like_expression(field_sql))
            params.append(like_value)
        where.append("(" + " OR ".join(clauses) + ")")

    def _build_property_where_clause(
        self,
        client_id: str,
        query_text: str,
        include_terms: bool = True,
    ) -> tuple[List[str], List[Any], Dict[str, Any]]:
        filters = self._extract_property_filters(query_text)
        where = ["client_id = %s", "COALESCE(price, 0) > 0"]
        params: List[Any] = [client_id]

        searchable_fields = [
            "title",
            "address_city",
            "address_state",
            "features->>'address'",
            "features::text",
        ]

        location = filters.get("location")
        if location:
            self._append_text_match_clause(where, params, f"%{location}%", searchable_fields)

        min_price = filters.get("min_price")
        if min_price is not None:
            where.append("COALESCE(price, 0) >= %s")
            params.append(min_price)

        max_price = filters.get("max_price")
        if max_price is not None:
            where.append("COALESCE(price, 0) <= %s")
            params.append(max_price)

        bedrooms_min = filters.get("bedrooms_min")
        if bedrooms_min is not None:
            where.append(
                "COALESCE(NULLIF(regexp_replace(COALESCE(features->>'bedrooms_clean', features->>'bedrooms', ''), '[^0-9\\.]', '', 'g'), '')::numeric, 0) >= %s"
            )
            params.append(bedrooms_min)

        bathrooms_min = filters.get("bathrooms_min")
        if bathrooms_min is not None:
            where.append(
                "COALESCE(NULLIF(regexp_replace(COALESCE(features->>'bathrooms_clean', features->>'bathrooms', ''), '[^0-9\\.]', '', 'g'), '')::numeric, 0) >= %s"
            )
            params.append(bathrooms_min)

        terms = filters.get("terms") or []
        if include_terms and terms:
            term_clauses = []
            for term in terms:
                like_value = f"%{term}%"
                single_term_clauses = []
                for field_sql in searchable_fields:
                    single_term_clauses.append(self._normalized_like_expression(field_sql))
                    params.append(like_value)
                term_clauses.append("(" + " OR ".join(single_term_clauses) + ")")
            where.append("(" + " OR ".join(term_clauses) + ")")

        return where, params, filters

    def extract_property_filters(self, query_text: str) -> Dict[str, Any]:
        return self._extract_property_filters(query_text)

    def count_properties(self, client_id: str, query_text: str, include_terms: bool = True) -> int:
        conn = self.get_connection()
        if not conn:
            return 0
        try:
            where, params, _filters = self._build_property_where_clause(
                client_id,
                query_text,
                include_terms=include_terms,
            )

            query = f"SELECT COUNT(*) AS total FROM lead_properties WHERE {' AND '.join(where)}"
            with conn.cursor() as cur:
                cur.execute(query, tuple(params))
                row = cur.fetchone() or {}
                return int(row.get("total") or 0)
        except Exception as e:
            logger.error(f"Error counting properties for client {client_id}: {e}")
            return 0

    def get_property_price_stats(self, client_id: str, query_text: str, include_terms: bool = False) -> Dict[str, Any]:
        conn = self.get_connection()
        if not conn:
            return {"count": 0, "min_price": None, "max_price": None}
        try:
            where, params, _filters = self._build_property_where_clause(
                client_id,
                query_text,
                include_terms=include_terms,
            )
            query = f"""
                SELECT
                    COUNT(*) AS total,
                    MIN(price) AS min_price,
                    MAX(price) AS max_price
                FROM lead_properties
                WHERE {' AND '.join(where)}
            """
            with conn.cursor() as cur:
                cur.execute(query, tuple(params))
                row = cur.fetchone() or {}
                return {
                    "count": int(row.get("total") or 0),
                    "min_price": float(row.get("min_price")) if row.get("min_price") is not None else None,
                    "max_price": float(row.get("max_price")) if row.get("max_price") is not None else None,
                }
        except Exception as e:
            logger.error(f"Error getting property price stats for client {client_id}: {e}")
            return {"count": 0, "min_price": None, "max_price": None}

    def search_properties(
        self,
        client_id: str,
        query_text: str,
        limit: int = 4,
        include_terms: bool = True,
    ) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        if not conn:
            return []
        try:
            limit = max(1, min(int(limit or 4), 12))
        except Exception:
            limit = 4

        try:
            where, params, filters = self._build_property_where_clause(
                client_id,
                query_text,
                include_terms=include_terms,
            )
            location = filters.get("location")
            terms = filters.get("terms") or []

            query = f"""
                SELECT id, title, price, address_city, address_state, features
                FROM lead_properties
                WHERE {' AND '.join(where)}
                ORDER BY CASE WHEN price IS NULL THEN 1 ELSE 0 END, price ASC
                LIMIT %s
            """
            params.append(limit)

            with conn.cursor() as cur:
                cur.execute(query, tuple(params))
                rows = cur.fetchall() or []

                if not rows and (location or terms):
                    cur.execute(
                        """
                        SELECT id, title, price, address_city, address_state, features
                        FROM lead_properties
                        WHERE client_id = %s
                        ORDER BY CASE WHEN price IS NULL THEN 1 ELSE 0 END, price ASC
                        LIMIT %s
                        """,
                        (client_id, limit),
                    )
                    rows = cur.fetchall() or []

                property_ids = [str(r.get("id")) for r in rows if r.get("id") is not None]
                images_map = self.get_property_images_batch(property_ids)
                for row in rows:
                    row_id = str(row.get("id")) if row.get("id") is not None else None
                    row["images"] = images_map.get(row_id, [])
                return rows
        except Exception as e:
            logger.error(f"Error searching properties for client {client_id}: {e}")
            return []

    def get_property_images_batch(self, property_ids: List[str]) -> Dict[str, List[str]]:
        conn = self.get_connection()
        if not conn or not property_ids:
            return {}
        try:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """
                        SELECT property_id, original_url
                        FROM lead_property_images
                        WHERE property_id = ANY(%s)
                        ORDER BY property_id, sort_order
                        """,
                        (property_ids,),
                    )
                except Exception:
                    conn.rollback()
                    cur.execute(
                        """
                        SELECT property_id, original_url
                        FROM lead_property_images
                        WHERE property_id = ANY(%s)
                        ORDER BY property_id
                        """,
                        (property_ids,),
                    )
                rows = cur.fetchall() or []

            result: Dict[str, List[str]] = {}
            for row in rows:
                prop_id = str(row.get("property_id")) if row.get("property_id") is not None else None
                url = row.get("original_url")
                if not prop_id or not url:
                    continue
                result.setdefault(prop_id, []).append(url)
            return result
        except Exception as e:
            logger.error(f"Error fetching property images batch: {e}")
            return {}

    def get_branding(self, client_id, brand_project=None):
        conn = self.get_connection()
        if not conn: return None
        try:
            with conn.cursor() as cur:
                brand = None
                if brand_project:
                    cur.execute(
                        "SELECT * FROM lead_brand_configs WHERE client_id = %s AND project = %s",
                        (client_id, brand_project),
                    )
                    brand = cur.fetchone()

                if not brand:
                    cur.execute(
                        "SELECT * FROM lead_brand_configs WHERE client_id = %s AND project = %s",
                        (client_id, "default"),
                    )
                    brand = cur.fetchone()

                if not brand:
                    cur.execute(
                        "SELECT * FROM lead_brand_configs WHERE client_id = %s ORDER BY project LIMIT 1",
                        (client_id,),
                    )
                    brand = cur.fetchone()

                if not brand:
                    # Fallback to client name if no config exists
                    cur.execute("SELECT name FROM lead_clients WHERE id = %s", (client_id,))
                    client = cur.fetchone()
                    if client:
                        return {"agent_name": client['name']}
                return brand
        except Exception as e:
            logger.error(f"Error fetching branding for {client_id}: {e}")
            return None

    def get_client_vertical_context(self, client_id: str) -> Optional[Dict[str, Any]]:
        """
        Resolve tenant vertical context from lead_clients.vertical_id + lead_client_verticals.
        """
        conn = self.get_connection()
        if not conn:
            return None
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        c.id AS client_id,
                        c.vertical_id AS vertical_id,
                        c.scoring_model_id AS scoring_model_id,
                        v.slug AS vertical_slug,
                        v.name AS vertical_name
                    FROM lead_clients c
                    LEFT JOIN lead_client_verticals v ON v.id = c.vertical_id
                    WHERE c.id = %s
                """, (client_id,))
                row = cur.fetchone()
                if not row:
                    return {
                        "client_exists": False,
                        "vertical_id": None,
                        "scoring_model_id": None,
                        "vertical_slug": None,
                        "vertical_name": None,
                    }
                return {
                    "client_exists": True,
                    "vertical_id": row["vertical_id"],
                    "scoring_model_id": row["scoring_model_id"],
                    "vertical_slug": row["vertical_slug"],
                    "vertical_name": row["vertical_name"],
                }
        except Exception as e:
            logger.error(f"Error resolving client vertical context: {e}")
            return None

db_manager = DatabaseManager()
