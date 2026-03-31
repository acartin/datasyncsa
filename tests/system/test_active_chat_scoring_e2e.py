#!/usr/bin/env python3
"""
Smoke E2E del camino activo:
chat-web-renderer -> ai-runtime -> scoring-core

Valida:
1) chat responde (HTTP 200 + contenido)
2) response incluye scoringJobId
3) job en scoring-core llega a estado completed

Uso:
  python3 tests/system/test_active_chat_scoring_e2e.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

import requests


CHAT_WEB_RENDERER_URL = os.getenv("CHAT_WEB_RENDERER_URL", "http://localhost:8086").rstrip("/")
SCORING_CORE_API = os.getenv("SCORING_CORE_API", "http://localhost:8097")
SCORING_API_PREFIX = os.getenv("SCORING_API_PREFIX", "/api/v1")
CLIENT_ID = os.getenv("CLIENT_ID", "64f357a0-98eb-44f1-9f41-6e615ed26180")
CHANNEL = os.getenv("CHANNEL", "web_html")
CHANNEL_USER_ID = os.getenv("CHANNEL_USER_ID", f"smoke-e2e-user-{int(time.time())}")
MESSAGE_TEXT = os.getenv("MESSAGE_TEXT", "Hola, busco propiedades en Heredia")
SCORING_WAIT_SECONDS = int(os.getenv("SCORING_WAIT_SECONDS", "120"))
SCORING_POLL_SECONDS = float(os.getenv("SCORING_POLL_SECONDS", "2.0"))
INTERNAL_API_TOKEN = (os.getenv("INTERNAL_API_TOKEN") or "").strip()
RESET_BEFORE_CHAT = (os.getenv("RESET_BEFORE_CHAT", "true").strip().lower() == "true")


def _scoring_base_url() -> str:
    prefix = SCORING_API_PREFIX.strip()
    if not prefix.startswith("/"):
        prefix = f"/{prefix}"
    return f"{SCORING_CORE_API.rstrip('/')}{prefix.rstrip('/')}"


def _extract_chat_text(response_json: dict[str, Any]) -> str:
    for comp in response_json.get("components") or []:
        if str(comp.get("type", "")).strip().lower() == "chat":
            return str(comp.get("text") or "").strip()
    return ""


def _reset_memory_best_effort() -> None:
    if not RESET_BEFORE_CHAT:
        return
    if not INTERNAL_API_TOKEN:
        print("WARN reset skipped: INTERNAL_API_TOKEN no definido")
        return

    headers = {"X-Internal-Token": INTERNAL_API_TOKEN}
    payload = {"client_id": CLIENT_ID, "reason": "smoke_active_path"}
    try:
        response = requests.post(
            f"{CHAT_WEB_RENDERER_URL}/internal/memory/reset",
            json=payload,
            headers=headers,
            timeout=20,
        )
        print("POST /internal/memory/reset:", response.status_code)
        if response.status_code != 200:
            print("WARN reset failed:", response.text[:500])
    except Exception as exc:
        print("WARN reset exception:", str(exc))


def _poll_scoring_job(job_id: str) -> dict[str, Any] | None:
    deadline = time.time() + SCORING_WAIT_SECONDS
    endpoint = f"{_scoring_base_url()}/scoring/jobs/{job_id}"
    last_payload: dict[str, Any] | None = None

    while time.time() < deadline:
        try:
            response = requests.get(endpoint, timeout=10)
            if response.status_code == 200:
                data = response.json()
                last_payload = data
                status = str(data.get("status") or "").strip().lower()
                print("scoring status:", status)
                if status == "completed":
                    return data
                if status in {"failed", "cancelled", "degraded"}:
                    return data
            elif response.status_code not in {404}:
                print("WARN scoring poll HTTP", response.status_code, response.text[:300])
        except Exception as exc:
            print("WARN scoring poll exception:", str(exc))
        time.sleep(max(0.5, SCORING_POLL_SECONDS))

    return last_payload


def main() -> int:
    print("Smoke E2E activo chat-web-renderer -> ai-runtime -> scoring-core")
    print("=" * 72)
    print("CHAT_WEB_RENDERER_URL:", CHAT_WEB_RENDERER_URL)
    print("SCORING_BASE_URL:", _scoring_base_url())
    print("CLIENT_ID:", CLIENT_ID)

    _reset_memory_best_effort()

    payload = {
        "client_id": CLIENT_ID,
        "channel": CHANNEL,
        "channel_user_id": CHANNEL_USER_ID,
        "message_text": MESSAGE_TEXT,
        "metadata": {
            "debug_trace_id": "smoke-active-path",
            "source": "tests/system/test_active_chat_scoring_e2e.py",
        },
    }
    print("\nPOST /chat payload:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    try:
        chat_resp = requests.post(
            f"{CHAT_WEB_RENDERER_URL}/chat",
            json=payload,
            timeout=45,
            headers={"Content-Type": "application/json"},
        )
    except Exception as exc:
        print("FAIL chat exception:", str(exc))
        return 1

    print("\nPOST /chat status:", chat_resp.status_code)
    if chat_resp.status_code != 200:
        print("FAIL chat error body:", chat_resp.text[:800])
        return 1

    data = chat_resp.json()
    chat_text = _extract_chat_text(data)
    meta = data.get("meta") or {}
    scoring_job_id = str(meta.get("scoringJobId") or "").strip()
    scoring_status = str(meta.get("scoringStatus") or "").strip().lower()

    print("session_id:", data.get("session_id"))
    print("chat_text_chars:", len(chat_text))
    print("scoringStatus:", scoring_status or "<empty>")
    print("scoringJobId:", scoring_job_id or "<empty>")

    if not chat_text:
        print("FAIL chat response sin texto")
        return 1
    if not scoring_job_id:
        print("FAIL chat response sin scoringJobId")
        print("meta:", json.dumps(meta, indent=2, ensure_ascii=False))
        return 1

    print(f"\nPolling scoring job hasta {SCORING_WAIT_SECONDS}s...")
    job_payload = _poll_scoring_job(scoring_job_id)
    if not job_payload:
        print("FAIL scoring job no disponible en el tiempo esperado")
        return 1

    final_status = str(job_payload.get("status") or "").strip().lower()
    print("scoring final status:", final_status or "<empty>")
    if final_status != "completed":
        print("FAIL scoring no completado")
        print(json.dumps(job_payload, indent=2, ensure_ascii=False))
        return 1

    print("\nRESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
