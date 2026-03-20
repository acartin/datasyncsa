from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import settings

logger = logging.getLogger("scoring-core.llm-trace")

_SAFE_TOKEN_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _json_safe(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _safe_filename_token(value: str) -> str:
    normalized = _SAFE_TOKEN_RE.sub("_", str(value or "").strip()).strip("._")
    return normalized or f"conversation_{uuid4().hex}"


class LLMTraceLogger:
    def __init__(self, *, service_name: str) -> None:
        self._service_name = service_name

    async def log_event(
        self,
        *,
        trace_context: dict[str, Any] | None,
        status: str,
        request: dict[str, Any],
        response: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        if not settings.llm_trace_enabled:
            return

        context = dict(trace_context or {})
        conversation_id = str(context.pop("conversation_id", "") or "").strip()
        if not conversation_id:
            return

        component = str(context.pop("component", "") or "llm").strip() or "llm"
        operation = str(context.pop("operation", "") or "generate_content").strip() or "generate_content"
        path = Path(settings.llm_trace_root)
        path.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "event_type": "llm_exchange",
            "call_id": uuid4().hex,
            "service": self._service_name,
            "component": component,
            "operation": operation,
            "conversation_id": conversation_id,
            "status": str(status or "unknown"),
            "request": _json_safe(request),
            "response": _json_safe(response) if response is not None else None,
            "error": (
                {
                    "type": error.__class__.__name__,
                    "message": str(error),
                }
                if error is not None
                else None
            ),
        }
        if context:
            payload["context"] = _json_safe(context)

        try:
            await asyncio.to_thread(
                self._append_line,
                path / f"{_safe_filename_token(conversation_id)}.jsonl",
                json.dumps(payload, ensure_ascii=False, default=str),
            )
        except Exception as exc:
            logger.warning("llm_trace_write_failed conversation=%s: %s", conversation_id, exc)

    @staticmethod
    def _append_line(path: Path, line: str) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"{line}\n")


llm_trace_logger = LLMTraceLogger(service_name="scoring-core")
