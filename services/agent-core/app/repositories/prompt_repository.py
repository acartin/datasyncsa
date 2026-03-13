from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings

logger = logging.getLogger("agent-core.prompt-repository")


def _as_uuid(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(UUID(str(value).strip()))
    except Exception:
        return None


def _to_asyncpg_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + database_url[len("postgresql://") :]
    if database_url.startswith("postgres://"):
        return "postgresql+asyncpg://" + database_url[len("postgres://") :]
    return database_url


class PromptRepository:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = _to_asyncpg_url(database_url or settings.database_url)
        self.engine = create_async_engine(self.database_url, pool_pre_ping=True)

    async def get_client_vertical_slug(self, client_id: str | None) -> str | None:
        client_uuid = _as_uuid(client_id)
        if not client_uuid:
            return None
        stmt = text(
            """
            SELECT v.slug
            FROM lead_clients c
            LEFT JOIN lead_client_verticals v ON v.id = c.vertical_id
            WHERE c.id = :client_id
            LIMIT 1
            """
        )
        try:
            async with self.engine.connect() as conn:
                row = (await conn.execute(stmt, {"client_id": client_uuid})).mappings().first()
            if row and row.get("slug"):
                return str(row["slug"]).strip()
        except Exception as exc:
            logger.warning("prompt_repo_get_client_vertical_failed: %s", exc)
        return None

    async def get_lead_prompt(self, *, client_id: str | None, slug: str) -> str | None:
        if not slug:
            return None

        client_uuid = _as_uuid(client_id)
        scoped_stmt = text(
            """
            SELECT prompt_text
            FROM lead_ai_prompts
            WHERE client_id = :client_id
              AND slug = :slug
              AND COALESCE(is_active, true) = true
              AND deleted_at IS NULL
            LIMIT 1
            """
        )
        fallback_stmt = text(
            """
            SELECT prompt_text
            FROM lead_ai_prompts
            WHERE client_id IS NULL
              AND slug = :slug
              AND COALESCE(is_active, true) = true
              AND deleted_at IS NULL
            LIMIT 1
            """
        )

        try:
            async with self.engine.connect() as conn:
                if client_uuid:
                    row = (
                        await conn.execute(
                            scoped_stmt,
                            {"client_id": client_uuid, "slug": slug},
                        )
                    ).mappings().first()
                    if row and row.get("prompt_text"):
                        return str(row["prompt_text"])

                row = (await conn.execute(fallback_stmt, {"slug": slug})).mappings().first()
                if row and row.get("prompt_text"):
                    return str(row["prompt_text"])
        except Exception as exc:
            logger.warning("prompt_repo_get_lead_prompt_failed slug=%s: %s", slug, exc)
        return None

    async def get_ai_system_prompt(self, *, node_slug: str, vertical_slug: str | None) -> str | None:
        if not node_slug:
            return None

        scoped_stmt = text(
            """
            SELECT prompt_text
            FROM ai_system_prompts
            WHERE node_slug = :node_slug
              AND vertical_slug = :vertical_slug
              AND is_active = true
            ORDER BY version DESC, updated_at DESC
            LIMIT 1
            """
        )
        fallback_stmt = text(
            """
            SELECT prompt_text
            FROM ai_system_prompts
            WHERE node_slug = :node_slug
              AND vertical_slug IS NULL
              AND is_active = true
            ORDER BY version DESC, updated_at DESC
            LIMIT 1
            """
        )

        try:
            async with self.engine.connect() as conn:
                if vertical_slug:
                    row = (
                        await conn.execute(
                            scoped_stmt,
                            {"node_slug": node_slug, "vertical_slug": vertical_slug},
                        )
                    ).mappings().first()
                    if row and row.get("prompt_text"):
                        return str(row["prompt_text"])

                row = (await conn.execute(fallback_stmt, {"node_slug": node_slug})).mappings().first()
                if row and row.get("prompt_text"):
                    return str(row["prompt_text"])
        except Exception as exc:
            logger.warning(
                "prompt_repo_get_ai_system_prompt_failed node_slug=%s vertical_slug=%s: %s",
                node_slug,
                vertical_slug,
                exc,
            )
        return None


prompt_repository = PromptRepository()

