from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class GoalType(str, Enum):
    answer = "answer"
    clarify = "clarify"
    rag = "rag"
    realtor_search = "realtor_search"
    realtor_refine = "realtor_refine"
    workflow = "workflow"


class ResponseMode(str, Enum):
    text_only = "text_only"
    text_plus_cards = "text_plus_cards"


class RealtorSearchSlots(BaseModel):
    city: Optional[str] = None
    property_type: Optional[Literal["apartment", "house", "land", "office"]] = None
    max_price: Optional[int] = None
    min_price: Optional[int] = None
    min_rooms: Optional[int] = None
    max_rooms: Optional[int] = None
    min_bathrooms: Optional[float] = None
    max_bathrooms: Optional[float] = None
    min_garage: Optional[int] = None
    max_garage: Optional[int] = None
    min_area_m2: Optional[float] = None
    max_area_m2: Optional[float] = None
    neighborhood: Optional[str] = None
    features: list[str] = Field(default_factory=list)


class RAGQuery(BaseModel):
    query_text: str
    top_k: int = Field(default=5, ge=1, le=20)
    filter_doc_type: Optional[str] = None


class WorkflowCall(BaseModel):
    workflow_name: str
    params: dict[str, Any] = Field(default_factory=dict)


class ToolName(str, Enum):
    rag = "rag"
    realtor_sql = "realtor_sql"
    workflow = "workflow"


class ToolCall(BaseModel):
    tool_name: ToolName
    rag: Optional[RAGQuery] = None
    realtor_slots: Optional[RealtorSearchSlots] = None
    workflow: Optional[WorkflowCall] = None

    @model_validator(mode="after")
    def check_payload(self) -> "ToolCall":
        if self.tool_name == ToolName.rag and not self.rag:
            raise ValueError("tool_name=rag requiere payload rag")
        if self.tool_name == ToolName.realtor_sql and not self.realtor_slots:
            raise ValueError("tool_name=realtor_sql requiere payload realtor_slots")
        if self.tool_name == ToolName.workflow and not self.workflow:
            raise ValueError("tool_name=workflow requiere payload workflow")
        return self


class RouterDecision(BaseModel):
    goal: GoalType
    confidence: float = Field(ge=0.0, le=1.0)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    missing_slots: list[str] = Field(default_factory=list)
    clarify_message: Optional[str] = None
    response_mode: ResponseMode = ResponseMode.text_only

    @model_validator(mode="after")
    def check_clarify(self) -> "RouterDecision":
        if self.goal == GoalType.clarify and not self.clarify_message:
            raise ValueError("goal=clarify requiere clarify_message")
        if self.goal == GoalType.clarify and self.tool_calls:
            raise ValueError("goal=clarify no debe tener tool_calls")
        return self


class GateRejectCode(str, Enum):
    schema_invalid = "schema_invalid"
    tenant_not_authorized = "tenant_not_authorized"
    tool_not_permitted = "tool_not_permitted"
    missing_required_slots = "missing_required_slots"
    confidence_too_low = "confidence_too_low"
    side_effects_blocked = "side_effects_blocked"
    budget_exceeded = "budget_exceeded"


class GateResult(BaseModel):
    accepted: bool
    reject_code: Optional[GateRejectCode] = None

    @model_validator(mode="after")
    def check_consistency(self) -> "GateResult":
        if not self.accepted and not self.reject_code:
            raise ValueError("reject requiere reject_code")
        if self.accepted and self.reject_code:
            raise ValueError("accept no debe tener reject_code")
        return self


class RAGChunk(BaseModel):
    chunk_id: str
    doc_id: str
    content: str
    score: float
    source_url: Optional[str] = None


class RAGResult(BaseModel):
    chunks: list[RAGChunk]
    query_used: str


class PropertyListing(BaseModel):
    listing_id: str
    title: str
    city: str
    neighborhood: Optional[str] = None
    price: int
    currency: str
    rooms: Optional[int] = None
    area_m2: Optional[float] = None
    property_type: str
    features: list[str] = Field(default_factory=list)
    image_urls: list[str] = Field(default_factory=list)
    listing_url: Optional[str] = None


class RealtorSQLResult(BaseModel):
    listings: list[PropertyListing]
    total_found: int
    sql_executed: str
    slots_used: RealtorSearchSlots


class WorkflowResult(BaseModel):
    workflow_name: str
    success: bool
    output: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    tool_name: ToolName
    status: Literal["ok", "error"] = "ok"
    error_code: str | None = None
    rag: Optional[RAGResult] = None
    realtor: Optional[RealtorSQLResult] = None
    workflow: Optional[WorkflowResult] = None
    error: Optional[str] = None


class PropertyCard(BaseModel):
    listing_id: str
    title: str
    price_display: str
    rooms: Optional[int] = None
    area_display: Optional[str] = None
    neighborhood: Optional[str] = None
    image_url: Optional[str] = None
    cta_url: Optional[str] = None
    card_type: Literal["property_card"] = "property_card"


class SearchSummaryCard(BaseModel):
    total_found: int
    city: str
    price_range: Optional[str] = None
    card_type: Literal["search_summary"] = "search_summary"


class RAGSourceCard(BaseModel):
    doc_id: str
    title: str
    excerpt: str
    source_url: Optional[str] = None
    card_type: Literal["rag_source"] = "rag_source"


CardModel = PropertyCard | SearchSummaryCard | RAGSourceCard


class SynthesizerInput(BaseModel):
    context_snapshot: dict[str, Any]
    tool_results: list[ToolResult]
    response_mode: ResponseMode
    tenant_tone: str


class SynthesizerOutput(BaseModel):
    text: str
    evidence_ids: list[str] = Field(default_factory=list)
    needs_cards: bool = False


class GuardrailRejectCode(str, Enum):
    no_evidence_cited = "no_evidence_cited"
    claim_without_source = "claim_without_source"
    schema_violation = "schema_violation"
    hallucinated_listing_id = "hallucinated_listing_id"


class GuardrailResult(BaseModel):
    accepted: bool
    reject_code: Optional[GuardrailRejectCode] = None

    @model_validator(mode="after")
    def check_consistency(self) -> "GuardrailResult":
        if not self.accepted and not self.reject_code:
            raise ValueError("reject requiere reject_code")
        return self


class AnswerEnvelope(BaseModel):
    conversation_id: str
    text: str
    cards: list[CardModel] = Field(default_factory=list)
    response_mode: ResponseMode
    evidence_ids: list[str] = Field(default_factory=list)
    goal: GoalType
    confidence: float = Field(ge=0.0, le=1.0)
    clarify_message: Optional[str] = None
