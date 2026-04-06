import unittest

from services.ai_runtime.domain.contracts import LeadExtracted
from services.ai_runtime.graph._shared.nodes.capture_memory_entities_node import (
    _extract_name_fallback,
    _merge_canonical_fields,
    _normalize_appointment_intent,
    _should_extract_memory,
)


class CaptureMemoryEntitiesNodeTests(unittest.TestCase):
    def test_normalize_appointment_intent_maps_booleans(self) -> None:
        self.assertEqual(_normalize_appointment_intent(True), "positive")
        self.assertEqual(_normalize_appointment_intent(False), "negative")

    def test_merge_canonical_fields_normalizes_boolean_appointment_intent(self) -> None:
        merged = _merge_canonical_fields(
            LeadExtracted(tipo_cita="visita"),
            {"appointment_intent": True},
        )

        self.assertEqual(merged.appointment_intent, "positive")
        self.assertEqual(merged.tipo_cita, "visita")

    def test_negative_appointment_intent_clears_tipo_cita(self) -> None:
        merged = _merge_canonical_fields(
            LeadExtracted(tipo_cita="visita"),
            {"appointment_intent": False},
        )

        self.assertEqual(merged.appointment_intent, "negative")
        self.assertIsNone(merged.tipo_cita)

    def test_short_name_pattern_accepts_uppercase_con_prefix(self) -> None:
        message = "Con Alvaro Cartin"

        self.assertTrue(_should_extract_memory(message))
        self.assertEqual(_extract_name_fallback(message), "Alvaro Cartin")

    def test_explicit_self_identification_embedded_in_search_message_extracts_name(self) -> None:
        message = "Hola, soy Maria Jimenez, busco una casa en Alajuela"

        self.assertTrue(_should_extract_memory(message))
        self.assertEqual(_extract_name_fallback(message), "Maria Jimenez")

    def test_self_description_without_name_does_not_extract_name(self) -> None:
        message = "Hola, soy inversionista y busco apartamentos"

        self.assertFalse(_should_extract_memory(message))
        self.assertIsNone(_extract_name_fallback(message))


if __name__ == "__main__":
    unittest.main()
