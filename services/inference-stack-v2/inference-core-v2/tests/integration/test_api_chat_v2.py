import pytest
from fastapi.testclient import TestClient
from uuid import uuid4

from main import app


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.mark.asyncio
async def test_chat_v2_endpoint_missing_client_id(client):
    """Test /api/v2/chat with missing client_id"""
    request_data = {
        "queryText": "Test query",
        # Missing clientId
    }
    
    response = client.post("/api/v2/chat", json=request_data)
    
    assert response.status_code == 422  # Pydantic validation error
    assert "client_id" in response.text.lower()


@pytest.mark.asyncio
async def test_chat_v2_endpoint_success(client, mocker):
    """Test successful /api/v2/chat endpoint"""
    # Mock orchestrator
    mock_orchestrator = mocker.patch('app.api.chat_v2.ScoringOrchestrator')
    mock_instance = mocker.AsyncMock()
    mock_orchestrator.return_value = mock_instance
    
    # Mock response
    mock_response = {
        "answer": "Test response",
        "conversation_id": str(uuid4()),
        "scorecard_id": None,
        "scorecard": None,
        "scoring_status": "pending",
        "scoring_job_id": None,
        "scoring_eta": "2026-02-22T00:00:00+00:00",
    }
    mock_instance.process_chat.return_value = mock_response
    
    request_data = {
        "queryText": "Test query",
        "clientId": str(uuid4()),
    }
    
    response = client.post("/api/v2/chat", json=request_data)
    
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Test response"
    assert "conversationId" in data
    assert "scorecardId" in data
    assert data["scoringStatus"] == "pending"


@pytest.mark.asyncio
async def test_chat_v2_endpoint_accepts_cliente_id_alias(client, mocker):
    """Test /api/v2/chat accepts clienteId alias for client_id"""
    mock_orchestrator = mocker.patch('app.api.chat_v2.ScoringOrchestrator')
    mock_instance = mocker.AsyncMock()
    mock_orchestrator.return_value = mock_instance
    mock_instance.process_chat.return_value = {
        "answer": "Alias response",
        "conversation_id": str(uuid4()),
        "scorecard_id": None,
        "scorecard": None,
        "scoring_status": "pending",
        "scoring_job_id": None,
        "scoring_eta": None,
    }

    request_data = {
        "queryText": "Test query",
        "clienteId": str(uuid4()),
    }
    response = client.post("/api/v2/chat", json=request_data)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_active_model_endpoint(client, mocker):
    """Test /api/v2/scoring/models/active endpoint"""
    # Mock orchestrator
    mock_orchestrator = mocker.patch('app.api.chat_v2.ScoringOrchestrator')
    mock_instance = mocker.AsyncMock()
    mock_orchestrator.return_value = mock_instance
    mock_instance.resolve_vertical_for_client.return_value = {"vertical_id": 1, "scoring_model_id": str(uuid4())}
    
    # Mock model data
    mock_model_data = {
        "id": str(uuid4()),
        "version": 1,
        "prompt_version": 1,
        "criteria": [
            {
                "criterion_key": "intent",
                "label": "Intent",
                "weight": 1.0,
                "bands": []
            }
        ]
    }
    mock_instance.get_active_scoring_model.return_value = mock_model_data
    
    client_id = str(uuid4())
    response = client.get(f"/api/v2/scoring/models/active?client_id={client_id}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["modelId"] == mock_model_data["id"]
    assert data["modelVersion"] == 1
    assert len(data["criteria"]) == 1


@pytest.mark.asyncio
async def test_get_scoring_job_endpoint(client, mocker):
    mock_orchestrator = mocker.patch('app.api.chat_v2.ScoringOrchestrator')
    mock_instance = mocker.AsyncMock()
    mock_orchestrator.return_value = mock_instance

    job_id = uuid4()
    mock_instance.get_scoring_job_response.return_value = {
        "id": str(job_id),
        "lead_id": str(uuid4()),
        "conversation_id": str(uuid4()),
        "client_id": str(uuid4()),
        "status": "queued",
        "attempts": 0,
        "max_attempts": 3,
        "scheduled_for": "2026-02-22T00:00:00+00:00",
        "created_at": "2026-02-22T00:00:00+00:00",
        "updated_at": "2026-02-22T00:00:00+00:00",
    }

    response = client.get(f"/api/v2/scoring/jobs/{job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(job_id)
    assert data["status"] == "queued"


@pytest.mark.asyncio
async def test_get_active_model_endpoint_not_found(client, mocker):
    """Test /api/v2/scoring/models/active when model not found"""
    mock_orchestrator = mocker.patch('app.api.chat_v2.ScoringOrchestrator')
    mock_instance = mocker.AsyncMock()
    mock_orchestrator.return_value = mock_instance
    mock_instance.resolve_vertical_for_client.return_value = {"vertical_id": 1, "scoring_model_id": str(uuid4())}
    
    mock_instance.get_active_scoring_model.return_value = None
    
    client_id = str(uuid4())
    response = client.get(f"/api/v2/scoring/models/active?client_id={client_id}")
    
    assert response.status_code == 404
    assert "no active scoring model found for vertical_id" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_active_model_endpoint_requires_client_id(client):
    """Test /api/v2/scoring/models/active requires tenant client_id"""
    response = client.get("/api/v2/scoring/models/active")
    assert response.status_code == 422
    assert "client_id" in response.text.lower()


@pytest.mark.asyncio
async def test_health_check(client):
    """Test health check endpoint"""
    response = client.get("/api/v2/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "unhealthy"]
    assert data["service"] == "inference-core-v2"


@pytest.mark.asyncio
async def test_cache_invalidation(client, mocker):
    """Test cache invalidation endpoint"""
    mock_cache = mocker.patch('app.api.chat_v2.cache_service')
    mock_cache.invalidate_active_model = mocker.AsyncMock(return_value=True)
    mock_cache.invalidate_client_prompts = mocker.AsyncMock(return_value=True)
    
    # Test specific invalidation
    response = client.post(f"/api/v2/cache/invalidate?client_id={uuid4()}")
    
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    # Test all cache invalidation
    mock_cache.invalidate_all_models = mocker.AsyncMock(return_value=True)
    mock_cache.invalidate_all_prompts = mocker.AsyncMock(return_value=True)
    response = client.post("/api/v2/cache/invalidate")
    
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@pytest.mark.asyncio
async def test_cache_invalidation_ignores_unknown_query_params(client, mocker):
    """Unknown query params are ignored; endpoint invalidates all cache when client_id is absent."""
    mock_cache = mocker.patch('app.api.chat_v2.cache_service')
    mock_cache.invalidate_all_models = mocker.AsyncMock(return_value=True)
    mock_cache.invalidate_all_prompts = mocker.AsyncMock(return_value=True)

    response = client.post("/api/v2/cache/invalidate?vertical_id=1")

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_cache.invalidate_all_models.assert_called_once()


@pytest.mark.asyncio
async def test_root_endpoint(client):
    """Test root endpoint"""
    response = client.get("/")
    
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "inference-core-v2"
    assert data["version"] == "2.0.0"
