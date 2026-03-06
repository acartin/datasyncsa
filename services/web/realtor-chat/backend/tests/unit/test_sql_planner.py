from unittest.mock import AsyncMock

import pytest

from app.planner.models import SQLIntent
from app.planner.sql_planner import SQLPlanner


class DummyLLM:
    def __init__(self, response: str):
        self.response = response

    async def complete(self, system, messages):
        return self.response


@pytest.mark.asyncio
async def test_sql_planner_plan_maps_property_search_intent_and_sql():
    planner = SQLPlanner(
        search_limit=4,
        llm_client=DummyLLM(
            '{"intent":"PROPERTY_SEARCH","sql":"SELECT id, title, description, features FROM lead_leads WHERE client_id = {client_id} LIMIT 4","reasoning":"ok"}'
        ),
    )

    plan = await planner.plan("muéstrame casas en Escazú", session_data={})

    assert plan.intent == SQLIntent.PROPERTY_SEARCH
    assert "SELECT" in (plan.effective_query or "")


@pytest.mark.asyncio
async def test_sql_planner_plan_returns_none_on_invalid_json():
    planner = SQLPlanner(search_limit=4, llm_client=DummyLLM("not-json"))

    plan = await planner.plan("hola", session_data={})

    assert plan.intent == SQLIntent.NONE
    assert plan.effective_query is None


@pytest.mark.asyncio
async def test_sql_planner_execute_blocks_sql_without_client_scope():
    planner = SQLPlanner(search_limit=4)

    result = await planner.execute(
        plan=type("P", (), {
            "intent": SQLIntent.PROPERTY_SEARCH,
            "user_query": "casas",
            "effective_query": "SELECT id FROM lead_leads LIMIT 4",
            "needs_clarification": False,
            "clarification_message": None,
        })(),
        client_id="abc-123",
        transformer=type("T", (), {"extract_property_filters_for_query": AsyncMock(return_value={"location": None})})(),
    )

    assert result.handled is False


@pytest.mark.asyncio
async def test_sql_planner_execute_inventory_sets_session_updates():
    planner = SQLPlanner(search_limit=4)
    planner._run_sql = AsyncMock(return_value=[{"count": 9}])

    result = await planner.execute(
        plan=type("P", (), {
            "intent": SQLIntent.PROPERTY_INVENTORY,
            "user_query": "cuántas propiedades tienes",
            "effective_query": "SELECT COUNT(*) AS count FROM lead_leads WHERE client_id = {client_id}",
            "needs_clarification": False,
            "clarification_message": None,
        })(),
        client_id="abc-123",
        transformer=type("T", (), {"extract_property_filters_for_query": AsyncMock(return_value={"location": "escazu"})})(),
    )

    assert result.handled is True
    assert result.session_updates["planner_last_property_query"] == "cuántas propiedades tienes"
    assert "planner_last_sql" in result.session_updates
