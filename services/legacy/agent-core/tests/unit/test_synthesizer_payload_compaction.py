from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.core.llm_client import llm_service
from app.core.prompt_service import PromptBundle, prompt_service
from app.models.contracts import (
    PropertyListing,
    RAGChunk,
    RAGResult,
    RealtorSQLResult,
    RealtorSearchSlots,
    ResponseMode,
    ToolName,
    ToolResult,
)
from app.synthesizers.synthesizer_service import (
    SynthesizerService,
    _compact_context_snapshot,
    _compact_tool_results,
)


def _build_listing(index: int) -> PropertyListing:
    return PropertyListing(
        listing_id=f"listing-{index}",
        title=f"Casa amplia {index} " + ("x" * 120),
        city="Heredia",
        neighborhood="Santo Domingo",
        price=120000 + index,
        currency="USD",
        rooms=3,
        area_m2=110.0,
        property_type="house",
        features=[f"feature-{item}" for item in range(20)],
        image_urls=[f"https://cdn.example.com/{index}/{item}.jpg" for item in range(8)],
        listing_url=f"https://example.com/listings/{index}",
    )


def test_compact_tool_results_limits_realtor_and_rag_payload() -> None:
    realtor_result = ToolResult(
        tool_name=ToolName.realtor_sql,
        status="ok",
        realtor=RealtorSQLResult(
            listings=[_build_listing(i) for i in range(20)],
            total_found=20,
            sql_executed="SELECT * FROM lead_properties WHERE very_long_condition = true",
            slots_used=RealtorSearchSlots(city="Heredia"),
        ),
    )
    rag_result = ToolResult(
        tool_name=ToolName.rag,
        status="ok",
        rag=RAGResult(
            chunks=[
                RAGChunk(
                    chunk_id=f"chunk-{i}",
                    doc_id=f"doc-{i}",
                    content="contenido-" + ("z" * 1200),
                    score=0.99,
                    source_url=f"https://docs.example.com/{i}",
                )
                for i in range(8)
            ],
            query_used="que documentos hay sobre politica comercial",
        ),
    )

    compacted = _compact_tool_results([realtor_result, rag_result])
    assert len(compacted) == 2

    compacted_realtor = compacted[0].realtor
    assert compacted_realtor is not None
    assert len(compacted_realtor.listings) <= settings.synth_realtor_listing_limit
    assert compacted_realtor.sql_executed == ""
    for listing in compacted_realtor.listings:
        assert len(listing.features) <= settings.synth_realtor_features_limit
        assert len(listing.image_urls) <= settings.synth_realtor_images_per_listing

    compacted_rag = compacted[1].rag
    assert compacted_rag is not None
    assert len(compacted_rag.chunks) <= settings.synth_rag_chunk_limit
    for chunk in compacted_rag.chunks:
        assert len(chunk.content) <= settings.synth_rag_chunk_max_chars


def test_run_sends_compacted_payload_to_llm(monkeypatch) -> None:
    captured_payload: dict[str, object] = {}
    captured_max_tokens: dict[str, int] = {}
    captured_trace_context: dict[str, object] = {}

    async def fake_resolve_prompts(*, tenant_id: str, vertical: str, channel: str) -> PromptBundle:
        return PromptBundle(
            planner_system_prompt="planner",
            synthesizer_system_prompt="Overlay de contexto:\n{context_text}",
        )

    async def fake_generate_json(
        *,
        system_instruction: str,
        payload: dict,
        temperature: float,
        max_output_tokens: int,
        trace_context: dict | None = None,
    ):
        captured_payload.update(payload)
        captured_max_tokens["value"] = max_output_tokens
        captured_trace_context.update(trace_context or {})
        return {"text": "ok", "evidence_ids": ["listing-0"], "needs_cards": True}

    monkeypatch.setattr(prompt_service, "resolve_prompts", fake_resolve_prompts)
    monkeypatch.setattr(llm_service, "generate_json", fake_generate_json)

    service = SynthesizerService()
    result = asyncio.run(
        service.run(
            tenant_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
            raw_input={"channel": "web_html", "vertical": "realtor"},
            tool_results=[
                ToolResult(
                    tool_name=ToolName.realtor_sql,
                    status="ok",
                    realtor=RealtorSQLResult(
                        listings=[_build_listing(i) for i in range(20)],
                        total_found=20,
                        sql_executed="SELECT * FROM lead_properties",
                        slots_used=RealtorSearchSlots(city="Heredia"),
                    ),
                )
            ],
            goal="realtor_search",
            response_mode=ResponseMode.text_plus_cards,
            context_snapshot={
                "conversation_summary": "quiero ver casas",
                "vertical": "realtor",
                "conversation_state": {"history": ["hola"] * 500},
                "last_user_turn": "heredia",
            },
            conversation_id="conv-test-002",
            lead_id="lead-test-002",
        )
    )

    assert result.text == "ok"
    context_snapshot = captured_payload.get("context_snapshot") or {}
    tool_results = captured_payload.get("tool_results") or []
    assert isinstance(context_snapshot, dict)
    assert isinstance(context_snapshot.get("conversation_state"), dict)
    assert "recent_history" not in context_snapshot
    assert "last_answer_cards" not in context_snapshot
    assert len(json.dumps(context_snapshot, ensure_ascii=False)) <= settings.synth_context_max_chars
    assert isinstance(tool_results, list) and tool_results
    first_realtor = tool_results[0].get("realtor") if isinstance(tool_results[0], dict) else None
    assert isinstance(first_realtor, dict)
    assert len(first_realtor.get("listings") or []) <= settings.synth_realtor_listing_limit
    assert captured_max_tokens.get("value") == settings.synth_max_output_tokens
    assert captured_trace_context.get("conversation_id") == "conv-test-002"
    assert captured_trace_context.get("lead_id") == "lead-test-002"
    assert captured_trace_context.get("component") == "synthesizer"


