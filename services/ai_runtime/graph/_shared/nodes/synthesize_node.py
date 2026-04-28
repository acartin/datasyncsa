"""Final synthesis node.

Reads the pre-computed ``TurnFrame`` from graph state and renders the
user-facing answer.  The LLM only *writes* — all interpretation is already
resolved by ``prepare_synthesis``.
"""

from __future__ import annotations

import re
from typing import Any

from services.ai_runtime.config.prompt_composer import compose
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import BaseGraphState
from services.ai_runtime.domain.turn_frame import BaseTurnFrame


# ---------------------------------------------------------------------------
# Lead question post-processing
# ---------------------------------------------------------------------------

FIELD_QUESTIONS: dict[str, str] = {
    "nombre": "Antes de seguir, con quien tengo el gusto?",
    "email": "Si te parece, compartime tu correo y te envio el resumen.",
    "telefono": "Si te queda bien, compartime tu telefono y te contacto por ahi.",
    "contacto": "Si queres, te dejo esto encaminado. Te queda mejor compartirme tu telefono o tu correo?",
    "presupuesto": "Para afinar mejor las opciones, en que rango de presupuesto te sentis comodo?",
    "aprobacion": "Ya tenes alguna aprobacion bancaria o prefieres que lo revisemos desde cero?",
    "preferencias": "Para ayudarte mejor, que zona o caracteristicas priorizas?",
    "fecha": "Para cuando te gustaria mover esto?",
    "fecha_preferida": "Para cuando te gustaria mover esto?",
    "tipo_cita": "Prefieres visita presencial, videollamada o una llamada rapida?",
    "appointment_intent": "Te gustaria que dejemos una cita coordinada para avanzar?",
    "cita": "Si te sirve, tambien te ayudo a dejar la cita encaminada. Te gustaria que la coordinemos?",
}

POLICY_RESPONSES: dict[str, str] = {
    "policy_block": (
        "Te puedo ayudar a buscar tu casa sonada, pero este tipo de consultas "
        "sobre inventario, totales o promedios del negocio no te las puedo "
        "responder. Si queres, con gusto te ayudo a encontrar opciones segun "
        "zona, presupuesto o tipo de propiedad."
    ),
}

_APPOINTMENT_CONFIRMATION_HINTS = (
    "agendada",
    "agendado",
    "confirmada",
    "confirmado",
    "queda agendada",
    "queda confirmada",
    "visita confirmada",
)
_TRAILING_INVERTED_QUESTION_BLOCK = re.compile(r"\s*¿[^?]*\?\s*$")
_TRAILING_PLAIN_QUESTION_BLOCK = re.compile(r"\s*[^¿?!.][^?]*\?\s*$")
_TRAILING_LEAD_BRIDGE = re.compile(
    r"\s*(?:y\s+)?(?:para\s+continuar|para\s+seguir|y\s+si\s+te\s+parece|si\s+te\s+parece)[\s,.:;-]*$",
    flags=re.IGNORECASE,
)
_RECOMMENDATION_CUE_PATTERN = re.compile(r"\b(recomend|me inclin|de las opciones)\b", flags=re.IGNORECASE)
_BUDGET_RANGE_PATTERN = re.compile(
    r"\b(?:entre\s+)?(\d{2,3}(?:[.,]\d{3})?)\s*(mil|miles)?\s*(?:y|a|-)\s*(\d{2,3}(?:[.,]\d{3})?)\s*(mil|miles)?\b",
    flags=re.IGNORECASE,
)
_PARKING_QUERY_PATTERN = re.compile(
    r"\b(estacion(?:amiento|amientos)?|parqueo|cochera|garage)\b",
    flags=re.IGNORECASE,
)
_CAR_SPACES_PATTERN = re.compile(
    r"\b(?:espacio|garaje|garage)\s+para\s+(\d+)\s+carros?\b",
    flags=re.IGNORECASE,
)
_BUDGET_REFERENCE_PATTERN = re.compile(r"\bcon\s+ese\s+presupuesto\b", flags=re.IGNORECASE)


def _looks_like_appointment_confirmation(answer: str) -> bool:
    lowered = re.sub(r"\s+", " ", (answer or "").strip().lower())
    return any(hint in lowered for hint in _APPOINTMENT_CONFIRMATION_HINTS)


def _strip_trailing_question_blocks(answer: str) -> str:
    text = str(answer or "").strip()
    while True:
        updated = re.sub(_TRAILING_INVERTED_QUESTION_BLOCK, "", text).strip()
        if updated == text:
            break
        text = updated
    while text.endswith("?"):
        updated = re.sub(_TRAILING_PLAIN_QUESTION_BLOCK, "", text).strip()
        if updated == text:
            break
        text = updated
    return re.sub(r"\s{2,}", " ", text).strip()


