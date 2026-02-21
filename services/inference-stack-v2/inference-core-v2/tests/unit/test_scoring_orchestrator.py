import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.scoring_orchestrator import ScoringOrchestrator
from app.models.chat_v2 import ChatV2Request, ScorecardV2, ScoreItemV2


@pytest.mark.asyncio
async def test_get_active_scoring_model_cache_hit(mocker):
    """Test cache hit for active scoring model"""
    # Mock cache service
    mock_cache = mocker.patch('app.services.scoring_orchestrator.cache_service')
    mock_cache.get_active_model = AsyncMock(return_value={
        "id": str(uuid4()),
        "version": 1,
        "prompt_version": 1,
        "criteria": []
    })
    mock_cache.is_enabled.return_value = True
    
    # Create orchestrator
    orchestrator = ScoringOrchestrator(AsyncMock())
    
    # Call method
    vertical_id = 1
    client_id = uuid4()
    result = await orchestrator.get_active_scoring_model(
        client_id=client_id,
        vertical_id=vertical_id,
        scoring_model_id=None,
    )
    
    # Verify cache was called
    mock_cache.get_active_model.assert_called_once_with(client_id)
    assert result is not None
    assert "id" in result
    assert "version" in result


@pytest.mark.asyncio
async def test_calculate_scores_basic():
    """Test basic score calculation"""
    orchestrator = ScoringOrchestrator(None)  # No session needed for this test
    
    model_data = {
        "version": 1,
        "prompt_version": 1,
        "criteria": [
            {
                "criterion_key": "intent",
                "label": "Intent",
                "weight": 1.0,
                "min_score": 0.0,
                "max_score": 10.0,
                "bands": [
                    {"band_key": "low", "min_score": 0.0, "max_score": 3.0},
                    {"band_key": "medium", "min_score": 3.0, "max_score": 7.0},
                    {"band_key": "high", "min_score": 7.0, "max_score": 10.0}
                ]
            },
            {
                "criterion_key": "urgency",
                "label": "Urgency",
                "weight": 0.8,
                "min_score": 0.0,
                "max_score": 10.0,
                "bands": []
            }
        ]
    }
    
    conversation_data = {
        "query_text": "Test query",
        "user_metadata": {}
    }
    
    scorecard = orchestrator.calculate_scores(model_data, conversation_data)
    
    assert isinstance(scorecard, ScorecardV2)
    assert scorecard.model_version == 1
    assert scorecard.prompt_version == 1
    assert len(scorecard.score_items) == 2
    assert scorecard.score_total >= 0.0
    assert scorecard.priority_label in ["low", "medium", "high"]
    
    # Verify each score item
    for item in scorecard.score_items:
        assert item.criterion_key in ["intent", "urgency"]
        assert item.score >= 0.0
        assert item.score <= 10.0


@pytest.mark.asyncio
async def test_process_chat_missing_tenant_vertical_mapping(mocker):
    """Test chat processing when tenant vertical mapping is missing"""
    orchestrator = ScoringOrchestrator(AsyncMock())

    mocker.patch.object(
        orchestrator,
        "resolve_vertical_for_client",
        new=AsyncMock(side_effect=ValueError("TENANT_VERTICAL_NOT_CONFIGURED")),
    )

    request = ChatV2Request(
        query_text="Test query",
        client_id=uuid4(),
    )
    
    with pytest.raises(ValueError, match="TENANT_VERTICAL_NOT_CONFIGURED"):
        await orchestrator.process_chat(request)


@pytest.mark.asyncio
async def test_create_scorecard_transaction_success(mocker):
    """Test successful scorecard creation transaction"""
    class _AsyncTx:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    db_session = MagicMock()
    db_session.begin.return_value = _AsyncTx()
    orchestrator = ScoringOrchestrator(db_session)
    mock_repo = AsyncMock()
    orchestrator.repo = mock_repo
    
    # Mock scorecard creation
    mock_scorecard = MagicMock()
    mock_scorecard.id = uuid4()
    mock_repo.create_scorecard.return_value = mock_scorecard
    
    # Mock score items creation
    mock_repo.create_score_items.return_value = []
    
    # Mock lead update
    mock_repo.update_lead_current_scorecard.return_value = True
    
    model_data = {
        "id": str(uuid4()),
        "version": 1,
        "prompt_version": 1,
        "criteria": [],
        "normalization_strategy": "weighted_sum"
    }
    
    scorecard_data = ScorecardV2(
        score_total=7.5,
        priority_label="medium",
        reasoning="Test reasoning",
        model_version=1,
        prompt_version=1,
        score_items=[
            ScoreItemV2(
                criterion_key="intent",
                score=8.0,
                band_key="high",
                explanation="High intent",
                extracted_data={}
            )
        ]
    )
    
    lead_id = uuid4()
    scorecard_id = await orchestrator.create_scorecard_transaction(
        lead_id=lead_id,
        model_data=model_data,
        scorecard_data=scorecard_data
    )
    
    assert scorecard_id == mock_scorecard.id
    
    # Verify repository calls
    mock_repo.create_scorecard.assert_called_once()
    mock_repo.create_score_items.assert_called_once()
    mock_repo.update_lead_current_scorecard.assert_called_once_with(lead_id, mock_scorecard.id)


def test_scorecard_response_building():
    """Test building scorecard response"""
    orchestrator = ScoringOrchestrator(None)
    
    # Create mock scorecard with items
    mock_scorecard = MagicMock()
    mock_scorecard.id = uuid4()
    mock_scorecard.lead_id = uuid4()
    mock_scorecard.conversation_id = uuid4()
    mock_scorecard.model_id = uuid4()
    mock_scorecard.model_version = 1
    mock_scorecard.prompt_version = 1
    mock_scorecard.score_total = 7.5
    mock_scorecard.priority_label = "medium"
    mock_scorecard.reasoning = "Test reasoning"
    mock_scorecard.created_at = datetime.now(timezone.utc)
    
    mock_item = MagicMock()
    mock_item.criterion_key = "intent"
    mock_item.score = 8.0
    mock_item.band_id = uuid4()
    mock_item.explanation = "High intent"
    mock_item.extracted_data = {"confidence": 0.9}
    mock_item.created_at = datetime.now(timezone.utc)
    
    mock_scorecard.score_items = [mock_item]
    
    # Test the private method
    response = asyncio.run(orchestrator._build_scorecard_response(mock_scorecard))
    
    assert response["id"] == str(mock_scorecard.id)
    assert response["lead_id"] == str(mock_scorecard.lead_id)
    assert response["model_version"] == 1
    assert response["score_total"] == 7.5
    assert len(response["score_items"]) == 1
    assert response["score_items"][0]["criterion_key"] == "intent"
