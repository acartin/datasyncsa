from __future__ import annotations

import time
import uuid
from typing import Any

from app.core.config import settings
from app.models.contracts import (
    AnswerEnvelope,
    GoalType,
    GuardrailRejectCode,
    GuardrailResult,
    GateResult,
    GateRejectCode,
    ResponseMode,
    RouterDecision,
    SynthesizerOutput,
    ToolResult,
)
from app.planners.planner_service import planner_service
from app.renderers.card_renderer import card_renderer
from app.repositories.persistence import runtime_repository
from app.runtime.answer_guardrail import run_answer_guardrail
from app.runtime.policy_gate import run_policy_gate
from app.services.scoring_client import scoring_client
from app.core.prompt_service import prompt_service
from app.tools.executor import tool_executor
from app.synthesizers.synthesizer_service import synthesizer_service
from app.graph.state import AgentCoreState


def _timing(state: AgentCoreState, node_name: str, started: float) -> dict[str, Any]:
    elapsed = (time.perf_counter() - started) * 1000.0
    timings = dict(state.get("node_timings_ms", {}))
    timings[node_name] = timings.get(node_name, 0.0) + elapsed
    return {"node_timings_ms": timings}


def _fallback_synthesizer_output(
    *,
    goal: GoalType,
    tool_results: list[ToolResult],
) -> SynthesizerOutput:
    if goal in {GoalType.realtor_search, GoalType.realtor_refine}:
        for result in tool_results:
            if result.status != "ok" or result.realtor is None:
                continue
            listings = result.realtor.listings
            if listings:
                evidence_ids = [item.listing_id for item in listings[:3] if item.listing_id]
                return SynthesizerOutput(
                    text="Te comparto propiedades para que las revises.",
                    evidence_ids=evidence_ids,
                    needs_cards=True,
                )
        return SynthesizerOutput(
            text="No encontré propiedades con esos criterios. Si quieres, afinamos zona, tipo o presupuesto.",
            evidence_ids=[],
            needs_cards=False,
        )

    if goal == GoalType.rag:
        for result in tool_results:
            if result.status != "ok" or result.rag is None:
                continue
            chunk_ids = [chunk.chunk_id for chunk in result.rag.chunks[:3] if chunk.chunk_id]
            if chunk_ids:
                return SynthesizerOutput(
                    text="Encontré información relevante en los documentos y ya te la comparto.",
                    evidence_ids=chunk_ids,
                    needs_cards=False,
                )

    return SynthesizerOutput(
        text="No pude sintetizar la respuesta en este momento, pero ya ejecuté la consulta solicitada.",
        evidence_ids=[],
        needs_cards=bool(tool_results),
    )


async def normalize_input(state: AgentCoreState) -> dict[str, Any]:
    started = time.perf_counter()
    raw = state.get("raw_input", {})
    if not isinstance(raw, dict):
        raw = {}

    conversation_id = str(
        raw.get("conversationId")
        or raw.get("conversation_id")
        or uuid.uuid4()
    )
    tenant_id = raw.get("tenant_id") or raw.get("clientId") or raw.get("client_id")
    channel = raw.get("channel") or "web_html"
    requested_vertical = str(raw.get("vertical") or "").strip() or "generic"
    vertical = await prompt_service.resolve_runtime_vertical(
        tenant_id=str(tenant_id) if tenant_id else None,
        requested_vertical=requested_vertical,
    )

    normalized_input = {
        "conversation_summary": str(raw.get("queryText") or raw.get("text") or "").strip(),
        "vertical": vertical,
        "conversation_state": raw.get("conversation_state") or {},
        "last_user_turn": str(raw.get("queryText") or raw.get("text") or ""),
    }

    return {
        **_timing(state, "normalize_input", started),
        "normalized_input": normalized_input,
        "tenant_id": str(tenant_id) if tenant_id else None,
        "channel": str(channel),
        "conversation_id": conversation_id,
        "errors": [],
    }


