from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app, inference_client, session_manager, transformer, vertical_router
from app.schemas.ui import BrandingConfig, SDUIResponse


def test_chat_keeps_sessions_isolated_per_client(monkeypatch):
    get_calls = []
    update_calls = []
    policy_calls = []

    async def fake_get_session_multichannel(client_id, channel, channel_user_id):
        get_calls.append((client_id, channel, channel_user_id))
        return {}

    async def fake_upsert_session(client_id, channel, channel_user_id, data):
        update_calls.append((client_id, channel, channel_user_id, data.get("conversation_id")))
        return None

    async def fake_chat(user_query, session):
        return {
            "answer": f"respuesta {user_query}",
            "sources": [],
            "conversation_id": str(uuid4()),
            "tenant_echo": session["client_id"],
        }

    class FakePolicy:
        def build_response(self, ai_text, components, session_id):
            policy_calls.append((session_id, ai_text))
            return {"components": [{"type": "chat", "text": ai_text, "sender": "bot"}]}

    async def fake_resolve_vertical(_client_id):
        return "generic"

    async def fake_get_handler(_client_id, _channel):
        return FakePolicy()

    async def fake_get_branding(*_args, **_kwargs):
        return BrandingConfig(agent_name="Tenant Scoped")

    monkeypatch.setattr(session_manager, "get_session_multichannel", fake_get_session_multichannel)
    monkeypatch.setattr(session_manager, "upsert_session", fake_upsert_session)
    monkeypatch.setattr(inference_client, "chat", fake_chat)
    monkeypatch.setattr(vertical_router, "resolve_vertical_for_client_async", fake_resolve_vertical)
    monkeypatch.setattr(vertical_router, "get_handler_async", fake_get_handler)
    monkeypatch.setattr(transformer, "_get_branding_for_client", fake_get_branding)

    client = TestClient(app)
    client_a = str(uuid4())
    client_b = str(uuid4())

    res_a = client.post(
        "/chat",
        json={
            "message_text": "hola-a",
            "client_id": client_a,
            "channel": "web_html",
            "channel_user_id": "u-a",
        },
    )
    res_b = client.post(
        "/chat",
        json={
            "message_text": "hola-b",
            "client_id": client_b,
            "channel": "web_html",
            "channel_user_id": "u-b",
        },
    )

    assert res_a.status_code == 200
    assert res_b.status_code == 200
    assert get_calls == [
        (client_a, "web_html", "u-a"),
        (client_b, "web_html", "u-b"),
    ]
    assert [(cid, channel, channel_user_id) for cid, channel, channel_user_id, _ in update_calls] == [
        (client_a, "web_html", "u-a"),
        (client_b, "web_html", "u-b"),
    ]
    assert len(policy_calls) == 2
