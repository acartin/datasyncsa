"""Final synthesis node."""

from __future__ import annotations

from typing import Any

from services.ai_runtime.config.prompt_composer import compose
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import BaseGraphState


FIELD_QUESTIONS = {
    "nombre": "Antes de seguir, con quien tengo el gusto?",
    "presupuesto": "Para afinar mejor las opciones, en que rango de presupuesto te sentis comodo?",
    "aprobacion": "Ya tenes alguna aprobacion bancaria o prefieres que lo revisemos desde cero?",
    "fecha": "Para cuando te gustaria mover esto?",
    "contacto": "Si queres, te dejo esto encaminado. Te queda mejor compartirme tu telefono o tu correo?",
    "cita": "Si te sirve, tambien te ayudo a dejar la cita encaminada. Te gustaria que la coordinemos?",
}


async def synthesize(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    """Merge all turn outputs into the final response and schedule side effects."""

    graph_state = BaseGraphState.model_validate(state)
    prompt = compose(
        "synthesis_prompt",
        graph_state.tenant_config,
        graph_state.vertical,
        {
            "turn_outputs": graph_state.turn_outputs,
            "lead_advisor": graph_state.lead_advisor.model_dump(mode="json"),
            "render_mode": state.get("render_mode"),
            "cards_mode": state.get("cards_mode"),
        },
    )
    answer = await deps.llm.synthesize_response(prompt)
    if graph_state.lead_advisor.should_ask and graph_state.lead_advisor.field_to_ask:
        question = FIELD_QUESTIONS.get(graph_state.lead_advisor.field_to_ask)
        if question and question not in answer:
            answer = f"{answer} {question}".strip()

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
        "turn_outputs": [*graph_state.turn_outputs],
    }
