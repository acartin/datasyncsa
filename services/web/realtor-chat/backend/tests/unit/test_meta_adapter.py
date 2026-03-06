import pytest

from app.adapters.meta.output_adapter import (
    MetaOutputAdapter,
    MetaChannel,
    create_meta_adapter,
    META_COMPONENT_LIMITS,
)


class TestMetaOutputAdapterWhatsApp:
    def setup_method(self):
        self.adapter = MetaOutputAdapter(MetaChannel.WHATSAPP)

    def test_adapt_chat_text(self):
        canonical = {
            "canonical_answer": "Hola, ¿en qué puedo ayudarte?",
            "intent": "greeting",
            "payload": {
                "components": [
                    {"type": "chat_text", "text": "Hola, ¿en qué puedo ayudarte?"}
                ]
            }
        }
        result = self.adapter.adapt(canonical)
        assert result["type"] == "text"
        assert "Hola" in result["text"]

    def test_adapt_property_card(self):
        canonical = {
            "canonical_answer": "Aquí tienes una propiedad",
            "payload": {
                "components": [
                    {
                        "type": "property_card",
                        "title": "Casa en la Playa",
                        "price": 250000,
                        "location": "Guanacaste",
                        "id": "prop-123"
                    }
                ]
            }
        }
        result = self.adapter.adapt(canonical)
        assert result["type"] == "interactive"
        assert "interactive" in result

    def test_adapt_image(self):
        canonical = {
            "canonical_answer": "Mira esta imagen",
            "payload": {
                "components": [
                    {
                        "type": "image",
                        "image_url": "https://example.com/image.jpg"
                    }
                ]
            }
        }
        result = self.adapter.adapt(canonical)
        assert result["type"] == "image"
        assert result["image"]["link"] == "https://example.com/image.jpg"

    def test_adapt_gallery(self):
        canonical = {
            "canonical_answer": "Fotos de la propiedad",
            "payload": {
                "components": [
                    {
                        "type": "gallery",
                        "images": ["https://example.com/img1.jpg", "https://example.com/img2.jpg"]
                    }
                ]
            }
        }
        result = self.adapter.adapt(canonical)
        assert result["type"] == "image"
        assert result["image"]["link"] == "https://example.com/img1.jpg"

    def test_adapt_map(self):
        canonical = {
            "canonical_answer": "Ubicación",
            "payload": {
                "components": [
                    {
                        "type": "property-map",
                        "location": "San José",
                        "center": {"lat": 9.9281, "lng": -84.0907}
                    }
                ]
            }
        }
        result = self.adapter.adapt(canonical)
        assert result["type"] == "text"
        assert "google.com/maps" in result["text"]

    def test_adapt_action_menu_list(self):
        canonical = {
            "canonical_answer": "Selecciona una opción",
            "payload": {
                "components": [
                    {
                        "type": "action-menu",
                        "options": [
                            {"label": "Agendar Visita", "payload": "SCHEDULE"},
                            {"label": "Llamar", "payload": "CALL"},
                        ]
                    }
                ]
            }
        }
        result = self.adapter.adapt(canonical)
        assert result["type"] == "interactive"
        assert result["interactive"]["type"] == "list"

    def test_adapt_empty_components(self):
        canonical = {
            "canonical_answer": "Respuesta simple",
            "payload": {"components": []}
        }
        result = self.adapter.adapt(canonical)
        assert result["type"] == "text"
        assert result["text"] == "Respuesta simple"

    def test_adapt_no_canonical_answer(self):
        canonical = {
            "payload": {
                "components": [
                    {"type": "chat_text", "text": "Mensaje sin canonical"}
                ]
            }
        }
        result = self.adapter.adapt(canonical)
        assert result["type"] == "text"


class TestMetaOutputAdapterInstagram:
    def setup_method(self):
        self.adapter = MetaOutputAdapter(MetaChannel.INSTAGRAM)

    def test_instagram_adapts_action_menu_to_buttons(self):
        canonical = {
            "canonical_answer": "Opciones",
            "payload": {
                "components": [
                    {
                        "type": "action-menu",
                        "options": [
                            {"label": "Opción A", "payload": "A"},
                            {"label": "Opción B", "payload": "B"},
                        ]
                    }
                ]
            }
        }
        result = self.adapter.adapt(canonical)
        assert result["type"] == "interactive"
        assert result["interactive"]["type"] == "button"


class TestMetaAdapterFactory:
    def test_create_whatsapp_adapter(self):
        adapter = create_meta_adapter("meta_whatsapp")
        assert isinstance(adapter, MetaOutputAdapter)
        assert adapter.channel == MetaChannel.WHATSAPP

    def test_create_instagram_adapter(self):
        adapter = create_meta_adapter("meta_ig")
        assert isinstance(adapter, MetaOutputAdapter)
        assert adapter.channel == MetaChannel.INSTAGRAM

    def test_invalid_channel_raises(self):
        with pytest.raises(ValueError):
            create_meta_adapter("invalid_channel")


class TestMetaComponentLimits:
    def test_limits_defined(self):
        assert META_COMPONENT_LIMITS["quick_replies"] == 13
        assert META_COMPONENT_LIMITS["list_elements"] == 10
        assert META_COMPONENT_LIMITS["button_elements"] == 3


class TestMetaAdapterDegradation:
    """Tests for component degradation when not supported."""

    def test_property_card_without_id_no_buttons(self):
        adapter = MetaOutputAdapter(MetaChannel.WHATSAPP)
        canonical = {
            "canonical_answer": "Propiedad",
            "payload": {
                "components": [
                    {
                        "type": "property_card",
                        "title": "Casa",
                        "price": 100000,
                        "location": "San José"
                    }
                ]
            }
        }
        result = adapter.adapt(canonical)
        assert result["type"] == "text"
        assert "Casa" in result["text"]

    def test_gallery_without_images_returns_none(self):
        adapter = MetaOutputAdapter(MetaChannel.WHATSAPP)
        canonical = {
            "canonical_answer": "Fotos",
            "payload": {
                "components": [
                    {"type": "gallery", "images": []}
                ]
            }
        }
        result = adapter.adapt(canonical)
        assert result["type"] == "text"
        assert "Fotos" in result["text"]