def test_run_prunes_stale_history_context_for_realtor_tool_results(monkeypatch) -> None:
    captured_payload: dict[str, object] = {}
    captured_instruction: dict[str, str] = {}

    async def fake_resolve_prompts(*, tenant_id: str, vertical: str, channel: str) -> PromptBundle:
        return PromptBundle(
            planner_system_prompt="planner",
            synthesizer_system_prompt="Overlay de contexto:\n{context_text}",
        )

    async def fake_generate_json(
        *,
        system_instruction: str,
        payload: dict,
        temperature: float,
        max_output_tokens: int,
        trace_context: dict | None = None,
    ):
        captured_instruction["value"] = system_instruction
        captured_payload.update(payload)
        return {"text": "ok", "evidence_ids": ["listing-0"], "needs_cards": False}

    monkeypatch.setattr(prompt_service, "resolve_prompts", fake_resolve_prompts)
    monkeypatch.setattr(llm_service, "generate_json", fake_generate_json)

    service = SynthesizerService()
    _ = asyncio.run(
        service.run(
            tenant_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
            raw_input={"channel": "web_html", "vertical": "realtor"},
            tool_results=[
                ToolResult(
                    tool_name=ToolName.realtor_sql,
                    status="ok",
                    realtor=RealtorSQLResult(
                        listings=[],
                        total_found=0,
                        sql_executed="SELECT * FROM lead_properties",
                        slots_used=RealtorSearchSlots(city="Curridabat", property_type="house"),
                    ),
                )
            ],
            goal="realtor_search",
            response_mode=ResponseMode.text_only,
            context_snapshot={
                "conversation_summary": "que tienes en curridabat?",
                "vertical": "realtor",
                "last_user_turn": "que tienes en curridabat?",
                "conversation_state": {"active_search": {"city": "Curridabat"}},
                "recent_history": [
                    {"role": "user", "content": "busco tres habitaciones"},
                    {"role": "assistant", "content": "no encontré con tres habitaciones"},
                ],
                "last_answer_envelope": {"text": "No encontré con tres habitaciones."},
            },
            conversation_id="conv-test-003",
        )
    )

    context_snapshot = captured_payload.get("context_snapshot") or {}
    assert isinstance(context_snapshot, dict)
    assert "recent_history" not in context_snapshot
    assert "last_answer_text" not in context_snapshot
    assert context_snapshot.get("conversation_summary") == "que tienes en curridabat?"
    # Non-rag goals must clear context placeholder instead of injecting stale text.
    assert "{context_text}" not in captured_instruction.get("value", "")
    assert "chunk-" not in captured_instruction.get("value", "")


def test_compact_context_snapshot_caps_payload_size() -> None:
    context = {
        "conversation_summary": "hola " * 200,
        "vertical": "realtor",
        "conversation_state": {"messages": ["heredia"] * 1000},
        "last_user_turn": "alajuela " * 200,
    }
    compacted = _compact_context_snapshot(context)
    assert isinstance(compacted, dict)
    assert len(json.dumps(compacted, ensure_ascii=False)) <= settings.synth_context_max_chars
    assert "recent_history" not in compacted
    assert "last_answer_cards" not in compacted


def test_run_injects_context_text_only_for_rag_goal(monkeypatch) -> None:
    captured_instruction: dict[str, str] = {}

    async def fake_resolve_prompts(*, tenant_id: str, vertical: str, channel: str) -> PromptBundle:
        return PromptBundle(
            planner_system_prompt="planner",
            synthesizer_system_prompt="Overlay:\n{context_text}",
        )

    async def fake_generate_json(
        *,
        system_instruction: str,
        payload: dict,
        temperature: float,
        max_output_tokens: int,
        trace_context: dict | None = None,
    ):
        captured_instruction["value"] = system_instruction
        return {"text": "ok", "evidence_ids": ["chunk-1"], "needs_cards": False}

    monkeypatch.setattr(prompt_service, "resolve_prompts", fake_resolve_prompts)
    monkeypatch.setattr(llm_service, "generate_json", fake_generate_json)

    service = SynthesizerService()
    _ = asyncio.run(
        service.run(
            tenant_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
            raw_input={"channel": "web_html", "vertical": "realtor"},
            tool_results=[
                ToolResult(
                    tool_name=ToolName.rag,
                    status="ok",
                    rag=RAGResult(
                        chunks=[
                            RAGChunk(
                                chunk_id="chunk-1",
                                doc_id="doc-1",
                                content="politica comercial vigente",
                                score=0.9,
                                source_url=None,
                            )
                        ],
                        query_used="politica comercial",
                    ),
                )
            ],
            goal="rag",
            response_mode=ResponseMode.text_only,
            context_snapshot={
                "conversation_summary": "cual es la politica comercial?",
                "vertical": "realtor",
                "conversation_state": {"search_state": {}},
            },
            conversation_id="conv-test-004",
        )
    )

    assert "{context_text}" not in captured_instruction.get("value", "")
    assert "politica comercial vigente" in captured_instruction.get("value", "")
