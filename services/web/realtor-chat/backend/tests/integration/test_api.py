from fastapi.testclient import TestClient

from app.main import app, inference_client, session_manager, transformer
from app.schemas.ui import BrandingConfig, SDUIResponse


def test_chat_rejects_invalid_client_id():
    client = TestClient(app)
    res = client.post("/chat", json={"text": "hola", "client_id": "bad-id"})
    assert res.status_code == 422


def test_chat_init_returns_sdui(monkeypatch):
    async def fake_transform(*_args, **_kwargs):
        return SDUIResponse(
            session_id="init",
            branding=BrandingConfig(agent_name="Test Agent"),
            components=[],
        )

    monkeypatch.setattr(transformer, "transform", fake_transform)
    client = TestClient(app)

    res = client.post("/chat/init", json={"client_id": "64f357a0-98eb-44f1-9f41-6e615ed26180"})
    body = res.json()

    assert res.status_code == 200
    assert body["session_id"] == "init"
    assert body["branding"]["agent_name"] == "Test Agent"


def test_chat_happy_path(monkeypatch):
    async def fake_get_session(_client_id):
        return {}

    async def fake_update_session(_client_id, _data):
        return None

    async def fake_chat(user_query, session):
        assert user_query == "hola"
        assert session["client_id"] == "64f357a0-98eb-44f1-9f41-6e615ed26180"
        return {"answer": "respuesta", "sources": [], "conversation_id": "11111111-1111-1111-1111-111111111111"}

    async def fake_transform(*_args, **_kwargs):
        return SDUIResponse(
            session_id="11111111-1111-1111-1111-111111111111",
            branding=BrandingConfig(),
            components=[],
        )

    monkeypatch.setattr(session_manager, "get_session", fake_get_session)
    monkeypatch.setattr(session_manager, "update_session", fake_update_session)
    monkeypatch.setattr(inference_client, "chat", fake_chat)
    monkeypatch.setattr(transformer, "transform", fake_transform)

    client = TestClient(app)
    res = client.post(
        "/chat",
        json={"text": "hola", "client_id": "64f357a0-98eb-44f1-9f41-6e615ed26180"},
    )
    body = res.json()

    assert res.status_code == 200
    assert body["session_id"] == "11111111-1111-1111-1111-111111111111"