def _ensure_sentence_ending(text: str) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""
    if cleaned[-1] in ".!?":
        return cleaned
    return f"{cleaned}."


def _strip_trailing_lead_bridge(answer: str) -> str:
    return re.sub(_TRAILING_LEAD_BRIDGE, "", str(answer or "").strip()).strip()


def _enforce_recommendation_cue(answer: str) -> str:
    text = str(answer or "").strip()
    if not text:
        return "De las opciones que te mostre, me inclinaria por esta opcion."
    if _RECOMMENDATION_CUE_PATTERN.search(text):
        return text
    return f"De las opciones que te mostre, me inclinaria por esta opcion. {text}".strip()


def _build_recommendation_objection_answer(turn_frame: BaseTurnFrame) -> str | None:
    user_message = str(turn_frame.user_message or "").strip().lower()
    if "como sabes" not in user_message and "por que" not in user_message and "por qué" not in user_message:
        return None

    focused = getattr(turn_frame, "focused_property", None)
    if not focused:
        visible = list(getattr(turn_frame, "visible_properties", []) or [])
        focused = visible[0] if visible else None
    if not focused:
        return "Claro, me base en los detalles visibles de las opciones que veniamos revisando."

    details: list[str] = []
    bedrooms = getattr(focused, "bedrooms_clean", None)
    bathrooms = getattr(focused, "bathrooms_clean", None)
    sqm = getattr(focused, "sqm_clean", None)
    price = getattr(focused, "price", None)
    province = getattr(focused, "province", None)
    if bedrooms:
        details.append(f"{bedrooms} habitaciones")
    if bathrooms:
        details.append(f"{bathrooms} banos")
    if sqm:
        details.append(f"{sqm} m2")
    if price:
        details.append(f"precio de {price}")
    if province:
        details.append(f"ubicada en {province}")

    detail_text = ", ".join(details[:4]) if details else "los detalles visibles de esa opcion"
    return f"Claro, me base en {detail_text} dentro del set que estabamos comparando."


def _build_property_focus_answer(turn_frame: BaseTurnFrame) -> str | None:
    focused = getattr(turn_frame, "focused_property", None)
    if not focused:
        visible = list(getattr(turn_frame, "visible_properties", []) or [])
        focused = visible[0] if len(visible) == 1 else None
    if not focused:
        return None

    label = str(getattr(focused, "position_label", "") or "").strip()
    subject = label or "La propiedad"
    details: list[str] = []
    bedrooms = int(getattr(focused, "bedrooms_clean", 0) or 0)
    bathrooms = getattr(focused, "bathrooms_clean", 0) or 0
    garage = int(getattr(focused, "garage_clean", 0) or 0)
    sqm = getattr(focused, "sqm_clean", None)
    if bedrooms:
        details.append(f"{bedrooms} habitaciones")
    if bathrooms:
        details.append(f"{bathrooms} banos")
    if garage:
        details.append(f"{garage} estacionamientos")
    if sqm:
        details.append(f"{sqm} m2")
    if not details:
        title = str(getattr(focused, "title", "") or "").strip()
        if title:
            return f"{subject} es {title}."
        return None
    return f"{subject} tiene {', '.join(details)}."


def _build_relaxation_continuation_answer(turn_frame: BaseTurnFrame) -> str | None:
    if str(getattr(turn_frame, "framing", "") or "").strip().lower() != "confirm_continuation":
        return None
    if bool(getattr(turn_frame, "has_new_cards", False)):
        return None
    search = getattr(turn_frame, "search", None)
    result_count = int(getattr(search, "result_count", 0) or 0) if search else 0
    if result_count > 0:
        return None
    return (
        "No encontré coincidencias exactas con ese rango. "
        "Si querés, ampliemos el rango de precio o una zona cercana para seguir."
    )


def _parking_label(count: int) -> str:
    return "estacionamiento" if count == 1 else "estacionamientos"


