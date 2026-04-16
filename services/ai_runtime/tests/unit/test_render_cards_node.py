import unittest

from services.ai_runtime.graph.realtor.contracts import Property
from services.ai_runtime.graph.realtor.nodes.render_cards_node import build_card_payload


class RenderCardsNodeTests(unittest.TestCase):
    def test_build_card_payload_keeps_ui_friendly_property_fields(self) -> None:
        property_item = Property.model_validate(
            {
                "id": "prop-1",
                "client_id": "tenant-1",
                "title": "Casa amplia en Escazú",
                "description_html": "<p>Casa familiar con terraza y jardin.</p>",
                "price": 285000,
                "currency": "USD",
                "address": "Escazú, San José",
                "features": {
                    "garage_clean": 2,
                    "bedrooms_clean": 4,
                    "bathrooms_clean": 3,
                    "sqm_clean": 285,
                    "amenities": ["Piscina", "Jardín"],
                    "is_featured": True,
                },
                "media": {
                    "primary_image_url": "https://example.com/main.jpg",
                    "image_urls": [
                        "https://example.com/main.jpg",
                        "https://example.com/alt.jpg",
                    ],
                },
                "location": {
                    "province": "San José",
                },
                "meta": {
                    "public_url": "https://example.com/listing/prop-1",
                },
            }
        )

        payload = build_card_payload([property_item])[0]

        self.assertEqual(payload["location"], "Escazú, San José")
        self.assertEqual(payload["photo_count"], 2)
        self.assertEqual(payload["badge_main"], "Destacada")
        self.assertEqual(payload["amenities"], ["Piscina", "Jardín"])
        self.assertEqual(payload["description"], "Casa familiar con terraza y jardin.")
        self.assertEqual(
            payload["stats"],
            [
                {"icon": "bed", "value": "4", "label": "Hab."},
                {"icon": "bath", "value": "3", "label": "Baños"},
                {"icon": "area", "value": "285", "label": "m² constr."},
            ],
        )

    def test_build_card_payload_prefers_land_stats_for_lots(self) -> None:
        property_item = Property.model_validate(
            {
                "id": "prop-2",
                "client_id": "tenant-1",
                "title": "Terreno residencial en Heredia",
                "description_html": "<p>Lote plano listo para construir.</p>",
                "price": 95000,
                "currency": "USD",
                "address": "San Rafael, Heredia",
                "features": {
                    "garage_clean": 0,
                    "bedrooms_clean": 0,
                    "bathrooms_clean": 0,
                    "sqm_clean": None,
                    "lot_size_sqm": "650 m²",
                    "front": "18m",
                    "land_use": "Residencial",
                    "property_type": "Terreno",
                    "amenities": [],
                    "is_featured": False,
                },
                "media": {
                    "primary_image_url": "https://example.com/lot.jpg",
                    "image_urls": ["https://example.com/lot.jpg"],
                },
                "location": {
                    "province": "Heredia",
                },
                "meta": {
                    "public_url": "https://example.com/listing/prop-2",
                },
            }
        )

        payload = build_card_payload([property_item])[0]

        self.assertEqual(
            payload["stats"],
            [
                {"icon": "area", "value": "650", "label": "m² terreno"},
                {"icon": "front", "value": "18m", "label": "Frente"},
                {"icon": "use", "value": "Residencial", "label": "Uso suelo"},
            ],
        )
        self.assertEqual(payload["property_type"], "Terreno")
        self.assertEqual(payload["lot_size_sqm"], "650 m²")


if __name__ == "__main__":
    unittest.main()
