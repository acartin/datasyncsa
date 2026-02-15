from fastapi.testclient import TestClient

from app.main import app, memory_reset_client, session_manager


def test_internal_memory_reset_orchestrates_session_and_inference(monkeypatch):
    called = {}

    async def fake_delete_session(client_id):
        called["delete_session_client_id"] = client_id
        return True

    async def fake_reset_inference_memory(client_id, reason=None):
        called["inference_client_id"] = client_id
        called["reason"] = reason
        return {"status": "ok", "client_id": client_id, "conversations_deleted": 2}

    monkeypatch.setattr(session_manager, "delete_session", fake_delete_session)
    monkeypatch.setattr(memory_reset_client, "reset_inference_memory", fake_reset_inference_memory)

    client = TestClient(app)
    res = client.post(
        "/internal/memory/reset",
        json={"client_id": "64f357a0-98eb-44f1-9f41-6e615ed26180", "reason": "knowledge_sync"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["session_deleted"] is True
    assert body["inference"]["conversations_deleted"] == 2
    assert called["delete_session_client_id"] == "64f357a0-98eb-44f1-9f41-6e615ed26180"
    assert called["inference_client_id"] == "64f357a0-98eb-44f1-9f41-6e615ed26180"
    assert called["reason"] == "knowledge_sync"
