from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.models.chat_v2 import ChatV2Request, ScorecardV2
from app.services.scoring_orchestrator import ScoringOrchestrator


@pytest.mark.asyncio
async def test_get_active_scoring_model_cache_hit(mocker):
    """Uses cache result and skips repository lookup when cache hits."""
    mock_cache = mocker.patch("app.services.scoring_orchestrator.cache_service")
    cached_model = {
        "id": str(uuid4()),
        "version": 1,
        "prompt_version": 1,
        "criteria": [],
    }
    mock_cache.get_active_model = AsyncMock(return_value=cached_model)

    orchestrator = ScoringOrchestrator(AsyncMock())
    orchestrator.repo = AsyncMock()

    result = await orchestrator.get_active_scoring_model(
        client_id=uuid4(),
        vertical_id=1,
        scoring_model_id=None,
    )

    assert result == cached_model
    orchestrator.repo.get_active_scoring_model.assert_not_called()


def test_build_scorecard_from_result_clamps_scores_and_sets_priority():
    orchestrator = ScoringOrchestrator(AsyncMock())

    model_data = {
        "version": 3,
        "criteria": [
            {
                "criterion_key": "intent",
                "weight": 1.0,
                "min_score": 0,
                "max_score": 10,
                "bands": [
                    {"band_key": "low", "min_score": 0, "max_score": 5},
                    {"band_key": "high", "min_score": 5, "max_score": 10},
                ],
            },
            {
                "criterion_key": "urgency",
                "weight": 1.0,
                "min_score": 0,
                "max_score": 10,
                "bands": [],
            },
        ],
    }
    result = {
        "scores": {
            "intent": 20,   # clamp to 10
            "urgency": -1,  # clamp to 0
        },
        "explanations": {
            "intent": "Muy alto",
            "urgency": "No urgente",
        },
        "reasoning": "Resultado de prueba",
    }

    scorecard = orchestrator._build_scorecard_from_result(model_data=model_data, result=result)

    assert isinstance(scorecard, ScorecardV2)
    assert scorecard.model_version == 3
    assert len(scorecard.score_items) == 2
    assert scorecard.score_items[0].score == 10.0
    # Band upper bound is exclusive, so score==max_score currently yields no band.
    assert scorecard.score_items[0].band_key is None
    assert scorecard.score_items[1].score == 0.0
    assert scorecard.priority_label == "medium"


@pytest.mark.asyncio
async def test_process_chat_missing_tenant_vertical_mapping(mocker):
    orchestrator = ScoringOrchestrator(AsyncMock())

    mocker.patch.object(
        orchestrator,
        "resolve_vertical_for_client",
        new=AsyncMock(side_effect=ValueError("TENANT_VERTICAL_NOT_CONFIGURED")),
    )

    request = ChatV2Request(query_text="Test query", client_id=uuid4())

    with pytest.raises(ValueError, match="TENANT_VERTICAL_NOT_CONFIGURED"):
        await orchestrator.process_chat(request)


def test_build_scorecard_response_from_repo_dict():
    orchestrator = ScoringOrchestrator(AsyncMock())

    scorecard_id = uuid4()
    lead_id = uuid4()
    conversation_id = uuid4()
    model_id = uuid4()
    band_id = uuid4()
    now = datetime.now(timezone.utc)
    scorecard = {
        "id": scorecard_id,
        "lead_id": lead_id,
        "conversation_id": conversation_id,
        "model_id": model_id,
        "model_version": 2,
        "prompt_version": 4,
        "prompt_id": None,
        "score_total": 8.5,
        "priority_label": "high",
        "reasoning": "Bien calificado",
        "extraction_result": {"extracted_name": "Alice"},
        "created_at": now,
        "score_items": [
            {
                "criterion_key": "intent",
                "score": 9.0,
                "band_id": band_id,
                "explanation": "Alto interés",
                "extracted_data": {"confidence": 0.9},
                "created_at": now,
            }
        ],
    }

    response = orchestrator._build_scorecard_response(scorecard)

    assert response["id"] == str(scorecard_id)
    assert response["lead_id"] == str(lead_id)
    assert response["conversation_id"] == str(conversation_id)
    assert response["model_id"] == str(model_id)
    assert response["model_version"] == 2
    assert response["score_total"] == 8.5
    assert len(response["score_items"]) == 1
    assert response["score_items"][0]["criterion_key"] == "intent"
    assert response["score_items"][0]["band_id"] == str(band_id)
