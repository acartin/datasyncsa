"""Turn-level tracing utilities for ai-runtime graph execution."""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from shutil import rmtree
from threading import Lock
from typing import TYPE_CHECKING, Any, Awaitable, Callable
import json
import logging
import traceback

if TYPE_CHECKING:
    from services.ai_runtime.domain.ports import GraphDependencies, LLMPort


AsyncNodeFn = Callable[[dict[str, Any], "GraphDependencies"], Awaitable[dict[str, Any]]]
RouterFn = Callable[[dict[str, object]], str]
logger = logging.getLogger(__name__)

_ACTIVE_TRACE: ContextVar["TurnTraceContext | None"] = ContextVar("ai_runtime_turn_trace", default=None)
_LATEST_STATE: ContextVar[dict[str, Any] | None] = ContextVar("ai_runtime_turn_trace_latest_state", default=None)


@dataclass(slots=True)
class TurnTraceContext:
    trace_id: str
    client_id: str
    session_id: str
    conversation_id: str
    vertical: str
    flow: str
    turn: int
    user_id: str
    user_message: str
    started_at: str


def utc_now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def activate_turn_trace(context: TurnTraceContext) -> Token:
    return _ACTIVE_TRACE.set(context)


def deactivate_turn_trace(token: Token) -> None:
    _ACTIVE_TRACE.reset(token)


def get_active_turn_trace() -> TurnTraceContext | None:
    return _ACTIVE_TRACE.get()


def activate_latest_turn_state(state: dict[str, Any]) -> Token:
    return _LATEST_STATE.set(state)


def update_latest_turn_state(state: dict[str, Any]) -> None:
    _LATEST_STATE.set(state)


def deactivate_latest_turn_state(token: Token) -> None:
    _LATEST_STATE.reset(token)


def get_latest_turn_state() -> dict[str, Any] | None:
    return _LATEST_STATE.get()


def _safe_text(value: Any, max_length: int = 1200) -> str | None:
    if value is None:
        return None
    text = str(value)
    if len(text) <= max_length:
        return text
    return f"{text[:max_length]}... ({len(text) - max_length} chars more)"


def _safe_serialize(value: Any, *, depth: int = 0) -> Any:
    if depth > 5:
        return _safe_text(value, max_length=240)
    if hasattr(value, "model_dump"):
        return _safe_serialize(value.model_dump(mode="json"), depth=depth + 1)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        items = list(value.items())
        if len(items) > 25:
            items = items[:25]
        return {str(key): _safe_serialize(item, depth=depth + 1) for key, item in items}
    if isinstance(value, (list, tuple, set)):
        items = list(value)
        truncated = len(items) > 8
        payload = [_safe_serialize(item, depth=depth + 1) for item in items[:8]]
        if truncated:
            payload.append({"_truncated": len(items) - 8})
        return payload
    if isinstance(value, str):
        return _safe_text(value, max_length=20000)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _safe_text(repr(value), max_length=20000)


def _summarize_intent(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if not item:
        return None
    return {
        "id": _item_get(item, "id"),
        "type": _item_get(item, "type"),
        "status": _item_get(item, "status"),
        "priority": _item_get(item, "priority"),
        "depends_on": _item_get(item, "depends_on", []),
    }


def _item_get(item: Any, key: str, default: Any = None) -> Any:
    if item is None:
        return default
    if isinstance(item, dict):
        return item.get(key, default)
    if hasattr(item, "model_dump"):
        return item.model_dump(mode="json").get(key, default)
    return getattr(item, key, default)


def _summarize_messages(messages: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "role": _item_get(item, "role"),
            "content": _safe_text(_item_get(item, "content"), max_length=280),
        }
        for item in messages[-4:]
    ]


