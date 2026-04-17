import unittest

from services.ai_runtime.domain.contracts import Appointment, ChatMessage, TenantBusinessProfile, TenantConfig
from services.ai_runtime.graph.realtor.policies import RealtorPolicy
from services.ai_runtime.graph.realtor.state.model import RealtorGraphState, SearchFilters
from services.ai_runtime.verticals import get_vertical_spec


def _tenant_config(vertical: str = "realtor") -> TenantConfig:
    return TenantConfig(
        client_id="client-1",
        vertical=vertical,
        business=TenantBusinessProfile(name="Demo"),
    )


class VerticalPoliciesTests(unittest.TestCase):
    def test_realtor_policy_syncs_budget_from_search_filters(self) -> None:
        policy = RealtorPolicy()
        state = RealtorGraphState(
            session_id="session-1",
            conversation_id="conversation-1",
            user_id="user-1",
            client_id="client-1",
            vertical="realtor",
            flow="realtor_flow",
            tenant_config=_tenant_config("realtor"),
            messages=[ChatMessage(role="user", content="hola")],
            capabilities=[],
            cita=Appointment(client_id="client-1"),
            search_filters=SearchFilters(precio_max=275000),
        )

        payload = policy.extra_lead_sync(state, {})

        self.assertEqual(payload["presupuesto"], 275000.0)

    def test_realtor_policy_marks_negative_appointment_intent_from_user_message(self) -> None:
        policy = RealtorPolicy()
        state = RealtorGraphState(
            session_id="session-1",
            conversation_id="conversation-1",
            user_id="user-1",
            client_id="client-1",
            vertical="realtor",
            flow="realtor_flow",
            tenant_config=_tenant_config("realtor"),
            messages=[ChatMessage(role="user", content="No quiero agendar todavia, solo estoy comparando")],
            capabilities=[],
            cita=Appointment(client_id="client-1"),
            search_filters=SearchFilters(),
        )

        payload = policy.extra_lead_sync(
            state,
            {"appointment_intent": None, "tipo_cita": "visita"},
        )

        self.assertEqual(payload.get("appointment_intent"), "negative")
        self.assertIsNone(payload.get("tipo_cita"))

    def test_vertical_registry_exposes_realtor_specific_hooks(self) -> None:
        spec = get_vertical_spec("realtor")

        self.assertIsInstance(spec.policy, RealtorPolicy)
        self.assertEqual(spec.turn_frame_model.__name__, "RealtorTurnFrame")
        self.assertEqual(spec.turn_frame_builder.__name__, "build_realtor_turn_frame")


if __name__ == "__main__":
    unittest.main()
