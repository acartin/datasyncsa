from pydantic import BaseModel, Field, field_validator, ConfigDict, AliasChoices
from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic.alias_generators import to_camel


class ChatV2Request(BaseModel):
    """Request contract for /api/v2/chat"""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore"
    )
    
    query_text: str = Field(..., min_length=1, max_length=4000, description="The user's question or message")
    client_id: UUID = Field(
        ...,
        description="The tenant/client identifier",
        validation_alias=AliasChoices("client_id", "clientId", "cliente_id", "clienteId"),
    )
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Optional filters like category or source")
    conversation_id: Optional[UUID] = Field(None, description="Existing conversation ID if applicable")
    user_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context about the user")
    
    @field_validator('conversation_id', mode='before')
    @classmethod
    def empty_string_to_none(cls, v):
        if not v or v == "":
            return None
        if isinstance(v, str):
            try:
                UUID(v)
            except ValueError:
                return None
        return v


class ScoreItemV2(BaseModel):
    """Individual scoring criterion result"""
    criterion_key: str = Field(..., description="Criterion key (e.g., intent, urgency, data_quality)")
    score: float = Field(..., ge=0.0, description="Score for this criterion")
    band_key: Optional[str] = Field(None, description="Visual band key (e.g., low, medium, high)")
    explanation: Optional[str] = Field(None, description="Explanation for this specific score")
    extracted_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Extracted data specific to this criterion")


class ScorecardV2(BaseModel):
    """Complete scoring result for a lead"""
    score_total: float = Field(..., ge=0.0, description="Total normalized score")
    priority_label: Optional[str] = Field(None, description="Derived priority label")
    reasoning: Optional[str] = Field(None, description="Overall scoring reasoning")
    model_version: int = Field(..., gt=0, description="Model version used for scoring")
    prompt_version: int = Field(..., gt=0, description="Prompt version used for scoring")
    score_items: List[ScoreItemV2] = Field(default_factory=list, description="Individual criterion scores")


class ChatV2Response(BaseModel):
    """Response contract for /api/v2/chat"""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    answer: str = Field(..., description="The AI generated response")
    conversation_id: UUID = Field(..., description="The conversation ID for this session")
    lead_id: Optional[UUID] = Field(None, description="Lead ID if created/identified")
    scorecard_id: Optional[UUID] = Field(None, description="Scorecard ID if scoring was performed")
    scorecard: Optional[ScorecardV2] = Field(None, description="Scoring results if performed")
    scoring_status: Optional[str] = Field(None, description="Background scoring state (e.g., pending, disabled)")
    scoring_job_id: Optional[UUID] = Field(None, description="Background scoring job ID if available")
    scoring_eta: Optional[str] = Field(None, description="Estimated UTC completion timestamp for scoring")


class ScoringJobResponse(BaseModel):
    """Response contract for background scoring job status."""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

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


class ScoringOpsSummaryResponse(BaseModel):
    """Operational summary for async scoring pipeline."""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

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


class ScorecardResponse(BaseModel):
    """Response contract for scorecard endpoints"""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    id: UUID = Field(..., description="Scorecard ID")
    lead_id: UUID = Field(..., description="Lead ID")
    conversation_id: Optional[UUID] = Field(None, description="Conversation ID")
    model_id: UUID = Field(..., description="Model ID used for scoring")
    model_version: int = Field(..., description="Model version used")
    prompt_version: int = Field(..., description="Prompt version used")
    prompt_id: Optional[UUID] = Field(None, description="Prompt ID used")
    score_total: float = Field(..., description="Total score")
    priority_label: Optional[str] = Field(None, description="Priority label")
    reasoning: Optional[str] = Field(None, description="Reasoning text")
    extraction_result: Dict[str, Any] = Field(default_factory=dict, description="Accumulated extraction result")
    created_at: str = Field(..., description="Creation timestamp")
    score_items: List[Dict[str, Any]] = Field(default_factory=list, description="Score items with details")


class ActiveModelResponse(BaseModel):
    """Response for active model resolution"""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    model_id: UUID = Field(..., description="Model ID")
    model_version: int = Field(..., description="Model version")
    prompt_version: int = Field(..., description="Prompt version")
    criteria: List[Dict[str, Any]] = Field(default_factory=list, description="Active criteria with weights and bands")


class InternalMemoryResetRequest(BaseModel):
    client_id: UUID
    reason: Optional[str] = None


class InternalMemoryResetResponse(BaseModel):
    status: str
    client_id: UUID
    conversations_deleted: int
