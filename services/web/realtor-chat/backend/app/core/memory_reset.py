import logging
import os
from typing import Any, Dict

import httpx


logger = logging.getLogger("memory_reset")


class MemoryResetClient:
    def __init__(self):
        self.reset_url = os.getenv(
            "INFERENCE_CORE_RESET_URL",
            "http://inference-core:8003/api/v1/internal/memory/reset",
        ).rstrip("/")
        self.timeout = float(os.getenv("INFERENCE_TIMEOUT", 60))
        self.internal_token = (os.getenv("INTERNAL_API_TOKEN") or "").strip()

    async def reset_inference_memory(self, client_id: str, reason: str | None = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"client_id": client_id}
        if reason:
            payload["reason"] = reason

        headers: Dict[str, str] = {}
        if self.internal_token:
            headers["X-Internal-Token"] = self.internal_token

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.reset_url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
