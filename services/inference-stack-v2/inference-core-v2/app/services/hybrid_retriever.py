import asyncio
import logging
from typing import Any, Dict, List

import httpx

from app.core.config import settings

logger = logging.getLogger("inference-core-v2.hybrid-retriever")


class HybridRetriever:
    """
    V2-owned retrieval client for hybrid RAG context assembly.
    """

    def __init__(self) -> None:
        self.base_url = settings.rag_retriever_url.rstrip("/")
        self.search_path = settings.rag_retriever_search_path
        self.timeout_secs = settings.rag_retriever_timeout_secs
        self.retries = max(0, settings.rag_retriever_retries)

    async def search(
        self,
        query_text: str,
        client_id: str,
        filters: Dict[str, Any],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        payload = {
            "query_text": query_text,
            "client_id": client_id,
            "filters": filters or {},
            "top_k": top_k,
        }
        url = f"{self.base_url}{self.search_path}"
        attempts = self.retries + 1

        async with httpx.AsyncClient(timeout=self.timeout_secs) as client:
            for attempt in range(1, attempts + 1):
                try:
                    response = await client.post(url, json=payload)
                    response.raise_for_status()
                    data = response.json()
                    return data.get("results", [])
                except Exception as exc:
                    if attempt >= attempts:
                        logger.warning("V2 retriever unavailable after retries: %s", exc)
                        return []
                    await asyncio.sleep(0.2 * attempt)
