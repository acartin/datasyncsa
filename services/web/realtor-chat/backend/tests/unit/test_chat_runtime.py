from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

import app.main as main_module
from app.schemas.internal_chat import InternalChatRequest
from app.schemas.ui import PropertyCard


class _DummyPolicy:
    def build_response(self, ai_text, components, session_id):
        return {"components": [{"type": "chat", "text": ai_text, "sender": "bot"}]}


class _EchoPolicy:
    def build_response(self, ai_text, components, session_id):
        return {
            "components": [
                {"type": "chat", "text": ai_text, "sender": "bot"},
                *[c.model_dump() for c in components],
            ]
        }


def _request(channel: str = "web_html") -> InternalChatRequest:
    return InternalChatRequest(
        client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
        channel=channel,
        channel_user_id="user-1",
        message_text="hola",
    )


def _patch_chat_dependencies(monkeypatch):
    monkeypatch.setattr(main_module.inference_client, "chat", AsyncMock(return_value={
        "conversation_id": "conv-1",
        "answer": "ok",
        "intent": None,
        "sources": [],
    }))
    monkeypatch.setattr(
        main_module.vertical_router,
        "resolve_vertical_for_client_async",
        AsyncMock(return_value="generic"),
    )
    monkeypatch.setattr(
        main_module.vertical_router,
        "get_handler_async",
        AsyncMock(return_value=_DummyPolicy()),
    )
    monkeypatch.setattr(main_module.transformer, "_extract_properties_from_sources", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        main_module.transformer,
        "_get_branding_for_client",
        AsyncMock(return_value={"agent_name": "x"}),
    )


@pytest.mark.asyncio
async def test_chat_accepts_web_channel_without_internal_flag_gate(monkeypatch):
    monkeypatch.setattr(main_module.feature_flags, "SESSION_MULTICHANNEL_ENABLED", False, raising=False)
    _patch_chat_dependencies(monkeypatch)
    monkeypatch.setattr(main_module.session_manager, "get_session", AsyncMock(return_value={}))
    monkeypatch.setattr(main_module.session_manager, "update_session", AsyncMock(return_value=None))

    resp = await main_module.chat_interaction(_request())
    assert resp.session_id == "conv-1"


@pytest.mark.asyncio
async def test_chat_rejects_non_web_channel(monkeypatch):
    with pytest.raises(HTTPException) as exc:
        await main_module.chat_interaction(_request(channel="meta_whatsapp"))

    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_chat_uses_legacy_session_when_multichannel_flag_off(monkeypatch):
    monkeypatch.setattr(main_module.feature_flags, "SESSION_MULTICHANNEL_ENABLED", False, raising=False)
    _patch_chat_dependencies(monkeypatch)

    get_session_legacy = AsyncMock(return_value={})
    update_session_legacy = AsyncMock(return_value=None)
    monkeypatch.setattr(main_module.session_manager, "get_session", get_session_legacy)
    monkeypatch.setattr(main_module.session_manager, "update_session", update_session_legacy)
    monkeypatch.setattr(main_module.session_manager, "get_session_multichannel", AsyncMock(return_value={}))
    monkeypatch.setattr(main_module.session_manager, "upsert_session", AsyncMock(return_value=None))

    resp = await main_module.chat_interaction(_request())

    assert resp.session_id == "conv-1"
    get_session_legacy.assert_awaited_once_with("64f357a0-98eb-44f1-9f41-6e615ed26180")
    assert update_session_legacy.await_count == 1
    assert "channel_user_id" in update_session_legacy.await_args.args[1]


