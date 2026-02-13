from uuid import uuid4

from fastapi.testclient import TestClient

from app.models.chat import ChatMessageResponse
from app.api import chat as chat_api
from main import app


def test_chat_endpoint_rejects_invalid_client_id():
    client = TestClient(app)
    res = client.post(
        "/api/v1/chat",
        json={"queryText": "hola", "clientId": "not-a-uuid"},
    )
    assert res.status_code == 422


def test_chat_endpoint_sanitizes_unhandled_errors(monkeypatch):
    async def boom(_request):
        raise RuntimeError("sensitive stack message")

    monkeypatch.setattr(chat_api.orchestrator, "chat", boom)
    client = TestClient(app)
    res = client.post(
        "/api/v1/chat",
        json={
            "queryText": "hola",
            "clientId": "64f357a0-98eb-44f1-9f41-6e615ed26180",
        },
    )
    assert res.status_code == 500
    assert res.json()["detail"] == "Internal inference error"


def test_chat_history_returns_list(monkeypatch):
    expected = [{"role": "user", "content": "hola"}]

    def fake_history(_conversation_id):
        return expected

    monkeypatch.setattr(chat_api.orchestrator, "get_conversation_history", fake_history)
    client = TestClient(app)
    res = client.get(f"/api/v1/chat/{uuid4()}")
    assert res.status_code == 200
    assert res.json() == expected
