from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.core.config import settings
from app.graph.workflow import agent_graph
from app.models.contracts import AnswerEnvelope, GoalType
from app.repositories.persistence import runtime_repository

RouteMode = Literal["answer_only", "tool_required", "clarify", "reject"]
ScoringStatus = Literal["disabled", "pending", "error"]


class ChatRequest(BaseModel):
    clientId: str = Field(min_length=1)
    queryText: str = Field(min_length=1)
    conversationId: str | None = None
    channel: Literal["web_html", "meta_whatsapp", "meta_ig", "api"] = "web_html"
    filters: dict[str, Any] = Field(default_factory=dict)
    userMetadata: dict[str, Any] = Field(default_factory=dict)
    leadId: str | None = None
    vertical: str | None = None
    history: list[dict[str, Any]] = Field(default_factory=list)
    conversation_state: dict[str, Any] = Field(default_factory=dict)
    tenant_tone: str | None = None

    model_config = ConfigDict(extra="allow")


class ChatResponse(BaseModel):
    answer: str
    conversationId: str
    leadId: str | None = None
    intent: str | None = None
    routeMode: RouteMode
    activeSubflow: str
    components: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    scoringStatus: ScoringStatus = "disabled"
    scoringJobId: str | None = None
    scoringEta: str | None = None


class InternalMemoryResetRequest(BaseModel):
    client_id: str = Field(
        min_length=1,
        validation_alias=AliasChoices("client_id", "clientId"),
    )
    reason: str | None = None


class InternalMemoryResetResponse(BaseModel):
    status: str = "ok"
    client_id: str
    conversations_deleted: int
    cache_keys_deleted: int = 0


router = APIRouter(prefix=settings.api_prefix, tags=["chat"])


def _serialize_card(card: Any) -> dict[str, Any]:
    if hasattr(card, "model_dump"):
        return card.model_dump(mode="json")
    if isinstance(card, dict):
        return card
    return {"value": str(card)}


def _normalize_scoring_status(value: Any) -> ScoringStatus:
    normalized = str(value or "disabled").strip().lower()
    if normalized in {"pending", "queued", "processing"}:
        return "pending"
    if normalized == "error":
        return "error"
    return "disabled"


def _route_mode(*, goal: GoalType, error_code: str | None, components: list[dict[str, Any]]) -> RouteMode:
    if error_code:
        return "reject"
    if goal == GoalType.clarify:
        return "clarify"
    if components:
        return "tool_required"
    return "answer_only"


def _active_subflow(*, goal: GoalType, vertical: str) -> str:
    if goal == GoalType.clarify:
        return "clarify"
    if goal == GoalType.rag:
        return "generic_rag"
    if goal == GoalType.workflow:
        return "workflow"
    if goal == GoalType.realtor_search:
        return "realtor_search"
    if goal == GoalType.realtor_refine:
        return "realtor_refine"
    if vertical == "realtor":
        return "realtor_answer"
    return "generic_answer"


def _assert_internal_token(request: Request) -> None:
    expected = (settings.internal_api_token or "").strip()
    if not expected:
        return
    provided = (request.headers.get("X-Internal-Token") or "").strip()
    if provided != expected:
        raise HTTPException(status_code=401, detail="Invalid internal token")


async def _invoke_graph(payload: ChatRequest) -> tuple[AnswerEnvelope, dict[str, Any]]:
    graph_input = payload.model_dump(exclude_none=True)
    graph_input.setdefault("tenant_id", payload.clientId)
    graph_input.setdefault("client_id", payload.clientId)
    graph_input.setdefault("text", payload.queryText)
    graph_input.setdefault("queryText", payload.queryText)

    try:
        result_state = await agent_graph.ainvoke({"raw_input": graph_input})
    except Exception as exc:
        raise HTTPException(status_code=500, detail="agent_core_runtime_error") from exc

    envelope_raw = result_state.get("answer_envelope")
    if isinstance(envelope_raw, AnswerEnvelope):
        envelope = envelope_raw
    elif isinstance(envelope_raw, dict):
        envelope = AnswerEnvelope.model_validate(envelope_raw)
    else:
        raise HTTPException(status_code=500, detail="agent_core_invalid_envelope")

    return envelope, result_state


@router.get("/health")
async def health_v1() -> dict[str, str]:
    return {"status": "ok", "service": "agent-core"}


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    envelope, result_state = await _invoke_graph(payload)

    components = [_serialize_card(card) for card in envelope.cards]
    error_code = (
        str(result_state.get("error_code")).strip()
        if result_state.get("error_code")
        else None
    )
    vertical = str(
        (result_state.get("normalized_input") or {}).get("vertical")
        or payload.vertical
        or "generic"
    ).strip().lower()

    metadata: dict[str, Any] = {
        "goal": envelope.goal.value,
        "confidence": envelope.confidence,
        "evidenceIds": envelope.evidence_ids,
    }
    if envelope.clarify_message:
        metadata["clarifyMessage"] = envelope.clarify_message
    if error_code:
        metadata["errorCode"] = error_code
    if result_state.get("node_timings_ms"):
        metadata["nodeTimingsMs"] = result_state.get("node_timings_ms")

    return ChatResponse(
        answer=envelope.text,
        conversationId=envelope.conversation_id,
        leadId=(
            str(result_state.get("lead_id"))
            if result_state.get("lead_id")
            else payload.leadId
        ),
        intent=envelope.goal.value,
        routeMode=_route_mode(goal=envelope.goal, error_code=error_code, components=components),
        activeSubflow=_active_subflow(goal=envelope.goal, vertical=vertical),
        components=components,
        metadata=metadata,
        scoringStatus=_normalize_scoring_status(result_state.get("scoring_status")),
        scoringJobId=result_state.get("scoring_job_id"),
        scoringEta=None,
    )


@router.post("/internal/memory/reset", response_model=InternalMemoryResetResponse)
async def internal_memory_reset(
    payload: InternalMemoryResetRequest,
    request: Request,
) -> InternalMemoryResetResponse:
    _assert_internal_token(request)
    conversations_deleted = await runtime_repository.reset_client_memory(payload.client_id)
    return InternalMemoryResetResponse(
        client_id=payload.client_id,
        conversations_deleted=conversations_deleted,
        cache_keys_deleted=0,
    )
