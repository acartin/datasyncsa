"""Lead advisor node."""

from __future__ import annotations

from typing import Any

from services.ai_runtime.domain.contracts import LeadExtracted, LeadScores
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import BaseGraphState, LeadAdvisorState


async def lead_advisor(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    """Evaluate the next best lead question with deterministic business rules."""

    graph_state = BaseGraphState.model_validate(state)
    cached = await deps.lead_store.get_lead_state(graph_state.client_id, graph_state.session_id)
    current_scores = LeadScores.model_validate((cached or {}).get("lead_scores", graph_state.lead_advisor.lead_scores.model_dump()))
    current_extracted = LeadExtracted.model_validate(
        (cached or {}).get("lead_extracted", graph_state.lead_advisor.lead_extracted.model_dump())
    )

    user_reacted_to_property = bool(getattr(graph_state, "last_mentioned", None) or graph_state.resolved_references)
    asked_for_quote = any(item.type == "calcular" for item in graph_state.completed_intents)
    appointment_intent = current_extracted.appointment_intent
    lead_complete = bool(
        current_extracted.nombre
        and (current_extracted.telefono or current_extracted.email)
        and current_extracted.presupuesto
        and appointment_intent == "positive"
    )

    field_to_ask = None
    if graph_state.current_turn >= 2 and current_scores.apertura >= 5 and not current_extracted.nombre:
        field_to_ask = "nombre"
    elif current_scores.match >= 5 and not current_extracted.presupuesto and user_reacted_to_property:
        field_to_ask = "presupuesto"
    elif asked_for_quote and not current_extracted.aprobacion:
        field_to_ask = "aprobacion"
    elif current_scores.urgencia >= 6 and not current_extracted.fecha_preferida:
        field_to_ask = "fecha"
    elif current_scores.intencion >= 7 and not (current_extracted.telefono or current_extracted.email):
        field_to_ask = "contacto"
    elif lead_complete and appointment_intent != "positive":
        field_to_ask = "cita"

    advisor_state = LeadAdvisorState(
        lead_scores=current_scores,
        lead_extracted=current_extracted,
        lead_completo=lead_complete,
        should_ask=field_to_ask is not None,
        field_to_ask=field_to_ask,
    )
    return {"lead_advisor": advisor_state.model_dump(mode="json")}
