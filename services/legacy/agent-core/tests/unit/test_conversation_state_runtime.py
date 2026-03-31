from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.models.contracts import (  # noqa: E402
    AnswerEnvelope,
    GoalType,
    PropertyListing,
    RealtorSQLResult,
    RealtorSearchSlots,
    ResponseMode,
    RouterDecision,
    SynthesizerOutput,
    ToolCall,
    ToolName,
    ToolResult,
)
from app.runtime.conversation_state import (  # noqa: E402
    advance_conversation_state,
    normalize_conversation_state,
    resolve_response_mode,
)


def test_normalize_conversation_state_exposes_canonical_sections() -> None:
    state = normalize_conversation_state(
        raw_state={"active_search": {"city": "Heredia", "min_rooms": 2}},
        history=[
            {"role": "user", "content": "hola"},
            {"role": "assistant", "content": "hola"},
            {"role": "user", "content": "busco en heredia"},
        ],
    )

    assert state["search_state"]["active_slots"]["city"] == "Heredia"
    assert state["search_state"]["active_slots"]["min_rooms"] == 2
    assert state["lead_progression_state"]["user_turn_count"] == 2
    assert state["lead_progression_state"]["assistant_turn_count"] == 1
    assert "presentation_state" in state
    assert "pending_state" in state


def test_resolve_response_mode_prefers_cards_when_realtor_tool_call_exists() -> None:
    decision = RouterDecision(
        goal=GoalType.realtor_search,
        confidence=0.9,
        tool_calls=[
            ToolCall(
                tool_name=ToolName.realtor_sql,
                realtor_slots=RealtorSearchSlots(city="Curridabat"),
            )
        ],
        missing_slots=[],
        response_mode=ResponseMode.text_only,
    )

    assert resolve_response_mode(decision=decision) == ResponseMode.text_plus_cards


def test_advance_conversation_state_updates_search_and_presentation_from_results() -> None:
    listing = PropertyListing(
        listing_id="listing-1",
        title="Casa Curridabat",
        city="Curridabat",
        neighborhood=None,
        price=120000000,
        currency="CRC",
        rooms=3,
        area_m2=180.0,
        property_type="house",
        features=[],
        image_urls=[],
        listing_url=None,
    )
    decision = RouterDecision(
        goal=GoalType.realtor_search,
        confidence=0.9,
        tool_calls=[
            ToolCall(
                tool_name=ToolName.realtor_sql,
                realtor_slots=RealtorSearchSlots(city="Curridabat", min_rooms=3),
            )
        ],
        missing_slots=[],
        response_mode=ResponseMode.text_plus_cards,
    )
    tool_results = [
        ToolResult(
            tool_name=ToolName.realtor_sql,
            status="ok",
            realtor=RealtorSQLResult(
                listings=[listing],
                total_found=1,
                sql_executed="SELECT ...",
                slots_used=RealtorSearchSlots(city="Curridabat", min_rooms=3),
            ),
        )
    ]
    envelope = AnswerEnvelope(
        conversation_id="conv-1",
        text="Aqui tienes opciones.",
        cards=[],
        response_mode=ResponseMode.text_only,
        evidence_ids=["listing-1"],
        goal=GoalType.realtor_search,
        confidence=0.9,
    )
    output = SynthesizerOutput(
        text="ok",
        evidence_ids=["listing-1"],
        needs_cards=True,
    )

    updated = advance_conversation_state(
        current_state={},
        decision=decision,
        tool_results=tool_results,
        envelope=envelope,
        synthesizer_output=output,
        user_turn_text="busco casa en curridabat",
    )

    assert updated["search_state"]["last_total_found"] == 1
    assert updated["search_state"]["last_listing_ids"] == ["listing-1"]
    assert updated["search_state"]["active_slots"]["city"] == "Curridabat"
    assert updated["presentation_state"]["last_needs_cards"] is True
    assert updated["lead_progression_state"]["user_turn_count"] == 1


def test_advance_conversation_state_preserves_last_property_cards_across_clarify_turns() -> None:
    initial = {
        "presentation_state": {
            "last_property_cards": [
                {
                    "card_type": "property_card",
                    "listing_id": "listing-1",
                    "price_display": "USD 100,000",
                }
            ]
        }
    }
    decision = RouterDecision(
        goal=GoalType.clarify,
        confidence=0.8,
        tool_calls=[],
        missing_slots=[],
        clarify_message="¿A cuál te refieres?",
        response_mode=ResponseMode.text_only,
    )
    envelope = AnswerEnvelope(
        conversation_id="conv-2",
        text="¿A cuál te refieres?",
        cards=[],
        response_mode=ResponseMode.text_only,
        evidence_ids=[],
        goal=GoalType.clarify,
        confidence=0.8,
        clarify_message="¿A cuál te refieres?",
    )
    output = SynthesizerOutput(
        text="¿A cuál te refieres?",
        evidence_ids=[],
        needs_cards=False,
    )
    updated = advance_conversation_state(
        current_state=initial,
        decision=decision,
        tool_results=[],
        envelope=envelope,
        synthesizer_output=output,
        user_turn_text="de cuantas habitaciones son?",
    )
    assert updated["presentation_state"]["last_property_cards"][0]["listing_id"] == "listing-1"
