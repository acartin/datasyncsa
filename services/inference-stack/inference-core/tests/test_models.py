import pytest
from pydantic import ValidationError

from app.models.chat import ChatMessageRequest


def test_chat_request_validates_client_uuid():
    req = ChatMessageRequest(queryText="hola", clientId="64f357a0-98eb-44f1-9f41-6e615ed26180")
    assert str(req.client_id) == "64f357a0-98eb-44f1-9f41-6e615ed26180"


def test_chat_request_rejects_invalid_client_uuid():
    with pytest.raises(ValidationError):
        ChatMessageRequest(queryText="hola", clientId="not-a-uuid")


def test_chat_request_ignores_invalid_conversation_uuid():
    req = ChatMessageRequest(
        queryText="hola",
        clientId="64f357a0-98eb-44f1-9f41-6e615ed26180",
        conversationId="bad-conv-id",
    )
    assert req.conversation_id is None
