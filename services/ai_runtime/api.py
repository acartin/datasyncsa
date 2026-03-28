"""FastAPI router for the AI runtime."""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel

from services.ai_runtime.domain.contracts import (
    ChatRequest,
    ChatResponse,
    InternalMemoryResetRequest,
    InternalMemoryResetResponse,
    InternalSessionResetRequest,
    InternalSessionResetResponse,
)
from services.ai_runtime.runtime.bootstrap import runtime

router = APIRouter()
TURN_TRACE_WEB_ROOT = Path(__file__).resolve().parent / "web" / "turn_trace"
CONVERSATION_SUITE_WEB_ROOT = Path(__file__).resolve().parent / "web" / "conversation_suites"
GENERATED_CONVERSATION_SUITE_DIR = Path(
    os.getenv("AI_GENERATED_CONVERSATION_SUITES_DIR", "/app/log/generated-conversation-suites")
)
NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


class HealthResponse(BaseModel):
    status: str
    service: str


def _load_json_file(path: Path) -> dict[str, object] | list[object] | None:
    if not path.exists() or not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _infer_suite_type(*, bundle_id: str, meta: dict[str, object], report: dict[str, object]) -> str:
    explicit = str(meta.get("suite_type") or report.get("suite_type") or "").strip().lower()
    if explicit in {"generated", "regression", "manual"}:
        return explicit

    candidates = [
        bundle_id,
        str(meta.get("suite_id") or ""),
        str(report.get("suite_id") or ""),
    ]
    for candidate in candidates:
        normalized = candidate.strip().lower()
        if "regression" in normalized:
            return "regression"
        if "manual" in normalized:
            return "manual"
        if "generated" in normalized:
            return "generated"
    return "manual"


def _list_generated_suite_bundles() -> list[dict[str, object]]:
    if not GENERATED_CONVERSATION_SUITE_DIR.exists():
        return []
    bundles: list[dict[str, object]] = []
    for entry in GENERATED_CONVERSATION_SUITE_DIR.iterdir():
        if not entry.is_dir():
            continue
        meta = _load_json_file(entry / "meta.json") or {}
        report = _load_json_file(entry / "report.json") or {}
        summary = (report.get("summary") or {}) if isinstance(report, dict) else {}
        suite_type = _infer_suite_type(
            bundle_id=entry.name,
            meta=meta if isinstance(meta, dict) else {},
            report=report if isinstance(report, dict) else {},
        )
        bundles.append(
            {
                "bundle_id": entry.name,
                "suite_id": meta.get("suite_id") or entry.name,
                "suite_type": suite_type,
                "generated_at": meta.get("generated_at"),
                "conversations_total": summary.get("conversations_total"),
                "turns_total": summary.get("turns_total"),
                "turns_failed": summary.get("turns_failed"),
            }
        )
    bundles.sort(key=lambda item: str(item.get("generated_at") or ""), reverse=True)
    return bundles


def _load_generated_suite_bundle(bundle_id: str) -> dict[str, object]:
    bundle_dir = (GENERATED_CONVERSATION_SUITE_DIR / bundle_id).resolve()
    if not str(bundle_dir).startswith(str(GENERATED_CONVERSATION_SUITE_DIR.resolve())) or not bundle_dir.exists():
        raise HTTPException(status_code=404, detail="Bundle not found")
    suite = _load_json_file(bundle_dir / "suite.json")
    report = _load_json_file(bundle_dir / "report.json")
    meta = _load_json_file(bundle_dir / "meta.json")
    if suite is None and report is None:
        raise HTTPException(status_code=404, detail="Bundle is empty")
    bundle_meta = dict(meta or {}) if isinstance(meta, dict) else {}
    bundle_report = dict(report or {}) if isinstance(report, dict) else {}
    suite_type = _infer_suite_type(
        bundle_id=bundle_id,
        meta=bundle_meta,
        report=bundle_report,
    )
    bundle_meta.setdefault("suite_type", suite_type)
    bundle_report.setdefault("suite_type", suite_type)
    return {
        "bundle_id": bundle_id,
        "meta": bundle_meta,
        "suite": suite,
        "report": bundle_report,
    }


@router.get("/health", response_model=HealthResponse)
async def healthcheck() -> HealthResponse:
    return HealthResponse(status="ok", service="datasyncsa-ai-runtime")


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    return await runtime.handle_turn(request)


def _assert_internal_token(request: Request) -> None:
    expected = (os.getenv("INTERNAL_API_TOKEN") or "").strip()
    if not expected:
        return
    provided = (request.headers.get("X-Internal-Token") or "").strip()
    if provided != expected:
        raise HTTPException(status_code=401, detail="Invalid internal token")


