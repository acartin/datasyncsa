import pytest
from pydantic import ValidationError

from app.schemas.internal_chat import InternalChatRequest, InternalChatResponse


def test_internal_chat_request_minimal():
    req = InternalChatRequest(
        client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
        channel="web_html",
        channel_user_id="web_2f8c7ed5-8e75-4d86-8d7d-5be326a5e2be",
        message_text="Hola",
    )
    assert str(req.client_id) == "64f357a0-98eb-44f1-9f41-6e615ed26180"
    assert req.channel == "web_html"
    assert req.channel_user_id == "web_2f8c7ed5-8e75-4d86-8d7d-5be326a5e2be"
    assert req.message_text == "Hola"
    assert req.metadata == {}


def test_internal_chat_request_full():
    req = InternalChatRequest(
        client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
        channel="meta_whatsapp",
        channel_user_id="wa_50688887777",
        auth_user_id="admin_123",
        message_text="Quiero ver casas en Escazu",
        conversation_id="9f579ceb-5f9e-45f7-8408-906f6a36e326",
        metadata={"utm_source": "meta", "locale": "es-CR"},
        brand_project="default",
    )
    assert req.auth_user_id == "admin_123"
    assert str(req.conversation_id) == "9f579ceb-5f9e-45f7-8408-906f6a36e326"
    assert req.metadata["utm_source"] == "meta"


def test_internal_chat_request_client_id_alias():
    req = InternalChatRequest(
        clientId="64f357a0-98eb-44f1-9f41-6e615ed26180",
        channel="web_html",
        channelUserId="web_abc123",
        messageText="Hello",
    )
    assert str(req.client_id) == "64f357a0-98eb-44f1-9f41-6e615ed26180"
    assert req.channel_user_id == "web_abc123"
    assert req.message_text == "Hello"


def test_internal_chat_request_message_text_alias():
    req = InternalChatRequest(
        client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
        channel="api",
        channel_user_id="api_user",
        text="Prueba alias text",
    )
    assert req.message_text == "Prueba alias text"


def test_internal_chat_request_rejects_invalid_channel():
    with pytest.raises(ValidationError):
        InternalChatRequest(
            client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
            channel="invalid_channel",
            channel_user_id="user_123",
            message_text="test",
        )


def test_internal_chat_request_rejects_invalid_client_id():
    with pytest.raises(ValidationError):
        InternalChatRequest(
            client_id="not-a-uuid",
            channel="web_html",
            channel_user_id="user_123",
            message_text="test",
        )


def test_internal_chat_response_minimal():
    resp = InternalChatResponse(
        conversation_id="9f579ceb-5f9e-45f7-8408-906f6a36e326",
        canonical_answer="Claro, te comparto opciones disponibles.",
    )
    assert str(resp.conversation_id) == "9f579ceb-5f9e-45f7-8408-906f6a36e326"
    assert resp.canonical_answer == "Claro, te comparto opciones disponibles."
    assert resp.intent is None
    assert resp.payload == {}


def test_internal_chat_response_full():
    resp = InternalChatResponse(
        conversation_id="9f579ceb-5f9e-45f7-8408-906f6a36e326",
        canonical_answer="Claro, te comparto opciones disponibles.",
        intent="property_search",
        payload={
            "components": [
                {
                    "type": "chat_text",
                    "text": "Claro, te comparto opciones disponibles."
                }
            ]
        },
        meta={"vertical": "realtor", "channel": "meta_whatsapp"},
    )
    assert resp.intent == "property_search"
    assert resp.payload["components"][0]["type"] == "chat_text"
    assert resp.meta["vertical"] == "realtor"


def test_internal_chat_response_alias():
    resp = InternalChatResponse(
        conversationId="9f579ceb-5f9e-45f7-8408-906f6a36e326",
        canonicalAnswer="Respuesta canonica",
        intent="search",
        Payload={"components": []},
    )
    assert resp.canonical_answer == "Respuesta canonica"
    assert resp.payload == {"components": []}


def test_internal_chat_request_all_channels():
    channels = ["web_html", "meta_whatsapp", "meta_ig", "api"]
    for channel in channels:
        req = InternalChatRequest(
            client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
            channel=channel,
            channel_user_id="user_test",
            message_text="Test",
        )
        assert req.channel == channel


def test_internal_chat_response_conversation_id_alias():
    resp = InternalChatResponse(
        conversationId="9f579ceb-5f9e-45f7-8408-906f6a36e326",
        answer="Respuesta",
    )
    assert str(resp.conversation_id) == "9f579ceb-5f9e-45f7-8408-906f6a36e326"
    assert resp.canonical_answer == "Respuesta"
