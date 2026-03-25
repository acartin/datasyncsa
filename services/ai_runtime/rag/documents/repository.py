"""Tenant-isolated document retrieval."""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


class DocumentsRAGRepository:
    """Reads tenant document vectors scoped to categoria=documentos."""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def search(
        self,
        *,
        client_id: str,
        query_embedding: Sequence[float],
        query_text: str,
        limit: int = 5,
    ) -> list[dict[str, object]]:
        query = text(
            """
            SELECT
                id::text AS id,
                content,
                metadata,
                categoria,
                1 - (embedding <=> CAST(:query_embedding AS vector)) AS score
            FROM ai_vectors
            WHERE client_id = :client_id
              AND categoria = 'documentos'
            ORDER BY embedding <=> CAST(:query_embedding AS vector)
            LIMIT :limit
            """
        )
        async with self.engine.begin() as connection:
            rows = (
                await connection.execute(
                    query,
                    {
                        "client_id": client_id,
                        "query_embedding": list(query_embedding),
                        "limit": limit,
                    },
                )
            ).mappings().all()
        return [dict(row) | {"query_text": query_text} for row in rows]