def summarize_state(state: dict[str, Any]) -> dict[str, Any]:
    turn_outputs = state.get("turn_outputs", [])
    summary = {
        "current_turn": state.get("current_turn"),
        "turn_analysis": _safe_serialize(state.get("turn_analysis")),
        "pending_clarification": state.get("pending_clarification"),
        "pending_decision": _safe_serialize(state.get("pending_decision")),
        "clarification_attempts": state.get("clarification_attempts"),
        "resolved_references": _safe_serialize(state.get("resolved_references", [])),
        "active_intent": _summarize_intent(state.get("active_intent")),
        "intent_queue": [_summarize_intent(item) for item in state.get("intent_queue", [])[:6]],
        "completed_intents": [_summarize_intent(item) for item in state.get("completed_intents", [])[-6:]],
        "turn_output_types": [_item_get(item, "type") for item in turn_outputs[-8:]],
        "messages_tail": _summarize_messages(state.get("messages", [])),
        "final_response": _safe_text(state.get("final_response"), max_length=320),
        "lead_advisor": {
            "capture_exposure_count": _item_get(state.get("lead_advisor"), "capture_exposure_count"),
            "should_ask": _item_get(state.get("lead_advisor"), "should_ask"),
            "field_to_ask": _item_get(state.get("lead_advisor"), "field_to_ask"),
            "question_to_ask": _safe_text(_item_get(state.get("lead_advisor"), "question_to_ask"), max_length=240),
            "lead_completo": _item_get(state.get("lead_advisor"), "lead_completo"),
            "target_criteria": _safe_serialize(_item_get(state.get("lead_advisor"), "target_criteria", [])),
            "criteria_scores": _safe_serialize(_item_get(state.get("lead_advisor"), "criteria_scores", {})),
            "criteria_reasons": _safe_serialize(_item_get(state.get("lead_advisor"), "criteria_reasons", {})),
            "scoring_reasoning": _safe_text(_item_get(state.get("lead_advisor"), "scoring_reasoning"), max_length=320),
            "scoring_confidence": _item_get(state.get("lead_advisor"), "scoring_confidence"),
            "scoring_last_updated_turn": _item_get(state.get("lead_advisor"), "scoring_last_updated_turn"),
            "required_fields": _safe_serialize(_item_get(state.get("lead_advisor"), "required_fields", [])),
            "completed_fields": _safe_serialize(_item_get(state.get("lead_advisor"), "completed_fields", [])),
            "lead_extracted": _safe_serialize(_item_get(state.get("lead_advisor"), "lead_extracted", {})),
        },
        "memory": {
            "entity_count": len(_item_get(state.get("memory"), "entities", []) or []),
            "entities_tail": _safe_serialize((_item_get(state.get("memory"), "entities", []) or [])[-6:]),
            "last_lookup": _safe_serialize(_item_get(state.get("memory"), "last_lookup", {})),
        },
        "cita": {
            "tipo": _item_get(state.get("cita"), "tipo"),
            "propiedad_id": _item_get(state.get("cita"), "propiedad_id"),
            "fecha": _item_get(state.get("cita"), "fecha"),
            "hora": _item_get(state.get("cita"), "hora"),
            "datos_completos": _item_get(state.get("cita"), "datos_completos"),
            "confirmada": _item_get(state.get("cita"), "confirmada"),
        },
        "escalacion": {
            "solicitada": _item_get(state.get("escalacion"), "solicitada"),
            "agente_asignado": _item_get(state.get("escalacion"), "agente_asignado"),
        },
    }
    if state.get("vertical") == "realtor" and "search_attempts" in state:
        summary["vertical_state"] = {
            "vertical": "realtor",
            "search_attempts": state.get("search_attempts"),
            "search_filters": _safe_serialize(state.get("search_filters", {})),
            "effective_search_filters": _safe_serialize(state.get("effective_search_filters")),
            "last_search_count": len(state.get("last_search_results", [])),
            "cards_mode": state.get("cards_mode"),
            "render_mode": state.get("render_mode"),
            "cards_shown": _safe_serialize(state.get("cards_shown", [])),
            "last_mentioned": _safe_serialize(_item_get(state.get("last_mentioned"), "id")),
            "active_comparison": _safe_serialize(state.get("active_comparison", [])),
        }
    return summary


