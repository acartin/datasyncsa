import unittest

from services.ai_runtime.graph._shared.scoring_hybrid import _timeline_floor_from_text


class TimelineGuardrailTests(unittest.TestCase):
    def test_timeline_floor_detects_medium_horizon(self) -> None:
        self.assertEqual(_timeline_floor_from_text("Podria mudarme este mes si aparece algo bueno"), 6.0)

    def test_timeline_floor_detects_high_urgency(self) -> None:
        self.assertEqual(_timeline_floor_from_text("Necesito mudarme cuanto antes, idealmente esta semana"), 8.0)

    def test_timeline_floor_ignores_non_temporal_text(self) -> None:
        self.assertIsNone(_timeline_floor_from_text("Estoy comparando opciones sin prisa"))


if __name__ == "__main__":
    unittest.main()
