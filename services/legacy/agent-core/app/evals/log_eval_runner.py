from __future__ import annotations

import argparse
import asyncio
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.models.contracts import (
    GoalType,
    ResponseMode,
    RouterDecision,
    SynthesizerOutput,
    ToolName,
    ToolResult,
)
from app.planners.planner_service import planner_service
from app.runtime.answer_guardrail import run_answer_guardrail
from app.synthesizers.synthesizer_service import synthesizer_service

_META_QUERY_RE = re.compile(
    r"(a\s*qu[eé]\s*te\s*dedicas|en\s*qu[eé]\s*zonas|trabajas\s*en|cobertura|servicio)",
    re.IGNORECASE,
)
_REFERENTIAL_QUERY_RE = re.compile(
    r"(la\s+[uú]ltima|la\s+ultima|la\s+primera|la\s+segunda|esa\s+casa|esta\s+propiedad|que\s+mostraste)",
    re.IGNORECASE,
)
_PERMISSION_PHRASE_RE = re.compile(
    r"(te\s+gustar[ií]a\s+ver|prefieres\s+que\s+te\s+muestre|quieres\s+ver\s+algunas\s+opciones|"
    r"te\s+gustar[ií]a\s+que\s+te\s+muestre)",
    re.IGNORECASE,
)
_RAG_RESTART_RE = re.compile(
    r"(¿\s*(en|como)\s+qu[eé]\s+puedo\s+ayudarte\s+hoy\??)\s*$",
    re.IGNORECASE,
)
_SENTENCE_RE = re.compile(r"[^.!?¿]+\??[.!?]?")
_NAME_DECLARATION_RE = re.compile(
    r"\bme\s+llamo\s+([A-Za-zÁÉÍÓÚÑáéíóúñ][A-Za-zÁÉÍÓÚÑáéíóúñ'`\-]*)\b",
    re.IGNORECASE,
)
_NAME_RECALL_RE = re.compile(
    r"\brecuerd(?:as|a)\s+c[oó]mo\s+me\s+llamo\b",
    re.IGNORECASE,
)
_GREETING_RE = re.compile(
    r"\b(hola|mucho gusto|encantad[oa]|gusto saludarte|bienvenido|bienvenida)\b",
    re.IGNORECASE,
)
_ROOMS_AMBIGUOUS_RE = re.compile(
    r"\bde\s+cu[aá]ntas?\s+habitaciones\s+son\b",
    re.IGNORECASE,
)
_PRICE_LAST_RE = re.compile(
    r"\b(cu[aá]l|cual|que)\s+es\s+el\s+precio\s+de\s+la\s+[uú]ltima\s+casa\b",
    re.IGNORECASE,
)
_CLARIFY_REFERENCE_RE = re.compile(
    r"\b(primera|segunda|tercera|[uú]ltima|c[uú]al\s+casa|cu[aá]l\s+propiedad)\b",
    re.IGNORECASE,
)
_PRICE_VALUE_RE = re.compile(r"\b(usd|crc|₡|\$)\s*\d|(?:\d{1,3}(?:[.,]\d{3})+)", re.IGNORECASE)


@dataclass(slots=True)
class EventRecord:
    source_file: str
    line_no: int
    order: int
    payload: dict[str, Any]


@dataclass(slots=True)
class PlannerCase:
    case_id: str
    conversation_id: str
    order: int
    source_file: str
    source_line: int
    query_text: str
    history: list[dict[str, Any]]
    normalized_input: dict[str, Any]
    tenant_id: str
    vertical: str
    channel: str
    lead_id: str | None
    expected_output: dict[str, Any] | None


@dataclass(slots=True)
class SynthCase:
    case_id: str
    conversation_id: str
    order: int
    source_file: str
    source_line: int
    tenant_id: str
    vertical: str
    channel: str
    lead_id: str | None
    response_mode_hint: str
    goal_hint: str | None
    context_snapshot: dict[str, Any]
    tool_results_raw: list[Any]
    expected_output: dict[str, Any] | None


@dataclass(slots=True)
class RuleOutcome:
    rule: str
    passed: bool | None
    detail: str | None = None
    component: str = ""
    case_id: str = ""
    conversation_id: str = ""
    query_text: str = ""


@dataclass(slots=True)
class RuleStats:
    passed: int = 0
    failed: int = 0
    skipped: int = 0


@dataclass(slots=True)
class EvalSummary:
    planner_cases: int = 0
    synth_cases: int = 0
    planner_errors: int = 0
    synth_errors: int = 0
    guardrail_rejects: int = 0
    outcomes: list[RuleOutcome] = field(default_factory=list)


def _safe_json_load(line: str) -> dict[str, Any] | None:
    try:
        raw = json.loads(line)
    except Exception:
        return None
    return raw if isinstance(raw, dict) else None


def _iter_event_records(log_paths: list[Path]) -> list[EventRecord]:
    records: list[EventRecord] = []
    order = 0
    for path in sorted(log_paths):
        if not path.is_file():
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                raw = _safe_json_load(line)
                if not raw:
                    continue
                order += 1
                records.append(
                    EventRecord(
                        source_file=str(path),
                        line_no=line_no,
                        order=order,
                        payload=raw,
                    )
                )
    return records


