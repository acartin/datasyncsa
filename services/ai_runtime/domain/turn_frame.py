"""Universal turn-frame building blocks.

The TurnFrame is built deterministically by ``prepare_synthesis`` and consumed
read-only by ``synthesize``.  It is **frozen** — no downstream node may modify
it once written to the graph state.

This module owns the vertical-agnostic pieces only.  Realtor extensions
(``PropertySummary``, ``RealtorTurnFrame`` and ``seen_properties`` helpers)
live in ``services/ai_runtime/graph/realtor/turn_frame``.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Framing enum
# ---------------------------------------------------------------------------

FramingKind = Literal[
    "exact_match",
    "relaxed_match",
    "no_results",
    "property_focus",
    "property_comparison",
    "property_selection",
    "result_set_detail",
    "recommendation",
    "financial_calc",
    "faq_answer",
    "appointment_progress",
    "lead_capture",
    "memory_answer",
    "off_domain",
    "small_talk",
    "policy_block",
    "reject_previous",
    "confirm_continuation",
    "generic_response",
]


class SearchContext(BaseModel):
    """Deterministic summary of the search executed in the current turn."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    requested_filters: dict[str, Any] = Field(default_factory=dict)
    effective_filters: dict[str, Any] = Field(default_factory=dict)
    relaxation_applied: bool = False
    result_count: int = 0
    attempt_count: int = 0


class LeadCaptureContext(BaseModel):
    """Pre-resolved lead-capture decision — the synthesizer never decides
    *what* to ask, only *how* to phrase the surrounding text."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    should_ask: bool = False
    field_to_ask: str | None = None
    question_to_ask: str | None = None
    lead_name_known: bool = False
    has_valid_contact: bool = False
    appointment_pending_contact: bool = False


class LeadSnapshot(BaseModel):
    """Compact lead state exposed directly to the synthesizer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    nombre: str | None = None
    email: str | None = None
    telefono: str | None = None
    presupuesto: float | None = None
    aprobacion: str | None = None
    preferencias: list[str] = Field(default_factory=list)
    fecha_preferida: str | None = None
    tipo_cita: str | None = None
    appointment_intent: str | None = None
    newly_captured_fields: list[str] = Field(default_factory=list)


class BaseTurnFrame(BaseModel):
    """Frame shared by every vertical."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # --- Turn identity ---
    framing: FramingKind
    dialogue_act: str
    user_message: str
    last_assistant_message: str | None = None

    # --- Primary narrative ---
    primary_narrative: str | None = None
    secondary_narratives: list[str] = Field(default_factory=list)

    # --- Conversational context (compact) ---
    recent_messages: list[dict[str, Any]] = Field(default_factory=list)
    memory_summary: dict[str, Any] = Field(default_factory=dict)

    # --- Lead capture (pre-resolved) ---
    lead_capture: LeadCaptureContext = Field(default_factory=LeadCaptureContext)
    lead_snapshot: LeadSnapshot = Field(default_factory=LeadSnapshot)

    # --- RAG ---
    rag_chunks: list[dict[str, Any]] = Field(default_factory=list)

    # --- Appointment ---
    appointment_summary: dict[str, Any] | None = None

    # --- Tenant capabilities ---
    capabilities: list[str] = Field(default_factory=list)
