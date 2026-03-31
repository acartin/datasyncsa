from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

from app.core.config import settings


logger = logging.getLogger("inference-core-v3.llm")


_LLM_MAX_RETRIES = 3
_LLM_CALL_TIMEOUT_SECONDS = 8


def json_payload_to_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    if isinstance(value, str):
        text = value.strip()
        try:
            return json.loads(text)
        except Exception:
            pass
        for marker in ("```json", "```"):
            if marker in text:
                start = text.find(marker)
                end = text.rfind("```")
                if start < end:
                    block = text[start + len(marker) : end].strip()
                    try:
                        return json.loads(block)
                    except Exception:
                        break
    return {}


def _is_transient_llm_error(exc: Exception) -> bool:
    message = str(exc).upper()
    transient_markers = (
        "503",
        "UNAVAILABLE",
        "DEADLINE_EXCEEDED",
        "TIMEOUT",
        "TIMED OUT",
        "RESOURCE_EXHAUSTED",
        "INTERNAL",
    )
    return any(marker in message for marker in transient_markers)


class LLMService:
    async def generate_text(
        self,
        *,
        system_instruction: str,
        contents: List[str],
        temperature: float = 0.2,
        max_output_tokens: Optional[int] = None,
    ) -> str:
        if not settings.google_api_key:
            raise RuntimeError("GOOGLE_API_KEY_NOT_CONFIGURED")

        llm_client = genai.Client(api_key=settings.google_api_key)
        last_exc: Exception | None = None

        for attempt in range(_LLM_MAX_RETRIES):
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        llm_client.models.generate_content,
                        model=settings.llm_model,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            temperature=temperature,
                            max_output_tokens=max_output_tokens
                            or max(256, int(settings.llm_max_output_tokens or 512)),
                        ),
                    ),
                    timeout=max(1, int(settings.llm_timeout_secs or _LLM_CALL_TIMEOUT_SECONDS)),
                )
                text = str(response.text or "").strip()
                if text:
                    return text
                raise ValueError("Empty LLM response")
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt >= (_LLM_MAX_RETRIES - 1) or not _is_transient_llm_error(exc):
                    raise
                await asyncio.sleep(0.6 * (attempt + 1))

        if last_exc is not None:
            raise last_exc
        return ""

    async def generate_json(
        self,
        *,
        system_instruction: str,
        payload: Dict[str, Any],
        temperature: float = 0.1,
        max_output_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        text = await self.generate_text(
            system_instruction=system_instruction,
            contents=[json.dumps(payload, ensure_ascii=False)],
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        normalized = json_payload_to_dict(text)
        if normalized:
            return normalized
        raise ValueError("INVALID_JSON_RESPONSE")


llm_service = LLMService()