class FileTurnTraceStore:
    """Simple JSON trace store for development-time graph inspection."""

    def __init__(self, root_dir: str | Path, *, enabled: bool = True):
        self.root_dir = Path(root_dir)
        self.enabled = enabled
        self._lock = Lock()
        if self.enabled:
            try:
                self.root_dir.mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                logger.warning("Turn trace disabled during init; unable to create %s: %s", self.root_dir, exc)
                self.enabled = False

    def _disable_due_to_io_failure(self, action: str, exc: Exception) -> None:
        logger.warning("Turn trace disabled after %s failure at %s: %s", action, self.root_dir, exc)
        self.enabled = False

    def _trace_path(self, context: TurnTraceContext) -> Path:
        return self.root_dir / context.client_id / context.session_id / f"turn-{context.turn:04d}-{context.trace_id}.json"

    def _load_document(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_document(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def start_turn(self, context: TurnTraceContext, *, request_metadata: dict[str, Any], state_summary: dict[str, Any]) -> None:
        if not self.enabled:
            return
        path = self._trace_path(context)
        document = {
            **asdict(context),
            "status": "running",
            "request_metadata": _safe_serialize(request_metadata),
            "initial_state_summary": state_summary,
            "events": [
                {
                    "seq": 1,
                    "timestamp": utc_now_iso(),
                    "kind": "turn_start",
                    "name": "handle_turn",
                    "payload": {
                        "user_message": context.user_message,
                        "state_summary": state_summary,
                    },
                }
            ],
        }
        try:
            with self._lock:
                self._write_document(path, document)
        except Exception as exc:
            self._disable_due_to_io_failure("start_turn", exc)

    def append_event(self, kind: str, name: str, payload: dict[str, Any] | None = None) -> None:
        if not self.enabled:
            return
        context = get_active_turn_trace()
        if not context:
            return
        path = self._trace_path(context)
        try:
            with self._lock:
                document = self._load_document(path)
                events = document.setdefault("events", [])
                events.append(
                    {
                        "seq": len(events) + 1,
                        "timestamp": utc_now_iso(),
                        "kind": kind,
                        "name": name,
                        "payload": _safe_serialize(payload or {}),
                    }
                )
                self._write_document(path, document)
        except Exception as exc:
            self._disable_due_to_io_failure("append_event", exc)

    def finish_turn(
        self,
        *,
        status: str,
        final_state_summary: dict[str, Any] | None = None,
        response_payload: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        if not self.enabled:
            return
        context = get_active_turn_trace()
        if not context:
            return
        path = self._trace_path(context)
        try:
            with self._lock:
                document = self._load_document(path)
                document["status"] = status
                document["ended_at"] = utc_now_iso()
                if final_state_summary is not None:
                    document["final_state_summary"] = final_state_summary
                if response_payload is not None:
                    document["response_payload"] = _safe_serialize(response_payload)
                if error:
                    document["error"] = error
                events = document.setdefault("events", [])
                events.append(
                    {
                        "seq": len(events) + 1,
                        "timestamp": utc_now_iso(),
                        "kind": "turn_end" if status == "completed" else "turn_error",
                        "name": "handle_turn",
                        "payload": {
                            "status": status,
                            "final_state_summary": final_state_summary,
                            "response_payload": _safe_serialize(response_payload),
                            "error": error,
                        },
                    }
                )
                self._write_document(path, document)
        except Exception as exc:
            self._disable_due_to_io_failure("finish_turn", exc)

    def list_sessions(self, client_id: str) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        client_dir = self.root_dir / client_id
        if not client_dir.exists():
            return []
        sessions: list[dict[str, Any]] = []
        for session_dir in sorted(client_dir.iterdir()):
            if not session_dir.is_dir():
                continue
            turn_files = sorted(session_dir.glob("turn-*.json"))
            if not turn_files:
                continue
            latest = json.loads(turn_files[-1].read_text(encoding="utf-8"))
            sessions.append(
                {
                    "client_id": client_id,
                    "session_id": session_dir.name,
                    "conversation_id": latest.get("conversation_id"),
                    "vertical": latest.get("vertical"),
                    "flow": latest.get("flow"),
                    "turn_count": len(turn_files),
                    "latest_turn": latest.get("turn"),
                    "latest_status": latest.get("status"),
                    "updated_at": latest.get("ended_at") or latest.get("started_at"),
                    "latest_user_message": latest.get("user_message"),
                }
            )
        sessions.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
        return sessions

    def list_clients(self) -> list[dict[str, Any]]:
        if not self.enabled or not self.root_dir.exists():
            return []
        clients: list[dict[str, Any]] = []
        for client_dir in sorted(self.root_dir.iterdir()):
            if not client_dir.is_dir():
                continue
            sessions = self.list_sessions(client_dir.name)
            if not sessions:
                continue
            latest_session = sessions[0]
            clients.append(
                {
                    "client_id": client_dir.name,
                    "session_count": len(sessions),
                    "latest_updated_at": latest_session.get("updated_at"),
                    "latest_status": latest_session.get("latest_status"),
                    "latest_user_message": latest_session.get("latest_user_message"),
                    "latest_session_id": latest_session.get("session_id"),
                    "vertical": latest_session.get("vertical"),
                    "flow": latest_session.get("flow"),
                }
            )
        clients.sort(key=lambda item: item.get("latest_updated_at") or "", reverse=True)
        return clients

    def list_turns(self, client_id: str, session_id: str) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        session_dir = self.root_dir / client_id / session_id
        if not session_dir.exists():
            return []
        turns: list[dict[str, Any]] = []
        for trace_file in sorted(session_dir.glob("turn-*.json")):
            payload = json.loads(trace_file.read_text(encoding="utf-8"))
            turns.append(
                {
                    "trace_id": payload.get("trace_id"),
                    "turn": payload.get("turn"),
                    "status": payload.get("status"),
                    "started_at": payload.get("started_at"),
                    "ended_at": payload.get("ended_at"),
                    "vertical": payload.get("vertical"),
                    "flow": payload.get("flow"),
                    "user_message": payload.get("user_message"),
                    "answer": ((payload.get("response_payload") or {}).get("answer")),
                    "event_count": len(payload.get("events", [])),
                }
            )
        return turns

    def delete_session(self, client_id: str, session_id: str) -> dict[str, Any]:
        if not self.enabled:
            return {"deleted": False, "deleted_turns": 0}
        session_dir = self.root_dir / client_id / session_id
        if not session_dir.exists():
            return {"deleted": False, "deleted_turns": 0}

        turn_files = sorted(session_dir.glob("turn-*.json"))
        deleted_turns = len(turn_files)
        with self._lock:
            rmtree(session_dir, ignore_errors=True)
            client_dir = self.root_dir / client_id
            if client_dir.exists() and not any(client_dir.iterdir()):
                client_dir.rmdir()
        return {"deleted": True, "deleted_turns": deleted_turns}

    def get_turn(self, client_id: str, session_id: str, turn: int) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        session_dir = self.root_dir / client_id / session_id
        if not session_dir.exists():
            return None
        matches = sorted(session_dir.glob(f"turn-{turn:04d}-*.json"))
        if not matches:
            return None
        return json.loads(matches[-1].read_text(encoding="utf-8"))


def build_traced_node(node_name: str, function: AsyncNodeFn, deps: "GraphDependencies") -> Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]:
    async def _inner(state: dict[str, Any]) -> dict[str, Any]:
        update_latest_turn_state(state)
        before_summary = summarize_state(state)
        deps.trace_store.append_event(
            "node_start",
            node_name,
            {
                "state_before": before_summary,
            },
        )
        started_at = datetime.now(tz=UTC)
        try:
            result = await function(state, deps)
        except Exception as exc:
            deps.trace_store.append_event(
                "node_error",
                node_name,
                {
                    "state_before": before_summary,
                    "error": repr(exc),
                    "traceback": traceback.format_exc(),
                },
            )
            raise
        projected_state = {**state, **(result or {})}
        update_latest_turn_state(projected_state)
        duration_ms = round((datetime.now(tz=UTC) - started_at).total_seconds() * 1000, 2)
        deps.trace_store.append_event(
            "node_end",
            node_name,
            {
                "duration_ms": duration_ms,
                "update_keys": sorted((result or {}).keys()),
                "state_updates": _safe_serialize(result or {}),
                "state_after": summarize_state(projected_state),
            },
        )
        return projected_state

    return _inner


def build_traced_router(router_name: str, function: RouterFn, deps: "GraphDependencies") -> RouterFn:
    def _inner(state: dict[str, object]) -> str:
        latest_state = get_latest_turn_state() or {}
        router_state = {**latest_state, **dict(state)}
        try:
            decision = function(router_state)
        except Exception as exc:
            deps.trace_store.append_event(
                "router_error",
                router_name,
                {
                    "error": repr(exc),
                    "traceback": traceback.format_exc(),
                    "state_summary": summarize_state(router_state),
                },
            )
            raise
        deps.trace_store.append_event(
            "router",
            router_name,
            {
                "decision": decision,
                "state_summary": summarize_state(router_state),
            },
        )
        return decision

    return _inner


class TracingLLMPort:
    """LLM proxy that records prompt/response events in the active turn trace."""

    def __init__(self, inner: "LLMPort", trace_store: FileTurnTraceStore):
        self.inner = inner
        self.trace_store = trace_store

    async def _record_call(self, method_name: str, prompt: Any, awaitable: Awaitable[Any]) -> Any:
        self.trace_store.append_event(
            "llm_start",
            method_name,
            {
                "prompt": prompt,
            },
        )
        started_at = datetime.now(tz=UTC)
        try:
            result = await awaitable
        except Exception as exc:
            self.trace_store.append_event(
                "llm_error",
                method_name,
                {
                    "prompt": prompt,
                    "error": repr(exc),
                    "traceback": traceback.format_exc(),
                },
            )
            raise
        duration_ms = round((datetime.now(tz=UTC) - started_at).total_seconds() * 1000, 2)
        self.trace_store.append_event(
            "llm_end",
            method_name,
            {
                "duration_ms": duration_ms,
                "prompt_cache": _safe_serialize(getattr(prompt, "cache_metadata", None)),
                "result": _safe_serialize(result),
            },
        )
        return result

    async def classify_reference(self, prompt: Any):
        return await self._record_call("classify_reference", prompt, self.inner.classify_reference(prompt))

    async def analyze_turn(self, prompt: Any):
        return await self._record_call("analyze_turn", prompt, self.inner.analyze_turn(prompt))

    async def detect_intents(self, prompt: Any):
        return await self._record_call("detect_intents", prompt, self.inner.detect_intents(prompt))

    async def evaluate_lazy_condition(self, prompt: Any):
        return await self._record_call("evaluate_lazy_condition", prompt, self.inner.evaluate_lazy_condition(prompt))

    async def extract_search_filters(self, prompt: Any):
        return await self._record_call("extract_search_filters", prompt, self.inner.extract_search_filters(prompt))

    async def extract_memory_entities(self, prompt: Any):
        return await self._record_call("extract_memory_entities", prompt, self.inner.extract_memory_entities(prompt))

    async def synthesize_response(self, prompt: Any):
        return await self._record_call("synthesize_response", prompt, self.inner.synthesize_response(prompt))

    async def redact_recommendation(self, prompt: Any):
        return await self._record_call("redact_recommendation", prompt, self.inner.redact_recommendation(prompt))

    async def translate_text_to_sql(self, prompt: Any):
        return await self._record_call("translate_text_to_sql", prompt, self.inner.translate_text_to_sql(prompt))

    async def extract_lead_fields(self, prompt: Any):
        return await self._record_call("extract_lead_fields", prompt, self.inner.extract_lead_fields(prompt))

    async def extract_appointment_fields(self, prompt: Any):
        return await self._record_call("extract_appointment_fields", prompt, self.inner.extract_appointment_fields(prompt))

    async def score_turn(self, prompt: Any):
        return await self._record_call("score_turn", prompt, self.inner.score_turn(prompt))
