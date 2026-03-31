import pytest

from app.api.schemas import (
    ExternalChatRequest,
    ExternalChatResponse,
    ExternalErrorResponse,
    EXTERNAL_ERROR_CODES,
)


class TestExternalChatRequest:
    def test_valid_request(self):
        req = ExternalChatRequest(
            client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
            channel_user_id="api_user_123",
            message_text="Hello",
        )
        assert str(req.client_id) == "64f357a0-98eb-44f1-9f41-6e615ed26180"
        assert req.channel_user_id == "api_user_123"
        assert req.message_text == "Hello"

    def test_with_conversation_id(self):
        req = ExternalChatRequest(
            client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
            channel_user_id="api_user_123",
            message_text="Hello",
            conversation_id="9f579ceb-5f9e-45f7-8408-906f6a36e326",
        )
        assert req.conversation_id is not None

    def test_with_metadata(self):
        req = ExternalChatRequest(
            client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
            channel_user_id="api_user_123",
            message_text="Hello",
            metadata={"source": "api", "version": "1.0"},
        )
        assert req.metadata["source"] == "api"

    def test_rejects_empty_message(self):
        with pytest.raises(ValueError):
            ExternalChatRequest(
                client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
                channel_user_id="api_user_123",
                message_text="",
            )

    def test_rejects_missing_channel_user_id(self):
        with pytest.raises(ValueError):
            ExternalChatRequest(
                client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
                message_text="hola",
            )


class TestExternalChatResponse:
    def test_response_structure(self):
        resp = ExternalChatResponse(
            conversation_id="conv-123",
            answer="Hello!",
            intent="greeting",
            components=[{"type": "chat_text", "text": "Hello!"}],
            meta={"vertical": "generic", "channel": "api"},
        )
        assert resp.conversation_id == "conv-123"
        assert resp.answer == "Hello!"
        assert resp.intent == "greeting"
        assert len(resp.components) == 1
        assert resp.meta["vertical"] == "generic"

    def test_response_minimal(self):
        resp = ExternalChatResponse(
            conversation_id="conv-123",
            answer="Hello!",
        )
        assert resp.intent is None
        assert resp.components == []
        assert resp.meta == {}


class TestExternalErrorCodes:
    def test_error_codes_defined(self):
        assert "VALIDATION_ERROR" in EXTERNAL_ERROR_CODES
        assert "NOT_FOUND" in EXTERNAL_ERROR_CODES
        assert "TIMEOUT" in EXTERNAL_ERROR_CODES
        assert "INTERNAL_ERROR" in EXTERNAL_ERROR_CODES
        assert "UNAUTHORIZED" in EXTERNAL_ERROR_CODES

    def test_error_codes_values(self):
        assert EXTERNAL_ERROR_CODES["VALIDATION_ERROR"] == "invalid_request"
        assert EXTERNAL_ERROR_CODES["TIMEOUT"] == "service_timeout"


class TestExternalAPIContract:
    """Test the external API contract matches specification."""

    def test_request_contract_example(self):
        """Example from spec: minimal request"""
        req = ExternalChatRequest(
            client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
            channel_user_id="api_user_123",
            message_text="Quiero ver casas en Escazu",
        )
        assert req.client_id is not None
        assert req.message_text is not None

    def test_response_contract_example(self):
        """Example from spec: response with all fields"""
        resp = ExternalChatResponse(
            conversation_id="9f579ceb-5f9e-45f7-8408-906f6a36e326",
            answer="Claro, te comparto opciones disponibles.",
            intent="property_search",
            components=[
                {"type": "chat_text", "text": "Claro, te comparto opciones disponibles."}
            ],
            meta={
                "vertical": "realtor",
                "channel": "api",
            },
        )
        assert resp.conversation_id is not None
        assert "answer" in resp.model_dump()
        assert "intent" in resp.model_dump()
        assert "components" in resp.model_dump()
        assert "meta" in resp.model_dump()
        assert resp.meta["vertical"] in ["realtor", "generic", "healthcare", "legal", "insurance"]
        assert resp.meta["channel"] == "api"

    def test_response_no_internal_details(self):
        """Response should not expose internal scoring details"""
        resp = ExternalChatResponse(
            conversation_id="conv-123",
            answer="Answer",
            components=[],
            meta={"vertical": "generic", "channel": "api"},
        )
        data = resp.model_dump()
        assert "score" not in data
        assert "scoring_details" not in data
        assert "internal_metrics" not in data
