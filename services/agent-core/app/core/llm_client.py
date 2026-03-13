from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

from app.core.config import settings


_LLM_MAX_RETRIES = 3
_LLM_CALL_TIMEOUT_SECONDS = 8


def extract_json(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}
    text = value.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"```json(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        block = match.group(1).strip()
        try:
            return json.loads(block)
        except Exception:
            return {}
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1 and last > first:
        block = text[first : last + 1]
        try:
            return json.loads(block)
        except Exception:
            return {}
    return {}


class LLMService:
    async def generate_text(
        self,
        *,
        system_instruction: str,
        contents: List[str],
        temperature: float = 0.1,
        max_output_tokens: Optional[int] = None,
        response_mime_type: Optional[str] = None,
    ) -> str:
        if not settings.google_api_key:
            raise RuntimeError("GOOGLE_API_KEY_NOT_CONFIGURED")

        llm = genai.Client(api_key=settings.google_api_key)
        max_tokens = max_output_tokens or max(256, settings.llm_max_output_tokens)
        last_exc: Exception | None = None

        for attempt in range(_LLM_MAX_RETRIES):
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        llm.models.generate_content,
                        model=settings.llm_model,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            temperature=temperature,
                            max_output_tokens=max_tokens,
                            response_mime_type=response_mime_type,
                        ),
                    ),
                    timeout=max(1, _LLM_CALL_TIMEOUT_SECONDS),
                )
                text = str(response.text or "").strip()
                if not text:
                    raise ValueError("Empty LLM response")
                return text
            except Exception as exc:
                last_exc = exc
                if attempt >= _LLM_MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(0.5 * (attempt + 1))

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
            response_mime_type="application/json",
        )
        normalized = extract_json(text)
        if not normalized:
            raise ValueError("INVALID_JSON_RESPONSE")
        return normalized


llm_service = LLMService()