@router.post("/internal/memory/reset", response_model=InternalMemoryResetResponse)
async def internal_memory_reset(
    payload: InternalMemoryResetRequest,
    request: Request,
) -> InternalMemoryResetResponse:
    _assert_internal_token(request)
    return await runtime.reset_client_memory(payload.client_id)


@router.post("/internal/session/reset", response_model=InternalSessionResetResponse)
async def internal_session_reset(
    payload: InternalSessionResetRequest,
    request: Request,
) -> InternalSessionResetResponse:
    _assert_internal_token(request)
    return await runtime.reset_session_memory(payload.client_id, payload.session_id)


@router.get("/debug/turn-trace")
async def turn_trace_console_redirect(request: Request) -> RedirectResponse:
    return RedirectResponse(url=f"{request.url.path}/")


@router.get("/debug/turn-trace/")
async def turn_trace_console() -> FileResponse:
    return FileResponse(TURN_TRACE_WEB_ROOT / "index.html", headers=NO_CACHE_HEADERS)


@router.get("/debug/turn-trace/assets/{asset_path:path}")
async def turn_trace_asset(asset_path: str) -> FileResponse:
    resolved = (TURN_TRACE_WEB_ROOT / asset_path).resolve()
    if not str(resolved).startswith(str(TURN_TRACE_WEB_ROOT.resolve())) or not resolved.exists():
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(resolved, headers=NO_CACHE_HEADERS)


@router.get("/debug/turn-traces/clients/{client_id}/sessions")
async def debug_turn_trace_sessions(client_id: str, request: Request) -> dict[str, object]:
    return {
        "client_id": client_id,
        "sessions": runtime.dependencies.trace_store.list_sessions(client_id),
    }


@router.get("/debug/turn-traces/config")
async def debug_turn_trace_config() -> dict[str, object]:
    return {
        "trace_enabled": runtime.dependencies.trace_store.enabled,
        "token_required": False,
    }


@router.get("/debug/turn-traces/clients")
async def debug_turn_trace_clients(request: Request) -> dict[str, object]:
    return {
        "clients": runtime.dependencies.trace_store.list_clients(),
    }


@router.get("/debug/turn-traces/clients/{client_id}/sessions/{session_id}/turns")
async def debug_turn_trace_turns(client_id: str, session_id: str, request: Request) -> dict[str, object]:
    return {
        "client_id": client_id,
        "session_id": session_id,
        "turns": runtime.dependencies.trace_store.list_turns(client_id, session_id),
    }


@router.delete("/debug/turn-traces/clients/{client_id}/sessions/{session_id}")
async def debug_turn_trace_delete_session(
    client_id: str,
    session_id: str,
    request: Request,
) -> dict[str, object]:
    payload = runtime.dependencies.trace_store.delete_session(client_id, session_id)
    return {
        "client_id": client_id,
        "session_id": session_id,
        **payload,
    }


@router.get("/debug/turn-traces/clients/{client_id}/sessions/{session_id}/turns/{turn}")
async def debug_turn_trace_turn(
    client_id: str,
    session_id: str,
    turn: int,
    request: Request,
) -> dict[str, object]:
    payload = runtime.dependencies.trace_store.get_turn(client_id, session_id, turn)
    if payload is None:
        raise HTTPException(status_code=404, detail="Turn trace not found")
    return payload


@router.get("/debug/conversation-suites")
async def conversation_suites_console_redirect(request: Request) -> RedirectResponse:
    return RedirectResponse(url=f"{request.url.path}/")


@router.get("/debug/conversation-suites/")
async def conversation_suites_console() -> FileResponse:
    return FileResponse(CONVERSATION_SUITE_WEB_ROOT / "index.html", headers=NO_CACHE_HEADERS)


@router.get("/debug/conversation-suites/assets/{asset_path:path}")
async def conversation_suites_asset(asset_path: str) -> FileResponse:
    resolved = (CONVERSATION_SUITE_WEB_ROOT / asset_path).resolve()
    if not str(resolved).startswith(str(CONVERSATION_SUITE_WEB_ROOT.resolve())) or not resolved.exists():
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(resolved, headers=NO_CACHE_HEADERS)


@router.get("/debug/generated-conversation-suites/config")
async def debug_generated_conversation_suites_config() -> dict[str, object]:
    return {
        "root_dir": str(GENERATED_CONVERSATION_SUITE_DIR),
        "bundle_count": len(_list_generated_suite_bundles()),
    }


@router.get("/debug/generated-conversation-suites/bundles")
async def debug_generated_conversation_suites_bundles() -> dict[str, object]:
    return {
        "bundles": _list_generated_suite_bundles(),
    }


@router.get("/debug/generated-conversation-suites/bundles/{bundle_id}")
async def debug_generated_conversation_suites_bundle(bundle_id: str) -> dict[str, object]:
    return _load_generated_suite_bundle(bundle_id)
