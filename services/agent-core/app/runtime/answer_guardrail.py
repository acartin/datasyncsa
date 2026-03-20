from __future__ import annotations

import logging
import re
from typing import Any

from app.models.contracts import (
    GuardrailRejectCode,
    GuardrailResult,
    GoalType,
    SynthesizerOutput,
    ToolResult,
)

logger = logging.getLogger(__name__)
RAG_AUTOFILL_MAX_EVIDENCE_IDS = 2
RAG_CONTINUITY_FALLBACK_QUESTION = "Para afinar opciones, ¿qué presupuesto y plazo de compra manejas?"
RAG_RESTART_PATTERN = re.compile(
    r"(¿\s*(en|como)\s+qu[eé]\s+puedo\s+ayudarte\s+hoy\??)\s*$",
    re.IGNORECASE,
)
NAME_DECLARATION_PATTERN = re.compile(
    r"\bme\s+llamo\s+([A-Za-zÁÉÍÓÚÑáéíóúñ][A-Za-zÁÉÍÓÚÑáéíóúñ'`\-]*)\b",
    re.IGNORECASE,
)
NAME_RECALL_PATTERN = re.compile(
    r"\brecuerd(?:as|a)\s+c[oó]mo\s+me\s+llamo\b",
    re.IGNORECASE,
)
ROOMS_AMBIGUOUS_PATTERN = re.compile(
    r"\bde\s+cu[aá]ntas?\s+habitaciones\s+son\b",
    re.IGNORECASE,
)
PRICE_QUERY_PATTERN = re.compile(
    r"\b(cu[aá]l|cual|que)\s+es\s+el\s+precio\b",
    re.IGNORECASE,
)
REFERENCE_LAST_PATTERN = re.compile(r"\b(la\s+[uú]ltima|ultima|última)\b", re.IGNORECASE)
REFERENCE_FIRST_PATTERN = re.compile(r"\b(la\s+primera|primera)\b", re.IGNORECASE)
REFERENCE_SECOND_PATTERN = re.compile(r"\b(la\s+segunda|segunda)\b", re.IGNORECASE)
REFERENCE_THIRD_PATTERN = re.compile(r"\b(la\s+tercera|tercera)\b", re.IGNORECASE)
REFERENCE_PRONOUN_PATTERN = re.compile(r"\b(esa|esta)\b", re.IGNORECASE)
CARD_PERMISSION_PATTERN = re.compile(
    r"(te\s+gustar[ií]a\s+ver|prefieres\s+que\s+te\s+muestre|quieres\s+ver\s+algunas\s+opciones|"
    r"te\s+gustar[ií]a\s+filtrar|te\s+gustar[ií]a\s+que\s+busquemos|te\s+gustar[ií]a\s+que\s+te\s+muestre)",
    re.IGNORECASE,
)
CARD_FALLBACK_NEXT_STEP_QUESTION = (
    "¿Quieres que te comparta más opciones similares o prefieres que agendemos una visita?"
)


def _tool_result_ids(tool_results: list[ToolResult]) -> set[str]:
    ids: set[str] = set()
    for tr in tool_results:
        if tr.rag:
            for chunk in tr.rag.chunks:
                if chunk.chunk_id:
                    ids.add(chunk.chunk_id)
        if tr.realtor:
            for listing in tr.realtor.listings:
                if listing.listing_id:
                    ids.add(listing.listing_id)
            if tr.realtor.sql_executed:
                ids.add(tr.realtor.sql_executed)
        if tr.workflow and tr.workflow.success and tr.workflow.output:
            ids.add(tr.workflow.workflow_name)
    return ids


def _rag_chunk_ids(tool_results: list[ToolResult]) -> list[str]:
    seen: set[str] = set()
    ordered_ids: list[str] = []
    for tr in tool_results:
        if tr.status != "ok" or tr.rag is None:
            continue
        for chunk in tr.rag.chunks:
            chunk_id = str(chunk.chunk_id or "").strip()
            if not chunk_id or chunk_id in seen:
                continue
            seen.add(chunk_id)
            ordered_ids.append(chunk_id)
    return ordered_ids


