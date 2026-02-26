from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services.scoring_job_service import ScoringJobService


@pytest.mark.asyncio
async def test_enqueue_post_chat_scoring_calls_repo():
    repo = AsyncMock()
    expected = {
        "id": str(uuid4()),
        "status": "queued",
        "scheduled_for": "2026-02-22T00:00:00+00:00",
    }
    repo.upsert_scoring_job = AsyncMock(return_value=expected)

    service = ScoringJobService(repo)
    result = await service.enqueue_post_chat_scoring(
        lead_id=uuid4(),
        conversation_id=uuid4(),
        client_id=uuid4(),
        expected_lead_messages=3,
        model_id=uuid4(),
        prompt_id=uuid4(),
    )

    assert result == expected
    repo.upsert_scoring_job.assert_called_once()


@pytest.mark.asyncio
async def test_enqueue_post_chat_scoring_schedules_immediately(mocker):
    repo = AsyncMock()
    repo.upsert_scoring_job = AsyncMock(return_value={"status": "queued"})
    fixed_now = datetime(2026, 2, 26, 12, 0, tzinfo=timezone.utc)

    service = ScoringJobService(repo)
    mocker.patch.object(service, "_utc_now", return_value=fixed_now)

    await service.enqueue_post_chat_scoring(
        lead_id=uuid4(),
        conversation_id=uuid4(),
        client_id=uuid4(),
        expected_lead_messages=1,
        model_id=uuid4(),
        prompt_id=uuid4(),
    )

    assert repo.upsert_scoring_job.call_count == 1
    assert repo.upsert_scoring_job.call_args.kwargs["scheduled_for"] == fixed_now
