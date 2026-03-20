from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

import app.api.external as external_module
from app.api.schemas import ExternalChatRequest


class _DummyPolicy:
    def build_response(self, ai_text, components, session_id):
        return {"components": [{"type": "chat", "text": ai_text}]}


def _make_request(headers: dict | None = None):
    return SimpleNamespace(headers=headers or {})


def _patch_router_transformer(monkeypatch):
    monkeypatch.setattr(
        external_module.vertical_router,
        "resolve_vertical_for_client_async",
        AsyncMock(return_value="generic"),
    )
    monkeypatch.setattr(
        external_module.vertical_router,
        "get_handler_async",
        AsyncMock(return_value=_DummyPolicy()),
    )
    monkeypatch.setattr(
        external_module.transformer,
        "_extract_properties_from_sources",
        AsyncMock(return_value=[]),
    )


@pytest.mark.asyncio
async def test_external_chat_rejects_missing_token(monkeypatch):
    monkeypatch.setenv("EXTERNAL_API_TOKEN", "token-123")
    monkeypatch.setattr(external_module.feature_flags, "EXTERNAL_API_V1_ENABLED", True, raising=False)

    req = ExternalChatRequest(
        client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
        channel_user_id="api-user-1",
        message_text="hola",
    )

    with pytest.raises(HTTPException) as exc:
        await external_module.external_chat(req, _make_request())

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_external_chat_rejects_when_token_not_configured(monkeypatch):
    monkeypatch.delenv("EXTERNAL_API_TOKEN", raising=False)
    monkeypatch.setattr(external_module.feature_flags, "EXTERNAL_API_V1_ENABLED", True, raising=False)

    req = ExternalChatRequest(
        client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
        channel_user_id="api-user-1",
        message_text="hola",
    )

    with pytest.raises(HTTPException) as exc:
        await external_module.external_chat(req, _make_request())

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_external_sessions_are_isolated_by_channel_user_id(monkeypatch):
    monkeypatch.setenv("EXTERNAL_API_TOKEN", "token-123")
    monkeypatch.setattr(external_module.feature_flags, "EXTERNAL_API_V1_ENABLED", True, raising=False)
    _patch_router_transformer(monkeypatch)

    get_session_mc = AsyncMock(return_value={})
    upsert_session_mc = AsyncMock(return_value=None)
    monkeypatch.setattr(external_module.session_manager, "get_session_multichannel", get_session_mc)
    monkeypatch.setattr(external_module.session_manager, "upsert_session", upsert_session_mc)

    async def _fake_chat(user_query, session):
        channel_user_id = session.get("channel_user_id")
        return {
            "conversation_id": f"conv-{channel_user_id}",
            "answer": f"ok-{channel_user_id}",
            "intent": "test",
            "sources": [],
        }

    monkeypatch.setattr(external_module.inference_client, "chat", AsyncMock(side_effect=_fake_chat))

    req_a = ExternalChatRequest(
        client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
        channel_user_id="userA",
        message_text="hola",
    )
    req_b = ExternalChatRequest(
        client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
        channel_user_id="userB",
        message_text="hola",
    )
    request = _make_request({"X-External-Token": "token-123"})

    resp_a = await external_module.external_chat(req_a, request)
    resp_b = await external_module.external_chat(req_b, request)

    assert resp_a.conversation_id != resp_b.conversation_id
    assert get_session_mc.await_count == 2
    assert upsert_session_mc.await_count == 2
    assert get_session_mc.await_args_list[0].kwargs["channel_user_id"] == "userA"
    assert get_session_mc.await_args_list[1].kwargs["channel_user_id"] == "userB"


@pytest.mark.asyncio
async def test_external_chat_persists_lead_id_from_core_response(monkeypatch):
    monkeypatch.setenv("EXTERNAL_API_TOKEN", "token-123")
    monkeypatch.setattr(external_module.feature_flags, "EXTERNAL_API_V1_ENABLED", True, raising=False)
    _patch_router_transformer(monkeypatch)

    monkeypatch.setattr(external_module.session_manager, "get_session_multichannel", AsyncMock(return_value={}))
    upsert_session_mc = AsyncMock(return_value=None)
    monkeypatch.setattr(external_module.session_manager, "upsert_session", upsert_session_mc)
    monkeypatch.setattr(
        external_module.inference_client,
        "chat",
        AsyncMock(return_value={
            "conversation_id": "conv-lead",
            "lead_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "answer": "ok",
            "intent": "test",
            "sources": [],
        }),
    )

    req = ExternalChatRequest(
        client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
        channel_user_id="userA",
        message_text="hola",
    )
    request = _make_request({"X-External-Token": "token-123"})
    await external_module.external_chat(req, request)

    assert upsert_session_mc.await_count == 1
    data = upsert_session_mc.await_args.kwargs["data"]
    assert data["conversation_id"] == "conv-lead"
    assert data["lead_id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
