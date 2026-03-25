"""Agent assignment repository."""

from __future__ import annotations

import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from services.ai_runtime.domain.contracts import AgentRecord


logger = logging.getLogger("ai-runtime.agent-repository")


class AgentRepository:
    """Reads active agents under a strict tenant boundary."""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def load_active_agents(self, client_id: str) -> list[AgentRecord]:
        query = text(
            """
            SELECT
                client_id::text AS client_id,
                id::text AS id,
                nombre,
                email,
                telefono,
                COALESCE(zonas, '[]'::jsonb) AS zonas,
                activo
            FROM lead_agents
            WHERE client_id = :client_id
              AND activo = true
            ORDER BY nombre
            """
        )
        try:
            async with self.engine.begin() as connection:
                rows = (await connection.execute(query, {"client_id": client_id})).mappings().all()
        except SQLAlchemyError as exc:
            logger.warning("load_active_agents fallback to empty list for client %s: %s", client_id, exc)
            return []
        return [AgentRecord.model_validate(row) for row in rows]

    async def assign_for_zone(self, *, client_id: str, zone: str | None) -> AgentRecord | None:
        if zone:
            zoned_query = text(
                """
                SELECT
                    client_id::text AS client_id,
                    id::text AS id,
                    nombre,
                    email,
                    telefono,
                    COALESCE(zonas, '[]'::jsonb) AS zonas,
                    activo
                FROM lead_agents
                WHERE client_id = :client_id
                  AND activo = true
                  AND :zone = ANY(zonas)
                ORDER BY nombre
                LIMIT 1
                """
            )
            try:
                async with self.engine.begin() as connection:
                    row = (
                        await connection.execute(zoned_query, {"client_id": client_id, "zone": zone})
                    ).mappings().first()
            except SQLAlchemyError as exc:
                logger.warning("assign_for_zone zoned lookup fallback for client %s: %s", client_id, exc)
                row = None
            if row:
                return AgentRecord.model_validate(row)

        fallback_query = text(
            """
            SELECT
                client_id::text AS client_id,
                id::text AS id,
                nombre,
                email,
                telefono,
                COALESCE(zonas, '[]'::jsonb) AS zonas,
                activo
            FROM lead_agents
            WHERE client_id = :client_id
              AND activo = true
            ORDER BY nombre
            LIMIT 1
            """
        )
        try:
            async with self.engine.begin() as connection:
                row = (await connection.execute(fallback_query, {"client_id": client_id})).mappings().first()
        except SQLAlchemyError as exc:
            logger.warning("assign_for_zone fallback lookup failed for client %s: %s", client_id, exc)
            return None
        return AgentRecord.model_validate(row) if row else None
