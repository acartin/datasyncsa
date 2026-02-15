import pytest
from pydantic import ValidationError

from app.schemas.chat import ChatRequest, InitRequest


def test_init_request_accepts_client_id_alias():
    req = InitRequest(clientId="64f357a0-98eb-44f1-9f41-6e615ed26180")
    assert str(req.client_id) == "64f357a0-98eb-44f1-9f41-6e615ed26180"


def test_chat_request_rejects_invalid_client_id():
    with pytest.raises(ValidationError):
        ChatRequest(text="hola", client_id="not-a-uuid")


def test_chat_request_maps_property_alias():
    req = ChatRequest(
        text="hola",
        client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
        propertyId="prop-123",
    )
    assert req.source_property_ref == "prop-123"