@pytest.mark.asyncio
async def test_chat_uses_multichannel_session_when_flag_on(monkeypatch):
    monkeypatch.setattr(main_module.feature_flags, "SESSION_MULTICHANNEL_ENABLED", True, raising=False)
    _patch_chat_dependencies(monkeypatch)

    get_session_mc = AsyncMock(return_value={})
    upsert_session_mc = AsyncMock(return_value=None)
    monkeypatch.setattr(main_module.session_manager, "get_session_multichannel", get_session_mc)
    monkeypatch.setattr(main_module.session_manager, "upsert_session", upsert_session_mc)
    monkeypatch.setattr(main_module.session_manager, "get_session", AsyncMock(return_value={}))
    monkeypatch.setattr(main_module.session_manager, "update_session", AsyncMock(return_value=None))

    resp = await main_module.chat_interaction(_request())

    assert resp.session_id == "conv-1"
    assert get_session_mc.await_count == 1
    assert upsert_session_mc.await_count == 1
    assert get_session_mc.await_args.kwargs["channel"] == "web_html"


@pytest.mark.asyncio
async def test_chat_realtor_queries_properties_when_sources_empty(monkeypatch):
    monkeypatch.setattr(main_module.feature_flags, "SESSION_MULTICHANNEL_ENABLED", False, raising=False)

    monkeypatch.setattr(main_module.inference_client, "chat", AsyncMock(return_value={
        "conversation_id": "conv-2",
        "answer": "Claro, te comparto opciones disponibles en Escazu.",
        "intent": None,
        "sources": [],
    }))
    monkeypatch.setattr(
        main_module.vertical_router,
        "resolve_vertical_for_client_async",
        AsyncMock(return_value="realtor"),
    )
    monkeypatch.setattr(
        main_module.vertical_router,
        "get_handler_async",
        AsyncMock(return_value=_EchoPolicy()),
    )
    monkeypatch.setattr(main_module.transformer, "_extract_properties_from_sources", AsyncMock(return_value=[]))
    monkeypatch.setattr(main_module.transformer, "count_properties_for_query", AsyncMock(return_value=1))
    monkeypatch.setattr(
        main_module.transformer,
        "extract_property_filters_for_query",
        AsyncMock(return_value={"location": "escazu"}),
    )
    search_mock = AsyncMock(return_value=[
        PropertyCard(id="p-1", title="Casa Premium", price=350000, location="Escazu")
    ])
    monkeypatch.setattr(main_module.transformer, "search_properties_for_query", search_mock)
    monkeypatch.setattr(
        main_module.transformer,
        "_get_branding_for_client",
        AsyncMock(return_value={"agent_name": "x"}),
    )
    monkeypatch.setattr(main_module.session_manager, "get_session", AsyncMock(return_value={}))
    monkeypatch.setattr(main_module.session_manager, "update_session", AsyncMock(return_value=None))

    req = InternalChatRequest(
        client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
        channel="web_html",
        channel_user_id="user-1",
        message_text="busco casas en escazu",
    )
    resp = await main_module.chat_interaction(req)

    search_mock.assert_awaited_once()
    component_types = [c.type for c in resp.components]
    assert "property-card" in component_types


