from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.api import chat as chat_api
from main import app


def test_chat_keeps_tenant_scope_across_requests(monkeypatch):
    seen_repo_client_ids = []
    seen_semantic_client_ids = []

    def fake_get_or_create_conversation(client_id, _conversation_id):
        seen_repo_client_ids.append(str(client_id))
        return {"id": str(uuid4()), "messages": [], "lead_id": None}

    async def fake_semantic(_query, client_id, _filters):
        seen_semantic_client_ids.append(client_id)
        return [
            {
                "content_id": f"doc-{client_id}",
                "title": "Scoped Doc",
                "body_content": "contenido",
                "metadata": {"client_id": client_id},
                "score": 0.8,
            }
        ]

    def fake_get_system_prompt(_client_id):
        return "Contexto: {context_text}"

    def fake_update_conversation(_conversation_id, _messages):
        return None

    class FakeModelResponse:
        text = "ok"

    def fake_generate_content(**_kwargs):
        return FakeModelResponse()

    monkeypatch.setattr(chat_api.orchestrator.repo, "get_or_create_conversation", fake_get_or_create_conversation)
    monkeypatch.setattr(chat_api.orchestrator, "_get_semantic_context", fake_semantic)
    monkeypatch.setattr(chat_api.orchestrator.repo, "get_system_prompt", fake_get_system_prompt)
    monkeypatch.setattr(chat_api.orchestrator.repo, "update_conversation", fake_update_conversation)
    monkeypatch.setattr(chat_api.orchestrator.client.models, "generate_content", fake_generate_content)

    client = TestClient(app)
    client_a = str(uuid4())
    client_b = str(uuid4())

    res_a = client.post("/api/v1/chat", json={"queryText": "hola", "clientId": client_a})
    res_b = client.post("/api/v1/chat", json={"queryText": "hola", "clientId": client_b})

    assert res_a.status_code == 200
    assert res_b.status_code == 200
    assert seen_repo_client_ids == [client_a, client_b]
    assert seen_semantic_client_ids == [client_a, client_b]
    assert res_a.json()["sources"][0]["metadata"]["client_id"] == client_a
    assert res_b.json()["sources"][0]["metadata"]["client_id"] == client_b
    UUID(res_a.json()["conversation_id"])
    UUID(res_b.json()["conversation_id"])
