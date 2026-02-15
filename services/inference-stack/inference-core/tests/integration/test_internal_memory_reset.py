from fastapi.testclient import TestClient

from app.api import chat as chat_api
from main import app


def test_internal_memory_reset_calls_repo(monkeypatch):
    captured = {}

    def fake_delete(client_id):
        captured["client_id"] = str(client_id)
        return 3

    monkeypatch.setattr(chat_api.orchestrator.repo, "delete_conversations_by_client", fake_delete)

    client = TestClient(app)
    res = client.post(
        "/api/v1/internal/memory/reset",
        json={"client_id": "64f357a0-98eb-44f1-9f41-6e615ed26180", "reason": "test"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["client_id"] == "64f357a0-98eb-44f1-9f41-6e615ed26180"
    assert body["conversations_deleted"] == 3
    assert captured["client_id"] == "64f357a0-98eb-44f1-9f41-6e615ed26180"
