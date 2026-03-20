from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from app.core.llm_trace_logger import llm_trace_logger  # noqa: E402


def test_llm_trace_logger_writes_one_jsonl_event_per_conversation(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "llm_trace_root", str(tmp_path))
    monkeypatch.setattr(settings, "llm_trace_enabled", True)

    asyncio.run(
        llm_trace_logger.log_event(
            trace_context={
                "conversation_id": "conv/trace:001",
                "component": "planner",
                "tenant_id": "tenant-123",
            },
            status="ok",
            request={"model": "gemini", "payload": {"query": "hola"}},
            response={"text": "{\"goal\":\"answer\"}", "json_valid": True},
        )
    )

    trace_files = list(tmp_path.glob("*.jsonl"))
    assert len(trace_files) == 1
    payload = json.loads(trace_files[0].read_text(encoding="utf-8").strip())
    assert payload["conversation_id"] == "conv/trace:001"
    assert payload["component"] == "planner"
    assert payload["status"] == "ok"
    assert payload["request"]["payload"]["query"] == "hola"
    assert payload["response"]["json_valid"] is True
