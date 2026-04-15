"""Realtor graph state definition.

Owns the realtor-specific state model (``RealtorGraphState``) and its nested
filters (``SearchFilters``, ``FinancialContext``).  These types must not be
imported by ``services/ai_runtime/domain`` nor by other verticals' code.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from services.ai_runtime.domain.state import BaseGraphState
from services.ai_runtime.graph.realtor.contracts import Property


class SearchFilters(BaseModel):
    ubicacion: str | None = None
    habitaciones: int | None = None
    banos: float | None = None
    garage: int | None = None
    precio_max: float | None = None
    precio_min: float | None = None
    currency: str | None = None
    provincia: str | None = None
    amenidades: list[str] = Field(default_factory=list)
    tipo: str | None = None
    operacion: str | None = None


class FinancialContext(BaseModel):
    property_id: str | None = None
    price: float | None = None
    currency: str | None = None
    prima: float | None = None
    plazo: int | None = None
    banco: str | None = None
    resultado: dict[str, Any] | None = None


class RealtorGraphState(BaseGraphState):
    """State for the full realtor graph."""

    search_filters: SearchFilters = Field(default_factory=SearchFilters)
    effective_search_filters: SearchFilters | None = None
    inventory: list[Property] = Field(default_factory=list)
    last_search_results: list[Property] = Field(default_factory=list)
    last_mentioned: Property | None = None
    active_comparison: list[str] = Field(default_factory=list)
    focus_scope: str | None = None
    search_attempts: int = 0
    cards_shown: list[str] = Field(default_factory=list)
    cards_mode: str | None = None
    render_mode: str | None = None
    ui_payload: dict[str, Any] | None = None
    financial_context: FinancialContext = Field(default_factory=FinancialContext)
    seen_properties: dict[str, Any] = Field(default_factory=dict)


__all__ = ["RealtorGraphState", "SearchFilters", "FinancialContext"]
