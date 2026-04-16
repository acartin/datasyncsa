"""Property access repository for realtor flows."""

from __future__ import annotations

from decimal import Decimal
import re
from typing import Sequence

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncEngine

from services.ai_runtime.graph.realtor.contracts import Property


class PropertyRepository:
    """Runs tenant-filtered property reads."""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine
        self._property_type_cache: list[str] | None = None

    async def load_property_types(self) -> list[str]:
        if self._property_type_cache is not None:
            return list(self._property_type_cache)
        query = text(
            """
            SELECT name
            FROM lead_property_types
            WHERE name IS NOT NULL
            ORDER BY id
            """
        )
        async with self.engine.begin() as connection:
            rows = (await connection.execute(query)).scalars().all()
        self._property_type_cache = [str(item) for item in rows if item]
        return list(self._property_type_cache)

    @staticmethod
    def _normalize_search_sql(sql: str) -> str:
        normalized = str(sql or "").strip()
        if not normalized:
            return "SELECT * FROM searchable_properties WHERE client_id = :client_id ORDER BY price ASC LIMIT 12"
        normalized = re.sub(r"(?i)\blead_properties\b", "searchable_properties", normalized)
        return normalized

    @staticmethod
    def _to_float(value: object) -> float | None:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return float(value)
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_int(value: object, *, default: int = 0) -> int:
        if value is None:
            return default
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, Decimal):
            return int(value)
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

    @staticmethod
    async def _fetch_property_assets(
        connection,
        property_ids: Sequence[str],
    ) -> dict[str, dict[str, object]]:
        ids = [str(item).strip() for item in property_ids if str(item).strip()]
        if not ids:
            return {}
        query = text(
            """
            SELECT property_id::text AS property_id, original_url
            FROM lead_property_images
            WHERE property_id::text IN :property_ids
            ORDER BY property_id, sort_order NULLS LAST
            """
        ).bindparams(bindparam("property_ids", expanding=True))
        rows = (await connection.execute(query, {"property_ids": ids})).mappings().all()
        assets: dict[str, dict[str, object]] = {}
        for row in rows:
            property_id = str(row.get("property_id") or "").strip()
            original_url = str(row.get("original_url") or "").strip()
            if not property_id or not original_url:
                continue
            entry = assets.setdefault(property_id, {"primary_image_url": None, "image_urls": []})
            image_urls = entry["image_urls"]
            if not image_urls:
                entry["primary_image_url"] = original_url
            image_urls.append(original_url)
        return assets

    @classmethod
    def _to_canonical_property(cls, row: dict[str, object]) -> Property:
        features_raw = row.get("features") if isinstance(row.get("features"), dict) else {}
        address_parts = [
            str(part).strip()
            for part in [
                row.get("address_street"),
                row.get("address_city"),
                row.get("address_state"),
                row.get("address_zip"),
            ]
            if part
        ]
        address = str(features_raw.get("address") or "").strip() or ", ".join(address_parts) or None
        garage_raw = features_raw.get("garage")
        garage_clean = cls._to_int(features_raw.get("garage_clean"), default=cls._to_int(garage_raw, default=0))
        bedrooms_clean = cls._to_int(features_raw.get("bedrooms_clean"), default=cls._to_int(row.get("bedrooms"), default=0))
        bathrooms_clean = cls._to_float(features_raw.get("bathrooms_clean"))
        if bathrooms_clean is None:
            bathrooms_clean = cls._to_float(row.get("bathrooms")) or 0.0
        sqm_clean_raw = features_raw.get("sqm_clean")
        sqm_clean = cls._to_int(sqm_clean_raw, default=cls._to_int(row.get("area_sqm"), default=0)) or None
        payload = {
            "id": str(row.get("id") or ""),
            "client_id": str(row.get("client_id") or ""),
            "title": str(row.get("title") or ""),
            "description_html": str(row.get("description") or ""),
            "price": cls._to_float(row.get("price")) or 0.0,
            "currency": str(row.get("currency_id") or ""),
            "address": address,
            "features": {
                "garage_clean": garage_clean,
                "bedrooms_clean": bedrooms_clean,
                "bathrooms_clean": bathrooms_clean,
                "sqm_clean": sqm_clean,
                "lot_size_sqm": features_raw.get("lot_size_sqm"),
                "front": (
                    features_raw.get("front")
                    or features_raw.get("frente")
                    or features_raw.get("frontage")
                    or features_raw.get("frontage_m")
                    or features_raw.get("frente_m")
                ),
                "land_use": (
                    features_raw.get("land_use")
                    or features_raw.get("uso_suelo")
                    or features_raw.get("use")
                ),
                "property_type": (
                    row.get("property_type_name")
                    or features_raw.get("property_type")
                    or features_raw.get("tipo")
                ),
                "year_built": features_raw.get("year_built"),
                "amenities": features_raw.get("amenities") or [],
                "is_featured": bool(features_raw.get("is_featured", False)),
                "size_unit": features_raw.get("size_unit"),
                "garage": garage_raw,
                "bedrooms": features_raw.get("bedrooms"),
                "bathrooms": features_raw.get("bathrooms"),
            },
            "media": {
                "primary_image_url": row.get("primary_image_url"),
                "image_urls": row.get("image_urls") or [],
            },
            "location": {
                "country": row.get("country"),
                "province": row.get("address_state") or row.get("province"),
                "lat": cls._to_float(row.get("location_lat")),
                "lng": cls._to_float(row.get("location_lng")),
            },
            "meta": {
                "source_system": "lead_properties",
                "public_url": row.get("public_url"),
                "ingested_at": row.get("created_at"),
                "updated_at": row.get("updated_at"),
            },
        }
        return Property.model_validate(payload)

    async def run_text_to_sql_query(
        self,
        *,
        client_id: str,
        sql: str,
        params: dict[str, object],
    ) -> list[Property]:
        normalized_sql = self._normalize_search_sql(sql)
        compiled_sql = f"""
        WITH searchable_properties AS (
            SELECT
                p.*,
                p.currency_id AS currency,
                pt.name AS property_type_name,
                LOWER(
                    CONCAT_WS(
                        ' ',
                        COALESCE(p.title, ''),
                        COALESCE(p.description, ''),
                        COALESCE(CAST(p.features AS text), '')
                    )
                ) AS searchable_text,
                LOWER(
                    CONCAT_WS(
                        ' ',
                        COALESCE(p.title, ''),
                        COALESCE(CAST(p.features AS text), '')
                    )
                ) AS location_search_text,
                COALESCE(
                    NULLIF(
                        regexp_replace(
                            COALESCE(p.features->>'bedrooms_clean', p.features->>'bedrooms', p.bedrooms::text, ''),
                            '[^0-9\\.]',
                            '',
                            'g'
                        ),
                        ''
                    )::numeric,
                    0
                ) AS bedrooms_clean,
                COALESCE(
                    NULLIF(
                        regexp_replace(
                            COALESCE(p.features->>'bathrooms_clean', p.features->>'bathrooms', p.bathrooms::text, ''),
                            '[^0-9\\.]',
                            '',
                            'g'
                        ),
                        ''
                    )::numeric,
                    0
                ) AS bathrooms_clean,
                COALESCE(
                    NULLIF(
                        regexp_replace(
                            COALESCE(p.features->>'garage_clean', p.features->>'garage', ''),
                            '[^0-9\\.]',
                            '',
                            'g'
                        ),
                        ''
                    )::numeric,
                    0
                ) AS garage_clean,
                COALESCE(
                    NULLIF(
                        regexp_replace(
                            COALESCE(p.features->>'sqm_clean', p.area_sqm::text, ''),
                            '[^0-9\\.]',
                            '',
                            'g'
                        ),
                        ''
                    )::numeric,
                    0
                ) AS sqm_clean
            FROM lead_properties p
            LEFT JOIN lead_property_types pt
                ON pt.id = p.property_type_id
            WHERE p.client_id = :client_id
              AND p.price > 10
              AND p.deleted_at IS NULL
        )
        SELECT *
        FROM ({normalized_sql}) AS candidate_properties
        WHERE candidate_properties.client_id = :client_id
        """
        merged_params = {"client_id": client_id, **params}
        async with self.engine.begin() as connection:
            rows = (await connection.execute(text(compiled_sql), merged_params)).mappings().all()
            row_payloads = [dict(row) for row in rows]
            assets_by_property_id = await self._fetch_property_assets(
                connection,
                [str(row.get("id")) for row in row_payloads if row.get("id") is not None],
            )
        enriched_rows: list[dict[str, object]] = []
        for row in row_payloads:
            row_id = str(row.get("id") or "").strip()
            assets = assets_by_property_id.get(row_id, {})
            enriched_rows.append(
                {
                    **row,
                    "primary_image_url": row.get("primary_image_url") or assets.get("primary_image_url"),
                    "image_urls": row.get("image_urls") or assets.get("image_urls") or [],
                }
            )
        return [self._to_canonical_property(row) for row in enriched_rows]

    async def load_properties_by_ids(
        self,
        *,
        client_id: str,
        property_ids: Sequence[str],
    ) -> list[Property]:
        property_ids_clean = [str(item).strip() for item in property_ids if str(item).strip()]
        if not property_ids_clean:
            return []
        query = (
            text(
                """
                SELECT p.*
                FROM lead_properties p
                WHERE p.client_id = :client_id
                  AND p.id::text IN :property_ids
                """
            ).bindparams(
                bindparam("property_ids", expanding=True),
            )
        )
        async with self.engine.begin() as connection:
            rows = (
                await connection.execute(
                    query,
                    {
                        "client_id": client_id,
                        "property_ids": property_ids_clean,
                    },
                )
            ).mappings().all()
            row_payloads = [dict(row) for row in rows]
            assets_by_property_id = await self._fetch_property_assets(
                connection,
                [str(row.get("id")) for row in row_payloads if row.get("id") is not None],
            )
        enriched_rows: list[dict[str, object]] = []
        for row in row_payloads:
            row_id = str(row.get("id") or "").strip()
            assets = assets_by_property_id.get(row_id, {})
            enriched_rows.append(
                {
                    **row,
                    "primary_image_url": row.get("primary_image_url") or assets.get("primary_image_url"),
                    "image_urls": row.get("image_urls") or assets.get("image_urls") or [],
                }
            )
        return [self._to_canonical_property(row) for row in enriched_rows]
