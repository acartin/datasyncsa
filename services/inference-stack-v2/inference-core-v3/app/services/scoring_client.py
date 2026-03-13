from __future__ import annotations

import logging
from typing import Any, Dict

import httpx

from app.core.config import settings

logger = logging.getLogger("inference-core-v3.scoring-client")


class ScoringClientError(Exception):
    def __init__(self, *, status_code: int | None, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class ScoringCoreClient:
    """Thin HTTP client for scoring-core enqueue contract."""

    def __init__(self) -> None:
        self.base_url = (settings.scoring_core_url or "").rstrip("/")
        api_prefix = str(settings.scoring_core_api_prefix or "/api/v1").strip()
        if api_prefix and not api_prefix.startswith("/"):
            api_prefix = f"/{api_prefix}"
        self.api_prefix = api_prefix
        self.timeout_secs = max(1.0, float(settings.scoring_core_timeout_secs or 8))
        self.internal_token = (settings.internal_api_token or "").strip()

    def _build_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if self.internal_token:
            headers["X-Internal-Token"] = self.internal_token
        return headers

    async def enqueue_scoring_job(
        self,
        *,
        client_id: str,
        lead_id: str,
        conversation_id: str,
        channel: str | None,
    ) -> Dict[str, Any]:
        if not self.base_url:
            raise ScoringClientError(status_code=None, detail="SCORING_CORE_URL_NOT_CONFIGURED")

        url = f"{self.base_url}{self.api_prefix}/scoring/jobs/enqueue"
        payload: Dict[str, Any] = {
            "client_id": client_id,
            "lead_id": lead_id,
            "conversation_id": conversation_id,
        }
        if channel:
            payload["channel"] = channel

        headers = self._build_headers()
        try:
            async with httpx.AsyncClient(timeout=self.timeout_secs) as client:
                response = await client.post(url, json=payload, headers=headers)
        except Exception as exc:  # noqa: BLE001
            raise ScoringClientError(status_code=None, detail=str(exc)) from exc

        if response.status_code >= 400:
            detail = "SCORING_ENQUEUE_FAILED"
            try:
                data = response.json()
                if isinstance(data, dict) and data.get("detail"):
                    detail = str(data.get("detail"))
            except Exception:  # noqa: BLE001
                text = (response.text or "").strip()
                if text:
                    detail = text[:500]

            raise ScoringClientError(status_code=response.status_code, detail=detail)

        data = response.json() if response.content else {}
        if not isinstance(data, dict) or not data.get("id"):
            raise ScoringClientError(status_code=response.status_code, detail="SCORING_ENQUEUE_EMPTY_RESPONSE")

        return {
            "id": str(data.get("id")),
            "status": str(data.get("status") or "queued"),
            "scheduled_for": data.get("scheduled_for"),
        }


scoring_core_client = ScoringCoreClient()
