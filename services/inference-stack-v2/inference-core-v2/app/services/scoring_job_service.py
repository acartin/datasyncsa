from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from app.core.config import settings
from app.repositories.scoring_repository import ScoringRepository


class ScoringJobService:
    """
    Persistence layer adapter for async scoring jobs.
    """

    def __init__(self, repo: ScoringRepository):
        self.repo = repo

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    async def enqueue_post_chat_scoring(
        self,
        *,
        lead_id: UUID,
        conversation_id: UUID,
        client_id: UUID,
        expected_lead_messages: Optional[int],
        model_id: Optional[UUID],
        prompt_id: Optional[UUID],
    ) -> Dict[str, Any]:
        # Queue immediately on each incoming message; no idle debounce.
        scheduled_for = self._utc_now()
        return await self.repo.upsert_scoring_job(
            lead_id=lead_id,
            conversation_id=conversation_id,
            client_id=client_id,
            expected_lead_messages=expected_lead_messages,
            scheduled_for=scheduled_for,
            max_attempts=settings.scoring_job_max_attempts,
            model_id=model_id,
            prompt_id=prompt_id,
        )

    async def get_job(self, job_id: UUID) -> Optional[Dict[str, Any]]:
        return await self.repo.get_scoring_job(job_id)