def _build_parking_answer(turn_frame: BaseTurnFrame) -> str | None:
    focused = getattr(turn_frame, "focused_property", None)
    visible = list(getattr(turn_frame, "visible_properties", []) or [])
    if focused:
        garage = int(getattr(focused, "garage_clean", 0) or 0)
        if garage > 0:
            subject = str(getattr(focused, "position_label", "") or "").strip() or "La propiedad"
            return f"{subject} tiene {garage} {_parking_label(garage)}."

    if not visible:
        return None

    garage_values = [int(getattr(item, "garage_clean", 0) or 0) for item in visible]
    positive_values = [value for value in garage_values if value > 0]
    if not positive_values:
        return None
    unique_values = set(positive_values)
    if len(unique_values) == 1 and len(positive_values) == len(visible):
        garage = positive_values[0]
        intro = "Las dos opciones" if len(visible) == 2 else "Las opciones visibles"
        return f"{intro} tienen {garage} {_parking_label(garage)}."

    parts: list[str] = []
    for index, item in enumerate(visible[:3], start=1):
        garage = int(getattr(item, "garage_clean", 0) or 0)
        if garage <= 0:
            continue
        label = str(getattr(item, "position_label", "") or "").strip() or f"La opcion {index}"
        parts.append(f"{label} tiene {garage} {_parking_label(garage)}")
    if not parts:
        return None
    if len(parts) == 1:
        return f"{parts[0]}."
    if len(parts) == 2:
        return f"{parts[0]} y {parts[1]}."
    return f"{'; '.join(parts[:-1])}; y {parts[-1]}."


def _extract_budget_range_match(message: str) -> re.Match[str] | None:
    return _BUDGET_RANGE_PATTERN.search(str(message or ""))


def _extract_budget_range_anchor(message: str) -> str | None:
    match = _extract_budget_range_match(message)
    if not match:
        return None
    low, low_unit, high, high_unit = match.groups(default="")
    first = " ".join(part for part in (low, low_unit) if part).strip()
    second = " ".join(part for part in (high, high_unit or low_unit) if part).strip()
    if not first or not second:
        return None
    return f"{first} a {second}".strip()


def _budget_anchor_present(answer: str, anchor: str) -> bool:
    normalized_answer = str(answer or "")
    numbers = re.findall(r"\d+", anchor)
    if not numbers:
        return False
    if not all(number in normalized_answer for number in numbers):
        return False
    lowered = normalized_answer.lower()
    return "rango" in lowered or "presupuesto" in lowered or "entre" in lowered


def _enforce_budget_range_anchor(answer: str, turn_frame: BaseTurnFrame) -> str:
    budget_anchor = _extract_budget_range_anchor(turn_frame.user_message)
    if not budget_anchor:
        return answer
    if _budget_anchor_present(answer, budget_anchor):
        return answer
    body = str(answer or "").strip()
    if not body:
        return f"Entendido, tomo un rango de {budget_anchor}."
    if _BUDGET_REFERENCE_PATTERN.search(body):
        return _BUDGET_REFERENCE_PATTERN.sub(f"con tu rango de {budget_anchor}", body, count=1)
    prefix = f"Entendido, tomo un rango de {budget_anchor}."
    if body.lower().startswith(("entendido", "perfecto", "claro")):
        return f"{prefix} {body}".strip()
    return f"{prefix} {_ensure_sentence_ending(body)}".strip()


def _normalize_parking_vocabulary(answer: str, turn_frame: BaseTurnFrame) -> str:
    user_message = str(turn_frame.user_message or "")
    if not _PARKING_QUERY_PATTERN.search(user_message):
        return answer
    if _PARKING_QUERY_PATTERN.search(str(answer or "")):
        return answer
    normalized = _CAR_SPACES_PATTERN.sub(r"\1 estacionamientos", str(answer or ""))
    if normalized != answer:
        return normalized
    focused = getattr(turn_frame, "focused_property", None)
    garage = int(getattr(focused, "garage_clean", 0) or 0) if focused else 0
    if garage <= 0:
        return answer
    return f"{_ensure_sentence_ending(answer)} En total tiene {garage} estacionamientos.".strip()


def _apply_lead_question(answer: str, turn_frame: BaseTurnFrame) -> tuple[str, str | None, str | None]:
    """Append the lead-capture question and return (answer, field_to_ask, question_to_ask).

    The returned ``field_to_ask`` / ``question_to_ask`` reflect the *effective*
    values after appointment-contact overrides so the caller can persist them
    back into ``lead_advisor``.
    """

    lc = turn_frame.lead_capture
    resolved_answer = answer

    forced_field: str | None = None

    # Appointment pending-contact overrides
    if lc.appointment_pending_contact and lc.lead_name_known:
        forced_field = "contacto"
        if _looks_like_appointment_confirmation(resolved_answer):
            resolved_answer = (
                "Perfecto, ya tengo la fecha y la hora. Para dejar la cita "
                "confirmada, compartime tu telefono o tu correo."
            )
    elif lc.appointment_pending_contact and not lc.lead_name_known:
        if _looks_like_appointment_confirmation(resolved_answer):
            resolved_answer = "Perfecto, puedo ayudarte a coordinar la visita de esa opcion."

    field_to_ask = lc.field_to_ask if lc.should_ask and lc.field_to_ask else None
    if forced_field:
        field_to_ask = forced_field

    question_to_ask: str | None = None
    if field_to_ask:
        suggested_question = str(lc.question_to_ask or "").strip()
        if forced_field:
            question_to_ask = FIELD_QUESTIONS.get(field_to_ask)
        else:
            question_to_ask = suggested_question or FIELD_QUESTIONS.get(field_to_ask)

    if field_to_ask and question_to_ask:
        answer_body = _strip_trailing_question_blocks(_strip_trailing_lead_bridge(resolved_answer))
        if answer_body:
            resolved_answer = f"{_ensure_sentence_ending(answer_body)} {question_to_ask}".strip()
        else:
            resolved_answer = question_to_ask

    return resolved_answer, field_to_ask, question_to_ask


