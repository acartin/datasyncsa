"""LLM provider abstractions for prompts and structured outputs."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from pydantic import ValidationError

from services.ai_runtime.domain.contracts import IntentDefinition, ReferenceDecision, TextToSQLResult
from services.ai_runtime.runtime.settings import AISettings

logger = logging.getLogger(__name__)


def _extract_json(value: Any) -> Any:
    if isinstance(value, (dict, list, bool)):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        block = fenced.group(1).strip()
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            pass

    first_object = text.find("{")
    last_object = text.rfind("}")
    if first_object != -1 and last_object > first_object:
        try:
            return json.loads(text[first_object : last_object + 1])
        except json.JSONDecodeError:
            pass

    first_array = text.find("[")
    last_array = text.rfind("]")
    if first_array != -1 and last_array > first_array:
        try:
            return json.loads(text[first_array : last_array + 1])
        except json.JSONDecodeError:
            pass
    return None


def _extract_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    parsed = _extract_json(value)
    if isinstance(parsed, bool):
        return parsed
    text = str(value or "").strip().lower()
    return text == "true"


class NoopLLMPort:
    """Safe default provider used while the runtime is being wired to a real model."""

    async def classify_reference(self, prompt: str) -> ReferenceDecision:
        return ReferenceDecision(kind="NONE", confidence=1)

    async def detect_intents(self, prompt: str) -> list[IntentDefinition]:
        return []

    async def evaluate_lazy_condition(self, prompt: str) -> bool:
        return False

    async def extract_search_filters(self, prompt: str) -> dict[str, object]:
        return {}

    async def synthesize_response(self, prompt: str) -> str:
        return "Puedo ayudarte con eso. Contame un poquito mas para darte una respuesta mas precisa."

    async def redact_recommendation(self, prompt: str) -> str:
        return "Te puedo recomendar una opcion cuando tenga mejor contexto de lo que buscas."

    async def translate_text_to_sql(self, prompt: str) -> TextToSQLResult:
        return TextToSQLResult(sql="SELECT 1 WHERE 1 = 0", params={})

    async def extract_lead_fields(self, prompt: str) -> dict[str, object]:
        return {}

    async def extract_appointment_fields(self, prompt: str) -> dict[str, object]:
        return {}

    async def score_turn(self, prompt: str) -> dict[str, object]:
        return {
            "apertura": 1,
            "intencion": 1,
            "urgencia": 1,
            "match": 1,
            "solvencia": 1,
            "fields": {},
        }


class GeminiLLMPort:
    """Minimal Gemini-backed implementation for ai-runtime prompts."""

    def __init__(self, *, api_key: str, model: str, timeout_seconds: int = 30):
        if not api_key.strip():
            raise RuntimeError("GOOGLE_API_KEY_NOT_CONFIGURED")

        try:
            from google import genai
        except ImportError as exc:
            raise RuntimeError("google-genai package is required for Gemini provider") from exc

        self._genai = genai
        self._api_key = api_key.strip()
        self._model = model.strip()
        self._timeout_seconds = max(1, int(timeout_seconds))
        self._client = self._genai.Client(api_key=self._api_key)

    async def _generate_text(
        self,
        prompt: str,
        *,
        response_mime_type: str | None = None,
        temperature: float = 0.1,
        max_output_tokens: int = 1024,
    ) -> str:
        from google.genai import types

        response = await asyncio.wait_for(
            asyncio.to_thread(
                self._client.models.generate_content,
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    response_mime_type=response_mime_type,
                ),
            ),
            timeout=self._timeout_seconds,
        )
        text = str(response.text or "").strip()
        if not text:
            raise ValueError("EMPTY_LLM_RESPONSE")
        return text

    async def _generate_json(self, prompt: str, *, temperature: float = 0.1, max_output_tokens: int = 1024) -> Any:
        text = await self._generate_text(
            prompt,
            response_mime_type="application/json",
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        payload = _extract_json(text)
        if payload is None:
            raise ValueError("INVALID_JSON_RESPONSE")
        return payload

    async def classify_reference(self, prompt: str) -> ReferenceDecision:
        try:
            payload = await self._generate_json(prompt, temperature=0.0, max_output_tokens=256)
            return ReferenceDecision.model_validate(payload)
        except (ValidationError, ValueError, RuntimeError) as exc:
            logger.warning("LLM classify_reference fallback to NONE: %s", exc)
            return ReferenceDecision(kind="NONE", confidence=0)

    async def detect_intents(self, prompt: str) -> list[IntentDefinition]:
        try:
            payload = await self._generate_json(prompt, temperature=0.0, max_output_tokens=768)
        except (ValueError, RuntimeError) as exc:
            logger.warning("LLM detect_intents fallback to empty queue: %s", exc)
            return []

        queue = payload.get("intent_queue") if isinstance(payload, dict) else payload if isinstance(payload, list) else []
        detected: list[IntentDefinition] = []
        for item in queue[:4]:
            try:
                detected.append(IntentDefinition.model_validate(item))
            except ValidationError as exc:
                logger.warning("LLM detect_intents skipped invalid item: %s", exc)
        return detected

    async def evaluate_lazy_condition(self, prompt: str) -> bool:
        try:
            text = await self._generate_text(prompt, temperature=0.0, max_output_tokens=8)
        except (ValueError, RuntimeError) as exc:
            logger.warning("LLM evaluate_lazy_condition fallback false: %s", exc)
            return False
        return _extract_bool(text)

    async def extract_search_filters(self, prompt: str) -> dict[str, object]:
        try:
            payload = await self._generate_json(prompt, temperature=0.0, max_output_tokens=768)
        except (ValueError, RuntimeError) as exc:
            logger.warning("LLM extract_search_filters fallback empty payload: %s", exc)
            return {}
        return payload if isinstance(payload, dict) else {}

    async def synthesize_response(self, prompt: str) -> str:
        try:
            return await self._generate_text(prompt, temperature=0.3, max_output_tokens=900)
        except (ValueError, RuntimeError) as exc:
            logger.warning("LLM synthesize_response fallback generic answer: %s", exc)
            return "Puedo ayudarte con eso. Contame un poquito mas para darte una respuesta mas precisa."

    async def redact_recommendation(self, prompt: str) -> str:
        try:
            return await self._generate_text(prompt, temperature=0.35, max_output_tokens=700)
        except (ValueError, RuntimeError) as exc:
            logger.warning("LLM redact_recommendation fallback generic answer: %s", exc)
            return "Te puedo recomendar una opcion cuando tenga mejor contexto de lo que buscas."

    async def translate_text_to_sql(self, prompt: str) -> TextToSQLResult:
        try:
            payload = await self._generate_json(prompt, temperature=0.0, max_output_tokens=768)
            return TextToSQLResult.model_validate(payload)
        except (ValidationError, ValueError, RuntimeError) as exc:
            logger.warning("LLM translate_text_to_sql fallback empty query: %s", exc)
            return TextToSQLResult(sql="SELECT 1 WHERE 1 = 0", params={})

    async def extract_lead_fields(self, prompt: str) -> dict[str, object]:
        try:
            payload = await self._generate_json(prompt, temperature=0.1, max_output_tokens=512)
        except (ValueError, RuntimeError) as exc:
            logger.warning("LLM extract_lead_fields fallback empty payload: %s", exc)
            return {}
        return payload if isinstance(payload, dict) else {}

    async def extract_appointment_fields(self, prompt: str) -> dict[str, object]:
        try:
            payload = await self._generate_json(prompt, temperature=0.1, max_output_tokens=512)
        except (ValueError, RuntimeError) as exc:
            logger.warning("LLM extract_appointment_fields fallback empty payload: %s", exc)
            return {}
        return payload if isinstance(payload, dict) else {}

    async def score_turn(self, prompt: str) -> dict[str, object]:
        try:
            payload = await self._generate_json(prompt, temperature=0.1, max_output_tokens=768)
        except (ValueError, RuntimeError) as exc:
            logger.warning("LLM score_turn fallback baseline scores: %s", exc)
            return {
                "apertura": 1,
                "intencion": 1,
                "urgencia": 1,
                "match": 1,
                "solvencia": 1,
                "fields": {},
            }
        return payload if isinstance(payload, dict) else {}


def build_llm_port(settings: AISettings):
    provider = settings.llm_provider.strip().lower()
    if provider in {"", "auto"}:
        provider = "gemini" if settings.google_api_key.strip() else "noop"

    if provider == "noop":
        logger.warning("AI runtime LLM provider resolved to noop")
        return NoopLLMPort()
    if provider == "gemini":
        logger.info("AI runtime LLM provider resolved to gemini model=%s", settings.llm_model)
        return GeminiLLMPort(
            api_key=settings.google_api_key,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    raise ValueError(f"Unsupported AI_LLM_PROVIDER={settings.llm_provider!r}")
