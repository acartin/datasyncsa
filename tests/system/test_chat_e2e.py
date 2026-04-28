#!/usr/bin/env python3
"""
Smoke E2E del camino conversacional activo.

Valida:
1) chat-web-renderer responde por /chat
2) la respuesta incluye texto + scoringJobId
3) scoring-core completa el job asincrono

Uso:
  python3 tests/system/test_chat_e2e.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

import requests


CHAT_WEB_RENDERER_URL = os.getenv("CHAT_WEB_RENDERER_URL", "http://localhost:8086").rstrip("/")
SCORING_CORE_API = os.getenv("SCORING_CORE_API", "http://localhost:8097").rstrip("/")
SCORING_API_PREFIX = os.getenv("SCORING_API_PREFIX", "/api/v1")
CLIENT_ID = os.getenv("CLIENT_ID", "64f357a0-98eb-44f1-9f41-6e615ed26180")
CHANNEL = os.getenv("CHANNEL", "web_html")
CHANNEL_USER_ID = os.getenv("CHANNEL_USER_ID", f"system-e2e-{int(time.time())}")
MESSAGE_TEXT = os.getenv("MESSAGE_TEXT", "Hola, quiero opciones de propiedades de 2 habitaciones.")
E2E_WAIT_SECONDS = int(os.getenv("E2E_WAIT_SECONDS", "60"))


def _candidate_scoring_bases() -> list[str]:
    port = os.getenv("SCORING_CORE_PORT", "8097").strip() or "8097"
    candidates = [
        SCORING_CORE_API.rstrip("/"),
        f"http://localhost:{port}",
        f"http://127.0.0.1:{port}",
    ]
    seen: set[str] = set()
    ordered: list[str] = []
    for item in candidates:
        if item and item not in seen:
            ordered.append(item)
            seen.add(item)
    return ordered


def _scoring_base_url() -> str:
    prefix = SCORING_API_PREFIX.strip()
    if not prefix.startswith("/"):
        prefix = f"/{prefix}"
    normalized_prefix = prefix.rstrip("/")
    for raw_base in _candidate_scoring_bases():
        candidate = raw_base if raw_base.endswith(normalized_prefix) else f"{raw_base}{normalized_prefix}"
        try:
            response = requests.get(f"{candidate}/health", timeout=5)
            if response.status_code != 200:
                continue
            payload = response.json()
            if str(payload.get("service") or "").strip().lower() == "scoring-core":
                return candidate
        except Exception:
            continue
    raw_base = _candidate_scoring_bases()[0]
    if raw_base.endswith(normalized_prefix):
        return raw_base
    return f"{raw_base}{normalized_prefix}"


def _extract_chat_text(response_json: dict[str, Any]) -> str:
    for comp in response_json.get("components") or []:
        if str(comp.get("type") or "").strip().lower() == "chat":
            return str(comp.get("text") or "").strip()
    return ""


def wait_for_scorecard(job_id: str, timeout_seconds: int) -> dict[str, Any] | None:
    deadline = time.time() + timeout_seconds
    endpoint = f"{_scoring_base_url()}/scoring/jobs/{job_id}"
    last_payload: dict[str, Any] | None = None

    while time.time() < deadline:
        try:
            resp = requests.get(endpoint, timeout=10)
            if resp.status_code == 200:
                payload = resp.json()
                last_payload = payload
                status = str(payload.get("status") or "").strip().lower()
                if status == "completed":
                    return payload
                if status in {"failed", "cancelled", "degraded"}:
                    return payload
        except Exception:
            pass
        time.sleep(1.5)
    return last_payload


def test_chat_flow() -> bool:
    print("Test End-to-End: Chat activo + scoring-core")
    print("=" * 60)

    health = requests.get(f"{CHAT_WEB_RENDERER_URL}/health", timeout=10)
    print("Health status:", health.status_code)
    if health.status_code != 200:
        print("ERROR health:", health.text[:500])
        return False

    payload = {
        "client_id": CLIENT_ID,
        "channel": CHANNEL,
        "channel_user_id": CHANNEL_USER_ID,
        "message_text": MESSAGE_TEXT,
        "metadata": {
            "debug_trace_id": "test-chat-e2e",
            "source": "tests/system/test_chat_e2e.py",
        },
    }

    print("\nEndpoint:", f"{CHAT_WEB_RENDERER_URL}/chat")
    print("Payload:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    try:
        response = requests.post(
            f"{CHAT_WEB_RENDERER_URL}/chat",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=45,
        )
    except Exception as exc:
        print("\nERROR:", str(exc))
        return False

    print("\nStatus Code:", response.status_code)
    if response.status_code != 200:
        print("ERROR:", response.text[:800])
        return False

    data = response.json()
    meta = data.get("meta") or {}
    chat_text = _extract_chat_text(data)
    scoring_job_id = str(meta.get("scoringJobId") or "").strip()

    print("\nRespuesta chat OK")
    print("session_id:", data.get("session_id"))
    print("conversation_id:", meta.get("conversation_id"))
    print("scoringJobId:", scoring_job_id or "<empty>")
    print("answer:", chat_text[:180])

    if not chat_text:
        print("ERROR: respuesta sin texto")
        return False
    if not scoring_job_id:
        print("ERROR: falta scoringJobId en meta")
        print(json.dumps(meta, indent=2, ensure_ascii=False))
        return False

    print(f"\nEsperando scorecard/job hasta {E2E_WAIT_SECONDS}s...")
    scorecard = wait_for_scorecard(scoring_job_id, E2E_WAIT_SECONDS)
    if not scorecard:
        print("ERROR: no se obtuvo job de scoring en el tiempo esperado")
        return False

    final_status = str(scorecard.get("status") or "").strip().lower()
    print("Job status:", final_status or "<empty>")
    if final_status != "completed":
        print(json.dumps(scorecard, indent=2, ensure_ascii=False))
        return False

    return True


if __name__ == "__main__":
    success = test_chat_flow()
    sys.exit(0 if success else 1)
