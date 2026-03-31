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

logger = logging.getLogger("agent-core.llm-trace")

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

    async def log_turn(
        self,
        *,
        trace_context: dict[str, Any] | None,
        query_text: str,
        state_json: dict[str, Any] | None,
        planner_output: dict[str, Any] | None,
        tool_results: list[Any] | None,
        synthesizer_output: dict[str, Any] | None,
        guardrail_result: dict[str, Any] | None,
        final_response_to_user: str | None,
        error: Exception | None = None,
    ) -> None:
        if not settings.llm_trace_enabled:
            return

        context = dict(trace_context or {})
        conversation_id = str(context.get("conversation_id", "") or "").strip()
        if not conversation_id:
            return

        accepted: Any = None
        reject_code: Any = None
        if isinstance(guardrail_result, dict):
            accepted = guardrail_result.get("accepted")
            reject_code = guardrail_result.get("reject_code")
        elif guardrail_result is not None:
            accepted = getattr(guardrail_result, "accepted", None)
            reject_code = getattr(guardrail_result, "reject_code", None)

        if error is not None or accepted is False:
            log_severity = "error"
        elif accepted is True and reject_code is not None:
            log_severity = "warning"
        else:
            log_severity = "ok"

        path = Path(settings.llm_trace_root)
        path.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "event_type": "turn_complete",
            "call_id": uuid4().hex,
            "service": self._service_name,
            "conversation_id": conversation_id,
            "trace_context": _json_safe(trace_context),
            "query_text": _json_safe(query_text),
            "state_json": _json_safe(state_json),
            "planner_output": _json_safe(planner_output),
            "tool_results": _json_safe(tool_results),
            "synthesizer_output": _json_safe(synthesizer_output),
            "guardrail_result": _json_safe(guardrail_result),
            "final_response_to_user": _json_safe(final_response_to_user),
            "error": (
                {
                    "type": error.__class__.__name__,
                    "message": str(error),
                }
                if error is not None
                else None
            ),
            "log_severity": log_severity,
        }

        try:
            await asyncio.to_thread(
                self._append_line,
                path / f"{_safe_filename_token(conversation_id)}.jsonl",
                json.dumps(payload, ensure_ascii=False, default=str),
            )
        except Exception as exc:
            logger.warning("llm_trace_turn_write_failed conversation=%s: %s", conversation_id, exc)

    @staticmethod
    def _append_line(path: Path, line: str) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"{line}\n")


llm_trace_logger = LLMTraceLogger(service_name="agent-core")
