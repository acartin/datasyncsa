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
from services.ai_runtime.graph.realtor.state.model import RealtorGraphState
from services.ai_runtime.graph.realtor.turn_frame import RealtorTurnFrame


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
        answer_body = _strip_trailing_question_blocks(resolved_answer)
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

    graph_state: BaseGraphState
    if state.get("vertical") == "realtor":
        graph_state = RealtorGraphState.model_validate(state)
    else:
        graph_state = BaseGraphState.model_validate(state)

    # --- Read TurnFrame from state (written by prepare_synthesis) ---
    turn_frame_data = state.get("turn_frame")
    if not turn_frame_data:
        raise RuntimeError(
            "synthesize called without turn_frame in state — "
            "prepare_synthesis must run before synthesize"
        )

    turn_frame: BaseTurnFrame
    if isinstance(graph_state, RealtorGraphState):
        turn_frame = RealtorTurnFrame.model_validate(turn_frame_data)
    else:
        turn_frame = BaseTurnFrame.model_validate(turn_frame_data)

    # --- Policy responses (deterministic, skip LLM) ---
    if turn_frame.framing in POLICY_RESPONSES:
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
