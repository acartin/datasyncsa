import unittest

from services.ai_runtime.graph._shared.nodes.synthesize_node import _resolve_lead_prompt_for_synthesis


class SynthesizeNodeTests(unittest.TestCase):
    def test_forces_contact_prompt_when_appointment_pending_and_name_known(self) -> None:
        answer, field_to_ask, question_to_ask = _resolve_lead_prompt_for_synthesis(
            answer="Perfecto, Diana. La visita queda agendada para el proximo viernes por la tarde.",
            lead_should_ask=False,
            lead_field_to_ask=None,
            lead_question_to_ask=None,
            appointment_pending_contact=True,
            lead_name_known=True,
        )

        self.assertEqual(field_to_ask, "contacto")
        self.assertEqual(
            question_to_ask,
            "Si queres, te dejo esto encaminado. Te queda mejor compartirme tu telefono o tu correo?",
        )
        self.assertIn("telefono o tu correo", answer)

    def test_keeps_existing_lead_prompt_when_no_contact_override_is_needed(self) -> None:
        answer, field_to_ask, question_to_ask = _resolve_lead_prompt_for_synthesis(
            answer="Te puedo ayudar con eso.",
            lead_should_ask=True,
            lead_field_to_ask="nombre",
            lead_question_to_ask="Antes de seguir, con quien tengo el gusto?",
            appointment_pending_contact=False,
            lead_name_known=False,
        )

        self.assertEqual(answer, "Te puedo ayudar con eso.")
        self.assertEqual(field_to_ask, "nombre")
        self.assertEqual(question_to_ask, "Antes de seguir, con quien tengo el gusto?")


if __name__ == "__main__":
    unittest.main()