async def plan_turn(state: AgentCoreState) -> dict[str, Any]:
    started = time.perf_counter()
    raw_input = state.get("raw_input") or {}
    normalized = state.get("normalized_input") or {}
    history = state.get("raw_input", {}).get("history", [])
    if not isinstance(history, list):
        history = []

    try:
        decision = await planner_service.run(
            raw_input=raw_input,
            normalized_input=normalized,
            history=history,
        )
        return {
            **_timing(state, "plan_turn", started),
            "router_decision": decision,
        }
    except Exception as exc:
        decision = RouterDecision(
            goal=GoalType.clarify,
            confidence=0.0,
            tool_calls=[],
            missing_slots=["planner_output_invalid"],
            clarify_message="No pude decidir el siguiente paso. Por favor formula la consulta de nuevo.",
            response_mode=ResponseMode.text_only,
        )
        return {
            **_timing(state, "plan_turn", started),
            "router_decision": decision,
            "errors": [str(exc)],
        }


def policy_gate(state: AgentCoreState) -> dict[str, Any]:
    started = time.perf_counter()
    decision = state.get("router_decision")
    if not isinstance(decision, RouterDecision):
        return {
            **_timing(state, "policy_gate", started),
            "gate_result": GateResult(
                accepted=False,
                reject_code=GateRejectCode.schema_invalid,
            ),
            "errors": ["invalid_router_decision"],
        }

    tenant_id = str(state.get("tenant_id")) if state.get("tenant_id") else "default"
    vertical = str((state.get("normalized_input") or {}).get("vertical", "generic"))
    gate = run_policy_gate(
        decision=decision,
        tenant_id=tenant_id,
        vertical=vertical,
    )
    return {
        **_timing(state, "policy_gate", started),
        "gate_result": gate,
    }


def clarify_response(state: AgentCoreState) -> dict[str, Any]:
    started = time.perf_counter()
    raw_input = state.get("raw_input") or {}
    decision = state.get("router_decision")
    goal = decision.goal if decision else GoalType.clarify
    message = (
        decision.clarify_message
        if decision and decision.clarify_message
        else "Necesito más contexto para continuar."
    )
    envelope = AnswerEnvelope(
        conversation_id=str(raw_input.get("conversationId") or raw_input.get("conversation_id") or state.get("conversation_id", "")),
        text=message,
        cards=[],
        response_mode=ResponseMode.text_only,
        evidence_ids=[],
        goal=goal,
        confidence=float(decision.confidence if decision else 0.0),
        clarify_message=message,
    )
    return {
        **_timing(state, "clarify_response", started),
        "answer_envelope": envelope,
    }


async def execute_tools(state: AgentCoreState) -> dict[str, Any]:
    started = time.perf_counter()
    raw_input = state.get("raw_input") or {}
    tenant_id = str(raw_input.get("tenant_id") or raw_input.get("clientId") or raw_input.get("client_id") or "default")
    vertical = str((state.get("normalized_input") or {}).get("vertical") or "generic")
    decision = state.get("router_decision")
    if not decision:
        return {"tool_results": [], **_timing(state, "execute_tools", started)}
    calls = decision.tool_calls
    if not calls:
        return {"tool_results": [], **_timing(state, "execute_tools", started)}
    results: list[ToolResult] = await tool_executor.execute_all(
        tenant_id=tenant_id,
        vertical=vertical,
        calls=calls,
    )
    return {"tool_results": results, **_timing(state, "execute_tools", started)}


async def synthesize(state: AgentCoreState) -> dict[str, Any]:
    started = time.perf_counter()
    raw_input = state.get("raw_input") or {}
    decision = state.get("router_decision")
    tool_results = state.get("tool_results") or []
    normalized = state.get("normalized_input") or {}
    if not isinstance(tool_results, list):
        tool_results = []

    if not isinstance(decision, RouterDecision):
        decision = RouterDecision(
            goal=GoalType.answer,
            confidence=0.0,
            tool_calls=[],
            missing_slots=[],
        )

    try:
        output = await synthesizer_service.run(
            tenant_id=str(raw_input.get("tenant_id") or raw_input.get("clientId") or raw_input.get("client_id") or "default"),
            raw_input=raw_input,
            tool_results=tool_results,
            response_mode=decision.response_mode,
            context_snapshot={
                "conversation_summary": normalized.get("conversation_summary", ""),
                "vertical": normalized.get("vertical", "generic"),
                "conversation_state": normalized.get("conversation_state", {}),
                "last_user_turn": normalized.get("last_user_turn", ""),
            },
        )
        return {
            **_timing(state, "synthesize", started),
            "synthesizer_output": output,
        }
    except Exception as exc:
        output = _fallback_synthesizer_output(
            goal=decision.goal,
            tool_results=tool_results,
        )
        return {
            **_timing(state, "synthesize", started),
            "synthesizer_output": output,
            "errors": [str(exc)],
        }