@pytest.mark.asyncio
async def test_chat_realtor_inventory_question_uses_real_count_and_asks_preferences(monkeypatch):
    monkeypatch.setattr(main_module.feature_flags, "SESSION_MULTICHANNEL_ENABLED", False, raising=False)

    monkeypatch.setattr(main_module.inference_client, "chat", AsyncMock(return_value={
        "conversation_id": "conv-3",
        "answer": "Claro, te ayudo con eso.",
        "intent": None,
        "sources": [],
    }))
    monkeypatch.setattr(
        main_module.vertical_router,
        "resolve_vertical_for_client_async",
        AsyncMock(return_value="realtor"),
    )
    monkeypatch.setattr(
        main_module.vertical_router,
        "get_handler_async",
        AsyncMock(return_value=_EchoPolicy()),
    )
    monkeypatch.setattr(main_module.transformer, "_extract_properties_from_sources", AsyncMock(return_value=[]))
    monkeypatch.setattr(main_module.transformer, "count_properties_for_query", AsyncMock(return_value=30))
    monkeypatch.setattr(
        main_module.transformer,
        "extract_property_filters_for_query",
        AsyncMock(return_value={"location": "santa ana"}),
    )
    search_mock = AsyncMock(return_value=[])
    monkeypatch.setattr(main_module.transformer, "search_properties_for_query", search_mock)
    monkeypatch.setattr(
        main_module.transformer,
        "_get_branding_for_client",
        AsyncMock(return_value={"agent_name": "x"}),
    )
    monkeypatch.setattr(main_module.session_manager, "get_session", AsyncMock(return_value={}))
    monkeypatch.setattr(main_module.session_manager, "update_session", AsyncMock(return_value=None))

    req = InternalChatRequest(
        client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
        channel="web_html",
        channel_user_id="user-1",
        message_text="tienes casas en santa ana?",
    )
    resp = await main_module.chat_interaction(req)

    search_mock.assert_not_awaited()
    assert resp.components[0].type == "chat"
    assert "tengo 30" in resp.components[0].text.lower()
    assert "santa ana" in resp.components[0].text.lower()
    assert "prefieres" in resp.components[0].text.lower()


@pytest.mark.asyncio
async def test_chat_realtor_price_range_followup_uses_last_property_query(monkeypatch):
    monkeypatch.setattr(main_module.feature_flags, "SESSION_MULTICHANNEL_ENABLED", False, raising=False)

    monkeypatch.setattr(main_module.inference_client, "chat", AsyncMock(return_value={
        "conversation_id": "conv-4",
        "answer": "Claro, te ayudo con eso.",
        "intent": None,
        "sources": [],
    }))
    monkeypatch.setattr(
        main_module.vertical_router,
        "resolve_vertical_for_client_async",
        AsyncMock(return_value="realtor"),
    )
    monkeypatch.setattr(
        main_module.vertical_router,
        "get_handler_async",
        AsyncMock(return_value=_EchoPolicy()),
    )
    monkeypatch.setattr(main_module.transformer, "_extract_properties_from_sources", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        main_module.transformer,
        "extract_property_filters_for_query",
        AsyncMock(return_value={"location": "heredia"}),
    )
    monkeypatch.setattr(
        main_module.transformer,
        "get_property_price_stats_for_query",
        AsyncMock(return_value={"count": 109, "min_price": 95000.0, "max_price": 420000.0}),
    )
    monkeypatch.setattr(main_module.transformer, "search_properties_for_query", AsyncMock(return_value=[]))
    monkeypatch.setattr(main_module.transformer, "count_properties_for_query", AsyncMock(return_value=0))
    monkeypatch.setattr(
        main_module.transformer,
        "_get_branding_for_client",
        AsyncMock(return_value={"agent_name": "x"}),
    )
    monkeypatch.setattr(
        main_module.session_manager,
        "get_session",
        AsyncMock(return_value={"planner_last_property_query": "tienes casas en heredia?"}),
    )
    monkeypatch.setattr(main_module.session_manager, "update_session", AsyncMock(return_value=None))

    req = InternalChatRequest(
        client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
        channel="web_html",
        channel_user_id="user-1",
        message_text="cual es el rango de precios de ellas?",
    )
    resp = await main_module.chat_interaction(req)

    assert resp.components[0].type == "chat"
    text = resp.components[0].text.lower()
    assert "109" in text
    assert "95,000" in text
    assert "420,000" in text


