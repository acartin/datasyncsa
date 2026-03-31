"""Helpers for structured pending decisions that block the next step."""

from __future__ import annotations

from services.ai_runtime.domain.contracts import PendingDecision


def render_pending_decision_question(decision: PendingDecision | None) -> str | None:
    """Return a deterministic question for known pending decision kinds."""

    if decision is None:
        return None

    kind = str(decision.kind or "").strip().lower()
    if kind == "search_relaxation_choice":
        return "Todavia no encontre coincidencias exactas. Que queres flexibilizar: precio, zona o algun otro criterio?"
    if kind == "search_relaxation_price_value":
        return "Claro. Hasta que monto te sirve subir el presupuesto?"
    if kind == "search_relaxation_zone_value":
        return "Claro. Que zona te gustaria explorar?"
    if kind == "search_relaxation_custom_value":
        return "Decime que criterio queres flexibilizar y lo revisamos."

    question = str(decision.question or "").strip()
    if question:
        return question
    reason = str(decision.reason or "").strip()
    if reason:
        return reason
    return None
