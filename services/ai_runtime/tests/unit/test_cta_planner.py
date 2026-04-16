import unittest

from services.ai_runtime.domain.contracts import Appointment, ChatMessage, TenantBusinessProfile, TenantConfig
from services.ai_runtime.domain.state import build_base_state
from services.ai_runtime.graph.realtor.state.model import RealtorGraphState
from services.ai_runtime.runtime.cta_planner import apply_cta_delivery_plan, build_cta_delivery_plan


def _tenant_config() -> TenantConfig:
    return TenantConfig(
        client_id="tenant-1",
        vertical="realtor",
        business=TenantBusinessProfile(name="Datasyncsa AI"),
    )


def _state(channel: str = "web_html") -> RealtorGraphState:
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
        initial_message_metadata={"channel": channel},
    )
    state = RealtorGraphState.model_validate(base_state.model_dump(mode="json"))
    state.cita = Appointment(client_id="tenant-1")
    state.ui_payload = {
        "property_cards": [
            {
                "id": "prop-1",
                "title": "Casa demo",
                "price": 175000,
                "currency": "USD",
            }
        ]
    }
    state.turn_outputs = [{"type": "render_cards", "count": 1}]
    state.messages = [ChatMessage(role="user", content="hola", metadata={"channel": channel})]
    return state


class CtaPlannerTests(unittest.TestCase):
    def test_builds_inline_plan_for_web_property_card(self) -> None:
        state = _state("web_html")

        plan = build_cta_delivery_plan(state)

        self.assertEqual(plan.channel, "web_html")
        self.assertEqual(plan.surface, "property_card_inline")
        self.assertEqual([item["id"] for item in plan.actions], ["interest_yes", "show_next", "reject_current"])

    def test_builds_action_menu_plan_for_whatsapp(self) -> None:
        state = _state("meta_whatsapp")
        state.messages.append(ChatMessage(role="assistant", content="Te comparto una opción"))

        plan = build_cta_delivery_plan(state)

        self.assertEqual(plan.channel, "meta_whatsapp")
        self.assertEqual(plan.surface, "action_menu")
        self.assertEqual(len(plan.actions), 3)

    def test_apply_action_menu_plan_appends_action_menu_component(self) -> None:
        state = _state("meta_whatsapp")
        plan = build_cta_delivery_plan(state)
        components = [{"type": "property-card", "id": "prop-1", "title": "Casa demo", "quick_actions": []}]

        enriched = apply_cta_delivery_plan(components, plan)

        self.assertEqual(enriched[-1]["type"], "action-menu")
        self.assertEqual(enriched[-1]["options"][0]["action_id"], "interest_yes")
        self.assertEqual(enriched[0]["quick_actions"], [])


if __name__ == "__main__":
    unittest.main()
