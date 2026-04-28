"""Realtor-specific runtime policy hooks."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from services.ai_runtime.domain.contracts import PendingDecision, TurnAnalysis
from services.ai_runtime.domain.policies import QuickActionResolution, VerticalPolicy
from services.ai_runtime.domain.state import (
    BaseGraphState,
    LeadAdvisorState,
    SCORING_FIELD_ALIASES,
    build_lead_advisor_state,
)
from services.ai_runtime.graph.realtor.state.model import RealtorGraphState
from services.ai_runtime.graph.realtor.turn_policies import (
    REALTOR_INTERNAL_INTENTS,
    apply_realtor_turn_policies,
    build_realtor_fallback_intent_plan,
    derive_realtor_pending_decision,
    merge_realtor_filters,
)

_NEGATIVE_APPOINTMENT_PATTERNS = (
    re.compile(
        r"\bno\s+(?:quiero|deseo|necesito)\s+(?:agendar|agenda|coordinar|cita|visita|visitar)\b"
    ),
    re.compile(
        r"\b(?:por\s+ahora|todavia|aun)\s+no\s+(?:quiero\s+)?(?:agendar|coordinar|cita|visita|visitar)\b"
    ),
    re.compile(r"\bprefiero\s+no\s+(?:agendar|coordinar|cita|visita|visitar)\b"),
)
_CHANNEL_ALIASES = {
    "meta_whatsapp": "whatsapp",
    "whatsapp": "whatsapp",
    "meta_telegram": "telegram",
    "telegram": "telegram",
    "web_html": "webchat",
    "webchat": "webchat",
    "web": "webchat",
    "api": "webchat",
    "meta_ig": "instagram",
    "instagram": "instagram",
    "meta_messenger": "messenger",
    "messenger": "messenger",
}
_REALTOR_PROGRESSIVE_DEFAULTS = {
    "sale": [
        "presupuesto",
        "aprobacion",
        "fecha_preferida",
        "appointment_intent",
        "tipo_cita",
        "contacto",
        "email",
        "telefono",
        "preferencias",
        "nombre",
    ],
    "rent": [
        "fecha_preferida",
        "presupuesto",
        "appointment_intent",
        "tipo_cita",
        "contacto",
        "email",
        "telefono",
        "preferencias",
        "nombre",
    ],
    "default": [
        "appointment_intent",
        "tipo_cita",
        "contacto",
        "email",
        "telefono",
        "presupuesto",
        "aprobacion",
        "fecha_preferida",
        "preferencias",
        "nombre",
    ],
}


def _normalize_text(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    return "".join(char for char in raw if not unicodedata.combining(char))


def _normalize_field_key(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    return SCORING_FIELD_ALIASES.get(normalized, normalized)


def _latest_user_message(graph_state: BaseGraphState) -> str:
    for message in reversed(graph_state.messages):
        if str(getattr(message, "role", "")).strip().lower() != "user":
            continue
        content = str(getattr(message, "content", "")).strip()
        if content:
            return content
    return ""


def _has_explicit_negative_appointment_intent(message: str) -> bool:
    normalized = _normalize_text(message)
    if not normalized:
        return False
    return any(pattern.search(normalized) for pattern in _NEGATIVE_APPOINTMENT_PATTERNS)


def _coerce_realtor_state(graph_state: BaseGraphState) -> RealtorGraphState:
    if isinstance(graph_state, RealtorGraphState):
        return graph_state
    return RealtorGraphState.model_validate(graph_state.model_dump(mode="json"))


def _coerce_property_dict(raw_item: Any) -> dict[str, Any] | None:
    if raw_item is None:
        return None
    if isinstance(raw_item, dict):
        return raw_item
    model_dump = getattr(raw_item, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json")
    return None


def _property_snapshot(raw_item: Any) -> dict[str, Any] | None:
    item = _coerce_property_dict(raw_item)
    if not item:
        return None
    location = item.get("location") if isinstance(item.get("location"), dict) else {}
    features = item.get("features") if isinstance(item.get("features"), dict) else {}
    province = location.get("province")
    address = item.get("address")
    area = features.get("sqm_clean")
    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "price": item.get("price"),
        "currency": item.get("currency"),
        "province": province,
        "address": address,
        "bedrooms_clean": features.get("bedrooms_clean"),
        "bathrooms_clean": features.get("bathrooms_clean"),
        "garage_clean": features.get("garage_clean"),
        "sqm_clean": area,
        "area": area,
        "is_featured": bool(features.get("is_featured")),
    }


def _property_id(item: dict[str, Any] | None) -> str:
    if not item:
        return ""
    return str(item.get("id") or "").strip()


def _reference_candidates(realtor_state: RealtorGraphState) -> list[dict[str, Any]]:
    search_items = [
        snapshot
        for snapshot in (_property_snapshot(item) for item in realtor_state.last_search_results)
        if snapshot and _property_id(snapshot)
    ]
    if search_items:
        return search_items
    return [
        snapshot
        for snapshot in (_property_snapshot(item) for item in realtor_state.inventory)
        if snapshot and _property_id(snapshot)
    ]


def _visible_reference_items(realtor_state: RealtorGraphState) -> list[dict[str, Any]]:
    visible_ids = [str(item) for item in realtor_state.cards_shown if item]
    if not visible_ids:
        return []
    by_id: dict[str, dict[str, Any]] = {}
    for snapshot in [*_reference_candidates(realtor_state), *[
        snapshot
        for snapshot in (_property_snapshot(item) for item in realtor_state.inventory)
        if snapshot and _property_id(snapshot)
    ]]:
        by_id[_property_id(snapshot)] = snapshot
    return [by_id[item_id] for item_id in visible_ids if item_id in by_id]


def _single_intent(
    intent_type: str,
    *,
    condition: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    return [
        {
            "type": intent_type,
            "priority": 1,
            "depends_on": [],
            "condition": condition,
            "skip_if_failed": False,
        }
    ]


def _lead_advisor_with_positive_intent(graph_state: RealtorGraphState) -> dict[str, Any] | None:
    current_intent = str(graph_state.lead_advisor.lead_extracted.appointment_intent or "").strip().lower()
    if current_intent == "positive":
        return None
    updated_extracted = graph_state.lead_advisor.lead_extracted.model_copy(
        update={"appointment_intent": "positive"}
    )
    updated_advisor = graph_state.lead_advisor.model_copy(update={"lead_extracted": updated_extracted})
    return build_lead_advisor_state(
        graph_state.tenant_config,
        updated_advisor,
    ).model_dump(mode="json")


def _schedule_cita_update(
    graph_state: RealtorGraphState,
    references: list[dict[str, Any]],
) -> dict[str, Any] | None:
    property_id = next(
        (
            str(item.get("property_id") or "").strip()
            for item in references
            if item.get("kind") == "property" and str(item.get("property_id") or "").strip()
        ),
        "",
    )
    cita_updates: dict[str, Any] = {}
    if not str(graph_state.cita.tipo or "").strip():
        cita_updates["tipo"] = "visita"
    if property_id and not str(graph_state.cita.propiedad_id or "").strip():
        cita_updates["propiedad_id"] = property_id
    if not cita_updates:
        return None
    return graph_state.cita.model_copy(update=cita_updates).model_dump(mode="json")


def _property_references_from_quick_action(
    graph_state: RealtorGraphState,
    metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    candidate_ids: list[str] = []
    for key in ("target_property_id", "property_id"):
        value = str(metadata.get(key) or "").strip()
        if value:
            candidate_ids.append(value)

    focused = _property_id(_property_snapshot(graph_state.last_mentioned))
    if not candidate_ids and focused:
        candidate_ids.append(focused)

    if not candidate_ids:
        visible = _visible_reference_items(graph_state)
        if visible:
            candidate_ids.append(_property_id(visible[0]))

    if not candidate_ids:
        candidates = _reference_candidates(graph_state)
        if candidates:
            candidate_ids.append(_property_id(candidates[0]))

    references: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate_id in candidate_ids:
        normalized = str(candidate_id or "").strip()
        if not normalized or normalized in seen:
            continue
        references.append({"kind": "property", "property_id": normalized})
        seen.add(normalized)
    return references


def _normalize_channel(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    return _CHANNEL_ALIASES.get(raw, raw)


def _resolve_current_channel(graph_state: RealtorGraphState) -> str:
    for message in reversed(graph_state.messages):
        if str(getattr(message, "role", "")).strip().lower() != "user":
            continue
        metadata = getattr(message, "metadata", None)
        if not isinstance(metadata, dict):
            continue
        for key in ("channel", "platform"):
            normalized = _normalize_channel(metadata.get(key))
            if normalized:
                return normalized
    return "webchat"


def _resolve_realtor_journey(graph_state: RealtorGraphState) -> str:
    candidates = [
        str(graph_state.search_filters.operacion or ""),
        str(graph_state.effective_search_filters.operacion or "") if graph_state.effective_search_filters else "",
    ]
    for candidate in candidates:
        normalized = candidate.strip().lower()
        if not normalized:
            continue
        if any(token in normalized for token in ("alquiler", "renta", "rent", "arrendar")):
            return "rent"
        if any(token in normalized for token in ("venta", "comprar", "compra", "sale", "buy")):
            return "sale"
    return "default"


def _resolve_contact_preference(
    *,
    graph_state: RealtorGraphState,
    advisor_state: LeadAdvisorState,
) -> list[str]:
    profile = advisor_state.scoring_profile
    scoring_contract = dict(profile.scoring_contract or {}) if profile else {}
    progressive = scoring_contract.get("progressive_profile")
    contact_policy: Any = None
    if isinstance(progressive, dict):
        contact_policy = progressive.get("contact_policy")

    policy_name = "channel_aware"
    channel = _resolve_current_channel(graph_state)
    if isinstance(contact_policy, str):
        policy_name = contact_policy.strip().lower() or policy_name
    elif isinstance(contact_policy, dict):
        default_policy = str(contact_policy.get("default") or "").strip().lower()
        by_channel = contact_policy.get("by_channel")
        if not isinstance(by_channel, dict):
            by_channel = contact_policy.get("channels")
        channel_policy = ""
        if isinstance(by_channel, dict):
            channel_policy = str(by_channel.get(channel) or "").strip().lower()
            if channel_policy:
                policy_name = channel_policy
        if not channel_policy and default_policy:
            policy_name = default_policy

    if policy_name in {"phone_first", "prefer_phone", "whatsapp_first"}:
        return ["telefono", "email"]
    if policy_name in {"email_first", "prefer_email"}:
        return ["email", "telefono"]
    if channel in {"whatsapp", "telegram"}:
        return ["telefono", "email"]
    return ["email", "telefono"]


def _resolve_progressive_sequence(
    *,
    graph_state: RealtorGraphState,
    advisor_state: LeadAdvisorState,
) -> list[str]:
    journey = _resolve_realtor_journey(graph_state)
    profile = advisor_state.scoring_profile
    scoring_contract = dict(profile.scoring_contract or {}) if profile else {}
    progressive = scoring_contract.get("progressive_profile")
    journey_orders: dict[str, Any] = {}
    if isinstance(progressive, dict):
        raw_orders = progressive.get("journey_field_orders")
        if isinstance(raw_orders, dict):
            journey_orders = raw_orders

    sequence = journey_orders.get(journey)
    if not isinstance(sequence, list):
        sequence = journey_orders.get("default")
    if not isinstance(sequence, list):
        sequence = _REALTOR_PROGRESSIVE_DEFAULTS.get(journey, _REALTOR_PROGRESSIVE_DEFAULTS["default"])

    expanded: list[str] = []
    seen: set[str] = set()
    for item in sequence:
        if not isinstance(item, str):
            continue
        normalized = _normalize_field_key(item)
        if not normalized:
            continue
        if normalized == "contacto":
            for contact_field in _resolve_contact_preference(
                graph_state=graph_state,
                advisor_state=advisor_state,
            ):
                if contact_field not in seen:
                    expanded.append(contact_field)
                    seen.add(contact_field)
            continue
        if normalized in seen:
            continue
        expanded.append(normalized)
        seen.add(normalized)
    return expanded


def _search_preferences_from_filters(realtor_state: RealtorGraphState) -> list[str]:
    filters = realtor_state.search_filters
    preferences: list[str] = []

    def _add(value: str | None) -> None:
        text = str(value or "").strip()
        if text and text not in preferences:
            preferences.append(text)

    _add(filters.ubicacion)
    _add(filters.provincia)
    _add(filters.tipo)
    _add(filters.operacion)
    if filters.habitaciones:
        _add(f"{int(filters.habitaciones)} habitaciones")
    if filters.banos:
        _add(f"{filters.banos} banos")
    if filters.garage:
        _add(f"{int(filters.garage)} estacionamientos")
    for amenity in filters.amenidades or []:
        _add(str(amenity))
    return preferences


class RealtorPolicy(VerticalPolicy):
    def snapshot_search_context(
        self,
        graph_state: BaseGraphState,
    ) -> dict[str, Any]:
        return _coerce_realtor_state(graph_state).search_filters.model_dump(mode="json")

    def resolve_visible_reference_items(
        self,
        graph_state: BaseGraphState,
    ) -> list[dict[str, Any]]:
        return _visible_reference_items(_coerce_realtor_state(graph_state))

    def resolve_reference_candidates(
        self,
        graph_state: BaseGraphState,
    ) -> list[dict[str, Any]]:
        return _reference_candidates(_coerce_realtor_state(graph_state))

    def snapshot_focused_entity(
        self,
        graph_state: BaseGraphState,
    ) -> dict[str, Any] | None:
        return _property_snapshot(_coerce_realtor_state(graph_state).last_mentioned)

    def handle_quick_action(
        self,
        graph_state: BaseGraphState,
        metadata: dict[str, Any],
    ) -> QuickActionResolution | None:
        realtor_state = _coerce_realtor_state(graph_state)
        action_id = str(metadata.get("action_id") or "").strip().lower()
        if not action_id:
            return None

        default_reference = {"kind": "NONE", "confidence": 1.0}
        property_references = _property_references_from_quick_action(realtor_state, metadata)

        if action_id == "interest_yes":
            return QuickActionResolution(
                analysis=TurnAnalysis(
                    dialogue_act="select_result",
                    confidence=1.0,
                    reference=default_reference,
                    intent_plan=_single_intent("focus_property", condition={"requires_reference": "resolved_property"}),
                ),
                resolved_references=property_references,
                lead_advisor=_lead_advisor_with_positive_intent(realtor_state),
            )

        if action_id == "show_next":
            return QuickActionResolution(
                analysis=TurnAnalysis(
                    dialogue_act="confirm_previous",
                    confidence=1.0,
                    reference=default_reference,
                    intent_plan=_single_intent("show_result_cards", condition={"min_search_results": 1}),
                    reuse_current_filters=True,
                ),
            )

        if action_id == "schedule_visit":
            return QuickActionResolution(
                analysis=TurnAnalysis(
                    dialogue_act="schedule",
                    confidence=1.0,
                    reference=default_reference,
                    intent_plan=_single_intent("agendar"),
                ),
                resolved_references=property_references,
                lead_advisor=_lead_advisor_with_positive_intent(realtor_state),
                cita=_schedule_cita_update(realtor_state, property_references),
            )

        if action_id == "ask_financing":
            return QuickActionResolution(
                analysis=TurnAnalysis(
                    dialogue_act="calculate",
                    confidence=1.0,
                    reference=default_reference,
                    intent_plan=_single_intent("calcular"),
                ),
                resolved_references=property_references,
            )

        if action_id == "human_handoff":
            return QuickActionResolution(
                analysis=TurnAnalysis(
                    dialogue_act="lead_capture",
                    confidence=1.0,
                    reference=default_reference,
                    intent_plan=_single_intent("escalar"),
                ),
                resolved_references=property_references,
                lead_advisor=_lead_advisor_with_positive_intent(realtor_state),
            )

        refinement_questions = {
            "reject_current": (
                "quick_refine_choice",
                "Perfecto. ¿Qué querés ajustar primero: precio, zona o tipo de propiedad?",
                ["precio", "zona", "tipo de propiedad"],
            ),
            "ask_price": (
                "quick_refine_price",
                "Perfecto. ¿Qué presupuesto máximo te gustaría manejar?",
                [],
            ),
            "ask_zone": (
                "quick_refine_zone",
                "Claro. ¿Qué zona te gustaría explorar ahora?",
                [],
            ),
            "ask_property_type": (
                "quick_refine_type",
                "Perfecto. ¿Qué tipo de propiedad preferís ver?",
                [],
            ),
            "ask_size_needs": (
                "quick_refine_size",
                "Claro. ¿Buscás más habitaciones, más baños o más metros cuadrados?",
                [],
            ),
            "ask_budget_fit": (
                "quick_refine_budget_fit",
                "Entiendo. ¿Hasta qué monto te gustaría bajar el presupuesto?",
                [],
            ),
            "ask_upgrade": (
                "quick_refine_upgrade",
                "Perfecto. ¿Querés subir presupuesto, ver más metros o más habitaciones?",
                [],
            ),
            "ask_features": (
                "quick_refine_features",
                "Claro. ¿Qué querés mantener sí o sí en la siguiente opción: zona, presupuesto o habitaciones?",
                ["zona", "presupuesto", "habitaciones"],
            ),
            "save_followup": (
                "quick_followup_contact",
                "Perfecto. ¿A qué correo o WhatsApp te la envío luego?",
                [],
            ),
        }
        if action_id in refinement_questions:
            kind, question, options = refinement_questions[action_id]
            return QuickActionResolution(
                analysis=TurnAnalysis(
                    dialogue_act="refine_search",
                    confidence=1.0,
                    reference=default_reference,
                ),
                resolved_references=property_references,
                pending_decision=PendingDecision(
                    kind=kind,
                    question=question,
                    options=options,
                    metadata={"source": "quick_action", "action_id": action_id},
                ),
            )

        return None

    async def merge_filters(
        self,
        graph_state: BaseGraphState,
        analysis: TurnAnalysis,
        deps: Any,
    ) -> dict[str, Any] | None:
        return await merge_realtor_filters(_coerce_realtor_state(graph_state), analysis, deps)

    def apply_turn_policies(
        self,
        graph_state: BaseGraphState,
        analysis: TurnAnalysis,
    ) -> tuple[TurnAnalysis, list[str]]:
        return apply_realtor_turn_policies(_coerce_realtor_state(graph_state), analysis)

    def derive_pending_decision(
        self,
        graph_state: BaseGraphState,
        analysis: TurnAnalysis,
    ) -> Any | None:
        return derive_realtor_pending_decision(_coerce_realtor_state(graph_state), analysis)

    def build_fallback_intent_plan(
        self,
        graph_state: BaseGraphState,
        analysis: TurnAnalysis,
    ) -> list[Any]:
        return build_realtor_fallback_intent_plan(_coerce_realtor_state(graph_state), analysis)

    def internal_intents(self) -> set[str]:
        return set(REALTOR_INTERNAL_INTENTS)

    def field_has_value(self, extracted: Any, field_key: str) -> bool | None:
        return None

    def resolve_journey(
        self,
        graph_state: BaseGraphState,
    ) -> str | None:
        return _resolve_realtor_journey(_coerce_realtor_state(graph_state))

    def progressive_field_plan(
        self,
        graph_state: BaseGraphState,
        lead_advisor_state: LeadAdvisorState,
    ) -> list[str]:
        return _resolve_progressive_sequence(
            graph_state=_coerce_realtor_state(graph_state),
            advisor_state=lead_advisor_state,
        )

    def extra_lead_sync(
        self,
        graph_state: BaseGraphState,
        lead_payload: dict[str, Any],
    ) -> dict[str, Any]:
        payload = dict(lead_payload)
        realtor_state = _coerce_realtor_state(graph_state)
        if payload.get("presupuesto") is None:
            candidate = realtor_state.search_filters.precio_max or realtor_state.search_filters.precio_min
            if candidate is not None:
                payload["presupuesto"] = float(candidate)

        if not payload.get("preferencias"):
            preferences = _search_preferences_from_filters(realtor_state)
            if preferences:
                payload["preferencias"] = preferences

        if _has_explicit_negative_appointment_intent(_latest_user_message(realtor_state)):
            payload["appointment_intent"] = "negative"
            payload["tipo_cita"] = None
        return payload

    def select_semantic_ctas(
        self,
        graph_state: BaseGraphState,
        *,
        channel: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        _ = channel
        from services.ai_runtime.graph.realtor.cta_selector import select_realtor_card_ctas

        return select_realtor_card_ctas(_coerce_realtor_state(graph_state), limit=limit)
