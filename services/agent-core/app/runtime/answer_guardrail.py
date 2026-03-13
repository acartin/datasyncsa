from __future__ import annotations

from app.models.contracts import (
    GuardrailRejectCode,
    GuardrailResult,
    GoalType,
    RAGChunk,
    RealtorSQLResult,
    SynthesizerOutput,
    ToolResult,
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


def run_answer_guardrail(
    *,
    goal: GoalType,
    synthesizer_output: SynthesizerOutput | None,
    tool_results: list[ToolResult],
) -> GuardrailResult:
    if goal == GoalType.clarify:
        return GuardrailResult(accepted=True)

    if not synthesizer_output:
        return GuardrailResult(accepted=False, reject_code=GuardrailRejectCode.schema_violation)

    if not synthesizer_output.text.strip():
        return GuardrailResult(accepted=False, reject_code=GuardrailRejectCode.claim_without_source)

    valid_ids = _tool_result_ids(tool_results)
    claimed_ids = [i for i in synthesizer_output.evidence_ids if i]
    if claimed_ids and not all(item in valid_ids for item in claimed_ids):
        return GuardrailResult(accepted=False, reject_code=GuardrailRejectCode.hallucinated_listing_id)

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