def _context_evidence_ids(context_snapshot: dict[str, Any] | None) -> set[str]:
    ids: set[str] = set()
    if not isinstance(context_snapshot, dict):
        return ids

    raw_tool_results = context_snapshot.get("last_tool_results")
    if isinstance(raw_tool_results, list):
        for item in raw_tool_results:
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
                sql_executed = str(realtor.get("sql_executed") or "").strip()
                if sql_executed:
                    ids.add(sql_executed)
            workflow = item.get("workflow")
            if isinstance(workflow, dict):
                workflow_name = str(workflow.get("workflow_name") or "").strip()
                if workflow_name:
                    ids.add(workflow_name)

    last_envelope = context_snapshot.get("last_answer_envelope")
    if isinstance(last_envelope, dict):
        evidence_ids = last_envelope.get("evidence_ids")
        if evidence_ids is None:
            evidence_ids = last_envelope.get("evidenceIds")
        if isinstance(evidence_ids, list):
            for item in evidence_ids:
                token = str(item or "").strip()
                if token:
                    ids.add(token)
        cards = last_envelope.get("cards")
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
            cached_cards = presentation_state.get("last_property_cards")
            if isinstance(cached_cards, list):
                for card in cached_cards:
                    if not isinstance(card, dict):
                        continue
                    listing_id = str(card.get("listing_id") or "").strip()
                    if listing_id:
                        ids.add(listing_id)

    return ids


def _is_realtor_empty_result(tool_results: list[ToolResult]) -> bool:
    realtor_seen = False
    for tr in tool_results:
        if tr.realtor is None:
            continue
        realtor_seen = True
        if tr.status != "ok":
            return False
        if tr.realtor.listings:
            return False
    return realtor_seen


def _has_realtor_listings(tool_results: list[ToolResult]) -> bool:
    for tr in tool_results:
        if tr.status == "ok" and tr.realtor is not None and tr.realtor.listings:
            return True
    return False


def _has_prior_context(context_snapshot: dict[str, Any] | None) -> bool:
    if not isinstance(context_snapshot, dict):
        return False

    recent_history = context_snapshot.get("recent_history")
    if isinstance(recent_history, list) and len(recent_history) > 0:
        return True

    conversation_state = context_snapshot.get("conversation_state")
    if not isinstance(conversation_state, dict):
        return False

    presentation_state = conversation_state.get("presentation_state")
    if isinstance(presentation_state, dict):
        if bool(presentation_state.get("cards_shown_ever")):
            return True

    lead_progression_state = conversation_state.get("lead_progression_state")
    if isinstance(lead_progression_state, dict):
        if int(lead_progression_state.get("user_turn_count") or 0) >= 1:
            return True
        if int(lead_progression_state.get("assistant_turn_count") or 0) >= 1:
            return True

    return False


def _is_rag_turn(tool_results: list[ToolResult]) -> bool:
    for tr in tool_results:
        if tr.status == "ok" and tr.rag is not None:
            return True
    return False


def _rewrite_rag_restart_phrase(text: str) -> str:
    if RAG_RESTART_PATTERN.search(text):
        return RAG_RESTART_PATTERN.sub(RAG_CONTINUITY_FALLBACK_QUESTION, text).strip()
    return text


def _last_user_turn(context_snapshot: dict[str, Any] | None) -> str:
    if not isinstance(context_snapshot, dict):
        return ""
    return str(context_snapshot.get("last_user_turn") or "").strip()


def _extract_known_name(context_snapshot: dict[str, Any] | None) -> str | None:
    if not isinstance(context_snapshot, dict):
        return None

    conversation_state = context_snapshot.get("conversation_state")
    if isinstance(conversation_state, dict):
        profile_state = conversation_state.get("profile_state")
        if isinstance(profile_state, dict):
            token = str(profile_state.get("name") or "").strip()
            if token:
                return token

    recent_history = context_snapshot.get("recent_history")
    if isinstance(recent_history, list):
        for item in reversed(recent_history):
            if not isinstance(item, dict):
                continue
            if str(item.get("role") or "").strip().lower() != "user":
                continue
            content = str(item.get("content") or "").strip()
            match = NAME_DECLARATION_PATTERN.search(content)
            if not match:
                continue
            name = str(match.group(1) or "").strip()
            if name:
                return name
    return None


