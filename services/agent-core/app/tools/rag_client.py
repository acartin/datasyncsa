from __future__ import annotations

import uuid
from typing import Any

import httpx

from app.core.config import settings
from app.models.contracts import RAGQuery, RAGResult, RAGChunk


class RAGClient:
    async def search(self, tenant_id: str, query: RAGQuery) -> RAGResult:
        endpoint = settings.rag_retriever_url.rstrip("/") + settings.rag_retriever_search_path
        payload = {
            "query_text": query.query_text,
            "client_id": tenant_id,
            "filters": {"doc_type": query.filter_doc_type} if query.filter_doc_type else {},
            "top_k": query.top_k,
        }

        async with httpx.AsyncClient(timeout=settings.rag_retriever_timeout_secs) as client:
            response = await client.post(endpoint, json=payload)
            response.raise_for_status()
            data = response.json()

        chunks: list[RAGChunk] = []
        for row in data.get("results", []) or []:
            chunk_id = str(row.get("content_id") or uuid.uuid4())
            score = row.get("score", 0.0)
            chunks.append(
                RAGChunk(
                    chunk_id=chunk_id,
                    doc_id=str(row.get("content_id") or chunk_id),
                    content=str(row.get("body_content") or row.get("content") or ""),
                    score=float(score) if score is not None else 0.0,
                    source_url=str((row.get("metadata") or {}).get("source_url") or "") or None,
                )
            )

        return RAGResult(chunks=chunks, query_used=query.query_text)


rag_client = RAGClient()
