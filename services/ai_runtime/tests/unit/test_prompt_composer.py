import unittest

from services.ai_runtime.config.prompt_composer import compose
from services.ai_runtime.domain.contracts import TenantBusinessProfile, TenantConfig


def _tenant_config(vertical: str) -> TenantConfig:
    return TenantConfig(
        client_id="client-1",
        vertical=vertical,  # type: ignore[arg-type]
        business=TenantBusinessProfile(name="Datasyncsa AI"),
    )


class PromptComposerAnalyzeTurnTests(unittest.TestCase):
    def test_realtor_analyze_turn_is_vertical_owned(self) -> None:
        payload = compose("analyze_turn", _tenant_config("realtor"), "realtor", {"message": "hola"})

        self.assertIn("vertical realtor", payload.stable_prefix.lower())
        self.assertIn("busqueda", payload.stable_prefix.lower())

    def test_healthcare_analyze_turn_is_vertical_owned(self) -> None:
        payload = compose("analyze_turn", _tenant_config("healthcare"), "healthcare", {"message": "hola"})

        self.assertIn("vertical healthcare", payload.stable_prefix.lower())
        self.assertIn("cita", payload.stable_prefix.lower())

    def test_realtor_intent_detector_is_vertical_owned(self) -> None:
        payload = compose("intent_detector", _tenant_config("realtor"), "realtor", {"message": "hola"})

        self.assertIn("vertical realtor", payload.stable_prefix.lower())
        self.assertIn("focus_property", payload.stable_prefix.lower())

    def test_healthcare_intent_detector_is_vertical_owned(self) -> None:
        payload = compose("intent_detector", _tenant_config("healthcare"), "healthcare", {"message": "hola"})

        self.assertIn("vertical healthcare", payload.stable_prefix.lower())
        self.assertIn("captura_lead", payload.stable_prefix.lower())

    def test_realtor_synthesis_is_vertical_owned(self) -> None:
        payload = compose("synthesis_prompt", _tenant_config("realtor"), "realtor", {"message": "hola"})

        self.assertIn("sintetizador conversacional del vertical realtor", payload.stable_prefix.lower())
        self.assertIn("respuestas equivalentes", payload.stable_prefix.lower())

    def test_healthcare_synthesis_uses_local_placeholder(self) -> None:
        payload = compose("synthesis_prompt", _tenant_config("healthcare"), "healthcare", {"message": "hola"})

        self.assertIn("sintetizador conversacional del vertical healthcare", payload.stable_prefix.lower())
        self.assertIn("placeholder funcional", payload.stable_prefix.lower())

if __name__ == "__main__":
    unittest.main()
