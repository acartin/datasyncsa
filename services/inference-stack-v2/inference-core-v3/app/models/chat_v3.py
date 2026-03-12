from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, AliasChoices, ConfigDict
from pydantic.alias_generators import to_camel


class ChatV3Request(BaseModel):
    """Request contract for /api/v3/chat."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )

    query_text: str = Field(..., min_length=1, max_length=4000)
    client_id: UUID = Field(
        ..., validation_alias=AliasChoices("client_id", "clientId", "cliente_id", "clienteId")
    )
    conversation_id: Optional[UUID] = Field(default=None)
    user_metadata: Dict[str, Any] = Field(default_factory=dict)
    filters: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("conversation_id", mode="before")
    @classmethod
    def _empty_str_to_none(cls, value):
        if not value or value == "":
            return None
        if isinstance(value, str):
            try:
                UUID(value)
            except ValueError:
                return None
        return value

    @field_validator("user_metadata", "filters", mode="before")
    @classmethod
    def _null_to_default_dict(cls, value):
        if value in (None, ""):
            return {}
        return value

    @field_validator("query_text", mode="after")
    @classmethod
    def _strip_query_text(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value


class ChatV3Response(BaseModel):
    """Canonical response contract for v3 runtime."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    answer: str
    conversation_id: UUID
    lead_id: Optional[UUID] = None
    intent: Optional[str] = None
    route_mode: Optional[str] = None
    active_subflow: Optional[str] = None
    vertical_slug: str = "generic"
    scoring_status: Optional[str] = None
    scoring_job_id: Optional[UUID] = None
    scoring_eta: Optional[str] = None
    components: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tracing: Optional[Dict[str, Any]] = None


class InternalMemoryResetRequest(BaseModel):
    client_id: UUID = Field(..., validation_alias=AliasChoices("client_id", "clientId"))
    reason: Optional[str] = None


class InternalMemoryResetResponse(BaseModel):
    status: str
    client_id: UUID
    conversations_deleted: int = 0
    cache_keys_deleted: int = 0


class CacheInvalidateResponse(BaseModel):
    status: str
    client_id: Optional[UUID] = None
    cache_keys_deleted: int = 0
