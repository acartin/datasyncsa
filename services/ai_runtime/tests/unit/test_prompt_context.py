import unittest

from services.ai_runtime.graph._shared.prompt_context import (
    summarize_lead_advisor_for_prompt,
    summarize_property_for_prompt,
)


class PromptContextTests(unittest.TestCase):
    def test_summarize_property_omits_heavy_fields_and_keeps_excerpt(self) -> None:
        payload = summarize_property_for_prompt(
            {
                "id": "prop-1",
                "title": "Casa amplia",
                "price": 250000,
                "currency": "USD",
                "address": "Escazu",
                "description_html": "<p>Hermosa casa familiar con jardin y terraza.</p>",
                "location": {"country": "CR", "province": "San Jose"},
                "features": {
                    "bedrooms_clean": 3,
                    "bathrooms_clean": 2,
                    "garage_clean": 2,
                    "sqm_clean": 180,
                    "amenities": ["jardin", "terraza"],
                    "is_featured": True,
                },
                "media": {"primary_image_url": "https://example.com/home.jpg"},
                "meta": {"public_url": "https://example.com/listing/1"},
            },
            include_description_excerpt=True,
        )

        assert payload is not None
        self.assertEqual(payload["id"], "prop-1")
        self.assertEqual(payload["bedrooms_clean"], 3)
        self.assertIn("description_excerpt", payload)
        self.assertNotIn("description_html", payload)
        self.assertNotIn("media", payload)
        self.assertNotIn("meta", payload)

    def test_summarize_lead_advisor_omits_scoring_profile(self) -> None:
        payload = summarize_lead_advisor_for_prompt(
            {
                "lead_extracted": {"nombre": "Diana", "telefono": "555-1212"},
                "lead_completo": False,
                "should_ask": True,
                "field_to_ask": "contacto",
                "criteria_scores": {"timeline_urgency": 4},
                "criteria_reasons": {"timeline_urgency": "Quiere visitar esta semana."},
                "scoring_profile": {
                    "id": "profile-1",
                    "prompt_template": "LARGO" * 200,
                },
            }
        )

        self.assertEqual(payload["field_to_ask"], "contacto")
        self.assertIn("criteria_scores", payload)
        self.assertNotIn("scoring_profile", payload)


if __name__ == "__main__":
    unittest.main()