def _property_cards_from_context(context_snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(context_snapshot, dict):
        return []
    last_answer = context_snapshot.get("last_answer_envelope")
    if not isinstance(last_answer, dict):
        cards = []
    else:
        cards = last_answer.get("cards")
    if not isinstance(cards, list):
        cards = []
    if not cards:
        conversation_state = context_snapshot.get("conversation_state")
        if isinstance(conversation_state, dict):
            presentation_state = conversation_state.get("presentation_state")
            if isinstance(presentation_state, dict):
                fallback_cards = presentation_state.get("last_property_cards")
                if isinstance(fallback_cards, list):
                    cards = fallback_cards
    output: list[dict[str, Any]] = []
    for card in cards:
        if isinstance(card, dict) and card.get("card_type") == "property_card":
            output.append(card)
    return output


def _resolve_reference_index(query_text: str, cards: list[dict[str, Any]]) -> int | None:
    if not cards:
        return None
    if REFERENCE_LAST_PATTERN.search(query_text):
        return len(cards) - 1
    if REFERENCE_FIRST_PATTERN.search(query_text):
        return 0
    if REFERENCE_SECOND_PATTERN.search(query_text):
        return 1 if len(cards) >= 2 else None
    if REFERENCE_THIRD_PATTERN.search(query_text):
        return 2 if len(cards) >= 3 else None
    if REFERENCE_PRONOUN_PATTERN.search(query_text):
        return len(cards) - 1
    return None


def _rewrite_cards_permission_phrase(text: str) -> str:
    if not CARD_PERMISSION_PATTERN.search(text):
        return text
    first_sentence = str(text or "").strip()
    for sep in (".", "?", "!"):
        index = first_sentence.find(sep)
        if index != -1:
            first_sentence = first_sentence[: index + 1].strip()
            break
    if not first_sentence:
        first_sentence = "Te comparto las opciones disponibles."
    if first_sentence[-1] not in ".!?":
        first_sentence = f"{first_sentence}."
    return f"{first_sentence} {CARD_FALLBACK_NEXT_STEP_QUESTION}"


def _apply_memory_reference_rewrites(
    *,
    synthesizer_output: SynthesizerOutput,
    context_snapshot: dict[str, Any] | None,
) -> None:
    query_text = _last_user_turn(context_snapshot)
    if not query_text:
        return

    name_decl = NAME_DECLARATION_PATTERN.search(query_text)
    if name_decl:
        user_name = str(name_decl.group(1) or "").strip()
        if user_name:
            synthesizer_output.text = (
                f"Mucho gusto, {user_name}. ¿Qué tipo de propiedad te gustaría buscar?"
            )
            return

    if NAME_RECALL_PATTERN.search(query_text):
        known_name = _extract_known_name(context_snapshot)
        if known_name:
            synthesizer_output.text = f"Sí, te llamas {known_name}."
            return

    cards = _property_cards_from_context(context_snapshot)
    if not cards:
        return

    has_reference = (
        REFERENCE_LAST_PATTERN.search(query_text)
        or REFERENCE_FIRST_PATTERN.search(query_text)
        or REFERENCE_SECOND_PATTERN.search(query_text)
        or REFERENCE_THIRD_PATTERN.search(query_text)
        or REFERENCE_PRONOUN_PATTERN.search(query_text)
    )
    if ROOMS_AMBIGUOUS_PATTERN.search(query_text) and not has_reference and len(cards) > 1:
        synthesizer_output.text = "¿Te refieres a la primera, segunda o última casa que te mostré?"
        return

    if PRICE_QUERY_PATTERN.search(query_text):
        reference_index = _resolve_reference_index(query_text, cards)
        if reference_index is None or reference_index < 0 or reference_index >= len(cards):
            return
        card = cards[reference_index]
        price_display = str(card.get("price_display") or "").strip()
        if not price_display:
            return
        synthesizer_output.text = f"La propiedad que me indicaste tiene un precio de {price_display}."
        listing_id = str(card.get("listing_id") or "").strip()
        if listing_id and listing_id not in synthesizer_output.evidence_ids:
            synthesizer_output.evidence_ids = [*synthesizer_output.evidence_ids, listing_id]


def run_answer_guardrail(
    *,
    goal: GoalType,
    synthesizer_output: SynthesizerOutput | None,
    tool_results: list[ToolResult],
    context_snapshot: dict[str, Any] | None = None,
) -> GuardrailResult:
    if goal == GoalType.clarify:
        return GuardrailResult(accepted=True)

    if not synthesizer_output:
        return GuardrailResult(accepted=False, reject_code=GuardrailRejectCode.schema_violation)

    if not synthesizer_output.text.strip():
        return GuardrailResult(accepted=False, reject_code=GuardrailRejectCode.claim_without_source)

    _apply_memory_reference_rewrites(
        synthesizer_output=synthesizer_output,
        context_snapshot=context_snapshot,
    )
    if not _has_realtor_listings(tool_results):
        synthesizer_output.needs_cards = False
    if synthesizer_output.needs_cards:
        synthesizer_output.text = _rewrite_cards_permission_phrase(synthesizer_output.text.strip())

    # En turnos RAG con continuidad previa, evita cierres de "reinicio"
    # que rompen el hilo conversacional.
    if (
        goal == GoalType.rag
        and _is_rag_turn(tool_results)
        and _has_prior_context(context_snapshot)
    ):
        rewritten_text = _rewrite_rag_restart_phrase(synthesizer_output.text.strip())
        if rewritten_text != synthesizer_output.text.strip():
            logger.warning(
                "rag_continuity_rewrite_applied original=%r rewritten=%r",
                synthesizer_output.text,
                rewritten_text,
            )
            synthesizer_output.text = rewritten_text

    valid_ids = _tool_result_ids(tool_results)
    # Referential turns can legitimately cite evidence from the previous answer
    # even when no tools are executed in the current turn.
    if not tool_results:
        valid_ids.update(_context_evidence_ids(context_snapshot))

    claimed_ids = [i for i in synthesizer_output.evidence_ids if i]
    if claimed_ids and not all(item in valid_ids for item in claimed_ids):
        return GuardrailResult(accepted=False, reject_code=GuardrailRejectCode.hallucinated_listing_id)

    # Fallback de formato para RAG: si el LLM omitió evidencia, adjuntamos
    # solo los primeros chunk_ids válidos del turno actual.
    if goal == GoalType.rag and tool_results and not claimed_ids:
        rag_ids = _rag_chunk_ids(tool_results)
        autofill_ids = rag_ids[:RAG_AUTOFILL_MAX_EVIDENCE_IDS]
        if autofill_ids:
            synthesizer_output.evidence_ids = list(autofill_ids)
            claimed_ids = list(autofill_ids)
            logger.warning(
                "rag_evidence_autofilled ids=%s total_rag_chunks=%s",
                autofill_ids,
                len(rag_ids),
            )

    if (
        tool_results
        and not claimed_ids
        and goal in {GoalType.rag, GoalType.realtor_search, GoalType.realtor_refine, GoalType.workflow}
    ):
        if goal in {GoalType.realtor_search, GoalType.realtor_refine} and _is_realtor_empty_result(tool_results):
            return GuardrailResult(accepted=True)
        return GuardrailResult(accepted=False, reject_code=GuardrailRejectCode.no_evidence_cited)

    if tool_results:
        if any(tr.status != "ok" and tr.error for tr in tool_results):
            if not claimed_ids:
                return GuardrailResult(accepted=False, reject_code=GuardrailRejectCode.claim_without_source)

    return GuardrailResult(accepted=True)
