"""Tenant-isolated document retrieval."""

from __future__ import annotations

import re
from typing import Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


class DocumentsRAGRepository:
    """Reads tenant document chunks from ai_vectors using the current metadata schema."""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    @staticmethod
    def _extract_terms(query_text: str) -> list[str]:
        normalized = " ".join(str(query_text or "").strip().lower().split())
        return [term for term in re.findall(r"[a-z0-9áéíóúñ]+", normalized) if len(term) >= 3]

    @staticmethod
    def _use_vector_search(query_embedding: Sequence[float]) -> bool:
        return len([value for value in query_embedding if value is not None]) > 8

    async def search(
        self,
        *,
        client_id: str,
        query_embedding: Sequence[float],
        query_text: str,
        limit: int = 5,
    ) -> list[dict[str, object]]:
        category_filter = (
            "COALESCE(metadata->>'category', '') IN "
            "('documentos', 'financial', 'financiero', 'properties', 'propiedades', 'publico', 'public')"
        )
        if self._use_vector_search(query_embedding):
            query = text(
                f"""
                SELECT
                    id::text AS id,
                    content_id,
                    title,
                    COALESCE(body_content, title, '') AS content,
                    metadata,
                    COALESCE(metadata->>'category', '') AS category,
                    COALESCE(metadata->>'scope_type', 'tenant') AS scope_type,
                    1 - (embedding <=> CAST(:query_embedding AS vector)) AS score
                FROM ai_vectors
                WHERE client_id = :client_id
                  AND COALESCE(metadata->>'scope_type', 'tenant') = 'tenant'
                  AND {category_filter}
                ORDER BY embedding <=> CAST(:query_embedding AS vector)
                LIMIT :limit
                """
            )
            params = {
                "client_id": client_id,
                "query_embedding": list(query_embedding),
                "limit": limit,
            }
        else:
            terms = self._extract_terms(query_text)
            if not terms:
                return []

            score_parts: list[str] = []
            match_parts: list[str] = []
            params = {"client_id": client_id, "limit": limit}
            for index, term in enumerate(terms):
                key = f"term_{index}"
                params[key] = f"%{term}%"
                score_parts.append(
                    f"CASE WHEN LOWER(COALESCE(title, '') || ' ' || COALESCE(body_content, '')) LIKE :{key} THEN 1 ELSE 0 END"
                )
                match_parts.append(
                    f"LOWER(COALESCE(title, '') || ' ' || COALESCE(body_content, '')) LIKE :{key}"
                )

            query = text(
                f"""
                SELECT
                    id::text AS id,
                    content_id,
                    title,
                    COALESCE(body_content, title, '') AS content,
                    metadata,
                    COALESCE(metadata->>'category', '') AS category,
                    COALESCE(metadata->>'scope_type', 'tenant') AS scope_type,
                    ({' + '.join(score_parts)})::float AS score
                FROM ai_vectors
                WHERE client_id = :client_id
                  AND COALESCE(metadata->>'scope_type', 'tenant') = 'tenant'
                  AND {category_filter}
                  AND ({' OR '.join(match_parts)})
                ORDER BY score DESC, updated_at DESC NULLS LAST, created_at DESC NULLS LAST
                LIMIT :limit
                """
            )

        async with self.engine.begin() as connection:
            rows = (
                await connection.execute(
                    query,
                    params,
                )
            ).mappings().all()
        return [dict(row) | {"query_text": query_text} for row in rows]
