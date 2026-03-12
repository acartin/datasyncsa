from unittest.mock import AsyncMock, patch

import pytest

from app.services.lead_followup_planner import lead_followup_planner


@pytest.mark.asyncio
async def test_lead_followup_planner_updates_memory_and_marks_asked_field():
    state = {
        "query_text": "me llamo Alvaro y tengo cien mil dolares",
        "vertical_slug": "real-estate",
        "active_subflow": "realtor_search",
        "conversation_memory": {"common": {}, "vertical": {"desired_location": "Heredia"}},
        "lead_progression_state": {
            "has_shown_cards": True,
        },
        "execution_facts": {"status": "results", "total_matches": 3},
        "last_result_set": {"status": "results", "search_summary": "casas en Heredia", "total_matches": 3},
        "components": [],
        "last_shown_components": [{"id": "prop-1"}],
        "history": [],
        "conversation_extraction_result": {},
        "tenant_runtime": {
            "prompts": {
                "lead_followup_planner": "followup prompt",
            }
        },
    }

    with patch(
        "app.services.lead_followup_planner.llm_service.generate_json",
        new=AsyncMock(
            return_value={
                "memory_updates": {
                    "common": {"name": "Alvaro", "budget": 100000},
                    "vertical": {},
                },
                "followup_goal": "capture_email",
                "should_ask": True,
                "question": "Si quieres, también puedo enviarte opciones parecidas. ¿A qué correo te las comparto?",
                "cta_type": "soft_question",
                "reasoning": "faltan datos de contacto",
            }
        ),
    ):
        result = await lead_followup_planner.plan(state)

    assert result["conversation_memory"]["common"]["name"] == "Alvaro"
    assert result["conversation_memory"]["common"]["budget"] == 100000
    assert result["lead_progression_state"]["name"]["status"] == "provided"
    assert result["lead_progression_state"]["last_asked_field"] == "email"
    assert result["followup_goal"] == "capture_email"
    assert result["should_ask"] is True


@pytest.mark.asyncio
async def test_lead_followup_planner_payload_marks_first_cards_shown_now():
    state = {
        "query_text": "quiero ver casas en heredia",
        "vertical_slug": "real-estate",
        "active_subflow": "realtor_search",
        "conversation_memory": {"common": {}, "vertical": {}},
        "lead_progression_state": {},
        "execution_facts": {"status": "results", "total_matches": 2},
        "last_result_set": {"status": "results", "total_matches": 2, "visible_count": 2},
        "components": [{"id": "a"}, {"id": "b"}],
        "last_shown_components": [],
        "history": [],
        "conversation_extraction_result": {},
        "tenant_runtime": {
            "prompts": {
                "lead_followup_planner": "followup prompt",
            }
        },
    }

    mock_generate = AsyncMock(
        return_value={
            "memory_updates": {"common": {}, "vertical": {}},
            "followup_goal": "capture_name",
            "should_ask": True,
            "question": "Por cierto, ¿con quién tengo el gusto?",
            "cta_type": "soft_question",
            "reasoning": "primera tanda de cards",
        }
    )
    with patch("app.services.lead_followup_planner.llm_service.generate_json", new=mock_generate):
        await lead_followup_planner.plan(state)

    payload = mock_generate.await_args.kwargs["payload"]
    assert payload["current_turn_has_components"] is True
    assert payload["previous_cards_seen"] is False
    assert payload["has_shown_cards_ever"] is True
    assert payload["first_cards_shown_now"] is True


@pytest.mark.asyncio
async def test_lead_followup_planner_blocks_capture_before_any_cards_are_shown():
    state = {
        "query_text": "hola",
        "vertical_slug": "real-estate",
        "active_subflow": "generic_answer",
        "conversation_memory": {"common": {}, "vertical": {}},
        "lead_progression_state": {},
        "execution_facts": {"status": "answer_only"},
        "last_result_set": {"status": "answer_only"},
        "components": [],
        "last_shown_components": [],
        "history": [],
        "conversation_extraction_result": {},
        "tenant_runtime": {
            "prompts": {
                "lead_followup_planner": "followup prompt",
            }
        },
    }

    with patch(
        "app.services.lead_followup_planner.llm_service.generate_json",
        new=AsyncMock(
            return_value={
                "memory_updates": {"common": {}, "vertical": {}},
                "followup_goal": "capture_name",
                "should_ask": True,
                "question": "¿Cómo te gustaría que te llame?",
                "cta_type": "soft_question",
                "reasoning": "capture early",
            }
        ),
    ):
        result = await lead_followup_planner.plan(state)

    assert result["followup_goal"] == "none"
    assert result["should_ask"] is False
    assert result["question"] is None
    assert result["reasoning"] == "capture_blocked_until_cards_are_shown"


