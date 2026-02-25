import pytest
from pydantic import ValidationError

from app.schemas.chat import ChatRequest, InitRequest


def test_init_request_accepts_client_id_alias():
    req = InitRequest(clientId="64f357a0-98eb-44f1-9f41-6e615ed26180")
    assert str(req.client_id) == "64f357a0-98eb-44f1-9f41-6e615ed26180"


def test_init_request_accepts_cliente_id_alias():
    req = InitRequest(clienteId="64f357a0-98eb-44f1-9f41-6e615ed26180")
    assert str(req.client_id) == "64f357a0-98eb-44f1-9f41-6e615ed26180"


def test_chat_request_rejects_invalid_client_id():
    with pytest.raises(ValidationError):
        ChatRequest(text="hola", client_id="not-a-uuid")


def test_chat_request_accepts_cliente_id_alias():
    req = ChatRequest(
        text="hola",
        cliente_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
    )
    assert str(req.client_id) == "64f357a0-98eb-44f1-9f41-6e615ed26180"


def test_chat_request_maps_property_alias():
    req = ChatRequest(
        text="hola",
        client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
        propertyId="prop-123",
    )
    assert req.source_property_ref == "prop-123"


def test_chat_request_accepts_attribution_fields():
    req = ChatRequest(
        text="hola",
        client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
        utm_source="google",
        utm_medium="cpc",
        utm_campaign="camp-x",
        utm_content="creative-a",
        utm_term="apartamentos",
        gclid="gclid-123",
        fbclid="fbclid-123",
        landing_page_url="https://example.com/landing",
        referrer_url="https://m.facebook.com",
    )
    assert req.utm_source == "google"
    assert req.utm_medium == "cpc"
    assert req.gclid == "gclid-123"
