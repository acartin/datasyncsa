from __future__ import annotations

import json
from typing import Any

from app.core.config import settings
from app.core.llm_client import llm_service
from app.core.llm_contract_normalizer import normalize_synthesizer_output
from app.core.prompt_service import prompt_service
from app.models.contracts import (
    GoalType,
    PropertyListing,
    RAGChunk,
    RAGResult,
    RealtorSQLResult,
    ResponseMode,
    SynthesizerInput,
    SynthesizerOutput,
    ToolResult,
    WorkflowResult,
)


def _truncate_text(value: Any, *, max_chars: int) -> str:
    text = str(value or "").strip()
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    if max_chars <= 3:
        return text[:max_chars]
    return text[: max_chars - 3].rstrip() + "..."


def _compact_value(value: Any, *, max_chars: int) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _truncate_text(value, max_chars=max_chars)
    if isinstance(value, (dict, list)):
        try:
            packed = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        except Exception:
            packed = str(value)
        return _truncate_text(packed, max_chars=max_chars)
    return _truncate_text(value, max_chars=max_chars)


def _compact_workflow_output(output: dict[str, Any], *, max_items: int, max_chars: int) -> dict[str, Any]:
    if not isinstance(output, dict) or not output:
        return {}

    compacted: dict[str, Any] = {}
    for idx, (raw_key, raw_value) in enumerate(output.items()):
        if idx >= max_items:
            break
        key = _truncate_text(raw_key, max_chars=max_chars) or f"item_{idx}"
        compacted[key] = _compact_value(raw_value, max_chars=max_chars)
    return compacted


def _compact_state_object(
    value: Any,
    *,
    max_depth: int,
    max_items: int,
    max_chars: int,
) -> Any:
    if max_depth <= 0:
        return None
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _truncate_text(value, max_chars=max_chars)
    if isinstance(value, list):
        compacted_list: list[Any] = []
        for item in value[:max_items]:
            compacted_list.append(
                _compact_state_object(
                    item,
                    max_depth=max_depth - 1,
                    max_items=max_items,
                    max_chars=max_chars,
                )
            )
        return compacted_list
    if isinstance(value, dict):
        compacted_dict: dict[str, Any] = {}
        for idx, (raw_key, raw_value) in enumerate(value.items()):
            if idx >= max_items:
                break
            key = _truncate_text(raw_key, max_chars=max_chars) or f"item_{idx}"
            compacted_dict[key] = _compact_state_object(
                raw_value,
                max_depth=max_depth - 1,
                max_items=max_items,
                max_chars=max_chars,
            )
        return compacted_dict
    return _truncate_text(value, max_chars=max_chars)


