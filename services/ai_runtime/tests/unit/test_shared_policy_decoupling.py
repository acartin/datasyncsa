import asyncio
import json
import unittest

from services.ai_runtime.domain.contracts import (
    Appointment,
    ChatMessage,
    IntentDefinition,
    TenantBusinessProfile,
    TenantConfig,
    TurnAnalysis,
)
from services.ai_runtime.domain.state import GenericGraphState, build_base_state, build_lead_advisor_state
from services.ai_runtime.graph._shared.nodes.analyze_turn_node import analyze_turn
from services.ai_runtime.graph._shared.nodes.classify_intent_node import classify_intent
from services.ai_runtime.graph._shared.nodes.lead_advisor_node import _select_field_to_ask
from services.ai_runtime.graph._shared.nodes.route_next_intent_node import route_next_intent


def _tenant_config(vertical: str = "healthcare") -> TenantConfig:
    return TenantConfig(
        client_id="tenant-1",
        vertical=vertical,
        business=TenantBusinessProfile(name="Datasyncsa AI"),
    )


def _generic_state() -> GenericGraphState:
    tenant_config = _tenant_config("healthcare")
    base_state = build_base_state(
        session_id="session-1",
        conversation_id="conversation-1",
        user_id="user-1",
        client_id="tenant-1",
        vertical="healthcare",
        flow="basic_flow",
        tenant_config=tenant_config,
        initial_message="Hola, quisiera una cita",
        initial_message_metadata={"channel": "web_html"},
    )
    state = GenericGraphState.model_validate(base_state.model_dump(mode="json"))
    state.cita = Appointment(client_id="tenant-1")
    return state


class _LLM:
    async def analyze_turn(self, prompt):
        self.last_prompt = prompt
        return TurnAnalysis(dialogue_act="schedule", confidence=0.9)

    async def detect_intents(self, prompt):
        self.last_prompt = prompt
        return []


class _Deps:
    def __init__(self):
        self.llm = _LLM()


class SharedPolicyDecouplingTests(unittest.TestCase):
    def test_generic_analyze_turn_does_not_require_realtor_state(self) -> None:
        state = _generic_state()
        state.messages = [ChatMessage(role="user", content="Quiero agendar una cita", metadata={"channel": "web_html"})]

        updates = asyncio.run(analyze_turn(state.model_dump(mode="json"), _Deps()))

        self.assertEqual(updates["turn_analysis"]["dialogue_act"], "schedule")
        self.assertIn("intent_queue", updates)

    def test_generic_analyze_turn_uses_neutral_prompt_context(self) -> None:
        deps = _Deps()
        state = _generic_state()
        state.messages = [ChatMessage(role="user", content="Quiero agendar una cita", metadata={"channel": "web_html"})]

        asyncio.run(analyze_turn(state.model_dump(mode="json"), deps))

        dynamic_context = json.loads(deps.llm.last_prompt.dynamic_context)
        self.assertIn("search_context", dynamic_context)
        self.assertIn("visible_reference_items", dynamic_context)
        self.assertIn("reference_candidates", dynamic_context)
        self.assertIn("focused_entity", dynamic_context)
        self.assertNotIn("cards_shown", dynamic_context)
        self.assertNotIn("last_search_results", dynamic_context)
        self.assertNotIn("last_mentioned", dynamic_context)

    def test_generic_classify_intent_does_not_require_realtor_results(self) -> None:
        deps = _Deps()
        state = _generic_state()
        state.messages = [
            ChatMessage(role="assistant", content="¿Quieres que te describa las opciones?"),
            ChatMessage(role="user", content="Sí"),
        ]

        updates = asyncio.run(classify_intent(state.model_dump(mode="json"), deps))

        self.assertEqual(updates["intent_queue"], [])
        self.assertIsNone(updates["active_intent"])

    def test_generic_route_next_intent_handles_min_search_results_without_realtor_state(self) -> None:
        deps = _Deps()
        state = _generic_state()
        state.intent_queue = [
            IntentDefinition(
                id="intent-1",
                type="agendar",
                priority=1,
                depends_on=[],
                condition={"min_search_results": 1},
                skip_if_failed=False,
                status="pending",
            )
        ]

        updates = asyncio.run(route_next_intent(state.model_dump(mode="json"), deps))

        self.assertIsNone(updates["active_intent"])
        self.assertEqual(updates["intent_queue"][0]["status"], "pending")

    def test_generic_schedule_keeps_contact_fallback(self) -> None:
        state = _generic_state()
        advisor_state = build_lead_advisor_state(state.tenant_config, state.lead_advisor).model_copy(
            update={
                "capture_exposure_count": 3,
                "required_fields": ["email", "telefono"],
                "target_fields": ["email", "telefono"],
                "completed_fields": [],
            }
        )

        field = _select_field_to_ask(
            state,
            advisor_state,
            suggested_field="contacto",
            dialogue_act="schedule",
            capture_exposure_count=3,
            current_turn_is_exposure=False,
        )

        self.assertEqual(field, "contacto")


if __name__ == "__main__":
    unittest.main()
