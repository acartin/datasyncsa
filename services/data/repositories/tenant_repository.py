"""Tenant configuration repository."""

from __future__ import annotations

import re

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


PROMPT_MODULE_PATTERN = re.compile(
    r"PROMPT\s*=\s*(?P<quote>\"\"\"|''')(?P<body>.*?)(?P=quote)",
    re.DOTALL,
)
TRIPLE_QUOTED_PATTERN = re.compile(
    r"^\s*(?P<quote>\"\"\"|''')(?P<body>.*?)(?P=quote)\s*$",
    re.DOTALL,
)


def _normalize_prompt_text(prompt_text: str | None) -> str:
    if not prompt_text:
        return ""
    candidate = str(prompt_text).strip()
    if not candidate:
        return ""
    module_match = PROMPT_MODULE_PATTERN.search(candidate)
    if module_match:
        return module_match.group("body").strip()
    triple_quoted_match = TRIPLE_QUOTED_PATTERN.match(candidate)
    if triple_quoted_match:
        return triple_quoted_match.group("body").strip()
    return candidate


class TenantRepository:
    """Loads tenant runtime data with strict client scoping."""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine
        self._system_prompts_table: str | None = None

    async def _resolve_system_prompts_table(self) -> str | None:
        if self._system_prompts_table is not None:
            return self._system_prompts_table

        query = text(
            """
            SELECT
                COALESCE(
                    to_regclass('public.system_prompts')::text,
                    to_regclass('public.ai_system_prompts')::text,
                    ''
                ) AS table_name
            """
        )
        async with self.engine.begin() as connection:
            table_name = (await connection.execute(query)).scalar_one()

        normalized = str(table_name or "").split(".")[-1]
        if normalized not in {"", "system_prompts", "ai_system_prompts"}:
            raise RuntimeError(f"Unsupported system prompts table: {normalized}")

        self._system_prompts_table = normalized or None
        return self._system_prompts_table

    async def load_tenant_config(self, client_id: str) -> TenantConfig | None:
        system_prompts_table = await self._resolve_system_prompts_table()
        planner_prompt_select = "''::text AS planner_prompt"
        synthesizer_prompt_select = "''::text AS synthesizer_prompt"
        system_prompt_joins = ""
        if system_prompts_table:
            planner_prompt_select = "COALESCE(planner_prompt.prompt_text, '') AS planner_prompt"
            synthesizer_prompt_select = "COALESCE(synthesizer_prompt.prompt_text, '') AS synthesizer_prompt"
            system_prompt_joins = f"""
            LEFT JOIN LATERAL (
                SELECT p.prompt_text
                FROM {system_prompts_table} p
                WHERE p.node_slug = 'planner_system'
                  AND p.vertical_slug = v.slug
                  AND COALESCE(p.is_active, true) = true
                ORDER BY p.version DESC, p.updated_at DESC NULLS LAST, p.created_at DESC NULLS LAST
                LIMIT 1
            ) planner_prompt ON TRUE
            LEFT JOIN LATERAL (
                SELECT p.prompt_text
                FROM {system_prompts_table} p
                WHERE p.node_slug = 'synthesizer_system'
                  AND p.vertical_slug = v.slug
                  AND COALESCE(p.is_active, true) = true
                ORDER BY p.version DESC, p.updated_at DESC NULLS LAST, p.created_at DESC NULLS LAST
                LIMIT 1
            ) synthesizer_prompt ON TRUE
            """

        query = text(
            f"""
            SELECT
                c.id::text AS client_id,
                CASE
                    WHEN v.slug = 'real-estate' THEN 'realtor'
                    WHEN v.slug = 'healthcare' THEN 'healthcare'
                    WHEN v.slug = 'legal' THEN 'legal'
                    ELSE 'legal'
                END AS vertical,
                COALESCE(c.name, 'Datasyncsa AI') AS bot_name,
                COALESCE(tone_prompt.prompt_text, '') AS tone_prompt,
                {planner_prompt_select},
                {synthesizer_prompt_select},
                3600 AS redis_ttl_seconds,
                '[]'::jsonb AS phones,
                NULL::text AS email,
                '[]'::jsonb AS operation_zones,
                '{{}}'::jsonb AS commissions,
                '{{}}'::jsonb AS appointment_policy,
                '{{}}'::jsonb AS schedules
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
                ORDER BY p.version DESC NULLS LAST, p.updated_at DESC NULLS LAST, p.created_at DESC NULLS LAST
                LIMIT 1
            ) tone_prompt ON TRUE
            {system_prompt_joins}
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
            tone_prompt=_normalize_prompt_text(row["tone_prompt"]),
            system_prompts={
                "planner_system": _normalize_prompt_text(row["planner_prompt"]),
                "synthesizer_system": _normalize_prompt_text(row["synthesizer_prompt"]),
            },
            capabilities=list(DEFAULT_CAPABILITIES_BY_VERTICAL.get(row["vertical"], [])),
            redis_ttl_seconds=row["redis_ttl_seconds"],
            business=business,
        )