def _compact_context_snapshot(context_snapshot: dict[str, Any]) -> dict[str, Any]:
    max_chars = max(300, int(settings.synth_context_max_chars))
    summary_limit = max(120, max_chars // 4)
    state_limit = max(120, max_chars // 3)
    state_object = context_snapshot.get("conversation_state")
    if not isinstance(state_object, dict):
        state_object = {}

    compacted = {
        "conversation_summary": _truncate_text(
            context_snapshot.get("conversation_summary"),
            max_chars=summary_limit,
        ),
        "vertical": _truncate_text(context_snapshot.get("vertical"), max_chars=64),
        "conversation_state": _compact_state_object(
            state_object,
            max_depth=6,
            max_items=20,
            max_chars=state_limit,
        ),
    }
    serialized = json.dumps(compacted, ensure_ascii=False, separators=(",", ":"))
    if len(serialized) <= max_chars:
        return compacted
    compacted["conversation_summary"] = _truncate_text(compacted.get("conversation_summary"), max_chars=max(64, summary_limit // 2))
    compacted["conversation_state"] = _compact_state_object(
        state_object,
        max_depth=4,
        max_items=10,
        max_chars=max(64, state_limit // 2),
    )
    return compacted


def _compact_tool_results(tool_results: list[ToolResult]) -> list[ToolResult]:
    string_max_chars = max(40, int(settings.synth_string_max_chars))
    rag_chunk_limit = max(1, int(settings.synth_rag_chunk_limit))
    rag_chunk_max_chars = max(80, int(settings.synth_rag_chunk_max_chars))
    realtor_listing_limit = max(1, int(settings.synth_realtor_listing_limit))
    realtor_features_limit = max(0, int(settings.synth_realtor_features_limit))
    realtor_images_limit = max(0, int(settings.synth_realtor_images_per_listing))
    workflow_output_items = max(1, int(settings.synth_workflow_output_items))

    compacted_results: list[ToolResult] = []
    for result in tool_results:
        compacted = ToolResult(
            tool_name=result.tool_name,
            status=result.status,
            error_code=result.error_code,
            error=_truncate_text(result.error, max_chars=string_max_chars) or None,
        )

        if result.rag is not None:
            rag_chunks: list[RAGChunk] = []
            for chunk in result.rag.chunks[:rag_chunk_limit]:
                rag_chunks.append(
                    RAGChunk(
                        chunk_id=_truncate_text(chunk.chunk_id, max_chars=string_max_chars),
                        doc_id=_truncate_text(chunk.doc_id, max_chars=string_max_chars),
                        content=_truncate_text(chunk.content, max_chars=rag_chunk_max_chars),
                        score=float(chunk.score),
                        source_url=_truncate_text(chunk.source_url, max_chars=string_max_chars * 3) or None,
                    )
                )
            compacted.rag = RAGResult(
                chunks=rag_chunks,
                query_used=_truncate_text(result.rag.query_used, max_chars=string_max_chars),
            )

        if result.realtor is not None:
            listings: list[PropertyListing] = []
            for listing in result.realtor.listings[:realtor_listing_limit]:
                listings.append(
                    PropertyListing(
                        listing_id=_truncate_text(listing.listing_id, max_chars=string_max_chars),
                        title=_truncate_text(listing.title, max_chars=string_max_chars * 2),
                        city=_truncate_text(listing.city, max_chars=string_max_chars),
                        neighborhood=_truncate_text(listing.neighborhood, max_chars=string_max_chars) or None,
                        price=int(listing.price),
                        currency=_truncate_text(listing.currency, max_chars=12) or "USD",
                        rooms=listing.rooms,
                        area_m2=listing.area_m2,
                        property_type=_truncate_text(listing.property_type, max_chars=string_max_chars) or "generic",
                        features=[
                            _truncate_text(feature, max_chars=string_max_chars)
                            for feature in listing.features[:realtor_features_limit]
                        ],
                        image_urls=[
                            _truncate_text(url, max_chars=string_max_chars * 3)
                            for url in listing.image_urls[:realtor_images_limit]
                        ],
                        listing_url=_truncate_text(listing.listing_url, max_chars=string_max_chars * 3) or None,
                    )
                )
            compacted.realtor = RealtorSQLResult(
                listings=listings,
                total_found=int(result.realtor.total_found),
                sql_executed="",
                slots_used=result.realtor.slots_used,
            )

        if result.workflow is not None:
            compacted.workflow = WorkflowResult(
                workflow_name=_truncate_text(result.workflow.workflow_name, max_chars=string_max_chars),
                success=bool(result.workflow.success),
                output=_compact_workflow_output(
                    result.workflow.output,
                    max_items=workflow_output_items,
                    max_chars=string_max_chars,
                ),
            )

        compacted_results.append(compacted)

    return compacted_results


def _is_rag_goal(goal: Any) -> bool:
    if isinstance(goal, GoalType):
        return goal == GoalType.rag
    return str(goal or "").strip().lower() == GoalType.rag.value


def _build_context_text_for_overlay(*, goal: Any, tool_results: list[ToolResult]) -> str:
    if not _is_rag_goal(goal):
        return ""
    lines: list[str] = []
    for result in tool_results:
        rag = result.rag
        if result.status != "ok" or rag is None:
            continue
        for chunk in rag.chunks:
            chunk_id = _truncate_text(chunk.chunk_id, max_chars=64)
            content = _truncate_text(chunk.content, max_chars=max(120, int(settings.synth_rag_chunk_max_chars)))
            if not content:
                continue
            lines.append(f"[{chunk_id}] {content}")
    return "\n".join(lines).strip()


def _inject_overlay_context(*, prompt: str, context_text: str) -> str:
    if "{context_text}" in prompt:
        return prompt.replace("{context_text}", context_text or "")
    return prompt


class SynthesizerService:
    async def run(
        self,
        *,
        tenant_id: str,
        raw_input: dict[str, Any],
        tool_results: list[ToolResult],
        goal: Any = None,
        response_mode: Any,
        context_snapshot: dict[str, Any],
        conversation_id: str | None = None,
        lead_id: str | None = None,
    ) -> SynthesizerOutput:
        channel = str(raw_input.get("channel") or "web_html").strip()
        vertical = str(raw_input.get("vertical") or "generic").strip()
        tenant = str(tenant_id or raw_input.get("tenant_id") or "default").strip()
        conversation_token = str(
            conversation_id
            or raw_input.get("conversationId")
            or raw_input.get("conversation_id")
            or ""
        ).strip()
        lead_token = str(
            lead_id
            or raw_input.get("leadId")
            or raw_input.get("lead_id")
            or ""
        ).strip()

        prompts = await prompt_service.resolve_prompts(
            tenant_id=tenant,
            vertical=vertical,
            channel=channel,
        )

        compacted_results = _compact_tool_results(tool_results)
        effective_context_snapshot = {
            "conversation_summary": (context_snapshot or {}).get("conversation_summary"),
            "vertical": (context_snapshot or {}).get("vertical"),
            "conversation_state": (context_snapshot or {}).get("conversation_state"),
        }
        synth_input = SynthesizerInput(
            context_snapshot=_compact_context_snapshot(effective_context_snapshot),
            tool_results=compacted_results,
            response_mode=response_mode,
            tenant_tone=str(raw_input.get("tenant_tone") or "formal"),
        )

        payload = synth_input.model_dump(mode="json")
        context_text = _build_context_text_for_overlay(goal=goal, tool_results=compacted_results)
        system_instruction = _inject_overlay_context(
            prompt=prompts.synthesizer_system_prompt,
            context_text=context_text,
        )
        raw = await llm_service.generate_json(
            system_instruction=system_instruction,
            payload=payload,
            temperature=0.2,
            max_output_tokens=max(256, int(settings.synth_max_output_tokens)),
            trace_context={
                "conversation_id": conversation_token,
                "lead_id": lead_token or None,
                "tenant_id": tenant,
                "channel": channel,
                "vertical": vertical,
                "component": "synthesizer",
                "operation": "answer_synthesis",
                "goal": goal.value if isinstance(goal, GoalType) else str(goal or ""),
                "tool_results_count": len(compacted_results),
                "response_mode": response_mode.value if isinstance(response_mode, ResponseMode) else str(response_mode or ""),
            },
        )
        normalized = normalize_synthesizer_output(raw)
        return SynthesizerOutput.model_validate(normalized)


synthesizer_service = SynthesizerService()
