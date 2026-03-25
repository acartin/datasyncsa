"""Property access repository for realtor flows."""

from __future__ import annotations

from decimal import Decimal
import re
from typing import Sequence

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncEngine

from services.ai_runtime.domain.contracts import Property


class PropertyRepository:
    """Runs tenant-filtered property reads."""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine

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
        property_id_internal = str(
            features_raw.get("property_id_internal")
            or row.get("external_prop_id")
            or row.get("id")
        )

        payload = {
            "property_id_internal": property_id_internal,
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
                "source_property_ref": row.get("external_prop_id"),
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
        return [self._to_canonical_property(dict(row)) for row in rows]

    async def load_properties_by_ids(
        self,
        *,
        client_id: str,
        property_ids: Sequence[str],
    ) -> list[Property]:
        if not property_ids:
            return []
        query = (
            text(
                """
                SELECT *
                FROM lead_properties
                WHERE client_id = :client_id
                  AND property_id_internal IN :property_ids
                """
            ).bindparams(bindparam("property_ids", expanding=True))
        )
        async with self.engine.begin() as connection:
            rows = (
                await connection.execute(
                    query,
                    {"client_id": client_id, "property_ids": list(property_ids)},
                )
            ).mappings().all()
        return [self._to_canonical_property(dict(row)) for row in rows]
