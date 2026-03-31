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


def _request(channel: str = "web_html", session_id: str | None = None) -> InternalChatRequest:
    return InternalChatRequest(
        client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
        channel=channel,
        channel_user_id="user-1",
        message_text="hola",
        session_id=session_id,
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
    _patch_chat_dependencies(monkeypatch)
    monkeypatch.setattr(main_module.session_manager, "get_session_multichannel", AsyncMock(return_value={}))
    monkeypatch.setattr(main_module.session_manager, "upsert_session", AsyncMock(return_value=None))

    resp = await main_module.chat_interaction(_request())
    assert resp.session_id == "conv-1"


@pytest.mark.asyncio
async def test_chat_rejects_non_web_channel(monkeypatch):
    with pytest.raises(HTTPException) as exc:
        await main_module.chat_interaction(_request(channel="meta_whatsapp"))

    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_chat_uses_composite_session_storage(monkeypatch):
    _patch_chat_dependencies(monkeypatch)

    get_session_mc = AsyncMock(return_value={})
    upsert_session_mc = AsyncMock(return_value=None)
    monkeypatch.setattr(main_module.session_manager, "get_session_multichannel", get_session_mc)
    monkeypatch.setattr(main_module.session_manager, "upsert_session", upsert_session_mc)

    resp = await main_module.chat_interaction(_request())

    assert resp.session_id == "conv-1"
    assert get_session_mc.await_count == 1
    assert upsert_session_mc.await_count == 1
    assert get_session_mc.await_args.kwargs["channel"] == "web_html"


@pytest.mark.asyncio
async def test_chat_ignores_init_placeholder_and_promotes_conversation_id_to_session(monkeypatch):
    async def fake_chat(user_query, session):
        assert user_query == "hola"
        assert session["session_id"] is None
        return {
            "conversation_id": "conv-1",
            "answer": "ok",
            "intent": None,
            "sources": [],
        }

    monkeypatch.setattr(main_module.inference_client, "chat", fake_chat)
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
    monkeypatch.setattr(main_module.session_manager, "get_session_multichannel", AsyncMock(return_value={}))
    upsert_session_mc = AsyncMock(return_value=None)
    monkeypatch.setattr(main_module.session_manager, "upsert_session", upsert_session_mc)

    resp = await main_module.chat_interaction(_request(session_id="init"))

    assert resp.session_id == "conv-1"
    assert upsert_session_mc.await_args.kwargs["data"]["session_id"] == "conv-1"
    assert upsert_session_mc.await_args.kwargs["data"]["conversation_id"] == "conv-1"


@pytest.mark.asyncio
async def test_chat_persists_lead_id_from_core_response(monkeypatch):
    monkeypatch.setattr(main_module.inference_client, "chat", AsyncMock(return_value={
        "conversation_id": "conv-1",
        "lead_id": "11111111-2222-3333-4444-555555555555",
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

    monkeypatch.setattr(main_module.session_manager, "get_session_multichannel", AsyncMock(return_value={}))
    upsert_session_mc = AsyncMock(return_value=None)
    monkeypatch.setattr(main_module.session_manager, "upsert_session", upsert_session_mc)

    await main_module.chat_interaction(_request())

    assert upsert_session_mc.await_count == 1
    data = upsert_session_mc.await_args.kwargs["data"]
    assert data["conversation_id"] == "conv-1"
    assert data["lead_id"] == "11111111-2222-3333-4444-555555555555"


@pytest.mark.asyncio
async def test_chat_realtor_passes_through_core_property_components(monkeypatch):
    monkeypatch.setattr(main_module.inference_client, "chat", AsyncMock(return_value={
        "conversation_id": "conv-2",
        "answer": "Claro, aquí tienes algunas casas en Escazú.",
        "intent": "PROPERTY_SEARCH",
        "sources": [],
        "components": [
            {
                "type": "property-card",
                "id": "p-1",
                "title": "Casa Premium",
                "price": 350000,
                "location": "Escazú",
                "public_url": "https://example.com/p-1",
            }
        ],
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
    count_mock = AsyncMock(return_value=1)
    search_mock = AsyncMock(return_value=[PropertyCard(id="p-1", title="Casa Premium", price=350000, location="Escazú")])
    monkeypatch.setattr(main_module.transformer, "count_properties_for_query", count_mock)
    monkeypatch.setattr(main_module.transformer, "search_properties_for_query", search_mock)
    monkeypatch.setattr(main_module.transformer, "get_property_price_stats_for_query", AsyncMock(return_value={"count": 0}))
    monkeypatch.setattr(
        main_module.transformer,
        "_get_branding_for_client",
        AsyncMock(return_value={"agent_name": "x"}),
    )
    monkeypatch.setattr(main_module.session_manager, "get_session_multichannel", AsyncMock(return_value={}))
    monkeypatch.setattr(main_module.session_manager, "upsert_session", AsyncMock(return_value=None))

    req = InternalChatRequest(
        client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
        channel="web_html",
        channel_user_id="user-1",
        message_text="busco casas en escazu",
    )
    resp = await main_module.chat_interaction(req)

    count_mock.assert_not_awaited()
    search_mock.assert_not_awaited()
    component_types = [c.type for c in resp.components]
    assert component_types == ["chat", "property-card"]
    property_card = next(c for c in resp.components if c.type == "property-card")
    assert property_card.public_url == "https://example.com/p-1"
    assert resp.components[0].text == "Claro, aquí tienes algunas casas en Escazú."


@pytest.mark.asyncio
async def test_chat_realtor_inventory_question_uses_core_answer_without_local_counting(monkeypatch):
    monkeypatch.setattr(main_module.inference_client, "chat", AsyncMock(return_value={
        "conversation_id": "conv-3",
        "answer": "Sí, tengo 30 propiedades en Santa Ana. Si quieres, te muestro algunas.",
        "intent": "PROPERTY_INVENTORY",
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
    count_mock = AsyncMock(return_value=30)
    search_mock = AsyncMock(return_value=[])
    monkeypatch.setattr(main_module.transformer, "count_properties_for_query", count_mock)
    monkeypatch.setattr(main_module.transformer, "search_properties_for_query", search_mock)
    monkeypatch.setattr(
        main_module.transformer,
        "_get_branding_for_client",
        AsyncMock(return_value={"agent_name": "x"}),
    )
    monkeypatch.setattr(main_module.session_manager, "get_session_multichannel", AsyncMock(return_value={}))
    monkeypatch.setattr(main_module.session_manager, "upsert_session", AsyncMock(return_value=None))

    req = InternalChatRequest(
        client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
        channel="web_html",
        channel_user_id="user-1",
        message_text="tienes casas en santa ana?",
    )
    resp = await main_module.chat_interaction(req)

    count_mock.assert_not_awaited()
    search_mock.assert_not_awaited()
    assert resp.components[0].type == "chat"
    assert "tengo 30" in resp.components[0].text.lower()
    assert "santa ana" in resp.components[0].text.lower()
    assert "muestro algunas" in resp.components[0].text.lower()


@pytest.mark.asyncio
async def test_chat_realtor_price_range_followup_uses_core_answer(monkeypatch):
    monkeypatch.setattr(main_module.inference_client, "chat", AsyncMock(return_value={
        "conversation_id": "conv-4",
        "answer": "En Heredia tengo 109 propiedades con precio publicado. El rango va de USD 95,000 a USD 420,000.",
        "intent": "PROPERTY_PRICE_RANGE",
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
    price_stats_mock = AsyncMock(return_value={"count": 109, "min_price": 95000.0, "max_price": 420000.0})
    count_mock = AsyncMock(return_value=0)
    search_mock = AsyncMock(return_value=[])
    monkeypatch.setattr(main_module.transformer, "get_property_price_stats_for_query", price_stats_mock)
    monkeypatch.setattr(main_module.transformer, "search_properties_for_query", search_mock)
    monkeypatch.setattr(main_module.transformer, "count_properties_for_query", count_mock)
    monkeypatch.setattr(
        main_module.transformer,
        "_get_branding_for_client",
        AsyncMock(return_value={"agent_name": "x"}),
    )
    monkeypatch.setattr(
        main_module.session_manager,
        "get_session_multichannel",
        AsyncMock(return_value={"planner_last_property_query": "tienes casas en heredia?"}),
    )
    monkeypatch.setattr(main_module.session_manager, "upsert_session", AsyncMock(return_value=None))

    req = InternalChatRequest(
        client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
        channel="web_html",
        channel_user_id="user-1",
        message_text="cual es el rango de precios de ellas?",
    )
    resp = await main_module.chat_interaction(req)

    price_stats_mock.assert_not_awaited()
    count_mock.assert_not_awaited()
    search_mock.assert_not_awaited()
    assert resp.components[0].type == "chat"
    text = resp.components[0].text.lower()
    assert "109" in text
    assert "95,000" in text
    assert "420,000" in text


@pytest.mark.asyncio
async def test_chat_realtor_location_followup_uses_core_answer(monkeypatch):
    monkeypatch.setattr(main_module.inference_client, "chat", AsyncMock(return_value={
        "conversation_id": "conv-5",
        "answer": "Perfecto, puedo buscar en Santa Ana. ¿Quieres que te muestre algunas opciones?",
        "intent": "CLARIFICATION",
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
    count_mock = AsyncMock(return_value=12)
    search_mock = AsyncMock(return_value=[])
    monkeypatch.setattr(main_module.transformer, "count_properties_for_query", count_mock)
    monkeypatch.setattr(main_module.transformer, "search_properties_for_query", search_mock)
    monkeypatch.setattr(
        main_module.transformer,
        "_get_branding_for_client",
        AsyncMock(return_value={"agent_name": "x"}),
    )
    monkeypatch.setattr(
        main_module.session_manager,
        "get_session_multichannel",
        AsyncMock(return_value={"planner_last_property_query": "tienes casas en heredia?"}),
    )
    monkeypatch.setattr(main_module.session_manager, "upsert_session", AsyncMock(return_value=None))

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
    count_mock.assert_not_awaited()
    search_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_chat_realtor_show_all_followup_uses_core_components(monkeypatch):
    monkeypatch.setattr(main_module.inference_client, "chat", AsyncMock(return_value={
        "conversation_id": "conv-6",
        "answer": "Claro, te muestro algunas opciones en Alajuela.",
        "intent": "PROPERTY_SEARCH",
        "sources": [],
        "components": [
            {
                "type": "property-card",
                "id": "p-9",
                "title": "Casa",
                "price": 220000,
                "location": "Alajuela",
            }
        ],
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
        "get_session_multichannel",
        AsyncMock(return_value={"planner_last_property_query": "tienes casas en alajuela"}),
    )
    monkeypatch.setattr(main_module.session_manager, "upsert_session", AsyncMock(return_value=None))

    req = InternalChatRequest(
        client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
        channel="web_html",
        channel_user_id="user-1",
        message_text="quiero verlas",
    )
    resp = await main_module.chat_interaction(req)

    assert any(c.type == "property-card" for c in resp.components)
    search_mock.assert_not_awaited()
