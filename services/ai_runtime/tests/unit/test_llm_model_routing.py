import unittest

from services.ai_runtime.domain.prompts import PromptPayload
from services.ai_runtime.runtime.llm import GeminiLLMPort


class GeminiModelRoutingTests(unittest.TestCase):
    def _build_port(self) -> GeminiLLMPort:
        port = object.__new__(GeminiLLMPort)
        port._default_model = "gemini-2.5-flash-lite"
        port._analyze_turn_model = "gemini-2.5-flash"
        return port

    def test_analyze_turn_uses_override_model(self) -> None:
        port = self._build_port()

        self.assertEqual(port._model_for_operation("analyze_turn"), "gemini-2.5-flash")

    def test_other_operations_use_default_model(self) -> None:
        port = self._build_port()

        self.assertEqual(port._model_for_operation("synthesize_response"), "gemini-2.5-flash-lite")

    def test_cache_registry_key_is_model_scoped(self) -> None:
        port = self._build_port()
        prompt = PromptPayload(
            node_type="analyze_turn",
            stable_prefix="stable",
            dynamic_context="dynamic",
            full_prompt="stable\n\ndynamic",
            cacheable=True,
            cache_namespace="analyze_turn",
            cache_key="shared-cache-key",
            cache_ttl_seconds=1800,
        )

        flash_key = port._cache_registry_key(prompt, model="gemini-2.5-flash")
        lite_key = port._cache_registry_key(prompt, model="gemini-2.5-flash-lite")

        self.assertNotEqual(flash_key, lite_key)
        self.assertTrue(flash_key.startswith("gemini-2.5-flash:"))
        self.assertTrue(lite_key.startswith("gemini-2.5-flash-lite:"))


if __name__ == "__main__":
    unittest.main()