@pytest.mark.asyncio
async def test_lead_followup_planner_enforces_two_turn_cooldown_between_capture_attempts():
    state = {
        "query_text": "que horario tienen?",
        "vertical_slug": "real-estate",
        "active_subflow": "generic_rag",
        "conversation_memory": {"common": {}, "vertical": {}},
        "lead_progression_state": {
            "has_shown_cards": True,
            "capture_attempt_count": 1,
            "assistant_turns_since_last_capture_attempt": 1,
            "last_capture_goal": "capture_name",
        },
        "execution_facts": {"status": "results"},
        "last_result_set": {"status": "results"},
        "components": [],
        "last_shown_components": [{"id": "a"}],
        "history": [],
        "conversation_extraction_result": {},
        "tenant_runtime": {
            "prompts": {
                "lead_followup_planner": "followup prompt",
            }
        },
    }

    with patch(
        "app.services.lead_followup_planner.llm_service.generate_json",
        new=AsyncMock(
            return_value={
                "memory_updates": {"common": {}, "vertical": {}},
                "followup_goal": "capture_budget",
                "should_ask": True,
                "question": "¿Qué presupuesto tienes en mente?",
                "cta_type": "soft_question",
                "reasoning": "capture budget",
            }
        ),
    ):
        result = await lead_followup_planner.plan(state)

    assert result["followup_goal"] == "none"
    assert result["should_ask"] is False
    assert result["question"] is None
    assert result["reasoning"] == "capture_delayed_until_two_turns_after_last_attempt"
    assert result["lead_progression_state"]["assistant_turns_since_last_capture_attempt"] == 2


@pytest.mark.asyncio
async def test_lead_followup_planner_keeps_model_question_on_first_card_turn():
    state = {
        "query_text": "busco una casa con dos habitaciones",
        "vertical_slug": "real-estate",
        "active_subflow": "realtor_search",
        "conversation_memory": {"common": {}, "vertical": {}},
        "lead_progression_state": {
            "has_shown_cards": False,
            "capture_attempt_count": 0,
            "assistant_turns_since_last_capture_attempt": 999,
        },
        "execution_facts": {"status": "results", "total_matches": 4},
        "last_result_set": {"status": "results", "total_matches": 4, "visible_count": 4},
        "components": [{"id": "a"}, {"id": "b"}],
        "last_shown_components": [],
        "history": [],
        "conversation_extraction_result": {},
        "tenant_runtime": {
            "prompts": {
                "lead_followup_planner": "followup prompt",
            }
        },
    }

    with patch(
        "app.services.lead_followup_planner.llm_service.generate_json",
        new=AsyncMock(
            return_value={
                "memory_updates": {"common": {}, "vertical": {}},
                "followup_goal": "refine_search",
                "should_ask": True,
                "question": "¿Hay algo más que te gustaría ajustar en tu búsqueda?",
                "cta_type": "soft_question",
                "reasoning": "generic refinement",
            }
        ),
    ):
        result = await lead_followup_planner.plan(state)

    assert result["followup_goal"] == "refine_search"
    assert result["should_ask"] is True
    assert result["question"] == "¿Hay algo más que te gustaría ajustar en tu búsqueda?"
    assert result["reasoning"] == "generic refinement"


