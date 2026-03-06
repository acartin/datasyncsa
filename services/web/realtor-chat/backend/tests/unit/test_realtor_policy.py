import pytest

from app.transformer.realtor_policy import (
    RealtorRendererPolicy,
    create_realtor_policy,
    REALTOR_VERTICAL,
)
from app.schemas.ui import (
    ChatMessage,
    PropertyCard,
    PropertyGrid,
    PropertyMap,
    PhotoCarousel,
    ActionMenu,
    MortgageCalculator,
)


class TestRealtorRendererPolicy:
    def test_init_web_html_channel(self):
        policy = RealtorRendererPolicy(channel="web_html")
        assert policy.channel == "web_html"
        assert "chat_text" in policy.allowed_components
        assert "property_card" in policy.allowed_components

    def test_init_meta_whatsapp_channel(self):
        policy = RealtorRendererPolicy(channel="meta_whatsapp")
        assert policy.channel == "meta_whatsapp"
        assert "chat_text" in policy.allowed_components
        assert "image" in policy.allowed_components

    def test_filter_components_allows_chat_text(self):
        policy = RealtorRendererPolicy(channel="web_html")
        components = [ChatMessage(text="Hello", sender="bot")]
        filtered = policy.filter_components({}, components)
        assert len(filtered) == 1
        assert filtered[0].type == "chat"

    def test_filter_components_allows_property_card(self):
        policy = RealtorRendererPolicy(channel="web_html")
        card = PropertyCard(title="Casa", price=100000, location="San Jose")
        components = [card]
        filtered = policy.filter_components({}, components)
        assert len(filtered) == 1
        assert filtered[0].type == "property-card"

    def test_filter_components_blocks_disallowed_for_whatsapp(self):
        policy = RealtorRendererPolicy(channel="meta_whatsapp")
        card = PropertyCard(title="Casa", price=100000, location="San Jose")
        components = [card]
        filtered = policy.filter_components({}, components)
        assert len(filtered) == 1
        assert filtered[0].type == "chat"

    def test_degrade_property_card_to_text(self):
        policy = RealtorRendererPolicy(channel="meta_whatsapp")
        card = PropertyCard(title="Beach House", price=250000, location=" Guanacaste")
        degraded = policy._degrade_to_text(card)
        assert len(degraded) == 1
        assert degraded[0].type == "chat"
        assert "Beach House" in degraded[0].text

    def test_build_response_includes_chat_text(self):
        policy = RealtorRendererPolicy(channel="web_html")
        card = PropertyCard(title="Casa", price=100000, location="San Jose")
        response = policy.build_response(
            ai_text="Here are properties:",
            components=[card],
            session_id="sess-123",
        )
        assert response["session_id"] == "sess-123"
        assert response["meta"]["vertical"] == REALTOR_VERTICAL
        assert response["meta"]["channel"] == "web_html"
        comp_types = [c["type"] for c in response["components"]]
        assert "chat" in comp_types

    def test_validate_response_passes_for_valid(self):
        policy = RealtorRendererPolicy(channel="web_html")
        response = {
            "components": [
                {"type": "chat", "text": "Hello"},
                {"type": "property-card", "title": "Test", "price": 100},
            ]
        }
        assert policy.validate_response(response) is True

    def test_validate_response_fails_for_invalid(self):
        policy = RealtorRendererPolicy(channel="meta_whatsapp")
        response = {
            "components": [
                {"type": "property-card", "title": "Test", "price": 100},
            ]
        }
        assert policy.validate_response(response) is False

    def test_create_realtor_policy_factory(self):
        policy = create_realtor_policy("api")
        assert isinstance(policy, RealtorRendererPolicy)
        assert policy.channel == "api"


class TestRealtorPolicyMeta:
    def test_meta_includes_vertical_and_channel(self):
        policy = RealtorRendererPolicy(channel="web_html")
        response = policy.build_response(
            ai_text="Test",
            components=[],
            session_id="sess-1",
        )
        assert response["meta"]["vertical"] == "realtor"
        assert response["meta"]["channel"] == "web_html"

    def test_meta_includes_allowed_components(self):
        policy = RealtorRendererPolicy(channel="api")
        response = policy.build_response(
            ai_text="Test",
            components=[],
            session_id="sess-1",
        )
        assert "allowed_components" in response["meta"]
        assert "property_card" in response["meta"]["allowed_components"]
