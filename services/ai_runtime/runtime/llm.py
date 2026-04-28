"""LLM provider abstractions for prompts and structured outputs."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import ValidationError

from services.ai_runtime.domain.contracts import IntentDefinition, TextToSQLResult, TurnAnalysis
from services.ai_runtime.domain.prompts import PromptInput, PromptPayload
from services.ai_runtime.runtime.settings import AISettings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _CachedContentEntry:
    name: str
    expires_at: datetime | None = None


def _coerce_prompt_text(prompt: PromptInput) -> str:
    if isinstance(prompt, PromptPayload):
        return prompt.full_prompt
    return str(prompt)


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


DETAIL_ATTRIBUTE_ALIASES = {
    "baño": "banos",
    "baños": "banos",
    "bano": "banos",
    "banos": "banos",
    "servicio": "banos",
    "servicios": "banos",
    "cuarto": "habitaciones",
    "cuartos": "habitaciones",
    "dormitorio": "habitaciones",
    "dormitorios": "habitaciones",
    "metros": "area",
    "metro": "area",
    "m2": "area",
    "m²": "area",
    "tamaño": "area",
    "tamano": "area",
    "garaje": "garage",
    "cochera": "garage",
    "cocheras": "garage",
    "estacionamiento": "garage",
    "estacionamientos": "garage",
    "parqueo": "garage",
    "parqueos": "garage",
    "ficha": "foto",
    "fichas": "foto",
    "imagen": "foto",
    "imagenes": "foto",
    "imágenes": "foto",
    "anuncio": "foto",
    "anuncios": "foto",
    "card": "foto",
    "cards": "foto",
    "tarjeta": "foto",
    "tarjetas": "foto",
}


def _normalize_turn_analysis_payload(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    normalized = dict(payload)
    raw_key = normalized.get("detail_attribute_key")
    if isinstance(raw_key, str):
        normalized["detail_attribute_key"] = DETAIL_ATTRIBUTE_ALIASES.get(raw_key.strip().lower(), raw_key.strip().lower())
    raw_scope = normalized.get("detail_scope")
    if isinstance(raw_scope, str):
        scope = raw_scope.strip().lower()
        detail_scope_aliases = {
            "property": "resolved_reference",
            "focused_property": "resolved_reference",
            "focused_entity": "resolved_reference",
            "current_results": "current_result_set",
            "visible_results": "current_result_set",
            "cards_shown": "current_result_set",
        }
        normalized["detail_scope"] = detail_scope_aliases.get(scope, scope)
    return normalized


class NoopLLMPort:
    """Safe default provider used while the runtime is being wired to a real model."""

    async def analyze_turn(self, prompt: PromptInput) -> TurnAnalysis:
        del prompt
        return TurnAnalysis()

    async def detect_intents(self, prompt: PromptInput) -> list[IntentDefinition]:
        return []

    async def evaluate_lazy_condition(self, prompt: PromptInput) -> bool:
        return False

    async def extract_search_filters(self, prompt: PromptInput) -> dict[str, object]:
        return {}

    async def extract_memory_entities(self, prompt: PromptInput) -> dict[str, object]:
        return {"canonical_fields": {}, "entities": []}

    async def synthesize_response(self, prompt: PromptInput) -> str:
        return "Puedo ayudarte con eso. Contame un poquito mas para darte una respuesta mas precisa."

    async def redact_recommendation(self, prompt: PromptInput) -> str:
        return "Te puedo recomendar una opcion cuando tenga mejor contexto de lo que buscas."

    async def translate_text_to_sql(self, prompt: PromptInput) -> TextToSQLResult:
        return TextToSQLResult(sql="SELECT 1 WHERE 1 = 0", params={})

    async def extract_lead_fields(self, prompt: PromptInput) -> dict[str, object]:
        return {}

    async def extract_appointment_fields(self, prompt: PromptInput) -> dict[str, object]:
        return {}

    async def score_turn(self, prompt: PromptInput) -> dict[str, object]:
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

    def __init__(
        self,
        *,
        api_key: str,
        default_model: str,
        analyze_turn_model: str | None = None,
        timeout_seconds: int = 30,
        context_cache_enabled: bool = True,
        context_cache_ttl_seconds: int = 1800,
        context_cache_min_stable_chars: int = 2000,
    ):
        if not api_key.strip():
            raise RuntimeError("GOOGLE_API_KEY_NOT_CONFIGURED")

        try:
            from google import genai
        except ImportError as exc:
            raise RuntimeError("google-genai package is required for Gemini provider") from exc

        self._genai = genai
        self._api_key = api_key.strip()
        self._default_model = default_model.strip()
        self._analyze_turn_model = (analyze_turn_model or default_model).strip()
        self._timeout_seconds = max(1, int(timeout_seconds))
        self._client = self._genai.Client(api_key=self._api_key)
        self._context_cache_enabled = bool(context_cache_enabled)
        self._context_cache_ttl_seconds = max(60, int(context_cache_ttl_seconds))
        self._context_cache_min_stable_chars = max(256, int(context_cache_min_stable_chars))
        self._context_cache_registry: dict[str, _CachedContentEntry] = {}
        self._context_cache_failures: set[str] = set()
        self._context_cache_lock: asyncio.Lock | None = None

    def _model_for_operation(self, operation_name: str) -> str:
        if operation_name == "analyze_turn":
            return self._analyze_turn_model
        return self._default_model

    def _cache_registry_key(self, prompt: PromptPayload, *, model: str) -> str:
        base_key = prompt.cache_key or hashlib.sha256(prompt.stable_prefix.encode("utf-8")).hexdigest()
        return f"{model}:{prompt.cache_namespace or prompt.node_type}:{base_key}"

    def _mark_cache_failure(self, registry_key: str, prompt: PromptPayload, exc: Exception) -> None:
        self._context_cache_failures.add(registry_key)
        message = str(exc)
        prompt.record_cache(status="create_failed", error=message)
        lower = message.lower()
        if "cached content" in lower and ("not support" in lower or "unsupported" in lower):
            self._context_cache_enabled = False
            prompt.record_cache(provider_cache_disabled=True)

    def _invalidate_cached_content(self, registry_key: str | None) -> None:
        if not registry_key:
            return
        self._context_cache_registry.pop(registry_key, None)

    def _is_invalid_cached_content_error(self, exc: Exception) -> bool:
        lower = str(exc).lower()
        return "cachedcontent" in lower or "cached content" in lower

    def _entry_is_expired(self, entry: _CachedContentEntry) -> bool:
        if entry.expires_at is None:
            return False
        return entry.expires_at <= datetime.now(tz=UTC) + timedelta(seconds=5)

    async def _get_or_create_cached_content(self, prompt: PromptPayload, *, model: str) -> str | None:
        if not self._context_cache_enabled:
            prompt.record_cache(status="disabled")
            return None
        if not prompt.cacheable or not prompt.stable_prefix.strip():
            prompt.record_cache(status="bypass", reason="not_cacheable")
            return None
        if len(prompt.stable_prefix) < self._context_cache_min_stable_chars:
            prompt.record_cache(
                status="bypass",
                reason="stable_prefix_too_small",
                stable_chars=len(prompt.stable_prefix),
            )
            return None

        registry_key = self._cache_registry_key(prompt, model=model)
        prompt.record_cache(
            eligible=True,
            registry_key=registry_key,
            stable_chars=len(prompt.stable_prefix),
            model=model,
        )
        if registry_key in self._context_cache_failures:
            prompt.record_cache(status="bypass", reason="previous_create_failed")
            return None

        cached_entry = self._context_cache_registry.get(registry_key)
        if cached_entry and self._entry_is_expired(cached_entry):
            self._invalidate_cached_content(registry_key)
            prompt.record_cache(status="expired_local_recreate", cached_content=cached_entry.name)
            cached_entry = None
        if cached_entry:
            prompt.record_cache(
                status="hit",
                cached_content=cached_entry.name,
                expires_at=cached_entry.expires_at.isoformat() if cached_entry.expires_at else None,
            )
            return cached_entry.name

        from google.genai import types

        if self._context_cache_lock is None:
            self._context_cache_lock = asyncio.Lock()

        async with self._context_cache_lock:
            cached_entry = self._context_cache_registry.get(registry_key)
            if cached_entry and self._entry_is_expired(cached_entry):
                self._invalidate_cached_content(registry_key)
                prompt.record_cache(status="expired_local_recreate", cached_content=cached_entry.name)
                cached_entry = None
            if cached_entry:
                prompt.record_cache(
                    status="hit",
                    cached_content=cached_entry.name,
                    expires_at=cached_entry.expires_at.isoformat() if cached_entry.expires_at else None,
                )
                return cached_entry.name
            try:
                cached = await asyncio.wait_for(
                    asyncio.to_thread(
                        self._client.caches.create,
                        model=model,
                        config=types.CreateCachedContentConfig(
                            display_name=f"{prompt.node_type}-{registry_key[-12:]}",
                            system_instruction=prompt.stable_prefix,
                            ttl=f"{prompt.cache_ttl_seconds or self._context_cache_ttl_seconds}s",
                        ),
                    ),
                    timeout=self._timeout_seconds,
                )
            except Exception as exc:
                logger.warning("LLM context cache create failed for %s: %s", prompt.node_type, exc)
                self._mark_cache_failure(registry_key, prompt, exc)
                return None

            cached_name = str(getattr(cached, "name", "") or "").strip()
            if not cached_name:
                prompt.record_cache(status="create_missing_name")
                self._context_cache_failures.add(registry_key)
                return None
            expire_at = getattr(cached, "expire_time", None)
            if expire_at is None:
                expire_at = datetime.now(tz=UTC) + timedelta(
                    seconds=prompt.cache_ttl_seconds or self._context_cache_ttl_seconds
                )
            self._context_cache_registry[registry_key] = _CachedContentEntry(
                name=cached_name,
                expires_at=expire_at,
            )
            prompt.record_cache(
                status="miss_created",
                cached_content=cached_name,
                expires_at=expire_at.isoformat() if expire_at else None,
            )
            return cached_name

    async def _generate_text(
        self,
        prompt: PromptInput,
        *,
        model: str,
        response_mime_type: str | None = None,
        temperature: float = 0.1,
        max_output_tokens: int = 1024,
    ) -> str:
        from google.genai import types

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            response_mime_type=response_mime_type,
        )
        contents: str = _coerce_prompt_text(prompt)
        registry_key: str | None = None
        cached_content: str | None = None
        if isinstance(prompt, PromptPayload):
            prompt.record_cache(model=model)
            registry_key = self._cache_registry_key(prompt, model=model)
            cached_content = await self._get_or_create_cached_content(prompt, model=model)
            if cached_content:
                config = types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    response_mime_type=response_mime_type,
                    cached_content=cached_content,
                )
                contents = prompt.dynamic_context

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self._client.models.generate_content,
                    model=model,
                    contents=contents,
                    config=config,
                ),
                timeout=self._timeout_seconds,
            )
        except Exception as exc:
            if cached_content and self._is_invalid_cached_content_error(exc):
                logger.warning("LLM context cache stale for %s, retrying uncached: %s", registry_key, exc)
                self._invalidate_cached_content(registry_key)
                prompt.record_cache(
                    status="stale_rejected_retry_uncached",
                    cached_content=cached_content,
                    error=str(exc),
                )
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self._client.models.generate_content,
                        model=model,
                        contents=_coerce_prompt_text(prompt),
                        config=types.GenerateContentConfig(
                            temperature=temperature,
                            max_output_tokens=max_output_tokens,
                            response_mime_type=response_mime_type,
                        ),
                    ),
                    timeout=self._timeout_seconds,
                )
            else:
                raise
        text = str(response.text or "").strip()
        if not text:
            raise ValueError("EMPTY_LLM_RESPONSE")
        return text

    async def _generate_json(
        self,
        prompt: PromptInput,
        *,
        model: str,
        temperature: float = 0.1,
        max_output_tokens: int = 1024,
    ) -> Any:
        text = await self._generate_text(
            prompt,
            model=model,
            response_mime_type="application/json",
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        payload = _extract_json(text)
        if payload is None:
            raise ValueError("INVALID_JSON_RESPONSE")
        return payload

    async def analyze_turn(self, prompt: PromptInput) -> TurnAnalysis:
        model = self._model_for_operation("analyze_turn")
        try:
            payload = await self._generate_json(prompt, model=model, temperature=0.0, max_output_tokens=1200)
            payload = _normalize_turn_analysis_payload(payload)
            return TurnAnalysis.model_validate(payload)
        except Exception as exc:
            logger.warning("LLM analyze_turn fallback empty analysis: %s", exc)
            return TurnAnalysis()

    async def detect_intents(self, prompt: PromptInput) -> list[IntentDefinition]:
        model = self._model_for_operation("detect_intents")
        try:
            payload = await self._generate_json(prompt, model=model, temperature=0.0, max_output_tokens=768)
        except Exception as exc:
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

    async def evaluate_lazy_condition(self, prompt: PromptInput) -> bool:
        model = self._model_for_operation("evaluate_lazy_condition")
        try:
            text = await self._generate_text(prompt, model=model, temperature=0.0, max_output_tokens=8)
        except Exception as exc:
            logger.warning("LLM evaluate_lazy_condition fallback false: %s", exc)
            return False
        return _extract_bool(text)

    async def extract_search_filters(self, prompt: PromptInput) -> dict[str, object]:
        model = self._model_for_operation("extract_search_filters")
        try:
            payload = await self._generate_json(prompt, model=model, temperature=0.0, max_output_tokens=768)
        except Exception as exc:
            logger.warning("LLM extract_search_filters fallback empty payload: %s", exc)
            return {}
        return payload if isinstance(payload, dict) else {}

    async def extract_memory_entities(self, prompt: PromptInput) -> dict[str, object]:
        model = self._model_for_operation("extract_memory_entities")
        try:
            payload = await self._generate_json(prompt, model=model, temperature=0.0, max_output_tokens=768)
        except Exception as exc:
            logger.warning("LLM extract_memory_entities fallback empty payload: %s", exc)
            return {"canonical_fields": {}, "entities": []}
        return payload if isinstance(payload, dict) else {"canonical_fields": {}, "entities": []}

    async def synthesize_response(self, prompt: PromptInput) -> str:
        model = self._model_for_operation("synthesize_response")
        try:
            return await self._generate_text(prompt, model=model, temperature=0.3, max_output_tokens=900)
        except Exception as exc:
            logger.warning("LLM synthesize_response fallback generic answer: %s", exc)
            return "Puedo ayudarte con eso. Contame un poquito mas para darte una respuesta mas precisa."

    async def redact_recommendation(self, prompt: PromptInput) -> str:
        model = self._model_for_operation("redact_recommendation")
        try:
            return await self._generate_text(prompt, model=model, temperature=0.35, max_output_tokens=700)
        except Exception as exc:
            logger.warning("LLM redact_recommendation fallback generic answer: %s", exc)
            return "Te puedo recomendar una opcion cuando tenga mejor contexto de lo que buscas."

    async def translate_text_to_sql(self, prompt: PromptInput) -> TextToSQLResult:
        model = self._model_for_operation("translate_text_to_sql")
        try:
            payload = await self._generate_json(prompt, model=model, temperature=0.0, max_output_tokens=768)
            return TextToSQLResult.model_validate(payload)
        except Exception as exc:
            logger.warning("LLM translate_text_to_sql fallback empty query: %s", exc)
            return TextToSQLResult(sql="SELECT 1 WHERE 1 = 0", params={})

    async def extract_lead_fields(self, prompt: PromptInput) -> dict[str, object]:
        model = self._model_for_operation("extract_lead_fields")
        try:
            payload = await self._generate_json(prompt, model=model, temperature=0.1, max_output_tokens=512)
        except Exception as exc:
            logger.warning("LLM extract_lead_fields fallback empty payload: %s", exc)
            return {}
        return payload if isinstance(payload, dict) else {}

    async def extract_appointment_fields(self, prompt: PromptInput) -> dict[str, object]:
        model = self._model_for_operation("extract_appointment_fields")
        try:
            payload = await self._generate_json(prompt, model=model, temperature=0.1, max_output_tokens=512)
        except Exception as exc:
            logger.warning("LLM extract_appointment_fields fallback empty payload: %s", exc)
            return {}
        return payload if isinstance(payload, dict) else {}

    async def score_turn(self, prompt: PromptInput) -> dict[str, object]:
        model = self._model_for_operation("score_turn")
        try:
            payload = await self._generate_json(prompt, model=model, temperature=0.1, max_output_tokens=768)
        except Exception as exc:
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
        logger.info(
            "AI runtime LLM provider resolved to gemini default_model=%s analyze_turn_model=%s",
            settings.llm_default_model,
            settings.llm_analyze_turn_model,
        )
        return GeminiLLMPort(
            api_key=settings.google_api_key,
            default_model=settings.llm_default_model,
            analyze_turn_model=settings.llm_analyze_turn_model,
            timeout_seconds=settings.llm_timeout_seconds,
            context_cache_enabled=settings.llm_context_cache_enabled,
            context_cache_ttl_seconds=settings.llm_context_cache_ttl_seconds,
            context_cache_min_stable_chars=settings.llm_context_cache_min_stable_chars,
        )
    raise ValueError(f"Unsupported AI_LLM_PROVIDER={settings.llm_provider!r}")
