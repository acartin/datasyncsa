from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services.scoring_worker import ScoringWorker


def _build_job(running_generation: int = 1):
    return {
        "id": str(uuid4()),
        "lead_id": str(uuid4()),
        "conversation_id": str(uuid4()),
        "client_id": str(uuid4()),
        "expected_lead_messages": 1,
        "running_generation": running_generation,
    }


@pytest.mark.asyncio
async def test_run_job_payload_skips_persist_when_claim_is_superseded(mocker):
    worker = ScoringWorker()
    job = _build_job(running_generation=4)

    repo = AsyncMock()
    db_session = AsyncMock()

    repo.get_conversation_message_counters.return_value = {"lead_messages": 1}
    repo.get_conversation_context_snapshot.return_value = {
        "vertical_ctx": {"vertical_name": "Real Estate", "vertical_slug": "real-estate"},
        "model_data": {"id": str(uuid4()), "version": 1, "criteria": []},
        "scoring_prompt": {"id": str(uuid4())},
    }
    repo.get_conversation_messages.return_value = [{"role": "user", "content": "hola"}]
    repo.is_scoring_job_claim_current.return_value = False

    mocker.patch("app.services.scoring_worker.settings.google_api_key", "test-key")
    mocker.patch(
        "app.services.scoring_worker.scoring_engine.analyze_conversation",
        new=AsyncMock(return_value={"scores": {}, "explanations": {}, "reasoning": "ok"}),
    )
    orchestrator_cls = mocker.patch("app.services.scoring_worker.ScoringOrchestrator")

    await worker._run_job_payload(job, db_session, repo)

    orchestrator_cls.assert_not_called()
    repo.complete_scoring_job.assert_not_called()


@pytest.mark.asyncio
async def test_run_job_payload_completes_with_expected_running_generation(mocker):
    worker = ScoringWorker()
    job = _build_job(running_generation=7)

    repo = AsyncMock()
    db_session = AsyncMock()

    repo.get_conversation_message_counters.return_value = {"lead_messages": 1}
    repo.get_conversation_context_snapshot.return_value = {
        "vertical_ctx": {"vertical_name": "Real Estate", "vertical_slug": "real-estate"},
        "model_data": {
            "id": str(uuid4()),
            "version": 1,
            "criteria": [
                {
                    "criterion_key": "intent",
                    "weight": 1.0,
                    "min_score": 0,
                    "max_score": 10,
                    "bands": [],
                }
            ],
        },
        "scoring_prompt": {"id": str(uuid4()), "version": 1},
    }
    repo.get_conversation_messages.return_value = [{"role": "user", "content": "hola"}]
    repo.is_scoring_job_claim_current.return_value = True
    repo.complete_scoring_job.return_value = True

    mocker.patch("app.services.scoring_worker.settings.google_api_key", "test-key")
    mocker.patch(
        "app.services.scoring_worker.scoring_engine.analyze_conversation",
        new=AsyncMock(
            return_value={
                "scores": {"intent": 8},
                "explanations": {"intent": "alto"},
                "reasoning": "ok",
                "fallback_used": False,
                "json_valid": True,
                "latency_ms": 1500,
                "response_chars": 250,
                "prompt_snapshot": "prompt",
                "extraction_result": {},
                "slot_state": {},
            }
        ),
    )

    orchestrator_cls = mocker.patch("app.services.scoring_worker.ScoringOrchestrator")
    orchestrator = orchestrator_cls.return_value
    orchestrator._build_scorecard_from_result.return_value = object()
    orchestrator._create_scorecard_with_engine = AsyncMock(return_value=None)

    await worker._run_job_payload(job, db_session, repo)

    assert repo.complete_scoring_job.call_count == 1
    assert repo.complete_scoring_job.call_args.kwargs["expected_running_generation"] == 7
