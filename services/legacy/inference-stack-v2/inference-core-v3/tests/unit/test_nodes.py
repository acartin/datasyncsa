from unittest.mock import AsyncMock, patch

import pytest

from app.graph.nodes import (
    _is_placeholder_lead_name,
    load_live_lead_state,
    route_turn,
    select_generic_executor_route,
    select_realtor_compiler_route,
)


@pytest.mark.asyncio
async def test_route_turn_updates_root_contract_from_router():
    state = {
        "vertical_slug": "real-estate",
        "history": [],
        "conversation_memory": {"common": {}, "vertical": {}},
        "active_search_state": {},
        "last_result_set": {},
        "tenant_runtime": {"tool_registry": {"realtor_sql_search": object()}},
        "trace": [],
    }

    with patch(
        "app.graph.nodes.turn_router.route",
        new=AsyncMock(
            return_value={
                "route_mode": "tool_required",
                "intent": "PROPERTY_SEARCH",
                "active_subflow": "realtor_search",
                "active_vertical_subgraph": "realtor_subgraph",
                "selected_tools": ["realtor_sql_search"],
                "requires_tools": True,
                "reasoning": "search turn",
            }
        ),
    ):
        result = await route_turn(state)

    assert result["route_mode"] == "tool_required"
    assert result["active_vertical_subgraph"] == "realtor_subgraph"
    assert result["last_agent_route"]["intent"] == "PROPERTY_SEARCH"


@pytest.mark.asyncio
async def test_load_live_lead_state_merges_lead_snapshot_into_memory():
    state = {
        "conversation_memory": {"common": {}, "vertical": {}},
        "lead_progression_state": {},
        "lead_snapshot": {
            "full_name": "Alvaro",
            "email": "alvaro@example.com",
            "phone": "+50612345678",
        },
        "conversation_extraction_result": {},
        "active_search_state": {
            "filters": {"desired_location": "Heredia", "property_type": "casa"},
            "search_summary": "casas en Heredia",
        },
        "trace": [],
    }

    result = await load_live_lead_state(state)

    assert result["conversation_memory"]["common"]["name"] == "Alvaro"
    assert result["conversation_memory"]["vertical"]["desired_location"] == "Heredia"
    assert result["lead_progression_state"]["email"]["status"] == "provided"


def test_select_realtor_compiler_route_uses_compiler_for_search_operations():
    state = {"tool_plan": [{"operation": "search"}]}
    assert select_realtor_compiler_route(state) == "realtor_search_transition_judge"


def test_select_realtor_compiler_route_skips_compiler_for_clarify():
    state = {"tool_plan": [{"operation": "clarify"}]}
    assert select_realtor_compiler_route(state) == "lead_followup_planner"


def test_select_realtor_compiler_route_uses_reference_resolver_for_shown_result_questions():
    state = {
        "tool_plan": [
            {
                "operation": "answer",
                "query_scope": "shown_result",
                "target_entity": "single_shown_property",
                "reference_request": {"mode": "shown_result", "target": "last", "field": "bathrooms"},
            }
        ]
    }
    assert select_realtor_compiler_route(state) == "shown_results_reference_resolver"


def test_select_realtor_compiler_route_uses_context_resolver_for_search_state_answers():
    state = {
        "tool_plan": [
            {
                "operation": "answer",
                "query_scope": "active_search",
                "target_entity": "search_state",
                "user_goal": "search_state",
            }
        ]
    }
    assert select_realtor_compiler_route(state) == "realtor_context_resolver"


def test_select_generic_executor_route_dispatches_rag_only_when_needed():
    assert select_generic_executor_route({"tool_plan": [{"operation": "rag"}]}) == "generic_tool_executor"
    assert select_generic_executor_route({"tool_plan": [{"operation": "answer"}]}) == "lead_followup_planner"


def test_placeholder_lead_name_is_not_treated_as_real_name():
    assert _is_placeholder_lead_name("Lead abcd1234") is True
    assert _is_placeholder_lead_name("Alvaro") is False
