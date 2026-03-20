from fastapi.testclient import TestClient

from app.core.memory_reset import RuntimeMemoryResetError
from app.main import app, memory_reset_client, session_manager


def test_internal_memory_reset_orchestrates_session_and_runtime(monkeypatch):
    called = {}
    token = "test-internal-token"

    async def fake_delete_sessions_by_client(client_id, channel=None):
        called["delete_sessions_client_id"] = client_id
        called["delete_sessions_channel"] = channel
        return 3

    async def fake_reset_runtime_memory(client_id, reason=None):
        called["runtime_client_id"] = client_id
        called["reason"] = reason
        return {
            "agent_core": {"status": "ok", "client_id": client_id, "conversations_deleted": 2},
            "scoring_core": {"status": "ok", "client_id": client_id, "conversations_deleted": 2},
        }

    monkeypatch.setenv("INTERNAL_API_TOKEN", token)
    monkeypatch.setattr(session_manager, "delete_sessions_by_client", fake_delete_sessions_by_client)
    monkeypatch.setattr(memory_reset_client, "reset_runtime_memory", fake_reset_runtime_memory)

    client = TestClient(app)
    res = client.post(
        "/internal/memory/reset",
        json={"client_id": "64f357a0-98eb-44f1-9f41-6e615ed26180", "reason": "knowledge_sync"},
        headers={"X-Internal-Token": token},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["session_deleted"] is True
    assert body["sessions_deleted"] == 3
    assert body["resets"]["agent_core"]["conversations_deleted"] == 2
    assert body["resets"]["scoring_core"]["conversations_deleted"] == 2
    assert body["inference"]["conversations_deleted"] == 2
    assert called["delete_sessions_client_id"] == "64f357a0-98eb-44f1-9f41-6e615ed26180"
    assert called["delete_sessions_channel"] is None
    assert called["runtime_client_id"] == "64f357a0-98eb-44f1-9f41-6e615ed26180"
    assert called["reason"] == "knowledge_sync"


def test_internal_memory_reset_returns_502_on_partial_runtime_failure(monkeypatch):
    token = "test-internal-token"

    async def fake_delete_sessions_by_client(client_id, channel=None):
        return 1

    async def fake_reset_runtime_memory(client_id, reason=None):
        raise RuntimeMemoryResetError(
            failures={"scoring_core": "HTTP 500 (internal error)"},
            partial_results={"agent_core": {"status": "ok", "client_id": client_id}},
        )

    monkeypatch.setenv("INTERNAL_API_TOKEN", token)
    monkeypatch.setattr(session_manager, "delete_sessions_by_client", fake_delete_sessions_by_client)
    monkeypatch.setattr(memory_reset_client, "reset_runtime_memory", fake_reset_runtime_memory)

    client = TestClient(app)
    res = client.post(
        "/internal/memory/reset",
        json={"client_id": "64f357a0-98eb-44f1-9f41-6e615ed26180", "reason": "knowledge_sync"},
        headers={"X-Internal-Token": token},
    )

    assert res.status_code == 502
    body = res.json()
    assert body["detail"]["error"] == "runtime_memory_reset_failed"
    assert body["detail"]["failures"]["scoring_core"].startswith("HTTP 500")
    assert body["detail"]["partial_results"]["agent_core"]["status"] == "ok"
