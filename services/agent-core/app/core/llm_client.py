from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

from app.core.config import settings
from app.core.llm_trace_logger import llm_trace_logger


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
    async def _call_model(
        self,
        *,
        system_instruction: str,
        contents: List[str],
        temperature: float,
        resolved_max_output_tokens: int,
        response_mime_type: Optional[str],
        request_trace: Dict[str, Any],
        trace_context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if not settings.google_api_key:
            raise RuntimeError("GOOGLE_API_KEY_NOT_CONFIGURED")

        llm = genai.Client(api_key=settings.google_api_key)
        last_exc: Exception | None = None

        for attempt in range(_LLM_MAX_RETRIES):
            started = time.perf_counter()
            attempt_payload = {
                **request_trace,
                "attempt": attempt + 1,
                "max_retries": _LLM_MAX_RETRIES,
            }
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        llm.models.generate_content,
                        model=settings.llm_model,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            temperature=temperature,
                            max_output_tokens=resolved_max_output_tokens,
                            response_mime_type=response_mime_type,
                        ),
                    ),
                    timeout=max(1, _LLM_CALL_TIMEOUT_SECONDS),
                )
                text = str(response.text or "").strip()
                if not text:
                    raise ValueError("Empty LLM response")
                return {
                    "text": text,
                    "attempt": attempt + 1,
                    "duration_ms": round((time.perf_counter() - started) * 1000.0, 3),
                }
            except Exception as exc:
                last_exc = exc
                await llm_trace_logger.log_event(
                    trace_context=trace_context,
                    status="error",
                    request=attempt_payload,
                    response={
                        "duration_ms": round((time.perf_counter() - started) * 1000.0, 3),
                    },
                    error=exc,
                )
                if attempt >= _LLM_MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(0.5 * (attempt + 1))

        if last_exc is not None:
            raise last_exc
        return {"text": "", "attempt": _LLM_MAX_RETRIES, "duration_ms": 0.0}

    async def generate_text(
        self,
        *,
        system_instruction: str,
        contents: List[str],
        temperature: float = 0.1,
        max_output_tokens: Optional[int] = None,
        response_mime_type: Optional[str] = None,
        trace_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        resolved_max_output_tokens = max_output_tokens or max(256, settings.llm_max_output_tokens)
        request_trace = {
            "provider": "google_genai",
            "model": settings.llm_model,
            "system_instruction": system_instruction,
            "contents": contents,
            "config": {
                "temperature": temperature,
                "max_output_tokens": resolved_max_output_tokens,
                "response_mime_type": response_mime_type,
                "timeout_secs": max(1, _LLM_CALL_TIMEOUT_SECONDS),
            },
        }
        result = await self._call_model(
            system_instruction=system_instruction,
            contents=contents,
            temperature=temperature,
            resolved_max_output_tokens=resolved_max_output_tokens,
            response_mime_type=response_mime_type,
            request_trace=request_trace,
            trace_context=trace_context,
        )
        await llm_trace_logger.log_event(
            trace_context=trace_context,
            status="ok",
            request={
                **request_trace,
                "attempt": result["attempt"],
                "max_retries": _LLM_MAX_RETRIES,
            },
            response={
                "text": result["text"],
                "duration_ms": result["duration_ms"],
                "response_chars": len(result["text"]),
            },
        )
        return str(result["text"])

    async def generate_json(
        self,
        *,
        system_instruction: str,
        payload: Dict[str, Any],
        temperature: float = 0.1,
        max_output_tokens: Optional[int] = None,
        trace_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        packed_payload = json.dumps(payload, ensure_ascii=False)
        resolved_max_output_tokens = max_output_tokens or max(256, settings.llm_max_output_tokens)
        request_trace = {
            "provider": "google_genai",
            "model": settings.llm_model,
            "system_instruction": system_instruction,
            "contents": [packed_payload],
            "payload": payload,
            "config": {
                "temperature": temperature,
                "max_output_tokens": resolved_max_output_tokens,
                "response_mime_type": "application/json",
                "timeout_secs": max(1, _LLM_CALL_TIMEOUT_SECONDS),
            },
        }
        result = await self._call_model(
            system_instruction=system_instruction,
            contents=[packed_payload],
            temperature=temperature,
            resolved_max_output_tokens=resolved_max_output_tokens,
            response_mime_type="application/json",
            request_trace=request_trace,
            trace_context=trace_context,
        )
        text = str(result["text"])
        normalized = extract_json(text)
        response_trace = {
            "text": text,
            "json": normalized or None,
            "json_valid": bool(normalized),
            "duration_ms": result["duration_ms"],
            "response_chars": len(text),
        }
        if not normalized:
            error = ValueError("INVALID_JSON_RESPONSE")
            await llm_trace_logger.log_event(
                trace_context=trace_context,
                status="error",
                request={
                    **request_trace,
                    "attempt": result["attempt"],
                    "max_retries": _LLM_MAX_RETRIES,
                },
                response=response_trace,
                error=error,
            )
            raise ValueError("INVALID_JSON_RESPONSE")
        await llm_trace_logger.log_event(
            trace_context=trace_context,
            status="ok",
            request={
                **request_trace,
                "attempt": result["attempt"],
                "max_retries": _LLM_MAX_RETRIES,
            },
            response=response_trace,
        )
        return normalized


llm_service = LLMService()
