from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


CHANNEL_LITERAL = Literal["web_html", "meta_whatsapp", "meta_ig", "api"]


class InternalChatRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    client_id: UUID = Field(
        validation_alias=AliasChoices("client_id", "clientId", "client_id")
    )
    channel: CHANNEL_LITERAL = Field(
        default="web_html",
        validation_alias=AliasChoices("channel", "Channel")
    )
    channel_user_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("channel_user_id", "channelUserId", "channel_user_id")
    )
    auth_user_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("auth_user_id", "authUserId", "auth_user_id")
    )
    message_text: str = Field(
        min_length=1,
        max_length=4000,
        validation_alias=AliasChoices("message_text", "messageText", "message_text", "text")
    )
    conversation_id: Optional[UUID] = Field(
        default=None,
        validation_alias=AliasChoices("conversation_id", "conversationId", "conversation_id")
    )
    session_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("session_id", "sessionId", "session_id")
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("metadata", "Metadata")
    )
    brand_project: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("brand_project", "brandProject", "brand_project")
    )


class InternalChatResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    conversation_id: UUID = Field(
        validation_alias=AliasChoices("conversation_id", "conversationId", "conversation_id")
    )
    canonical_answer: str = Field(
        validation_alias=AliasChoices("canonical_answer", "canonicalAnswer", "canonical_answer", "answer")
    )
    intent: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("intent", "Intent")
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("payload", "Payload")
    )
    debug: Optional[dict[str, Any]] = Field(
        default=None,
        validation_alias=AliasChoices("debug", "Debug")
    )
    meta: Optional[dict[str, Any]] = Field(
        default=None,
        validation_alias=AliasChoices("meta", "Meta")
    )
