"""Deterministic realtor property-card CTA selection."""

from __future__ import annotations

from typing import Any

from services.ai_runtime.domain.state import has_valid_lead_contact
from services.ai_runtime.graph.realtor.cta_matrix_loader import load_realtor_card_cta_matrix
from services.ai_runtime.graph.realtor.state.model import RealtorGraphState


def _interest_band(intention_score: float) -> str:
    if intention_score >= 7:
        return "high"
    if intention_score >= 4:
        return "medium"
    return "low"


def _contact_status(graph_state: RealtorGraphState) -> str:
    extracted = graph_state.lead_advisor.lead_extracted
    if has_valid_lead_contact(extracted):
        return "valid"
    if any(
        str(value or "").strip()
        for value in (extracted.nombre, extracted.email, extracted.telefono)
    ):
        return "partial"
    return "none"


def _budget_status(graph_state: RealtorGraphState) -> str:
    return "known" if graph_state.lead_advisor.lead_extracted.presupuesto is not None else "unknown"


def _approval_status(graph_state: RealtorGraphState) -> str:
    return "known" if str(graph_state.lead_advisor.lead_extracted.aprobacion or "").strip() else "unknown"


def _appointment_status(graph_state: RealtorGraphState) -> str:
    value = str(graph_state.lead_advisor.lead_extracted.appointment_intent or "").strip().lower()
    if value in {"positive", "negative", "uncertain"}:
        return value
    return "unknown"


def _browsing_stage(graph_state: RealtorGraphState) -> str:
    seen_count = len(graph_state.seen_properties or {})
    return "exploring" if seen_count > 1 else "fresh"


def build_realtor_cta_context(graph_state: RealtorGraphState) -> dict[str, Any]:
    return {
        "interest_band": _interest_band(float(graph_state.lead_advisor.lead_scores.intencion or 0.0)),
        "contact_status": _contact_status(graph_state),
        "budget_status": _budget_status(graph_state),
        "approval_status": _approval_status(graph_state),
        "appointment_status": _appointment_status(graph_state),
        "browsing_stage": _browsing_stage(graph_state),
    }


def _matches_rule(context: dict[str, Any], rule: dict[str, Any]) -> bool:
    for key, allowed in rule.items():
        if not isinstance(allowed, list):
            allowed = [allowed]
        if context.get(key) not in allowed:
            return False
    return True


def select_realtor_card_ctas(
    graph_state: RealtorGraphState,
    *,
    limit: int | None = None,
) -> list[dict[str, str]]:
    ui_payload = graph_state.ui_payload or {}
    if not (isinstance(ui_payload, dict) and ui_payload.get("property_cards")):
        return []

    matrix = load_realtor_card_cta_matrix()
    context = build_realtor_cta_context(graph_state)
    catalog = matrix.get("catalog") or {}
    max_visible = int(matrix.get("max_visible") or 3)
    if limit is not None:
        max_visible = min(max_visible, int(limit))

    selected_ids = list(matrix.get("fallback") or [])
    for row in matrix.get("rows") or []:
        when = row.get("when") or {}
        if _matches_rule(context, when):
            selected_ids = list(row.get("show") or selected_ids)
            break

    selected: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for action_id in selected_ids:
        normalized = str(action_id or "").strip()
        if not normalized or normalized in seen_ids:
            continue
        payload = catalog.get(normalized)
        if not isinstance(payload, dict):
            continue
        label = str(payload.get("label") or "").strip()
        if not label:
            continue
        selected.append(
            {
                "id": normalized,
                "label": label,
                "user_text": str(payload.get("user_text") or label).strip(),
            }
        )
        seen_ids.add(normalized)
        if len(selected) >= max_visible:
            break
    return selected
