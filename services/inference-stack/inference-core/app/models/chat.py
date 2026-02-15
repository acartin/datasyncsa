from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic.alias_generators import to_camel
import logging

logger = logging.getLogger("inference-core.models")

class ChatMessageRequest(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra='ignore' # Important to ignore leadId if not needed
    )

    query_text: str = Field(..., min_length=1, max_length=4000, description="The user's question or message")
    client_id: UUID = Field(..., description="The tenant/client identifier")
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
                # Try to validate if it's a valid UUID string
                UUID(v)
            except ValueError:
                # Ignore invalid values and treat the message as a new conversation
                logger.warning("Invalid UUID received for conversation_id; ignoring value")
                return None
        return v

class SourceDocument(BaseModel):
    content_id: str
    title: Optional[str] = None
    body_content: str
    score: float
    metadata: Dict[str, Any]

class ChatMessageResponse(BaseModel):
    answer: str = Field(..., description="The AI generated response")
    sources: List[SourceDocument] = Field(default_factory=list, description="The sources used to generate the answer")
    conversation_id: UUID = Field(..., description="The conversation ID for this session")

class LeadScoringResult(BaseModel):
    score_engagement: int = Field(0, description="Interest level (-20 to 30)")
    score_finance: int = Field(0, description="Financial capacity (-10 to 30)")
    score_timeline: int = Field(0, description="Buying timeframe (0 to 20)")
    score_match: int = Field(0, description="Product fit (0 to 15)")
    score_info: int = Field(0, description="Profile quality (-3 to 5)")
    reasoning: str = Field(..., description="Short explanation of scores")
    
    # New Automatic Extraction Fields
    extracted_name: Optional[str] = Field(None, description="Extracted full name")
    extracted_email: Optional[str] = Field(None, description="Extracted email address")
    extracted_phone: Optional[str] = Field(None, description="Extracted phone number")
    extracted_income: Optional[float] = Field(None, description="Detected declared income")
    extracted_debts: Optional[float] = Field(None, description="Detected current debts")
    extracted_currency_id: Optional[str] = Field(None, description="Currency code (e.g., USD, CRC)")
    extracted_contact_pref_id: Optional[str] = Field(None, description="Contact preference UUID")


class InternalMemoryResetRequest(BaseModel):
    client_id: UUID
    reason: Optional[str] = None


class InternalMemoryResetResponse(BaseModel):
    status: str
    client_id: UUID
    conversations_deleted: int
