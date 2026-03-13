from datetime import datetime, timezone, timedelta
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

    @staticmethod
    def _compute_scheduled_for(now: datetime) -> datetime:
        debounce_secs = max(0.0, float(settings.scoring_job_debounce_secs or 0.0))
        if debounce_secs <= 0:
            return now
        return now + timedelta(seconds=debounce_secs)

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
        # Small debounce to coalesce bursty user turns and avoid stale LLM runs.
        scheduled_for = self._compute_scheduled_for(self._utc_now())
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

    async def get_ops_summary(self, *, window_minutes: int = 60) -> Dict[str, Any]:
        return await self.repo.get_scoring_ops_summary(window_minutes=window_minutes)