@pytest.mark.asyncio
async def test_chat_realtor_location_followup_replaces_previous_location(monkeypatch):
    monkeypatch.setattr(main_module.feature_flags, "SESSION_MULTICHANNEL_ENABLED", False, raising=False)

    monkeypatch.setattr(main_module.inference_client, "chat", AsyncMock(return_value={
        "conversation_id": "conv-5",
        "answer": "Perfecto, te ayudo.",
        "intent": None,
        "sources": [],
    }))
    monkeypatch.setattr(
        main_module.vertical_router,
        "resolve_vertical_for_client_async",
        AsyncMock(return_value="realtor"),
    )
    monkeypatch.setattr(
        main_module.vertical_router,
        "get_handler_async",
        AsyncMock(return_value=_EchoPolicy()),
    )
    monkeypatch.setattr(main_module.transformer, "_extract_properties_from_sources", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        main_module.transformer,
        "extract_property_filters_for_query",
        AsyncMock(return_value={"location": "santa ana"}),
    )
    count_mock = AsyncMock(return_value=12)
    monkeypatch.setattr(main_module.transformer, "count_properties_for_query", count_mock)
    monkeypatch.setattr(main_module.transformer, "search_properties_for_query", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        main_module.transformer,
        "_get_branding_for_client",
        AsyncMock(return_value={"agent_name": "x"}),
    )
    monkeypatch.setattr(
        main_module.session_manager,
        "get_session",
        AsyncMock(return_value={"planner_last_property_query": "tienes casas en heredia?"}),
    )
    monkeypatch.setattr(main_module.session_manager, "update_session", AsyncMock(return_value=None))

    req = InternalChatRequest(
        client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
        channel="web_html",
        channel_user_id="user-1",
        message_text="en santa ana",
    )
    resp = await main_module.chat_interaction(req)

    assert resp.components[0].type == "chat"
    text = resp.components[0].text.lower()
    assert "santa ana" in text
    assert "heredia" not in text
    count_mock.assert_awaited_once()
    used_query = count_mock.await_args.kwargs["query_text"].lower()
    assert "santa ana" in used_query
    assert "heredia" not in used_query


@pytest.mark.asyncio
async def test_chat_realtor_show_all_followup_uses_previous_query(monkeypatch):
    monkeypatch.setattr(main_module.feature_flags, "SESSION_MULTICHANNEL_ENABLED", False, raising=False)

    monkeypatch.setattr(main_module.inference_client, "chat", AsyncMock(return_value={
        "conversation_id": "conv-6",
        "answer": "Entendido.",
        "intent": None,
        "sources": [],
    }))
    monkeypatch.setattr(
        main_module.vertical_router,
        "resolve_vertical_for_client_async",
        AsyncMock(return_value="realtor"),
    )
    monkeypatch.setattr(
        main_module.vertical_router,
        "get_handler_async",
        AsyncMock(return_value=_EchoPolicy()),
    )
    monkeypatch.setattr(main_module.transformer, "_extract_properties_from_sources", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        main_module.transformer,
        "extract_property_filters_for_query",
        AsyncMock(return_value={"location": "alajuela"}),
    )
    search_mock = AsyncMock(return_value=[PropertyCard(id="p-9", title="Casa", price=220000, location="Alajuela")])
    monkeypatch.setattr(main_module.transformer, "search_properties_for_query", search_mock)
    monkeypatch.setattr(main_module.transformer, "count_properties_for_query", AsyncMock(return_value=0))
    monkeypatch.setattr(main_module.transformer, "get_property_price_stats_for_query", AsyncMock(return_value={"count": 0}))
    monkeypatch.setattr(
        main_module.transformer,
        "_get_branding_for_client",
        AsyncMock(return_value={"agent_name": "x"}),
    )
    monkeypatch.setattr(
        main_module.session_manager,
        "get_session",
        AsyncMock(return_value={"planner_last_property_query": "tienes casas en alajuela"}),
    )
    monkeypatch.setattr(main_module.session_manager, "update_session", AsyncMock(return_value=None))

    req = InternalChatRequest(
        client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
        channel="web_html",
        channel_user_id="user-1",
        message_text="quiero verlas",
    )
    resp = await main_module.chat_interaction(req)

    assert any(c.type == "property-card" for c in resp.components)
    used_query = search_mock.await_args.kwargs["query_text"].lower()
    assert "alajuela" in used_query
