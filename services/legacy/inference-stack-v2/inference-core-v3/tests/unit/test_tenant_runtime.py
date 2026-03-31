from unittest.mock import AsyncMock

import pytest

from app.services.tenant_runtime import TenantRuntimeResolver


class DummyCache:
    async def get(self, *args, **kwargs):
        return None

    async def set(self, *args, **kwargs):
        return True


@pytest.mark.asyncio
async def test_resolve_loads_system_and_tenant_prompt_layers_for_realtor():
    repo = AsyncMock()
    repo.get_client_vertical_context.return_value = {
        "client_exists": True,
        "vertical_slug": "real-estate",
    }
    repo.get_active_ai_system_prompt_bundle.return_value = {
        "route_turn": "route system",
        "realtor_turn_planner": "realtor planner system",
        "generic_turn_planner": "generic planner system",
        "lead_followup_planner": "followup system",
        "realtor_answer_synthesis": "realtor answer system",
        "generic_answer_synthesis": "generic answer system",
        "workflow_planner": "workflow planner system",
        "workflow_answer_synthesis": "workflow answer system",
    }
    repo.get_client_prompt_bundle.return_value = {
        "primary_chat": "primary tenant prompt",
        "business_context": "business context",
        "route_turn": None,
        "generic_planner_system": "generic tenant planner",
        "generic_answer_synthesis": "generic tenant answer",
        "realtor_turn_system": "tenant realtor planner",
        "realtor_answer_synthesis": "tenant realtor answer",
        "lead_followup_planner": None,
        "workflow_planner_system": None,
        "workflow_answer_synthesis": None,
    }

    resolver = TenantRuntimeResolver(DummyCache(), cache_ttl_seconds=60)
    runtime = await resolver.resolve(
        client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
        repo=repo,
        channel="web",
    )

    assert runtime.system_prompts["realtor_turn_planner"] == "realtor planner system"
    assert runtime.tenant_prompts["realtor_turn_planner"] == "tenant realtor planner"
    assert "realtor planner system" in runtime.prompts["realtor_turn_planner"]
    assert "tenant realtor planner" in runtime.prompts["realtor_turn_planner"]
    assert "primary tenant prompt" not in runtime.prompts["realtor_turn_planner"]
    assert "primary tenant prompt" in runtime.prompts["realtor_answer_synthesis"]
    assert "workflow_handoff" in runtime.tool_registry
    assert "realtor_sql_search" in runtime.tool_registry
