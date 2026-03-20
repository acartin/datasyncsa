from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.graph.nodes import _should_render_cards
from app.models.contracts import (
    RealtorSQLResult,
    RealtorSearchSlots,
    GoalType,
    PropertyListing,
    ResponseMode,
    RouterDecision,
    SynthesizerOutput,
    ToolName,
    ToolResult,
)


def _decision(*, response_mode: ResponseMode) -> RouterDecision:
    return RouterDecision(
        goal=GoalType.realtor_search,
        confidence=0.9,
        tool_calls=[],
        missing_slots=[],
        response_mode=response_mode,
    )


def test_should_render_cards_requires_text_plus_cards_and_needs_cards_true() -> None:
    decision = _decision(response_mode=ResponseMode.text_plus_cards)
    output = SynthesizerOutput(text="ok", evidence_ids=["listing-1"], needs_cards=True)
    tool_results = [ToolResult(tool_name=ToolName.realtor_sql, status="ok")]

    assert _should_render_cards(
        decision=decision,
        synthesizer_output=output,
        tool_results=tool_results,
    )


def test_should_not_render_cards_when_synth_needs_cards_false() -> None:
    decision = _decision(response_mode=ResponseMode.text_plus_cards)
    output = SynthesizerOutput(text="ok", evidence_ids=[], needs_cards=False)
    tool_results = [ToolResult(tool_name=ToolName.realtor_sql, status="ok")]

    assert not _should_render_cards(
        decision=decision,
        synthesizer_output=output,
        tool_results=tool_results,
    )


def test_should_not_render_cards_when_response_mode_text_only() -> None:
    decision = _decision(response_mode=ResponseMode.text_only)
    output = SynthesizerOutput(text="ok", evidence_ids=["listing-1"], needs_cards=True)
    tool_results = [ToolResult(tool_name=ToolName.realtor_sql, status="ok")]

    assert not _should_render_cards(
        decision=decision,
        synthesizer_output=output,
        tool_results=tool_results,
    )


def test_should_render_cards_when_planner_mode_is_text_only_but_realtor_has_listings() -> None:
    decision = _decision(response_mode=ResponseMode.text_only)
    output = SynthesizerOutput(text="ok", evidence_ids=["listing-1"], needs_cards=True)
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
    tool_results = [
        ToolResult(
            tool_name=ToolName.realtor_sql,
            status="ok",
            realtor=RealtorSQLResult(
                listings=[listing],
                total_found=1,
                sql_executed="",
                slots_used=RealtorSearchSlots(city="Curridabat"),
            ),
        )
    ]

    assert _should_render_cards(
        decision=decision,
        synthesizer_output=output,
        tool_results=tool_results,
    )


def test_should_render_cards_with_realtor_listings_even_if_needs_cards_false() -> None:
    decision = _decision(response_mode=ResponseMode.text_only)
    output = SynthesizerOutput(text="ok", evidence_ids=["listing-1"], needs_cards=False)
    listing = PropertyListing(
        listing_id="listing-1",
        title="Casa Escazu",
        city="Escazu",
        neighborhood=None,
        price=150000000,
        currency="CRC",
        rooms=3,
        area_m2=175.0,
        property_type="house",
        features=[],
        image_urls=[],
        listing_url=None,
    )
    tool_results = [
        ToolResult(
            tool_name=ToolName.realtor_sql,
            status="ok",
            realtor=RealtorSQLResult(
                listings=[listing],
                total_found=1,
                sql_executed="",
                slots_used=RealtorSearchSlots(city="Escazu"),
            ),
        )
    ]

    assert _should_render_cards(
        decision=decision,
        synthesizer_output=output,
        tool_results=tool_results,
    )