# ---------------------------------------------------------------------------
# Node entry point
# ---------------------------------------------------------------------------

async def synthesize(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    """Render the final user-facing answer from the pre-computed TurnFrame."""

    from services.ai_runtime.verticals import get_vertical_spec

    vertical_spec = get_vertical_spec(state.get("vertical"))
    graph_state: BaseGraphState = vertical_spec.state_model.model_validate(state)

    # --- Read TurnFrame from state (written by prepare_synthesis) ---
    turn_frame_data = state.get("turn_frame")
    if not turn_frame_data:
        raise RuntimeError(
            "synthesize called without turn_frame in state — "
            "prepare_synthesis must run before synthesize"
        )

    turn_frame: BaseTurnFrame = vertical_spec.turn_frame_model.model_validate(turn_frame_data)

    # --- Policy responses (deterministic, skip LLM) ---
    relaxation_answer = _build_relaxation_continuation_answer(turn_frame)
    parking_answer = _build_parking_answer(turn_frame) if _PARKING_QUERY_PATTERN.search(str(turn_frame.user_message or "")) else None

    if relaxation_answer:
        answer = relaxation_answer
    elif parking_answer and turn_frame.dialogue_act in {"ask_detail", "select_result"}:
        answer = parking_answer
    elif (
        turn_frame.primary_narrative
        and (
            turn_frame.framing == "result_set_detail"
            or turn_frame.dialogue_act == "ask_detail"
        )
    ):
        answer = turn_frame.primary_narrative
    elif turn_frame.dialogue_act == "select_result":
        deterministic_focus = _build_property_focus_answer(turn_frame)
        if deterministic_focus:
            answer = deterministic_focus
        else:
            prompt = compose(
                "synthesis_prompt",
                graph_state.tenant_config,
                graph_state.vertical,
                turn_frame.model_dump(mode="json"),
                include_tone=True,
            )
            answer = await deps.llm.synthesize_response(prompt)
    elif turn_frame.framing in POLICY_RESPONSES:
        answer = POLICY_RESPONSES[turn_frame.framing]
    else:
        prompt = compose(
            "synthesis_prompt",
            graph_state.tenant_config,
            graph_state.vertical,
            turn_frame.model_dump(mode="json"),
            include_tone=True,
        )
        answer = await deps.llm.synthesize_response(prompt)

    if turn_frame.framing == "recommendation" or turn_frame.dialogue_act == "recommend":
        answer = _enforce_recommendation_cue(answer)
    elif turn_frame.framing == "reject_previous":
        deterministic_rejection = _build_recommendation_objection_answer(turn_frame)
        if deterministic_rejection:
            answer = deterministic_rejection
    answer = _enforce_budget_range_anchor(answer, turn_frame)
    answer = _normalize_parking_vocabulary(answer, turn_frame)

    # --- Post-process: lead question injection ---
    answer, field_to_ask, question_to_ask = _apply_lead_question(answer, turn_frame)

    # --- Persist lead_advisor update if the effective field changed ---
    lead_advisor = graph_state.lead_advisor
    if (
        bool(lead_advisor.should_ask) != bool(field_to_ask)
        or lead_advisor.field_to_ask != field_to_ask
        or str(lead_advisor.question_to_ask or "").strip() != str(question_to_ask or "").strip()
    ):
        lead_advisor = lead_advisor.model_copy(
            update={
                "should_ask": bool(field_to_ask),
                "field_to_ask": field_to_ask,
                "question_to_ask": question_to_ask,
            }
        )

    messages = [*graph_state.messages, {"role": "assistant", "content": answer}]

    await deps.worker_dispatcher.fire_and_forget(
        "lead_worker",
        {
            "client_id": graph_state.client_id,
            "session_id": graph_state.session_id,
            "state": graph_state.model_dump(mode="json"),
        },
    )

    return {
        "final_response": answer,
        "messages": messages,
        "lead_advisor": lead_advisor.model_dump(mode="json"),
        "turn_outputs": [*graph_state.turn_outputs],
    }
