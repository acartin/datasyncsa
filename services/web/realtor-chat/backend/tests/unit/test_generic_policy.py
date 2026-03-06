import pytest

from app.transformer.generic_policy import (
    GenericRendererPolicy,
    create_generic_policy,
    GENERIC_VERTICAL,
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


class TestGenericRendererPolicy:
    def test_init_web_html_channel(self):
        policy = GenericRendererPolicy(channel="web_html")
        assert policy.channel == "web_html"
        assert "chat_text" in policy.allowed_components
        assert "agenda" in policy.allowed_components
        assert "image" in policy.allowed_components

    def test_init_meta_whatsapp_channel(self):
        policy = GenericRendererPolicy(channel="meta_whatsapp")
        assert policy.channel == "meta_whatsapp"
        assert "chat_text" in policy.allowed_components
        assert "image" in policy.allowed_components

    def test_filter_components_allows_chat_text(self):
        policy = GenericRendererPolicy(channel="web_html")
        components = [ChatMessage(text="Hello", sender="bot")]
        filtered = policy.filter_components({}, components)
        assert len(filtered) == 1

    def test_filter_components_blocks_property_card(self):
        policy = GenericRendererPolicy(channel="web_html")
        card = PropertyCard(title="Casa", price=100000, location="San Jose")
        components = [card]
        filtered = policy.filter_components({}, components)
        assert len(filtered) == 1
        assert filtered[0].type == "chat"

    def test_filter_components_blocks_map(self):
        policy = GenericRendererPolicy(channel="web_html")
        map_comp = PropertyMap(center={"lat": 9.9, "lng": -84.0}, zoom=15)
        components = [map_comp]
        filtered = policy.filter_components({}, components)
        assert len(filtered) == 1
        assert filtered[0].type == "chat"

    def test_filter_components_blocks_property_grid(self):
        policy = GenericRendererPolicy(channel="web_html")
        grid = PropertyGrid(title="Props", properties=[])
        components = [grid]
        filtered = policy.filter_components({}, components)
        assert len(filtered) == 1
        assert filtered[0].type == "chat"

    def test_degrade_property_card_to_text(self):
        policy = GenericRendererPolicy(channel="web_html")
        card = PropertyCard(title="Casa", price=100000, location="San Jose")
        degraded = policy._degrade_to_text(card)
        assert len(degraded) == 1
        assert degraded[0].type == "chat"

    def test_degrade_map_to_text(self):
        policy = GenericRendererPolicy(channel="web_html")
        map_comp = PropertyMap(center={"lat": 9.9, "lng": -84.0}, zoom=15)
        degraded = policy._degrade_to_text(map_comp)
        assert len(degraded) == 1
        assert degraded[0].type == "chat"

    def test_build_response_includes_chat_text(self):
        policy = GenericRendererPolicy(channel="web_html")
        card = PropertyCard(title="Casa", price=100000, location="San Jose")
        response = policy.build_response(
            ai_text="Here are properties:",
            components=[card],
            session_id="sess-123",
        )
        assert response["session_id"] == "sess-123"
        assert response["meta"]["vertical"] == GENERIC_VERTICAL
        comp_types = [c["type"] for c in response["components"]]
        assert "chat" in comp_types

    def test_validate_response_passes_for_valid(self):
        policy = GenericRendererPolicy(channel="web_html")
        response = {
            "components": [
                {"type": "chat", "text": "Hello"},
            ]
        }
        assert policy.validate_response(response) is True

    def test_validate_response_fails_for_property_card(self):
        policy = GenericRendererPolicy(channel="web_html")
        response = {
            "components": [
                {"type": "property-card", "title": "Test", "price": 100},
            ]
        }
        assert policy.validate_response(response) is False

    def test_validate_response_fails_for_map(self):
        policy = GenericRendererPolicy(channel="web_html")
        response = {
            "components": [
                {"type": "property-map", "center": {"lat": 0, "lng": 0}},
            ]
        }
        assert policy.validate_response(response) is False

    def test_create_generic_policy_factory(self):
        policy = create_generic_policy("api")
        assert isinstance(policy, GenericRendererPolicy)
        assert policy.channel == "api"


class TestGenericPolicyMeta:
    def test_meta_includes_vertical_and_channel(self):
        policy = GenericRendererPolicy(channel="web_html")
        response = policy.build_response(
            ai_text="Test",
            components=[],
            session_id="sess-1",
        )
        assert response["meta"]["vertical"] == "generic"
        assert response["meta"]["channel"] == "web_html"

    def test_meta_includes_allowed_components(self):
        policy = GenericRendererPolicy(channel="api")
        response = policy.build_response(
            ai_text="Test",
            components=[],
            session_id="sess-1",
        )
        assert "allowed_components" in response["meta"]
        assert "agenda" in response["meta"]["allowed_components"]


class TestGenericPolicyBlocksRealtorComponents:
    """Tests verifying generic blocks realtor-specific components."""

    def test_blocks_property_card_input(self):
        policy = GenericRendererPolicy(channel="web_html")
        card = PropertyCard(title="Luxury Villa", price=500000, location="Playa")
        
        result = policy.build_response(
            ai_text="Found this property:",
            components=[card],
            session_id="sess-1",
        )
        
        types = [c["type"] for c in result["components"]]
        assert "property-card" not in types
        assert "chat" in types

    def test_blocks_gallery_input(self):
        policy = GenericRendererPolicy(channel="web_html")
        gallery = PhotoCarousel(images=["img1.jpg", "img2.jpg"])
        
        result = policy.build_response(
            ai_text="Check these photos:",
            components=[gallery],
            session_id="sess-1",
        )
        
        types = [c["type"] for c in result["components"]]
        assert "photo-carousel" in types

    def test_blocks_map_input(self):
        policy = GenericRendererPolicy(channel="web_html")
        map_comp = PropertyMap(center={"lat": 10.0, "lng": -84.0}, zoom=14)
        
        result = policy.build_response(
            ai_text="Location:",
            components=[map_comp],
            session_id="sess-1",
        )
        
        types = [c["type"] for c in result["components"]]
        assert "property-map" not in types
        assert "chat" in types

    def test_allows_image_for_web_html(self):
        policy = GenericRendererPolicy(channel="web_html")
        image = PhotoCarousel(images=["photo1.jpg"])
        
        result = policy.build_response(
            ai_text="Image:",
            components=[image],
            session_id="sess-1",
        )
        
        types = [c["type"] for c in result["components"]]
        assert "photo-carousel" in types

    def test_allows_chat_text_always(self):
        policy = GenericRendererPolicy(channel="web_html")
        
        result = policy.build_response(
            ai_text="Hello!",
            components=[],
            session_id="sess-1",
        )
        
        types = [c["type"] for c in result["components"]]
        assert "chat" in types