def _pick_str(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text else default


def _extract_cases(records: list[EventRecord], *, conversation_filter: str | None = None) -> tuple[list[PlannerCase], list[SynthCase]]:
    planner_cases: list[PlannerCase] = []
    synth_cases: list[SynthCase] = []

    for rec in records:
        event = rec.payload
        event_type = _pick_str(event.get("event_type"))
        conversation_id = _pick_str(event.get("conversation_id"))
        if not conversation_id:
            continue
        if conversation_filter and conversation_id != conversation_filter:
            continue

        if event_type == "llm_exchange":
            if _pick_str(event.get("status"), "unknown") != "ok":
                continue
            component = _pick_str(event.get("component")).lower()
            request = event.get("request") or {}
            response = event.get("response") or {}
            context = event.get("context") or {}
            if not isinstance(request, dict) or not isinstance(response, dict) or not isinstance(context, dict):
                continue

            payload = request.get("payload") or {}
            if not isinstance(payload, dict):
                continue

            tenant_id = _pick_str(payload.get("tenant_id") or context.get("tenant_id"), "default")
            channel = _pick_str(payload.get("channel") or context.get("channel"), "web_html")
            lead_id = _pick_str(context.get("lead_id")) or None

            if component == "planner":
                normalized_input = payload.get("normalized_input") or {}
                if not isinstance(normalized_input, dict):
                    normalized_input = {}
                context_snapshot = payload.get("context_snapshot") or {}
                if not isinstance(context_snapshot, dict):
                    context_snapshot = {}
                query_text = _pick_str(payload.get("query_text") or payload.get("queryText") or normalized_input.get("last_user_turn"))
                history = payload.get("history") or []
                if not isinstance(history, list):
                    history = []
                vertical = _pick_str(
                    normalized_input.get("vertical")
                    or context_snapshot.get("vertical")
                    or context.get("vertical"),
                    "generic",
                )
                planner_cases.append(
                    PlannerCase(
                        case_id=f"planner-{conversation_id}-{rec.order}",
                        conversation_id=conversation_id,
                        order=rec.order,
                        source_file=rec.source_file,
                        source_line=rec.line_no,
                        query_text=query_text,
                        history=[item for item in history if isinstance(item, dict)],
                        normalized_input=normalized_input,
                        tenant_id=tenant_id,
                        vertical=vertical,
                        channel=channel,
                        lead_id=lead_id,
                        expected_output=response.get("json") if isinstance(response.get("json"), dict) else None,
                    )
                )
                continue

            if component == "synthesizer":
                response_mode_hint = _pick_str(payload.get("response_mode"), "text_only")
                vertical = _pick_str(
                    payload.get("context_snapshot", {}).get("vertical") if isinstance(payload.get("context_snapshot"), dict) else None
                ) or _pick_str(context.get("vertical"), "generic")
                synth_cases.append(
                    SynthCase(
                        case_id=f"synth-{conversation_id}-{rec.order}",
                        conversation_id=conversation_id,
                        order=rec.order,
                        source_file=rec.source_file,
                        source_line=rec.line_no,
                        tenant_id=tenant_id,
                        vertical=vertical or "generic",
                        channel=channel,
                        lead_id=lead_id,
                        response_mode_hint=response_mode_hint,
                        goal_hint=_pick_str(context.get("goal")) or None,
                        context_snapshot=payload.get("context_snapshot") if isinstance(payload.get("context_snapshot"), dict) else {},
                        tool_results_raw=payload.get("tool_results") if isinstance(payload.get("tool_results"), list) else [],
                        expected_output=response.get("json") if isinstance(response.get("json"), dict) else None,
                    )
                )
                continue

        if event_type == "turn_complete":
            trace_context = event.get("trace_context") or {}
            if not isinstance(trace_context, dict):
                trace_context = {}
            tenant_id = _pick_str(trace_context.get("tenant_id"), "default")
            channel = _pick_str(trace_context.get("channel"), "web_html")
            vertical = _pick_str(trace_context.get("vertical"), "generic")
            lead_id = _pick_str(trace_context.get("lead_id")) or None
            query_text = _pick_str(event.get("query_text"))
            state_json = event.get("state_json") if isinstance(event.get("state_json"), dict) else {}
            planner_output = event.get("planner_output") if isinstance(event.get("planner_output"), dict) else None
            synthesizer_output = (
                event.get("synthesizer_output") if isinstance(event.get("synthesizer_output"), dict) else None
            )
            tool_results = event.get("tool_results") if isinstance(event.get("tool_results"), list) else []

            normalized_input = {
                "conversation_summary": "",
                "vertical": vertical,
                "conversation_state": state_json,
                "last_user_turn": query_text,
                "context_snapshot": {
                    "vertical": vertical,
                    "conversation_state": state_json,
                },
            }
            planner_cases.append(
                PlannerCase(
                    case_id=f"planner-turn-{conversation_id}-{rec.order}",
                    conversation_id=conversation_id,
                    order=rec.order,
                    source_file=rec.source_file,
                    source_line=rec.line_no,
                    query_text=query_text,
                    history=[],
                    normalized_input=normalized_input,
                    tenant_id=tenant_id,
                    vertical=vertical,
                    channel=channel,
                    lead_id=lead_id,
                    expected_output=planner_output,
                )
            )
            synth_cases.append(
                SynthCase(
                    case_id=f"synth-turn-{conversation_id}-{rec.order}",
                    conversation_id=conversation_id,
                    order=rec.order,
                    source_file=rec.source_file,
                    source_line=rec.line_no,
                    tenant_id=tenant_id,
                    vertical=vertical,
                    channel=channel,
                    lead_id=lead_id,
                    response_mode_hint=_pick_str(
                        planner_output.get("response_mode") if isinstance(planner_output, dict) else None,
                        "text_only",
                    ),
                    goal_hint=_pick_str(planner_output.get("goal") if isinstance(planner_output, dict) else None) or None,
                    context_snapshot={
                        "vertical": vertical,
                        "conversation_state": state_json,
                    },
                    tool_results_raw=tool_results,
                    expected_output=synthesizer_output,
                )
            )
    return planner_cases, synth_cases


def _to_goal(value: Any) -> GoalType:
    try:
        return GoalType(str(value))
    except Exception:
        return GoalType.answer


def _to_response_mode(value: Any) -> ResponseMode:
    try:
        return ResponseMode(str(value))
    except Exception:
        return ResponseMode.text_only


def _count_sentences(text: str) -> int:
    parts = [item.strip() for item in _SENTENCE_RE.findall(str(text or "")) if item.strip()]
    return len(parts)


def _has_prior_context(context_snapshot: dict[str, Any]) -> bool:
    if not isinstance(context_snapshot, dict):
        return False

    conversation_state = context_snapshot.get("conversation_state")
    if isinstance(conversation_state, dict):
        presentation_state = conversation_state.get("presentation_state")
        if isinstance(presentation_state, dict) and bool(presentation_state.get("cards_shown_ever")):
            return True
        lead_progression_state = conversation_state.get("lead_progression_state")
        if isinstance(lead_progression_state, dict):
            if int(lead_progression_state.get("user_turn_count") or 0) >= 1:
                return True
            if int(lead_progression_state.get("assistant_turn_count") or 0) >= 1:
                return True

    recent_history = context_snapshot.get("recent_history")
    if isinstance(recent_history, list) and len(recent_history) > 0:
        return True

    return False


def _extract_known_name_from_context(context_snapshot: dict[str, Any]) -> str | None:
    if not isinstance(context_snapshot, dict):
        return None

    conversation_state = context_snapshot.get("conversation_state")
    if isinstance(conversation_state, dict):
        profile_state = conversation_state.get("profile_state")
        if isinstance(profile_state, dict):
            value = str(profile_state.get("name") or "").strip()
            if value:
                return value

    recent_history = context_snapshot.get("recent_history")
    if isinstance(recent_history, list):
        for item in reversed(recent_history):
            if not isinstance(item, dict):
                continue
            if str(item.get("role") or "").strip().lower() != "user":
                continue
            content = str(item.get("content") or "").strip()
            match = _NAME_DECLARATION_RE.search(content)
            if match:
                value = str(match.group(1) or "").strip()
                if value:
                    return value
    return None


def _property_card_count(context_snapshot: dict[str, Any]) -> int:
    if not isinstance(context_snapshot, dict):
        return 0
    last_answer = context_snapshot.get("last_answer_envelope")
    cards: Any = []
    if isinstance(last_answer, dict):
        cards = last_answer.get("cards")
    if not isinstance(cards, list) or not cards:
        conversation_state = context_snapshot.get("conversation_state")
        if isinstance(conversation_state, dict):
            presentation_state = conversation_state.get("presentation_state")
            if isinstance(presentation_state, dict):
                cards = presentation_state.get("last_property_cards")
    if not isinstance(cards, list):
        return 0
    return sum(1 for card in cards if isinstance(card, dict) and card.get("card_type") == "property_card")


def _tool_ids(tool_results: list[ToolResult]) -> tuple[set[str], int, int]:
    ids: set[str] = set()
    listings_count = 0
    rag_chunks_count = 0
    for item in tool_results:
        if item.realtor is not None:
            listings_count += len(item.realtor.listings)
            for listing in item.realtor.listings:
                if listing.listing_id:
                    ids.add(listing.listing_id)
        if item.rag is not None:
            rag_chunks_count += len(item.rag.chunks)
            for chunk in item.rag.chunks:
                if chunk.chunk_id:
                    ids.add(chunk.chunk_id)
                elif chunk.doc_id:
                    ids.add(chunk.doc_id)
        if item.workflow is not None and item.workflow.workflow_name:
            ids.add(item.workflow.workflow_name)
    return ids, listings_count, rag_chunks_count


def _context_evidence_ids(context_snapshot: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    if not isinstance(context_snapshot, dict):
        return ids

    last_tool_results = context_snapshot.get("last_tool_results")
    if isinstance(last_tool_results, list):
        for item in last_tool_results:
            if not isinstance(item, dict):
                continue
            rag = item.get("rag")
            if isinstance(rag, dict):
                chunks = rag.get("chunks")
                if isinstance(chunks, list):
                    for chunk in chunks:
                        if not isinstance(chunk, dict):
                            continue
                        chunk_id = str(chunk.get("chunk_id") or "").strip()
                        if chunk_id:
                            ids.add(chunk_id)
            realtor = item.get("realtor")
            if isinstance(realtor, dict):
                listings = realtor.get("listings")
                if isinstance(listings, list):
                    for listing in listings:
                        if not isinstance(listing, dict):
                            continue
                        listing_id = str(listing.get("listing_id") or "").strip()
                        if listing_id:
                            ids.add(listing_id)

    last_answer = context_snapshot.get("last_answer_envelope")
    if isinstance(last_answer, dict):
        evidence_ids = last_answer.get("evidence_ids")
        if isinstance(evidence_ids, list):
            for item in evidence_ids:
                token = str(item or "").strip()
                if token:
                    ids.add(token)
        cards = last_answer.get("cards")
        if isinstance(cards, list):
            for card in cards:
                if not isinstance(card, dict):
                    continue
                listing_id = str(card.get("listing_id") or "").strip()
                if listing_id:
                    ids.add(listing_id)

    conversation_state = context_snapshot.get("conversation_state")
    if isinstance(conversation_state, dict):
        presentation_state = conversation_state.get("presentation_state")
        if isinstance(presentation_state, dict):
            cards = presentation_state.get("last_property_cards")
            if isinstance(cards, list):
                for card in cards:
                    if not isinstance(card, dict):
                        continue
                    listing_id = str(card.get("listing_id") or "").strip()
                    if listing_id:
                        ids.add(listing_id)

    return ids


def _new_outcome(
    *,
    rule: str,
    passed: bool | None,
    detail: str | None,
    component: str,
    case_id: str,
    conversation_id: str,
    query_text: str = "",
) -> RuleOutcome:
    return RuleOutcome(
        rule=rule,
        passed=passed,
        detail=detail,
        component=component,
        case_id=case_id,
        conversation_id=conversation_id,
        query_text=query_text,
    )


async def _evaluate_planner_case(case: PlannerCase, *, replay: bool) -> tuple[RouterDecision | None, list[RuleOutcome], str | None]:
    outcomes: list[RuleOutcome] = []
    decision: RouterDecision | None = None
    error_message: str | None = None

    if replay:
        raw_input = {
            "queryText": case.query_text,
            "tenant_id": case.tenant_id,
            "vertical": case.vertical,
            "channel": case.channel,
            "conversationId": case.conversation_id,
        }
        if case.lead_id:
            raw_input["leadId"] = case.lead_id
        try:
            decision = await planner_service.run(
                raw_input=raw_input,
                normalized_input=case.normalized_input,
                history=case.history,
                conversation_id=case.conversation_id,
                lead_id=case.lead_id,
            )
        except Exception as exc:
            error_message = str(exc)
    else:
        try:
            decision = RouterDecision.model_validate(case.expected_output or {})
        except Exception as exc:
            error_message = f"logged_planner_output_invalid:{exc}"

    if decision is None:
        outcomes.append(
            _new_outcome(
                rule="planner.contract_valid",
                passed=False,
                detail=error_message or "planner_decision_missing",
                component="planner",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=case.query_text,
            )
        )
        return None, outcomes, error_message

    outcomes.append(
        _new_outcome(
            rule="planner.contract_valid",
            passed=True,
            detail=None,
            component="planner",
            case_id=case.case_id,
            conversation_id=case.conversation_id,
            query_text=case.query_text,
        )
    )

    if decision.goal == GoalType.clarify:
        passed = bool(decision.clarify_message and not decision.tool_calls and decision.response_mode == ResponseMode.text_only)
        outcomes.append(
            _new_outcome(
                rule="planner.clarify_contract",
                passed=passed,
                detail=None if passed else "clarify must include clarify_message, empty tool_calls, response_mode=text_only",
                component="planner",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=case.query_text,
            )
        )
    else:
        outcomes.append(
            _new_outcome(
                rule="planner.clarify_contract",
                passed=None,
                detail=None,
                component="planner",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=case.query_text,
            )
        )

    has_realtor_sql = any(call.tool_name == ToolName.realtor_sql for call in decision.tool_calls)
    if has_realtor_sql:
        passed = decision.response_mode == ResponseMode.text_plus_cards
        outcomes.append(
            _new_outcome(
                rule="planner.realtor_response_mode_alignment",
                passed=passed,
                detail=None if passed else "realtor_sql requires response_mode=text_plus_cards",
                component="planner",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=case.query_text,
            )
        )
    else:
        outcomes.append(
            _new_outcome(
                rule="planner.realtor_response_mode_alignment",
                passed=None,
                detail=None,
                component="planner",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=case.query_text,
            )
        )

    if _META_QUERY_RE.search(case.query_text):
        passed = decision.goal == GoalType.rag
        outcomes.append(
            _new_outcome(
                rule="planner.meta_query_to_rag",
                passed=passed,
                detail=None if passed else f"meta query routed to goal={decision.goal.value}",
                component="planner",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=case.query_text,
            )
        )
    else:
        outcomes.append(
            _new_outcome(
                rule="planner.meta_query_to_rag",
                passed=None,
                detail=None,
                component="planner",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=case.query_text,
            )
        )

    if _REFERENTIAL_QUERY_RE.search(case.query_text):
        passed = decision.goal not in {GoalType.realtor_search, GoalType.realtor_refine}
        outcomes.append(
            _new_outcome(
                rule="planner.referential_not_search",
                passed=passed,
                detail=None if passed else f"referential query routed to goal={decision.goal.value}",
                component="planner",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=case.query_text,
            )
        )
    else:
        outcomes.append(
            _new_outcome(
                rule="planner.referential_not_search",
                passed=None,
                detail=None,
                component="planner",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=case.query_text,
            )
        )

    context_snapshot = (
        case.normalized_input.get("context_snapshot")
        if isinstance(case.normalized_input, dict)
        else {}
    )
    if not isinstance(context_snapshot, dict):
        context_snapshot = {}

    if _NAME_DECLARATION_RE.search(case.query_text):
        passed = decision.goal == GoalType.answer and not decision.tool_calls
        outcomes.append(
            _new_outcome(
                rule="planner.business_name_declaration_routes_to_answer",
                passed=passed,
                detail=None if passed else f"expected answer/no_tools, got goal={decision.goal.value}",
                component="planner",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=case.query_text,
            )
        )
    else:
        outcomes.append(
            _new_outcome(
                rule="planner.business_name_declaration_routes_to_answer",
                passed=None,
                detail=None,
                component="planner",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=case.query_text,
            )
        )

    if _NAME_RECALL_RE.search(case.query_text):
        known_name = _extract_known_name_from_context(context_snapshot)
        if known_name:
            passed = decision.goal == GoalType.answer and not decision.tool_calls
            detail = None if passed else f"expected answer/no_tools for name recall with known name '{known_name}'"
        else:
            passed = None
            detail = "no known name in context"
        outcomes.append(
            _new_outcome(
                rule="planner.business_name_recall_routes_to_answer",
                passed=passed,
                detail=detail,
                component="planner",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=case.query_text,
            )
        )
    else:
        outcomes.append(
            _new_outcome(
                rule="planner.business_name_recall_routes_to_answer",
                passed=None,
                detail=None,
                component="planner",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=case.query_text,
            )
        )

    if _ROOMS_AMBIGUOUS_RE.search(case.query_text):
        cards_count = _property_card_count(context_snapshot)
        if cards_count > 1:
            passed = decision.goal == GoalType.clarify
            detail = None if passed else f"expected clarify for ambiguous rooms question, got {decision.goal.value}"
        else:
            passed = None
            detail = "single/no property card in context"
        outcomes.append(
            _new_outcome(
                rule="planner.business_ambiguous_rooms_routes_to_clarify",
                passed=passed,
                detail=detail,
                component="planner",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=case.query_text,
            )
        )
    else:
        outcomes.append(
            _new_outcome(
                rule="planner.business_ambiguous_rooms_routes_to_clarify",
                passed=None,
                detail=None,
                component="planner",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=case.query_text,
            )
        )

    if _PRICE_LAST_RE.search(case.query_text):
        passed = decision.goal == GoalType.answer and not decision.tool_calls
        outcomes.append(
            _new_outcome(
                rule="planner.business_last_price_routes_to_answer",
                passed=passed,
                detail=None if passed else f"expected answer/no_tools, got goal={decision.goal.value}",
                component="planner",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=case.query_text,
            )
        )
    else:
        outcomes.append(
            _new_outcome(
                rule="planner.business_last_price_routes_to_answer",
                passed=None,
                detail=None,
                component="planner",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=case.query_text,
            )
        )

    return decision, outcomes, None


def _tool_results_from_raw(raw_list: list[Any]) -> tuple[list[ToolResult], str | None]:
    items: list[ToolResult] = []
    for idx, raw in enumerate(raw_list):
        if not isinstance(raw, dict):
            return [], f"tool_results[{idx}] is not an object"
        try:
            items.append(ToolResult.model_validate(raw))
        except ValidationError as exc:
            return [], f"tool_results[{idx}] invalid: {exc}"
    return items, None


async def _evaluate_synth_case(
    case: SynthCase,
    *,
    planner_decision: RouterDecision | None,
    planner_query_text: str | None,
    planner_context_snapshot: dict[str, Any] | None,
    replay: bool,
) -> tuple[SynthesizerOutput | None, list[RuleOutcome], str | None, bool]:
    outcomes: list[RuleOutcome] = []
    synth_output: SynthesizerOutput | None = None
    error_message: str | None = None
    query_text = str(planner_query_text or "").strip()
    effective_context_snapshot = (
        planner_context_snapshot
        if isinstance(planner_context_snapshot, dict) and planner_context_snapshot
        else case.context_snapshot
    )

    goal = planner_decision.goal if planner_decision is not None else _to_goal(case.goal_hint)
    response_mode = (
        planner_decision.response_mode if planner_decision is not None else _to_response_mode(case.response_mode_hint)
    )

    tool_results, parse_error = _tool_results_from_raw(case.tool_results_raw)
    if parse_error:
        outcomes.append(
            _new_outcome(
                rule="synth.tool_results_parse_valid",
                passed=False,
                detail=parse_error,
                component="synthesizer",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=query_text,
            )
        )
        return None, outcomes, parse_error, False
    outcomes.append(
        _new_outcome(
            rule="synth.tool_results_parse_valid",
            passed=True,
            detail=None,
            component="synthesizer",
            case_id=case.case_id,
            conversation_id=case.conversation_id,
            query_text=query_text,
        )
    )

    # In replay mode, planner output is source of truth for whether tools run.
    # If the new planner routes to answer/clarify with no tool_calls, runtime would not execute tools.
    if replay and planner_decision is not None and not planner_decision.tool_calls:
        tool_results = []

    if planner_decision is not None and planner_decision.goal == GoalType.clarify:
        outcomes.append(
            _new_outcome(
                rule="synth.skipped_due_clarify_goal",
                passed=True,
                detail="planner routed to clarify; synthesizer stage not applicable",
                component="synthesizer",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=query_text,
            )
        )
        clarify_text = str(planner_decision.clarify_message or "")
        if query_text and _ROOMS_AMBIGUOUS_RE.search(query_text):
            cards_count = _property_card_count(effective_context_snapshot)
            if cards_count > 1:
                pass_rule = bool(_CLARIFY_REFERENCE_RE.search(clarify_text))
                outcomes.append(
                    _new_outcome(
                        rule="business.rooms_question_requires_reference_clarify",
                        passed=pass_rule,
                        detail=None if pass_rule else "expected clarification about which property",
                        component="planner",
                        case_id=case.case_id,
                        conversation_id=case.conversation_id,
                        query_text=query_text,
                    )
                )
            else:
                outcomes.append(
                    _new_outcome(
                        rule="business.rooms_question_requires_reference_clarify",
                        passed=None,
                        detail="single/no property card in context",
                        component="planner",
                        case_id=case.case_id,
                        conversation_id=case.conversation_id,
                        query_text=query_text,
                    )
                )
        else:
            outcomes.append(
                _new_outcome(
                    rule="business.rooms_question_requires_reference_clarify",
                    passed=None,
                    detail=None,
                    component="planner",
                    case_id=case.case_id,
                    conversation_id=case.conversation_id,
                    query_text=query_text,
                )
            )
        outcomes.append(
            _new_outcome(
                rule="business.name_declaration_greeting",
                passed=None,
                detail=None,
                component="planner",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=query_text,
            )
        )
        outcomes.append(
            _new_outcome(
                rule="business.name_recall_returns_name",
                passed=None,
                detail=None,
                component="planner",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=query_text,
            )
        )
        outcomes.append(
            _new_outcome(
                rule="business.last_property_price_remembered",
                passed=None,
                detail=None,
                component="planner",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=query_text,
            )
        )
        outcomes.append(
            _new_outcome(
                rule="guardrail.accepted",
                passed=True,
                detail="not_applicable_for_clarify",
                component="guardrail",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=query_text,
            )
        )
        return None, outcomes, None, False

    if replay:
        raw_input = {
            "tenant_id": case.tenant_id,
            "vertical": case.vertical,
            "channel": case.channel,
            "conversationId": case.conversation_id,
        }
        if case.lead_id:
            raw_input["leadId"] = case.lead_id
        try:
            synth_output = await synthesizer_service.run(
                tenant_id=case.tenant_id,
                raw_input=raw_input,
                tool_results=tool_results,
                goal=goal,
                response_mode=response_mode,
                context_snapshot=effective_context_snapshot,
                conversation_id=case.conversation_id,
                lead_id=case.lead_id,
            )
        except Exception as exc:
            error_message = str(exc)
    else:
        try:
            synth_output = SynthesizerOutput.model_validate(case.expected_output or {})
        except Exception as exc:
            error_message = f"logged_synth_output_invalid:{exc}"

    if synth_output is None:
        outcomes.append(
            _new_outcome(
                rule="synth.contract_valid",
                passed=False,
                detail=error_message or "synth_output_missing",
                component="synthesizer",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=query_text,
            )
        )
        return None, outcomes, error_message, False

    outcomes.append(
        _new_outcome(
            rule="synth.contract_valid",
            passed=True,
            detail=None,
            component="synthesizer",
            case_id=case.case_id,
            conversation_id=case.conversation_id,
            query_text=query_text,
        )
    )

    guardrail = run_answer_guardrail(
        goal=goal,
        synthesizer_output=synth_output,
        tool_results=tool_results,
        context_snapshot=effective_context_snapshot,
    )
    guardrail_pass = bool(guardrail.accepted)
    outcomes.append(
        _new_outcome(
            rule="guardrail.accepted",
            passed=guardrail_pass,
            detail=None if guardrail_pass else str(guardrail.reject_code.value if guardrail.reject_code else "unknown_reject"),
            component="guardrail",
            case_id=case.case_id,
            conversation_id=case.conversation_id,
            query_text=query_text,
        )
    )

    valid_ids, listings_count, rag_chunks_count = _tool_ids(tool_results)
    evidence_ids = [str(item).strip() for item in synth_output.evidence_ids if str(item).strip()]
    has_prior_context = _has_prior_context(effective_context_snapshot)
    text = str(synth_output.text or "")

    if response_mode == ResponseMode.text_only:
        passed = synth_output.needs_cards is False
    elif response_mode == ResponseMode.text_plus_cards and listings_count > 0:
        passed = synth_output.needs_cards is True
    else:
        passed = True
    outcomes.append(
        _new_outcome(
            rule="synth.response_mode_alignment",
            passed=passed,
            detail=None if passed else f"response_mode={response_mode.value} needs_cards={synth_output.needs_cards}",
            component="synthesizer",
            case_id=case.case_id,
            conversation_id=case.conversation_id,
            query_text=query_text,
        )
    )

    if listings_count > 0 and synth_output.needs_cards:
        two_sentences = _count_sentences(text) == 2
        outcomes.append(
            _new_outcome(
                rule="synth.cards_two_sentences",
                passed=two_sentences,
                detail=None if two_sentences else f"sentence_count={_count_sentences(text)}",
                component="synthesizer",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=query_text,
            )
        )
        permission_free = not bool(_PERMISSION_PHRASE_RE.search(text))
        outcomes.append(
            _new_outcome(
                rule="synth.cards_no_permission_phrase",
                passed=permission_free,
                detail=None if permission_free else "permission phrase detected when cards are already delivered",
                component="synthesizer",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=query_text,
            )
        )
    else:
        outcomes.append(
            _new_outcome(
                rule="synth.cards_two_sentences",
                passed=None,
                detail=None,
                component="synthesizer",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=query_text,
            )
        )
        outcomes.append(
            _new_outcome(
                rule="synth.cards_no_permission_phrase",
                passed=None,
                detail=None,
                component="synthesizer",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=query_text,
            )
        )

    if not tool_results:
        valid_ids.update(_context_evidence_ids(effective_context_snapshot))
    evidence_valid = all(item in valid_ids for item in evidence_ids)
    outcomes.append(
        _new_outcome(
            rule="synth.evidence_ids_valid",
            passed=evidence_valid,
            detail=None if evidence_valid else f"invalid_ids={sorted(set(evidence_ids) - valid_ids)}",
            component="synthesizer",
            case_id=case.case_id,
            conversation_id=case.conversation_id,
            query_text=query_text,
        )
    )

    if rag_chunks_count > 0:
        has_evidence = len(evidence_ids) > 0
        outcomes.append(
            _new_outcome(
                rule="synth.rag_evidence_not_empty",
                passed=has_evidence,
                detail=None if has_evidence else "rag chunks available but evidence_ids is empty",
                component="synthesizer",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=query_text,
            )
        )
    else:
        outcomes.append(
            _new_outcome(
                rule="synth.rag_evidence_not_empty",
                passed=None,
                detail=None,
                component="synthesizer",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=query_text,
            )
        )

    if rag_chunks_count > 0 and has_prior_context:
        no_restart = not bool(_RAG_RESTART_RE.search(text))
        outcomes.append(
            _new_outcome(
                rule="synth.rag_continuity_no_restart",
                passed=no_restart,
                detail=None if no_restart else "restart phrase detected in RAG turn with prior context",
                component="synthesizer",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=query_text,
            )
        )
    else:
        outcomes.append(
            _new_outcome(
                rule="synth.rag_continuity_no_restart",
                passed=None,
                detail=None,
                component="synthesizer",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=query_text,
            )
        )

    if query_text and _NAME_DECLARATION_RE.search(query_text):
        name_match = _NAME_DECLARATION_RE.search(query_text)
        declared_name = str(name_match.group(1) if name_match else "").strip()
        has_greeting = bool(_GREETING_RE.search(text))
        mentions_name = bool(declared_name) and declared_name.lower() in text.lower()
        outcomes.append(
            _new_outcome(
                rule="business.name_declaration_greeting",
                passed=(has_greeting and mentions_name),
                detail=None if (has_greeting and mentions_name) else "expected greeting including declared name",
                component="synthesizer",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=query_text,
            )
        )
    else:
        outcomes.append(
            _new_outcome(
                rule="business.name_declaration_greeting",
                passed=None,
                detail=None,
                component="synthesizer",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=query_text,
            )
        )

    if query_text and _NAME_RECALL_RE.search(query_text):
        known_name = _extract_known_name_from_context(effective_context_snapshot)
        if known_name:
            pass_rule = known_name.lower() in text.lower() and "no recuerdo" not in text.lower()
            detail = None if pass_rule else f"expected remembered name '{known_name}' in response"
        else:
            pass_rule = None
            detail = "no known name in context to assert"
        outcomes.append(
            _new_outcome(
                rule="business.name_recall_returns_name",
                passed=pass_rule,
                detail=detail,
                component="synthesizer",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=query_text,
            )
        )
    else:
        outcomes.append(
            _new_outcome(
                rule="business.name_recall_returns_name",
                passed=None,
                detail=None,
                component="synthesizer",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=query_text,
            )
        )

    if query_text and _ROOMS_AMBIGUOUS_RE.search(query_text):
        cards_count = _property_card_count(effective_context_snapshot)
        if cards_count > 1:
            pass_rule = bool(_CLARIFY_REFERENCE_RE.search(text))
            detail = None if pass_rule else "expected clarification about which property"
        else:
            pass_rule = None
            detail = "single/no property card in context"
        outcomes.append(
            _new_outcome(
                rule="business.rooms_question_requires_reference_clarify",
                passed=pass_rule,
                detail=detail,
                component="synthesizer",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=query_text,
            )
        )
    else:
        outcomes.append(
            _new_outcome(
                rule="business.rooms_question_requires_reference_clarify",
                passed=None,
                detail=None,
                component="synthesizer",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=query_text,
            )
        )

    if query_text and _PRICE_LAST_RE.search(query_text):
        pass_rule = bool(_PRICE_VALUE_RE.search(text)) and "no puedo" not in text.lower() and "no recuerdo" not in text.lower()
        outcomes.append(
            _new_outcome(
                rule="business.last_property_price_remembered",
                passed=pass_rule,
                detail=None if pass_rule else "expected concrete remembered price for referenced last property",
                component="synthesizer",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=query_text,
            )
        )
    else:
        outcomes.append(
            _new_outcome(
                rule="business.last_property_price_remembered",
                passed=None,
                detail=None,
                component="synthesizer",
                case_id=case.case_id,
                conversation_id=case.conversation_id,
                query_text=query_text,
            )
        )

    return synth_output, outcomes, None, not guardrail_pass


def _build_rule_stats(outcomes: list[RuleOutcome]) -> dict[str, RuleStats]:
    stats: dict[str, RuleStats] = defaultdict(RuleStats)
    for item in outcomes:
        rule_stats = stats[item.rule]
        if item.passed is None:
            rule_stats.skipped += 1
        elif item.passed:
            rule_stats.passed += 1
        else:
            rule_stats.failed += 1
    return dict(stats)


def _serialize_stats(stats: dict[str, RuleStats]) -> dict[str, Any]:
    serialized: dict[str, Any] = {}
    for rule, row in sorted(stats.items()):
        applicable = row.passed + row.failed
        pass_rate = (row.passed / applicable) if applicable > 0 else None
        serialized[rule] = {
            "passed": row.passed,
            "failed": row.failed,
            "skipped": row.skipped,
            "applicable": applicable,
            "pass_rate": pass_rate,
        }
    return serialized


def _print_summary(summary: EvalSummary, stats: dict[str, RuleStats], *, replay: bool) -> None:
    print("")
    print("== Eval Runner Summary ==")
    print(f"Mode: {'replay' if replay else 'logged'}")
    print(f"Planner cases: {summary.planner_cases} (errors: {summary.planner_errors})")
    print(f"Synth cases: {summary.synth_cases} (errors: {summary.synth_errors})")
    print(f"Guardrail rejects: {summary.guardrail_rejects}")
    print("")
    print("Rule compliance:")
    for rule, row in sorted(stats.items()):
        applicable = row.passed + row.failed
        if applicable <= 0:
            rate = "n/a"
        else:
            rate = f"{(row.passed / applicable) * 100:.1f}%"
        print(
            f"- {rule}: pass={row.passed} fail={row.failed} skip={row.skipped} pass_rate={rate}"
        )

    failures = [item for item in summary.outcomes if item.passed is False]
    if failures:
        print("")
        print("Top failures:")
        for item in failures[:15]:
            detail = f" | {item.detail}" if item.detail else ""
            query = f" | query={item.query_text}" if item.query_text else ""
            print(
                f"- [{item.component}] {item.rule} | conv={item.conversation_id} | case={item.case_id}{query}{detail}"
            )


async def run_eval(
    *,
    log_dir: Path,
    pattern: str,
    conversation_id: str | None,
    max_cases: int | None,
    replay: bool,
    output_path: Path | None,
) -> dict[str, Any]:
    log_paths = sorted(log_dir.glob(pattern))
    records = _iter_event_records(log_paths)
    planner_cases, synth_cases = _extract_cases(records, conversation_filter=conversation_id)

    planner_cases = sorted(planner_cases, key=lambda item: item.order)
    synth_cases = sorted(synth_cases, key=lambda item: item.order)

    if max_cases is not None and max_cases > 0:
        planner_cases = planner_cases[:max_cases]
        synth_cases = synth_cases[:max_cases]

    summary = EvalSummary(
        planner_cases=len(planner_cases),
        synth_cases=len(synth_cases),
    )

    planner_decisions_by_conversation: dict[str, list[tuple[int, RouterDecision, PlannerCase]]] = defaultdict(list)
    for case in planner_cases:
        decision, outcomes, planner_error = await _evaluate_planner_case(case, replay=replay)
        summary.outcomes.extend(outcomes)
        if planner_error:
            summary.planner_errors += 1
            continue
        if decision is not None:
            planner_decisions_by_conversation[case.conversation_id].append((case.order, decision, case))

    for conversation, items in planner_decisions_by_conversation.items():
        items.sort(key=lambda row: row[0])
        planner_decisions_by_conversation[conversation] = items

    for case in synth_cases:
        planner_decision: RouterDecision | None = None
        planner_case: PlannerCase | None = None
        prior_decisions = planner_decisions_by_conversation.get(case.conversation_id, [])
        for order, decision, source_case in prior_decisions:
            if order <= case.order:
                planner_decision = decision
                planner_case = source_case
            else:
                break
        synth_output, outcomes, synth_error, guardrail_reject = await _evaluate_synth_case(
            case,
            planner_decision=planner_decision,
            planner_query_text=(planner_case.query_text if planner_case is not None else None),
            planner_context_snapshot=(
                planner_case.normalized_input.get("context_snapshot")
                if planner_case is not None and isinstance(planner_case.normalized_input, dict)
                else None
            ),
            replay=replay,
        )
        _ = synth_output
        summary.outcomes.extend(outcomes)
        if synth_error:
            summary.synth_errors += 1
        if guardrail_reject:
            summary.guardrail_rejects += 1

    stats = _build_rule_stats(summary.outcomes)
    _print_summary(summary, stats, replay=replay)

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "replay" if replay else "logged",
        "input": {
            "log_dir": str(log_dir),
            "pattern": pattern,
            "conversation_id": conversation_id,
            "max_cases": max_cases,
            "files": [str(item) for item in log_paths],
            "files_count": len(log_paths),
            "events_count": len(records),
            "planner_cases_count": len(planner_cases),
            "synth_cases_count": len(synth_cases),
        },
        "summary": {
            "planner_cases": summary.planner_cases,
            "synth_cases": summary.synth_cases,
            "planner_errors": summary.planner_errors,
            "synth_errors": summary.synth_errors,
            "guardrail_rejects": summary.guardrail_rejects,
        },
        "rule_stats": _serialize_stats(stats),
        "failed_rules": [
            {
                "rule": item.rule,
                "component": item.component,
                "conversation_id": item.conversation_id,
                "case_id": item.case_id,
                "query_text": item.query_text,
                "detail": item.detail,
            }
            for item in summary.outcomes
            if item.passed is False
        ],
    }

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print("")
        print(f"Report written to: {output_path}")

    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Eval runner for agent-core prompts. "
            "Reads JSONL logs, replays planner/synthesizer, and reports rule compliance."
        )
    )
    parser.add_argument(
        "--log-dir",
        default="/app/log",
        help="Directory containing *.jsonl trace logs (default: /app/log).",
    )
    parser.add_argument(
        "--pattern",
        default="*.jsonl",
        help="Glob pattern for log files (default: *.jsonl).",
    )
    parser.add_argument(
        "--conversation-id",
        default=None,
        help="Optional conversation id filter.",
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=None,
        help="Optional max number of planner/synth cases to evaluate.",
    )
    parser.add_argument(
        "--logged-only",
        action="store_true",
        help="Use logged planner/synth outputs instead of replaying LLM calls.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional path to write a JSON report.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    log_dir = Path(args.log_dir)
    if not log_dir.exists():
        raise SystemExit(f"log directory not found: {log_dir}")
    output_path = Path(args.output) if args.output else None
    asyncio.run(
        run_eval(
            log_dir=log_dir,
            pattern=args.pattern,
            conversation_id=args.conversation_id,
            max_cases=args.max_cases,
            replay=not bool(args.logged_only),
            output_path=output_path,
        )
    )


if __name__ == "__main__":
    main()
