from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app, inference_client, session_manager, transformer
from app.schemas.ui import BrandingConfig, SDUIResponse


def test_chat_keeps_sessions_isolated_per_client(monkeypatch):
    get_calls = []
    update_calls = []
    transform_calls = []

    async def fake_get_session(client_id):
        get_calls.append(client_id)
        return {}

    async def fake_update_session(client_id, data):
        update_calls.append((client_id, data.get("conversation_id")))
        return None

    async def fake_chat(user_query, session):
        return {
            "answer": f"respuesta {user_query}",
            "sources": [],
            "conversation_id": str(uuid4()),
            "tenant_echo": session["client_id"],
        }

    async def fake_transform(ai_response, session_id, client_id, **_kwargs):
        transform_calls.append((client_id, ai_response.get("tenant_echo")))
        return SDUIResponse(
            session_id=session_id,
            branding=BrandingConfig(agent_name="Tenant Scoped"),
            components=[],
        )

    monkeypatch.setattr(session_manager, "get_session", fake_get_session)
    monkeypatch.setattr(session_manager, "update_session", fake_update_session)
    monkeypatch.setattr(inference_client, "chat", fake_chat)
    monkeypatch.setattr(transformer, "transform", fake_transform)

    client = TestClient(app)
    client_a = str(uuid4())
    client_b = str(uuid4())

    res_a = client.post("/chat", json={"text": "hola-a", "client_id": client_a})
    res_b = client.post("/chat", json={"text": "hola-b", "client_id": client_b})

    assert res_a.status_code == 200
    assert res_b.status_code == 200
    assert get_calls == [client_a, client_b]
    assert [cid for cid, _ in update_calls] == [client_a, client_b]
    assert transform_calls == [(client_a, client_a), (client_b, client_b)]
