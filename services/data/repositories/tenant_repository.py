"""Tenant configuration repository."""

from __future__ import annotations

import json
import logging
import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from services.ai_runtime.domain.contracts import (
    ScoringCriterionConfig,
    ScoringFieldConfig,
    ScoringProfile,
    TenantBusinessProfile,
    TenantConfig,
)


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
    "insurance": [
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
VERTICAL_SLUG_ALIASES = {
    "realtor": "realtor",
    "real-estate": "realtor",
    "real_estate": "realtor",
    "healthcare": "healthcare",
    "legal": "legal",
    "insurance": "insurance",
}

logger = logging.getLogger("datasyncsa.tenant_repository")


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


def _normalize_runtime_vertical(source_vertical_slug: str | None) -> str:
    normalized = str(source_vertical_slug or "").strip().lower()
    runtime_vertical = VERTICAL_SLUG_ALIASES.get(normalized)
    if runtime_vertical:
        return runtime_vertical
    raise RuntimeError(f"Unsupported tenant vertical slug={source_vertical_slug!r}")


def _parse_json_payload(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return {}
        try:
            parsed = json.loads(candidate)
        except Exception:
            return {}
        if isinstance(parsed, dict):
            return dict(parsed)
    return {}


def _build_scoring_fields_from_schema(extraction_schema: dict[str, object]) -> list[ScoringFieldConfig]:
    response_schema = extraction_schema.get("response_schema")
    extracted_data = (response_schema.get("properties") or {}).get("extracted_data") if isinstance(response_schema, dict) else None
    required = extracted_data.get("required", []) if isinstance(extracted_data, dict) else []
    required_set = {str(item).strip() for item in required if str(item).strip()} if isinstance(required, list) else set()

    payload = extraction_schema.get("fields", [])
    fields: list[ScoringFieldConfig] = []
    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key") or "").strip()
            if not key:
                continue
            fields.append(
                ScoringFieldConfig(
                    key=key,
                    value_type=str(item.get("type") or "string"),
                    required=bool(item.get("required", False) or key in required_set),
                    question=(str(item.get("question") or "").strip() or None),
                )
            )
    if fields:
        return fields

    if not isinstance(response_schema, dict):
        return []
    if not isinstance(extracted_data, dict):
        return []
    extracted_props = extracted_data.get("properties")
    if not isinstance(extracted_props, dict):
        return []
    for key, definition in extracted_props.items():
        normalized = str(key or "").strip()
        if normalized:
            field_type = "string"
            if isinstance(definition, dict):
                field_type = str(definition.get("type") or field_type)
            fields.append(
                ScoringFieldConfig(
                    key=normalized,
                    value_type=field_type,
                    required=normalized in required_set,
                )
            )
    return fields


class TenantRepository:
    """Loads tenant runtime data with strict client scoping."""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def _load_scoring_profile(
        self,
        *,
        vertical_id: int | None,
        scoring_model_id: str | None,
    ) -> ScoringProfile | None:
        if vertical_id is None:
            return None

        try:
            async with self.engine.begin() as connection:
                if scoring_model_id:
                    model_query = text(
                        """
                        SELECT
                            id::text AS model_id,
                            version,
                            prompt_version
                        FROM lead_scoring_models
                        WHERE id = CAST(:model_id AS uuid)
                          AND vertical_id = :vertical_id
                          AND is_active = true
                        LIMIT 1
                        """
                    )
                    model_row = (
                        await connection.execute(
                            model_query,
                            {"model_id": scoring_model_id, "vertical_id": vertical_id},
                        )
                    ).mappings().first()
                else:
                    model_query = text(
                        """
                        SELECT
                            id::text AS model_id,
                            version,
                            prompt_version
                        FROM lead_scoring_models
                        WHERE vertical_id = :vertical_id
                          AND is_active = true
                        ORDER BY version DESC
                        LIMIT 1
                        """
                    )
                    model_row = (
                        await connection.execute(model_query, {"vertical_id": vertical_id})
                    ).mappings().first()

                if not model_row:
                    return None

                criteria_query = text(
                    """
                    SELECT
                        criterion_key,
                        label,
                        weight,
                        min_score,
                        max_score,
                        display_order
                    FROM lead_scoring_criteria
                    WHERE model_id = CAST(:model_id AS uuid)
                      AND is_active = true
                    ORDER BY display_order
                    """
                )
                criteria_rows = (
                    await connection.execute(
                        criteria_query,
                        {"model_id": str(model_row["model_id"])},
                    )
                ).mappings().all()

                prompt_query = text(
                    """
                    SELECT
                        id::text AS prompt_id,
                        version,
                        prompt_template,
                        extraction_schema
                    FROM lead_scoring_prompts
                    WHERE model_id = CAST(:model_id AS uuid)
                      AND is_active = true
                    ORDER BY version DESC
                    LIMIT 1
                    """
                )
                prompt_row = (
                    await connection.execute(
                        prompt_query,
                        {"model_id": str(model_row["model_id"])},
                    )
                ).mappings().first()
        except Exception as exc:
            logger.warning("Unable to load tenant scoring profile; fallback to defaults: %s", exc)
            return None

        extraction_schema = _parse_json_payload(prompt_row.get("extraction_schema") if prompt_row else None)
        criteria = [
            ScoringCriterionConfig(
                key=str(row.get("criterion_key") or ""),
                label=(str(row.get("label") or "").strip() or None),
                weight=float(row.get("weight") or 1.0),
                min_score=float(row.get("min_score") or 0.0),
                max_score=float(row.get("max_score") or 10.0),
                display_order=int(row.get("display_order") or 0),
            )
            for row in criteria_rows
            if str(row.get("criterion_key") or "").strip()
        ]

        return ScoringProfile(
            vertical_id=vertical_id,
            model_id=str(model_row["model_id"]),
            model_version=int(model_row.get("version") or 1),
            prompt_id=(str(prompt_row["prompt_id"]) if prompt_row else None),
            prompt_version=(int(prompt_row.get("version") or 1) if prompt_row else None),
            prompt_template=(
                (str(prompt_row.get("prompt_template") or "").strip() or None)
                if prompt_row
                else None
            ),
            criteria=criteria,
            extraction_fields=_build_scoring_fields_from_schema(extraction_schema),
            scoring_contract=(
                dict(extraction_schema.get("scoring_contract") or {})
                if isinstance(extraction_schema.get("scoring_contract"), dict)
                else {}
            ),
        )

    async def load_tenant_config(self, client_id: str) -> TenantConfig | None:
        query = text(
            """
            SELECT
                c.id::text AS client_id,
                c.vertical_id AS vertical_id,
                c.scoring_model_id::text AS scoring_model_id,
                v.slug AS source_vertical_slug,
                COALESCE(c.name, 'Datasyncsa AI') AS bot_name,
                COALESCE(tone_prompt.prompt_text, '') AS tone_prompt,
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
                ORDER BY p.version DESC NULLS LAST, p.updated_at DESC NULLS LAST, p.created_at DESC NULLS LAST
                LIMIT 1
            ) tone_prompt ON TRUE
            WHERE c.id = :client_id
              AND c.deleted_at IS NULL
            """
        )
        async with self.engine.begin() as connection:
            row = (await connection.execute(query, {"client_id": client_id})).mappings().first()
        if not row:
            return None
        runtime_vertical = _normalize_runtime_vertical(row["source_vertical_slug"])
        scoring_profile = await self._load_scoring_profile(
            vertical_id=row["vertical_id"],
            scoring_model_id=row["scoring_model_id"],
        )
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
            vertical=runtime_vertical,
            bot_name=row["bot_name"],
            tone_prompt=_normalize_prompt_text(row["tone_prompt"]),
            capabilities=list(DEFAULT_CAPABILITIES_BY_VERTICAL.get(runtime_vertical, [])),
            redis_ttl_seconds=row["redis_ttl_seconds"],
            business=business,
            scoring_profile=scoring_profile,
            metadata={
                "source_vertical_slug": str(row["source_vertical_slug"] or ""),
                "vertical_id": row["vertical_id"],
                "scoring_model_id": row["scoring_model_id"],
            },
        )