def answer_guardrail(state: AgentCoreState) -> dict[str, Any]:
    started = time.perf_counter()
    decision = state.get("router_decision")
    tool_results = state.get("tool_results") or []
    output = state.get("synthesizer_output")
    if not isinstance(decision, RouterDecision):
        decision = RouterDecision(
            goal=GoalType.answer,
            confidence=0.0,
            tool_calls=[],
            missing_slots=[],
        )

    guardrail = run_answer_guardrail(
        goal=decision.goal,
        synthesizer_output=output,
        tool_results=tool_results,
    )

    if not guardrail.accepted and output is None:
        return {
            **_timing(state, "answer_guardrail", started),
            "guardrail_result": guardrail,
            "answer_envelope": AnswerEnvelope(
                conversation_id=str((state.get("raw_input") or {}).get("conversationId") or state.get("conversation_id", "")),
                text="No puedo garantizar la validez de esta respuesta.",
                cards=[],
                response_mode=ResponseMode.text_only,
                evidence_ids=[],
                goal=decision.goal,
                confidence=decision.confidence,
            ),
        }

    return {
        **_timing(state, "answer_guardrail", started),
        "guardrail_result": guardrail,
    }


def _serialize_model(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def _resolve_reject_code(
    *,
    gate_result: GateResult | None,
    guardrail_result: GuardrailResult | None,
) -> str | None:
    if gate_result is not None and not gate_result.accepted:
        return (
            gate_result.reject_code.value
            if gate_result.reject_code is not None
            else GateRejectCode.schema_invalid.value
        )
    if guardrail_result is not None and not guardrail_result.accepted:
        return (
            guardrail_result.reject_code.value
            if guardrail_result.reject_code is not None
            else GuardrailRejectCode.schema_violation.value
        )
    return None


def _reject_message(reject_code: str) -> str:
    if reject_code == GateRejectCode.tenant_not_authorized.value:
        return "No tengo autorización para procesar esta solicitud."
    if reject_code == GateRejectCode.confidence_too_low.value:
        return "No puedo responder con confianza suficiente en este momento."
    if reject_code == GuardrailRejectCode.no_evidence_cited.value:
        return "No puedo responder porque faltan evidencias verificables."
    return "No puedo procesar esta solicitud con los controles de seguridad actuales."


async def persist(state: AgentCoreState) -> dict[str, Any]:
    started = time.perf_counter()
    raw_input = state.get("raw_input") or {}

    raw_decision = state.get("router_decision")
    decision = raw_decision if isinstance(raw_decision, RouterDecision) else RouterDecision(
        goal=GoalType.answer,
        confidence=0.0,
        tool_calls=[],
        missing_slots=[],
    )

    gate_result = state.get("gate_result") if isinstance(state.get("gate_result"), GateResult) else None
    guardrail_result = (
        state.get("guardrail_result")
        if isinstance(state.get("guardrail_result"), GuardrailResult)
        else None
    )
    tool_results = state.get("tool_results")
    if not isinstance(tool_results, list):
        tool_results = []
    output = state.get("synthesizer_output")
    if not isinstance(output, SynthesizerOutput):
        output = SynthesizerOutput(text="", evidence_ids=[], needs_cards=False)

    conversation_id = str(
        raw_input.get("conversationId")
        or raw_input.get("conversation_id")
        or state.get("conversation_id")
        or ""
    )
    tenant_id = str(
        raw_input.get("tenant_id")
        or raw_input.get("clientId")
        or raw_input.get("client_id")
        or ""
    ).strip()
    channel = str(raw_input.get("channel") or state.get("channel") or "web_html")
    lead_id = raw_input.get("leadId") or raw_input.get("lead_id")
    if not lead_id:
        user_metadata = raw_input.get("userMetadata") or raw_input.get("user_metadata") or {}
        if isinstance(user_metadata, dict):
            lead_id = user_metadata.get("lead_id") or user_metadata.get("leadId")
    if conversation_id and tenant_id:
        resolved = await runtime_repository.resolve_lead_id(
            conversation_id=conversation_id,
            payload={"raw_input": raw_input},
            tenant_id=tenant_id,
            explicit_lead_id=str(lead_id) if lead_id else None,
        )
        if resolved:
            lead_id = resolved

    reject_code = _resolve_reject_code(
        gate_result=gate_result,
        guardrail_result=guardrail_result,
    )

    existing_envelope = state.get("answer_envelope")
    if isinstance(existing_envelope, AnswerEnvelope):
        envelope = existing_envelope
    elif reject_code:
        envelope = AnswerEnvelope(
            conversation_id=conversation_id,
            text=_reject_message(reject_code),
            cards=[],
            response_mode=ResponseMode.text_only,
            evidence_ids=[],
            goal=decision.goal,
            confidence=decision.confidence,
        )
    elif decision.goal == GoalType.clarify:
        clarify_message = (
            decision.clarify_message
            or output.text.strip()
            or "Necesito más contexto para continuar."
        )
        envelope = AnswerEnvelope(
            conversation_id=conversation_id,
            text=clarify_message,
            cards=[],
            response_mode=ResponseMode.text_only,
            evidence_ids=[],
            goal=GoalType.clarify,
            confidence=decision.confidence,
            clarify_message=clarify_message,
        )
    else:
        vertical = str((state.get("normalized_input") or {}).get("vertical") or "generic")
        rendered_cards = card_renderer(tool_results, vertical=vertical)
        response_mode = ResponseMode.text_plus_cards if rendered_cards else ResponseMode.text_only
        envelope = AnswerEnvelope(
            conversation_id=conversation_id,
            text=output.text.strip() or "No encontré evidencia suficiente para responder.",
            cards=rendered_cards,
            response_mode=response_mode,
            evidence_ids=[item for item in output.evidence_ids if item],
            goal=decision.goal,
            confidence=decision.confidence,
        )

    scoring_status = "disabled"
    scoring_job_id: str | None = None
    if (
        settings.scoring_enabled
        and not reject_code
        and decision.goal != GoalType.clarify
        and bool(lead_id)
        and bool(tenant_id)
    ):
        try:
            job = await scoring_client.enqueue(
                client_id=tenant_id,
                lead_id=str(lead_id),
                conversation_id=conversation_id,
                channel=channel,
            )
            scoring_status = "error" if str(job.status).strip().lower() == "error" else "pending"
            scoring_job_id = job.id
        except Exception:
            scoring_status = "error"

    state_for_persistence = {
        "router_decision": decision.model_dump(mode="json"),
        "tool_results": [_serialize_model(item) for item in tool_results],
        "synthesizer_output": output.model_dump(mode="json"),
        "answer_envelope": envelope.model_dump(mode="json"),
        "gate_result": _serialize_model(gate_result),
        "guardrail_result": _serialize_model(guardrail_result),
        "timings_ms": state.get("node_timings_ms") or {},
        "raw_input": raw_input,
        "normalized_input": state.get("normalized_input") or {},
        "lead_id": str(lead_id) if lead_id else None,
        "errors": state.get("errors") or [],
        "scoring_status": scoring_status,
        "scoring_job_id": scoring_job_id,
        "error_code": reject_code,
    }
    await runtime_repository.persist_turn(
        conversation_id=conversation_id,
        payload=state_for_persistence,
        metrics={"node_timings_ms": state.get("node_timings_ms", {})},
        lead_id=str(lead_id) if lead_id else None,
    )

    return {
        **_timing(state, "persist", started),
        "answer_envelope": envelope,
        "lead_id": str(lead_id) if lead_id else None,
        "scoring_status": scoring_status,
        "scoring_job_id": scoring_job_id,
        "error_code": reject_code,
    }
