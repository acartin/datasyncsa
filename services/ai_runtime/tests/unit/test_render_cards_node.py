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


if __name__ == "__main__":
    unittest.main()
