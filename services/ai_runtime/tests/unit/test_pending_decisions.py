import unittest

from services.ai_runtime.domain.contracts import (
    Appointment,
    ChatMessage,
    PendingDecision,
    ReferenceDecision,
    TenantBusinessProfile,
    TenantConfig,
    TurnAnalysis,
)
from services.ai_runtime.graph._shared.pending_decisions import render_pending_decision_question
from services.ai_runtime.graph.realtor.state.model import RealtorGraphState, SearchFilters
from services.ai_runtime.graph.realtor.turn_policies import derive_realtor_pending_decision


def _tenant_config() -> TenantConfig:
    return TenantConfig(
        client_id="client-1",
        vertical="realtor",
        business=TenantBusinessProfile(name="Datasyncsa AI"),
    )


def _state(*messages: tuple[str, str]) -> RealtorGraphState:
    return RealtorGraphState(
        session_id="session-1",
        conversation_id="conversation-1",
        user_id="user-1",
        client_id="client-1",
        vertical="realtor",
        flow="realtor_flow",
        tenant_config=_tenant_config(),
        capabilities=["buscar"],
        cita=Appointment(client_id="client-1"),
        messages=[ChatMessage(role=role, content=content) for role, content in messages],
        search_filters=SearchFilters(
            ubicacion="Curridabat",
            provincia="San Jose",
            precio_max=200000,
            tipo="Casa de Habitacion",
        ),
    )


class PendingDecisionTests(unittest.TestCase):
    def test_render_search_relaxation_choice_question(self) -> None:
        question = render_pending_decision_question(
            PendingDecision(kind="search_relaxation_choice", options=["precio", "zona", "criterios"])
        )
        self.assertIsNotNone(question)
        self.assertIn("precio", question.lower())
        self.assertIn("zona", question.lower())

    def test_derive_pending_decision_for_affirmative_after_no_results(self) -> None:
        graph_state = _state(
            ("user", "Quiero una casa de menos de 200,000 en Curridabat"),
            ("assistant", "No encontre casas en Curridabat por menos de $200,000. Te gustaria ampliar un poco el rango de precio o buscar en otra zona?"),
            ("user", "Si"),
        )
        analysis = TurnAnalysis(
            dialogue_act="confirm_previous",
            confidence=0.9,
            reference=ReferenceDecision(kind="NONE", confidence=0.99),
        )

        decision = derive_realtor_pending_decision(graph_state, analysis)

        self.assertIsNotNone(decision)
        self.assertEqual(decision.kind, "search_relaxation_choice")

    def test_derive_pending_decision_for_price_option_answer(self) -> None:
        graph_state = _state(
            ("user", "Quiero una casa de menos de 200,000 en Curridabat"),
            ("assistant", "Todavia no encontre coincidencias exactas. Que queres flexibilizar: precio, zona o algun otro criterio?"),
            ("user", "precio"),
        )
        analysis = TurnAnalysis(
            dialogue_act="unknown",
            confidence=0.4,
            reference=ReferenceDecision(kind="NONE", confidence=0.99),
        )

        decision = derive_realtor_pending_decision(graph_state, analysis)

        self.assertIsNotNone(decision)
        self.assertEqual(decision.kind, "search_relaxation_price_value")

    def test_derive_pending_decision_not_created_for_explicit_refine_search(self) -> None:
        graph_state = _state(
            ("user", "Quiero una casa de menos de 200,000 en Curridabat"),
            ("assistant", "No encontre casas en Curridabat por menos de $200,000. Te gustaria ampliar un poco el rango de precio o buscar en otra zona?"),
            ("user", "Mejor en Heredia"),
        )
        analysis = TurnAnalysis(
            dialogue_act="refine_search",
            confidence=0.9,
            reference=ReferenceDecision(kind="NONE", confidence=0.99),
            filters_delta={"provincia": "Heredia"},
        )

        decision = derive_realtor_pending_decision(graph_state, analysis)

        self.assertIsNone(decision)

    def test_derive_pending_decision_not_created_for_explicit_financial_query(self) -> None:
        graph_state = _state(
            ("user", "Busco una casa en Heredia de 3 habitaciones"),
            ("assistant", "No encontre casas exactas. Te gustaria ver mas detalles de estas o preferis que ajustemos la busqueda de otra manera?"),
            ("user", "Si la financio, cuanto seria la cuota aproximada?"),
        )
        analysis = TurnAnalysis(
            dialogue_act="unknown",
            confidence=0.0,
            reference=ReferenceDecision(kind="NONE", confidence=0.0),
        )

        decision = derive_realtor_pending_decision(graph_state, analysis)

        self.assertIsNone(decision)


if __name__ == "__main__":
    unittest.main()
