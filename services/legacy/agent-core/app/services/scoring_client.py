from __future__ import annotations

import uuid
from dataclasses import dataclass

import httpx

from app.core.config import settings


@dataclass(frozen=True)
class ScoreJob:
    id: str
    status: str
    scheduled_for: str | None = None


class ScoringClient:
    def __init__(self) -> None:
        self.base_url = settings.scoring_core_api.rstrip("/")
        self.prefix = settings.scoring_api_prefix.rstrip("/")

    async def enqueue(self, *, client_id: str, lead_id: str | None, conversation_id: str, channel: str) -> ScoreJob:
        if not settings.scoring_enabled:
            return ScoreJob(id=str(uuid.uuid4()), status="disabled")
        if not lead_id:
            raise RuntimeError("lead_id_required")

        endpoint = f"{self.base_url}{self.prefix}/scoring/jobs/enqueue"
        payload = {
            "client_id": str(client_id),
            "lead_id": str(lead_id),
            "conversation_id": str(conversation_id),
            "channel": str(channel),
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(endpoint, json=payload)
            response.raise_for_status()
            data = response.json()
        return ScoreJob(
            id=str(data.get("id") or uuid.uuid4()),
            status=str(data.get("status") or "queued"),
            scheduled_for=data.get("scheduled_for"),
        )

    async def latest_scorecard(self, *, client_id: str, lead_id: str) -> dict:
        endpoint = f"{self.base_url}{self.prefix}/leads/{lead_id}/scorecards/latest?client_id={client_id}"
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(endpoint)
            if response.status_code == 404:
                return {}
            response.raise_for_status()
            return response.json()


scoring_client = ScoringClient()
