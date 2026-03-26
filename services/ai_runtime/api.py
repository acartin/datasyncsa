"""FastAPI router for the AI runtime."""

from __future__ import annotations

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
NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


class HealthResponse(BaseModel):
    status: str
    service: str


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
