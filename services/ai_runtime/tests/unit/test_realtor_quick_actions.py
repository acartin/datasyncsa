import asyncio
import unittest

from services.ai_runtime.domain.contracts import Appointment, ChatMessage, TenantBusinessProfile, TenantConfig
from services.ai_runtime.domain.state import build_base_state
from services.ai_runtime.graph._shared.nodes.analyze_turn_node import analyze_turn
from services.ai_runtime.graph.realtor.contracts import Property
from services.ai_runtime.graph.realtor.nodes.show_result_cards_node import show_result_cards
from services.ai_runtime.graph.realtor.state.model import RealtorGraphState
from services.ai_runtime.graph.realtor.turn_frame import merge_seen_properties


def _tenant_config() -> TenantConfig:
    return TenantConfig(
        client_id="tenant-1",
        vertical="realtor",
        business=TenantBusinessProfile(name="Datasyncsa AI"),
    )


def _property(property_id: str, title: str, price: float) -> Property:
    return Property.model_validate(
        {
            "id": property_id,
            "client_id": "tenant-1",
            "title": title,
            "description_html": "<p>Propiedad lista para mostrar.</p>",
            "price": price,
            "currency": "USD",
            "address": "Heredia, Costa Rica",
            "features": {
                "garage_clean": 2,
                "bedrooms_clean": 3,
                "bathrooms_clean": 2,
                "sqm_clean": 180,
                "amenities": ["Seguridad"],
                "is_featured": False,
            },
            "media": {
                "primary_image_url": "https://example.com/main.jpg",
                "image_urls": ["https://example.com/main.jpg"],
            },
            "location": {
                "province": "Heredia",
            },
            "meta": {
                "public_url": f"https://example.com/listing/{property_id}",
            },
        }
    )


def _state() -> RealtorGraphState:
    tenant_config = _tenant_config()
    base_state = build_base_state(
        session_id="session-1",
        conversation_id="conversation-1",
        user_id="user-1",
        client_id="tenant-1",
        vertical="realtor",
        flow="realtor_flow",
        tenant_config=tenant_config,
        initial_message="hola",
    )
    state = RealtorGraphState.model_validate(base_state.model_dump(mode="json"))
    state.capabilities = ["buscar", "agendar", "calcular", "escalar"]
    state.cita = Appointment(client_id="tenant-1")
    return state


class _FailingLLM:
    async def analyze_turn(self, prompt):
        raise AssertionError(f"analyze_turn no debería invocarse para quick actions: {prompt}")


class _Deps:
    llm = _FailingLLM()


class RealtorQuickActionsTests(unittest.TestCase):
    def test_interest_yes_quick_action_bypasses_llm(self) -> None:
        state = _state()
        prop = _property("prop-1", "Casa en condominio en San Rafael", 165000)
        state.last_mentioned = prop
        state.last_search_results = [prop]
        state.messages = [
            ChatMessage(
                role="user",
                content="Sí me interesa esta opción",
                metadata={"action_id": "interest_yes", "target_property_id": "prop-1"},
            )
        ]

        updates = asyncio.run(analyze_turn(state.model_dump(mode="json"), _Deps()))

        self.assertEqual(updates["turn_analysis"]["dialogue_act"], "select_result")
        self.assertEqual(updates["resolved_references"][0]["property_id"], "prop-1")
        self.assertEqual(updates["intent_queue"][0]["type"], "focus_property")
        self.assertEqual(updates["lead_advisor"]["lead_extracted"]["appointment_intent"], "positive")

    def test_reject_current_creates_refinement_decision(self) -> None:
        state = _state()
        prop = _property("prop-1", "Casa en Mercedes", 172000)
        state.last_mentioned = prop
        state.last_search_results = [prop]
        state.messages = [
            ChatMessage(
                role="user",
                content="No es lo que busco",
                metadata={"action_id": "reject_current", "target_property_id": "prop-1"},
            )
        ]

        updates = asyncio.run(analyze_turn(state.model_dump(mode="json"), _Deps()))

        self.assertEqual(updates["turn_analysis"]["dialogue_act"], "refine_search")
        self.assertEqual(updates["pending_decision"]["kind"], "quick_refine_choice")
        self.assertFalse(updates["intent_queue"])

    def test_show_next_action_rotates_to_unseen_property(self) -> None:
        state = _state()
        prop_1 = _property("prop-1", "Casa en San Rafael", 165000)
        prop_2 = _property("prop-2", "Casa en Mercedes", 172000)
        state.last_search_results = [prop_1, prop_2]
        state.cards_shown = ["prop-1"]
        state.last_mentioned = prop_1
        state.seen_properties = merge_seen_properties({}, [prop_1], current_turn=state.current_turn)
        state.messages = [
            ChatMessage(
                role="user",
                content="Mostrame otra opción",
                metadata={"action_id": "show_next"},
            )
        ]

        updates = asyncio.run(show_result_cards(state.model_dump(mode="json"), object()))

        cards = updates["ui_payload"]["property_cards"]
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["id"], "prop-2")
        self.assertEqual(updates["last_mentioned"]["id"], "prop-2")
        self.assertIn("prop-2", updates["seen_properties"])


if __name__ == "__main__":
    unittest.main()
