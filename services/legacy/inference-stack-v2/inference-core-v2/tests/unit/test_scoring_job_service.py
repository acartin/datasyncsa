from datetime import datetime, timezone, timedelta
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
async def test_enqueue_post_chat_scoring_applies_debounce(mocker):
    repo = AsyncMock()
    repo.upsert_scoring_job = AsyncMock(return_value={"status": "queued"})
    fixed_now = datetime(2026, 2, 26, 12, 0, tzinfo=timezone.utc)

    service = ScoringJobService(repo)
    mocker.patch.object(service, "_utc_now", return_value=fixed_now)
    mocker.patch("app.services.scoring_job_service.settings.scoring_job_debounce_secs", 1.5)

    await service.enqueue_post_chat_scoring(
        lead_id=uuid4(),
        conversation_id=uuid4(),
        client_id=uuid4(),
        expected_lead_messages=1,
        model_id=uuid4(),
        prompt_id=uuid4(),
    )

    assert repo.upsert_scoring_job.call_count == 1
    assert repo.upsert_scoring_job.call_args.kwargs["scheduled_for"] == fixed_now + timedelta(seconds=1.5)


@pytest.mark.asyncio
async def test_enqueue_post_chat_scoring_without_debounce_is_immediate(mocker):
    repo = AsyncMock()
    repo.upsert_scoring_job = AsyncMock(return_value={"status": "queued"})
    fixed_now = datetime(2026, 2, 26, 12, 0, tzinfo=timezone.utc)

    service = ScoringJobService(repo)
    mocker.patch.object(service, "_utc_now", return_value=fixed_now)
    mocker.patch("app.services.scoring_job_service.settings.scoring_job_debounce_secs", 0.0)

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


@pytest.mark.asyncio
async def test_get_ops_summary_proxies_repository():
    repo = AsyncMock()
    expected = {
        "window_minutes": 60,
        "queue_depth": 1,
        "queue_depth_due": 1,
        "running": 0,
        "completed_count": 3,
        "degraded_count": 0,
        "failed_count": 0,
        "timeout_count": 0,
        "stale_count": 1,
        "p95_wait_seconds": 2.1,
        "p95_end_to_end_seconds": 4.2,
        "completion_rate_per_min": 0.05,
        "failure_rate_pct": 0.0,
        "degraded_rate_pct": 0.0,
    }
    repo.get_scoring_ops_summary = AsyncMock(return_value=expected)

    service = ScoringJobService(repo)
    result = await service.get_ops_summary(window_minutes=60)

    assert result == expected
    repo.get_scoring_ops_summary.assert_called_once_with(window_minutes=60)
