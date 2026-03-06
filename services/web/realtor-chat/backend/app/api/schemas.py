from typing import Optional, Any, Dict, List
from uuid import UUID
from pydantic import BaseModel, Field


class ExternalChatRequest(BaseModel):
    client_id: UUID
    channel_user_id: str = Field(..., min_length=1, description="Identificador conversacional único del canal externo")
    message_text: str = Field(min_length=1, max_length=4000)
    auth_user_id: Optional[str] = Field(None, description="Identificador de autenticación interna (opcional para trazabilidad)")
    conversation_id: Optional[UUID] = None
    metadata: Optional[Dict[str, Any]] = None


class ExternalChatResponse(BaseModel):
    conversation_id: str
    answer: str
    intent: Optional[str] = None
    components: List[Dict[str, Any]] = Field(default_factory=list)
    meta: Dict[str, str] = Field(default_factory=dict)


class ExternalErrorResponse(BaseModel):
    error: str
    code: str
    details: Optional[Dict[str, Any]] = None


EXTERNAL_ERROR_CODES = {
    "VALIDATION_ERROR": "invalid_request",
    "NOT_FOUND": "conversation_not_found",
    "TIMEOUT": "service_timeout",
    "INTERNAL_ERROR": "internal_error",
    "UNAUTHORIZED": "unauthorized",
}
