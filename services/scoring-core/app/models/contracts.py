from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class ScoreConversationRequest(BaseModel):
    """
    Minimal cross-service contract from agent-core to scoring-core.
    """

    client_id: UUID = Field(
        ...,
        validation_alias=AliasChoices("client_id", "clientId"),
    )
    lead_id: UUID = Field(
        ...,
        validation_alias=AliasChoices("lead_id", "leadId"),
    )
    conversation_id: UUID = Field(
        ...,
        validation_alias=AliasChoices("conversation_id", "conversationId"),
    )
    channel: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class EnqueueScoreJobResponse(BaseModel):
    id: UUID
    status: str
    scheduled_for: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class ScoringJobResponse(BaseModel):
    id: UUID
    lead_id: UUID
    conversation_id: UUID
    client_id: UUID
    status: str
    attempts: int
    max_attempts: int
    expected_lead_messages: Optional[int] = None
    scheduled_for: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    last_error_code: Optional[str] = None
    last_error_message: Optional[str] = None
    fallback_used: Optional[bool] = None
    json_valid: Optional[bool] = None
    latency_ms: Optional[int] = None
    response_chars: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class ScoringOpsSummaryResponse(BaseModel):
    window_minutes: int
    queue_depth: int
    queue_depth_due: int
    running: int
    completed_count: int
    degraded_count: int
    failed_count: int
    timeout_count: int
    stale_count: int
    p95_wait_seconds: Optional[float] = None
    p95_end_to_end_seconds: Optional[float] = None
    completion_rate_per_min: float
    failure_rate_pct: float
    degraded_rate_pct: float

    model_config = ConfigDict(extra="ignore")


class ScoreItemV2(BaseModel):
    criterion_key: str
    score: float
    band_key: Optional[str] = None
    explanation: Optional[str] = None
    extracted_data: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ScorecardV2(BaseModel):
    score_total: float
    priority_label: Optional[str] = None
    reasoning: Optional[str] = None
    model_version: int
    prompt_version: int
    score_items: List[ScoreItemV2] = Field(default_factory=list)


class ScorecardResponse(BaseModel):
    id: UUID
    lead_id: UUID
    conversation_id: Optional[UUID] = None
    model_id: UUID
    model_version: int
    prompt_version: int
    prompt_id: Optional[UUID] = None
    score_total: float
    priority_label: Optional[str] = None
    reasoning: Optional[str] = None
    extraction_result: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    score_items: List[Dict[str, Any]] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")


class ActiveModelResponse(BaseModel):
    model_id: UUID
    model_version: int
    prompt_version: int
    criteria: List[Dict[str, Any]] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")


class InternalMemoryResetRequest(BaseModel):
    client_id: UUID = Field(
        ...,
        validation_alias=AliasChoices("client_id", "clientId"),
    )
    reason: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class InternalMemoryResetResponse(BaseModel):
    status: str = "ok"
    client_id: UUID
    conversations_deleted: int
    cache_keys_deleted: int = 0


class CacheInvalidateResponse(BaseModel):
    status: str
    message: str
