from __future__ import annotations

import asyncio
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.llm_client import llm_service  # noqa: E402
from app.core.prompt_service import PromptBundle, prompt_service  # noqa: E402
from app.models.contracts import GoalType, ResponseMode  # noqa: E402
from app.planners.planner_service import planner_service  # noqa: E402


def test_planner_includes_router_decision_schema_in_payload(monkeypatch) -> None:
    captured_payload: dict[str, object] = {}
    captured_trace_context: dict[str, object] = {}

    async def fake_resolve_prompts(*, tenant_id: str, vertical: str, channel: str) -> PromptBundle:
        return PromptBundle(
            planner_system_prompt="planner system {router_decision_schema}",
            synthesizer_system_prompt="synth",
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
        captured_trace_context.update(trace_context or {})
        return {
            "goal": "answer",
            "confidence": 0.9,
            "tool_calls": [],
            "missing_slots": [],
            "response_mode": "text_only",
        }

    monkeypatch.setattr(prompt_service, "resolve_prompts", fake_resolve_prompts)
    monkeypatch.setattr(llm_service, "generate_json", fake_generate_json)

    decision = asyncio.run(
        planner_service.run(
            raw_input={"clientId": "64f357a0-98eb-44f1-9f41-6e615ed26180", "queryText": "hola"},
            normalized_input={"vertical": "realtor", "conversation_state": {}},
            history=[],
            conversation_id="conv-test-001",
            lead_id="lead-test-001",
        )
    )

    schema = captured_payload.get("router_decision_schema")
    assert isinstance(schema, dict)
    assert schema.get("type") == "object"
    assert "goal" in (schema.get("properties") or {})
    assert "clarify_message" in (schema.get("properties") or {})
    assert decision.goal == GoalType.answer
    assert decision.response_mode == ResponseMode.text_only
    assert captured_trace_context.get("conversation_id") == "conv-test-001"
    assert captured_trace_context.get("lead_id") == "lead-test-001"
    assert captured_trace_context.get("component") == "planner"


def _mock_planner_dependencies(monkeypatch, raw_decision: dict[str, object]) -> None:
    async def fake_resolve_prompts(*, tenant_id: str, vertical: str, channel: str) -> PromptBundle:
        return PromptBundle(
            planner_system_prompt="planner",
            synthesizer_system_prompt="synth",
        )

    async def fake_generate_json(
        *,
        system_instruction: str,
        payload: dict,
        temperature: float,
        max_output_tokens: int,
        trace_context: dict | None = None,
    ):
        _ = (system_instruction, payload, temperature, max_output_tokens, trace_context)
        return raw_decision

    monkeypatch.setattr(prompt_service, "resolve_prompts", fake_resolve_prompts)
    monkeypatch.setattr(llm_service, "generate_json", fake_generate_json)


def test_planner_overrides_name_declaration_to_answer(monkeypatch) -> None:
    _mock_planner_dependencies(
        monkeypatch,
        {
            "goal": "rag",
            "confidence": 0.6,
            "tool_calls": [{"tool_name": "rag", "rag": {"query_text": "a que te dedicas", "top_k": 5}}],
            "missing_slots": [],
            "response_mode": "text_only",
        },
    )

    decision = asyncio.run(
        planner_service.run(
            raw_input={"clientId": "tenant-1", "queryText": "me llamo alvaro"},
            normalized_input={"vertical": "realtor", "conversation_state": {}, "context_snapshot": {}},
            history=[],
            conversation_id="conv-1",
            lead_id="lead-1",
        )
    )

    assert decision.goal == GoalType.answer
    assert decision.tool_calls == []
    assert decision.response_mode == ResponseMode.text_only


def test_planner_overrides_name_recall_to_answer_when_name_in_history(monkeypatch) -> None:
    _mock_planner_dependencies(
        monkeypatch,
        {
            "goal": "rag",
            "confidence": 0.7,
            "tool_calls": [{"tool_name": "rag", "rag": {"query_text": "recuerdas como me llamo", "top_k": 5}}],
            "missing_slots": [],
            "response_mode": "text_only",
        },
    )

    decision = asyncio.run(
        planner_service.run(
            raw_input={"clientId": "tenant-1", "queryText": "recuerdas como me llamo?"},
            normalized_input={
                "vertical": "realtor",
                "conversation_state": {},
                "context_snapshot": {
                    "recent_history": [
                        {"role": "user", "content": "me llamo Alvaro"},
                        {"role": "assistant", "content": "Mucho gusto"},
                    ]
                },
            },
            history=[],
            conversation_id="conv-2",
            lead_id="lead-2",
        )
    )

    assert decision.goal == GoalType.answer
    assert decision.tool_calls == []


def test_planner_overrides_ambiguous_rooms_question_to_clarify(monkeypatch) -> None:
    _mock_planner_dependencies(
        monkeypatch,
        {
            "goal": "answer",
            "confidence": 0.8,
            "tool_calls": [],
            "missing_slots": [],
            "response_mode": "text_only",
        },
    )

    decision = asyncio.run(
        planner_service.run(
            raw_input={"clientId": "tenant-1", "queryText": "de cuantas habitaciones son?"},
            normalized_input={
                "vertical": "realtor",
                "conversation_state": {},
                "context_snapshot": {
                    "last_answer_envelope": {
                        "cards": [
                            {"card_type": "property_card", "listing_id": "a"},
                            {"card_type": "property_card", "listing_id": "b"},
                        ]
                    }
                },
            },
            history=[],
            conversation_id="conv-3",
            lead_id="lead-3",
        )
    )

    assert decision.goal == GoalType.clarify
    assert "primera" in (decision.clarify_message or "").lower()


def test_planner_overrides_last_price_to_answer_when_card_has_price(monkeypatch) -> None:
    _mock_planner_dependencies(
        monkeypatch,
        {
            "goal": "clarify",
            "confidence": 0.7,
            "tool_calls": [],
            "missing_slots": [],
            "clarify_message": "No puedo recuperar el precio",
            "response_mode": "text_only",
        },
    )

    decision = asyncio.run(
        planner_service.run(
            raw_input={"clientId": "tenant-1", "queryText": "cual es el precio de la ultima casa?"},
            normalized_input={
                "vertical": "realtor",
                "conversation_state": {},
                "context_snapshot": {
                    "last_answer_envelope": {
                        "cards": [
                            {"card_type": "property_card", "listing_id": "a", "price_display": "USD 120,000"},
                            {"card_type": "property_card", "listing_id": "b", "price_display": "USD 200,000"},
                        ]
                    }
                },
            },
            history=[],
            conversation_id="conv-4",
            lead_id="lead-4",
        )
    )

    assert decision.goal == GoalType.answer
    assert decision.tool_calls == []


def test_planner_uses_cached_property_cards_from_presentation_state(monkeypatch) -> None:
    _mock_planner_dependencies(
        monkeypatch,
        {
            "goal": "clarify",
            "confidence": 0.7,
            "tool_calls": [],
            "missing_slots": [],
            "clarify_message": "No puedo recuperar el precio",
            "response_mode": "text_only",
        },
    )

    decision = asyncio.run(
        planner_service.run(
            raw_input={"clientId": "tenant-1", "queryText": "cual es el precio de la ultima casa?"},
            normalized_input={
                "vertical": "realtor",
                "conversation_state": {
                    "presentation_state": {
                        "last_property_cards": [
                            {"card_type": "property_card", "listing_id": "x", "price_display": "USD 90,000"},
                            {"card_type": "property_card", "listing_id": "y", "price_display": "USD 120,000"},
                        ]
                    }
                },
                "context_snapshot": {
                    "conversation_state": {
                        "presentation_state": {
                            "last_property_cards": [
                                {"card_type": "property_card", "listing_id": "x", "price_display": "USD 90,000"},
                                {"card_type": "property_card", "listing_id": "y", "price_display": "USD 120,000"},
                            ]
                        }
                    }
                },
            },
            history=[],
            conversation_id="conv-5",
            lead_id="lead-5",
        )
    )

    assert decision.goal == GoalType.answer