@pytest.mark.asyncio
async def test_lead_followup_planner_does_not_force_name_capture_on_first_cards():
    state = {
        "query_text": "hola, busco una casa para comprar en heredia",
        "vertical_slug": "real-estate",
        "active_subflow": "realtor_search",
        "conversation_memory": {"common": {}, "vertical": {"desired_location": "Heredia", "property_type": "casa"}},
        "lead_progression_state": {
            "has_shown_cards": False,
            "capture_attempt_count": 0,
            "assistant_turns_since_last_capture_attempt": 999,
        },
        "execution_facts": {"status": "results", "total_matches": 4},
        "last_result_set": {"status": "results", "total_matches": 4, "visible_count": 4},
        "components": [{"id": "a"}, {"id": "b"}],
        "last_shown_components": [],
        "history": [],
        "conversation_extraction_result": {},
        "tenant_runtime": {
            "prompts": {
                "lead_followup_planner": "followup prompt",
            }
        },
    }

    with patch(
        "app.services.lead_followup_planner.llm_service.generate_json",
        new=AsyncMock(
            return_value={
                "memory_updates": {"common": {}, "vertical": {}},
                "followup_goal": "capture_budget",
                "should_ask": True,
                "question": "¿Qué presupuesto tienes en mente?",
                "cta_type": "soft_question",
                "reasoning": "capture budget first",
            }
        ),
    ):
        result = await lead_followup_planner.plan(state)

    assert result["followup_goal"] == "none"
    assert result["should_ask"] is False
    assert result["question"] is None
    assert result["reasoning"] == "capture_blocked_on_first_cards_turn"
    assert result["lead_progression_state"].get("last_asked_field") is None


@pytest.mark.asyncio
async def test_lead_followup_planner_reapplies_capture_name_after_first_cards_turn():
    state = {
        "query_text": "¿Puedes mostrar opciones?",
        "vertical_slug": "real-estate",
        "active_subflow": "realtor_search",
        "conversation_memory": {"common": {}, "vertical": {}},
        "lead_progression_state": {
            "has_shown_cards": True,
            "capture_attempt_count": 0,
            "assistant_turns_since_last_capture_attempt": 999,
            "assistant_turns_since_first_cards_shown": 1,
        },
        "execution_facts": {"status": "results", "total_matches": 4},
        "last_result_set": {"status": "results", "total_matches": 4, "visible_count": 4},
        "components": [],
        "last_shown_components": [{"id": "a"}],
        "history": [],
        "conversation_extraction_result": {},
        "tenant_runtime": {
            "prompts": {
                "lead_followup_planner": "followup prompt",
            }
        },
    }

    with patch(
        "app.services.lead_followup_planner.llm_service.generate_json",
        new=AsyncMock(
            return_value={
                "memory_updates": {"common": {}, "vertical": {}},
                "followup_goal": "refine_search",
                "should_ask": True,
                "question": "¿Hay algo más que te gustaría ajustar en tu búsqueda?",
                "cta_type": "soft_question",
                "reasoning": "generic refinement",
            }
        ),
    ):
        result = await lead_followup_planner.plan(state)

    assert result["followup_goal"] == "capture_name"
    assert result["should_ask"] is True
    assert result["question"] == "Por cierto, ¿cómo te gustaría que te llame?"
    assert result["reasoning"] == "progression_override:capture_name"


@pytest.mark.asyncio
async def test_lead_followup_planner_blocks_capture_when_turn_is_empty():
    state = {
        "query_text": "que tienes en santo domingo en renta",
        "vertical_slug": "real-estate",
        "active_subflow": "realtor_search",
        "conversation_memory": {"common": {}, "vertical": {}},
        "lead_progression_state": {
            "has_shown_cards": True,
            "capture_attempt_count": 1,
            "assistant_turns_since_last_capture_attempt": 3,
        },
        "execution_facts": {"status": "empty", "total_matches": 0},
        "last_result_set": {"status": "empty", "total_matches": 0, "visible_count": 0},
        "components": [],
        "last_shown_components": [{"id": "a"}],
        "history": [],
        "conversation_extraction_result": {},
        "tenant_runtime": {
            "prompts": {
                "lead_followup_planner": "followup prompt",
            }
        },
    }

    with patch(
        "app.services.lead_followup_planner.llm_service.generate_json",
        new=AsyncMock(
            return_value={
                "memory_updates": {"common": {}, "vertical": {}},
                "followup_goal": "capture_name",
                "should_ask": True,
                "question": "¿Cómo te gustaría que te llame?",
                "cta_type": "soft_question",
                "reasoning": "capture anyway",
            }
        ),
    ):
        result = await lead_followup_planner.plan(state)

    assert result["followup_goal"] == "none"
    assert result["should_ask"] is False
    assert result["question"] is None
    assert result["reasoning"] == "capture_blocked_on_empty_results"
