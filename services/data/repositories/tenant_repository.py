"""Tenant configuration repository."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from services.ai_runtime.domain.contracts import TenantBusinessProfile, TenantConfig


DEFAULT_CAPABILITIES_BY_VERTICAL = {
    "realtor": [
        "buscar",
        "calcular",
        "comparar",
        "agendar",
        "recomendar",
        "rag_agencia",
        "rag_docs",
        "escalar",
        "mensajear",
    ],
    "healthcare": [
        "rag_agencia",
        "escalar",
        "captura_lead",
        "agendar",
        "mensajear",
    ],
    "legal": [
        "rag_agencia",
        "escalar",
        "captura_lead",
        "agendar",
        "mensajear",
    ],
}


class TenantRepository:
    """Loads tenant runtime data with strict client scoping."""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def load_tenant_config(self, client_id: str) -> TenantConfig | None:
        query = text(
            """
            SELECT
                c.id::text AS client_id,
                CASE
                    WHEN v.slug = 'real-estate' THEN 'realtor'
                    WHEN v.slug = 'healthcare' THEN 'healthcare'
                    WHEN v.slug = 'legal' THEN 'legal'
                    ELSE 'legal'
                END AS vertical,
                COALESCE(c.name, 'Datasyncsa AI') AS bot_name,
                COALESCE(prompt.prompt_text, '') AS tone_prompt,
                3600 AS redis_ttl_seconds,
                '[]'::jsonb AS phones,
                NULL::text AS email,
                '[]'::jsonb AS operation_zones,
                '{}'::jsonb AS commissions,
                '{}'::jsonb AS appointment_policy,
                '{}'::jsonb AS schedules
            FROM lead_clients c
            LEFT JOIN lead_client_verticals v
                ON v.id = c.vertical_id
            LEFT JOIN LATERAL (
                SELECT p.prompt_text
                FROM lead_ai_prompts p
                WHERE p.client_id = c.id
                  AND p.slug = 'primary_chat'
                  AND COALESCE(p.is_active, true) = true
                  AND p.deleted_at IS NULL
                ORDER BY p.updated_at DESC NULLS LAST, p.created_at DESC NULLS LAST
                LIMIT 1
            ) prompt ON TRUE
            WHERE c.id = :client_id
              AND c.deleted_at IS NULL
            """
        )
        async with self.engine.begin() as connection:
            row = (await connection.execute(query, {"client_id": client_id})).mappings().first()
        if not row:
            return None
        business = TenantBusinessProfile(
            name=row["bot_name"],
            phones=list(row["phones"] or []),
            email=row["email"],
            operation_zones=list(row["operation_zones"] or []),
            commissions=dict(row["commissions"] or {}),
            appointment_policy=dict(row["appointment_policy"] or {}),
            schedules=dict(row["schedules"] or {}),
        )
        return TenantConfig(
            client_id=row["client_id"],
            vertical=row["vertical"],
            bot_name=row["bot_name"],
            tone_prompt=row["tone_prompt"],
            capabilities=list(DEFAULT_CAPABILITIES_BY_VERTICAL.get(row["vertical"], [])),
            redis_ttl_seconds=row["redis_ttl_seconds"],
            business=business,
        )
