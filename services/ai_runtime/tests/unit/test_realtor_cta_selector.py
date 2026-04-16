import unittest

from services.ai_runtime.domain.contracts import TenantBusinessProfile, TenantConfig
from services.ai_runtime.graph.realtor.cta_matrix_loader import clear_realtor_card_cta_matrix_cache
from services.ai_runtime.graph.realtor.cta_selector import select_realtor_card_ctas
from services.ai_runtime.graph.realtor.state.model import RealtorGraphState
from services.ai_runtime.domain.state import build_base_state


def _state() -> RealtorGraphState:
    tenant_config = TenantConfig(
        client_id="tenant-1",
        vertical="realtor",
        business=TenantBusinessProfile(name="Datasyncsa AI"),
    )
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
    state.ui_payload = {
        "property_cards": [
            {
                "id": "prop-1",
                "title": "Casa demo",
                "price": 185000,
                "currency": "USD",
            }
        ]
    }
    return state


class RealtorCtaSelectorTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_realtor_card_cta_matrix_cache()

    def test_selector_uses_default_three_actions(self) -> None:
        state = _state()

        actions = select_realtor_card_ctas(state)

        self.assertEqual(
            [item["id"] for item in actions],
            ["interest_yes", "show_next", "reject_current"],
        )

    def test_selector_uses_finance_follow_up_row(self) -> None:
        state = _state()
        state.lead_advisor.lead_scores.intencion = 6.5
        state.lead_advisor.lead_extracted.presupuesto = 180000

        actions = select_realtor_card_ctas(state)

        self.assertEqual(
            [item["id"] for item in actions],
            ["interest_yes", "ask_financing", "show_next"],
        )


if __name__ == "__main__":
    unittest.main()
