"""Final synthesis node."""

from __future__ import annotations

from typing import Any

from services.ai_runtime.config.prompt_composer import compose
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import BaseGraphState, RealtorGraphState


FIELD_QUESTIONS = {
    "nombre": "Antes de seguir, con quien tengo el gusto?",
    "presupuesto": "Para afinar mejor las opciones, en que rango de presupuesto te sentis comodo?",
    "aprobacion": "Ya tenes alguna aprobacion bancaria o prefieres que lo revisemos desde cero?",
    "fecha": "Para cuando te gustaria mover esto?",
    "contacto": "Si queres, te dejo esto encaminado. Te queda mejor compartirme tu telefono o tu correo?",
    "cita": "Si te sirve, tambien te ayudo a dejar la cita encaminada. Te gustaria que la coordinemos?",
}

POLICY_RESPONSES = {
    "inventory_probe": (
        "Te puedo ayudar a buscar tu casa sonada, pero este tipo de consultas sobre inventario, totales o promedios del negocio no te las puedo responder. "
        "Si queres, con gusto te ayudo a encontrar opciones segun zona, presupuesto o tipo de propiedad."
    ),
}


def _serialize_messages(messages: list[Any], *, limit: int = 8) -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []
    for item in messages[-limit:]:
        if hasattr(item, "model_dump"):
            serialized.append(item.model_dump(mode="json"))
        elif isinstance(item, dict):
            serialized.append(dict(item))
    return serialized


def _serialize_property(item: Any) -> dict[str, Any] | None:
    if item in (None, {}):
        return None
    if hasattr(item, "model_dump"):
        return item.model_dump(mode="json")
    if isinstance(item, dict):
        return dict(item)
    return None


def _serialize_properties(items: list[Any], *, limit: int = 8) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for item in items[:limit]:
        serialized = _serialize_property(item)
        if serialized:
            payload.append(serialized)
    return payload


def _last_assistant_message(messages: list[Any]) -> dict[str, Any] | None:
    for item in reversed(messages[:-1]):
        if getattr(item, "role", None) == "assistant":
            if hasattr(item, "model_dump"):
                return item.model_dump(mode="json")
            if isinstance(item, dict):
                return dict(item)
    return None


def _serialize_displayed_cards(graph_state: RealtorGraphState) -> list[dict[str, Any]]:
    property_map: dict[str, Any] = {}
    for item in [*graph_state.last_search_results, *graph_state.inventory]:
        property_map[item.property_id_internal] = item

    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for property_id in graph_state.cards_shown:
        item = property_map.get(property_id)
        if not item or item.property_id_internal in seen:
            continue
        selected.append(item.model_dump(mode="json"))
        seen.add(item.property_id_internal)
    return selected


def _build_search_strategy(graph_state: RealtorGraphState) -> dict[str, Any] | None:
    search_outputs = [item for item in graph_state.turn_outputs if item.get("type") == "search"]
    if not search_outputs:
        return None

    latest = search_outputs[-1]
    exact_attempt = next((item for item in search_outputs if not item.get("relaxation_applied")), None)
    return {
        "requested_filters": graph_state.search_filters.model_dump(mode="json"),
        "effective_filters": (
            graph_state.effective_search_filters.model_dump(mode="json")
            if graph_state.effective_search_filters
            else latest.get("effective_filters")
        ),
        "relaxation_applied": bool(latest.get("relaxation_applied")),
        "match_scope": latest.get("match_scope"),
        "exact_result_count": exact_attempt.get("count") if exact_attempt else None,
        "final_result_count": latest.get("count"),
        "attempt_count": len(search_outputs),
    }


def _build_context(graph_state: BaseGraphState) -> dict[str, Any]:
    context: dict[str, Any] = {
        "current_message": graph_state.messages[-1].model_dump(mode="json"),
        "recent_messages": _serialize_messages(graph_state.messages),
        "last_assistant_message": _last_assistant_message(graph_state.messages),
        "turn_analysis": graph_state.turn_analysis.model_dump(mode="json") if graph_state.turn_analysis else None,
        "turn_outputs": graph_state.turn_outputs,
        "turn_output_types": [str(item.get("type")) for item in graph_state.turn_outputs],
        "lead_advisor": graph_state.lead_advisor.model_dump(mode="json"),
        "memory": graph_state.memory.model_dump(mode="json"),
        "render_mode": getattr(graph_state, "render_mode", None),
        "cards_mode": getattr(graph_state, "cards_mode", None),
        "capabilities": graph_state.capabilities,
    }

    if isinstance(graph_state, RealtorGraphState):
        context.update(
            {
                "search_filters": graph_state.search_filters.model_dump(mode="json"),
                "effective_search_filters": (
                    graph_state.effective_search_filters.model_dump(mode="json")
                    if graph_state.effective_search_filters
                    else None
                ),
                "search_strategy": _build_search_strategy(graph_state),
                "displayed_cards": _serialize_displayed_cards(graph_state),
                "last_search_results_preview": _serialize_properties(graph_state.last_search_results, limit=6),
                "inventory_preview": _serialize_properties(graph_state.inventory, limit=6),
                "last_mentioned": _serialize_property(graph_state.last_mentioned),
                "active_comparison": list(graph_state.active_comparison),
                "ui_payload": graph_state.ui_payload,
                "search_attempts": graph_state.search_attempts,
            }
        )

    return context


async def synthesize(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    """Render the final user-facing answer from structured turn context."""

    graph_state = (
        RealtorGraphState.model_validate(state)
        if state.get("vertical") == "realtor"
        else BaseGraphState.model_validate(state)
    )
    dialogue_act = graph_state.turn_analysis.dialogue_act if graph_state.turn_analysis else None
    if dialogue_act in POLICY_RESPONSES:
        answer = POLICY_RESPONSES[dialogue_act]
    else:
        prompt = compose(
            "synthesis_prompt",
            graph_state.tenant_config,
            graph_state.vertical,
            _build_context(graph_state),
            include_tone=True,
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
