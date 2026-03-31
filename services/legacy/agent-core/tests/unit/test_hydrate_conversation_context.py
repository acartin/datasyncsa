from __future__ import annotations

import asyncio
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.graph.nodes import hydrate_conversation_context
from app.repositories.persistence import runtime_repository


def test_hydrate_conversation_context_loads_history_and_snapshot(monkeypatch) -> None:
    captured: dict[str, str] = {}

    async def fake_get_conversation_memory(*, conversation_id: str, tenant_id: str, max_messages: int):
        captured["conversation_id"] = conversation_id
        captured["tenant_id"] = tenant_id
        captured["max_messages"] = str(max_messages)
        return {
            "history": [
                {"role": "user", "content": "en heredia"},
                {"role": "assistant", "content": "Te comparto una selección inicial."},
            ],
            "conversation_state": {"active_search": {"city": "Heredia", "rooms": 2}},
            "context_snapshot": {
                "last_answer_envelope": {
                    "cards": [{"listing_id": "prop-1", "title": "Casa Heredia"}],
                },
                "last_router_decision": {"goal": "realtor_search"},
            },
            "lead_id": "b4554db4-273d-4f67-a09a-f2b74db2f4eb",
        }

    monkeypatch.setattr(runtime_repository, "get_conversation_memory", fake_get_conversation_memory)

    state = {
        "raw_input": {
            "clientId": "64f357a0-98eb-44f1-9f41-6e615ed26180",
            "conversationId": "11111111-1111-1111-1111-111111111111",
            "queryText": "dos habitaciones",
        },
        "normalized_input": {
            "conversation_summary": "dos habitaciones",
            "vertical": "realtor",
            "conversation_state": {},
            "last_user_turn": "dos habitaciones",
        },
        "tenant_id": "64f357a0-98eb-44f1-9f41-6e615ed26180",
        "conversation_id": "11111111-1111-1111-1111-111111111111",
    }

    result = asyncio.run(hydrate_conversation_context(state))

    assert captured["conversation_id"] == "11111111-1111-1111-1111-111111111111"
    assert captured["tenant_id"] == "64f357a0-98eb-44f1-9f41-6e615ed26180"
    assert int(captured["max_messages"]) >= 1

    assert result["raw_input"]["history"][0]["content"] == "en heredia"
    assert result["raw_input"]["conversation_state"]["active_search"]["city"] == "Heredia"
    assert result["lead_id"] == "b4554db4-273d-4f67-a09a-f2b74db2f4eb"

    planner_snapshot = result["normalized_input"]["context_snapshot"]
    assert planner_snapshot["last_answer_envelope"]["cards"][0]["listing_id"] == "prop-1"
    assert planner_snapshot["conversation_state"]["active_search"]["rooms"] == 2


def test_hydrate_conversation_context_merges_incoming_state_and_history(monkeypatch) -> None:
    async def fake_get_conversation_memory(*, conversation_id: str, tenant_id: str, max_messages: int):
        return {
            "history": [
                {"role": "user", "content": "en heredia"},
                {"role": "assistant", "content": "Te comparto opciones."},
            ],
            "conversation_state": {
                "active_search": {"city": "Heredia", "rooms": 1},
                "customer_profile": {"name": "Ana"},
            },
            "context_snapshot": {},
            "lead_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        }

    monkeypatch.setattr(runtime_repository, "get_conversation_memory", fake_get_conversation_memory)

    state = {
        "raw_input": {
            "clientId": "64f357a0-98eb-44f1-9f41-6e615ed26180",
            "conversationId": "22222222-2222-2222-2222-222222222222",
            "queryText": "dos habitaciones",
            "leadId": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "history": [{"role": "user", "content": "si"}],
            "conversation_state": {"active_search": {"rooms": 2}},
        },
        "normalized_input": {
            "conversation_summary": "dos habitaciones",
            "vertical": "realtor",
            "conversation_state": {},
            "last_user_turn": "dos habitaciones",
        },
        "tenant_id": "64f357a0-98eb-44f1-9f41-6e615ed26180",
        "conversation_id": "22222222-2222-2222-2222-222222222222",
    }

    result = asyncio.run(hydrate_conversation_context(state))

    merged_history = result["raw_input"]["history"]
    assert len(merged_history) == 3
    assert merged_history[-1]["content"] == "si"

    merged_state = result["raw_input"]["conversation_state"]
    assert merged_state["active_search"]["city"] == "Heredia"
    assert merged_state["active_search"]["rooms"] == 2
    assert merged_state["customer_profile"]["name"] == "Ana"

    # Explicit leadId from request must remain authoritative.
    assert result["lead_id"] == "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
