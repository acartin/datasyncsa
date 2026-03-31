from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.models.chat_v2 import ChatV2Request, ScorecardV2
from app.services.scoring_orchestrator import ScoringOrchestrator


@pytest.mark.asyncio
async def test_get_active_scoring_model_cache_hit(mocker):
    """Uses cache result and skips repository lookup when cache hits."""
    mock_cache = mocker.patch("app.services.scoring_orchestrator.cache_service")
    cached_model = {
        "id": str(uuid4()),
        "version": 1,
        "prompt_version": 1,
        "criteria": [],
    }
    mock_cache.get_active_model = AsyncMock(return_value=cached_model)

    orchestrator = ScoringOrchestrator(AsyncMock())
    orchestrator.repo = AsyncMock()

    result = await orchestrator.get_active_scoring_model(
        client_id=uuid4(),
        vertical_id=1,
        scoring_model_id=None,
    )

    assert result == cached_model
    orchestrator.repo.get_active_scoring_model.assert_not_called()


def test_build_scorecard_from_result_clamps_scores_and_sets_priority():
    orchestrator = ScoringOrchestrator(AsyncMock())

    model_data = {
        "version": 3,
        "criteria": [
            {
                "criterion_key": "intent",
                "weight": 1.0,
                "min_score": 0,
                "max_score": 10,
                "bands": [
                    {"band_key": "low", "min_score": 0, "max_score": 5},
                    {"band_key": "high", "min_score": 5, "max_score": 10},
                ],
            },
            {
                "criterion_key": "urgency",
                "weight": 1.0,
                "min_score": 0,
                "max_score": 10,
                "bands": [],
            },
        ],
    }
    result = {
        "scores": {
            "intent": 20,   # clamp to 10
            "urgency": -1,  # clamp to 0
        },
        "explanations": {
            "intent": "Muy alto",
            "urgency": "No urgente",
        },
        "reasoning": "Resultado de prueba",
    }

    scorecard = orchestrator._build_scorecard_from_result(model_data=model_data, result=result)

    assert isinstance(scorecard, ScorecardV2)
    assert scorecard.model_version == 3
    assert len(scorecard.score_items) == 2
    assert scorecard.score_items[0].score == 10.0
    # Score 10.0 should now match band 'high' (max_score=10 is inclusive with epsilon)
    assert scorecard.score_items[0].band_key == "high"
    assert scorecard.score_items[1].score == 0.0
    assert scorecard.priority_label == "Media"


@pytest.mark.asyncio
async def test_process_chat_missing_tenant_vertical_mapping(mocker):
    orchestrator = ScoringOrchestrator(AsyncMock())

    mocker.patch.object(
        orchestrator,
        "resolve_vertical_for_client",
        new=AsyncMock(side_effect=ValueError("TENANT_VERTICAL_NOT_CONFIGURED")),
    )

    request = ChatV2Request(query_text="Test query", client_id=uuid4())

    with pytest.raises(ValueError, match="TENANT_VERTICAL_NOT_CONFIGURED"):
        await orchestrator.process_chat(request)


@pytest.mark.asyncio
async def test_process_chat_preserves_realtor_search_state_when_clarification_has_no_new_state(mocker):
    db_session = AsyncMock()
    orchestrator = ScoringOrchestrator(db_session)
    orchestrator.repo = AsyncMock()
    orchestrator.job_service = AsyncMock()
    orchestrator.realtor_turn_executor = AsyncMock()

    previous_search_state = {
        "planner_last_property_query": "casas en heredia",
        "planner_last_sql": "SELECT * FROM lead_properties WHERE client_id = 'x'",
        "intent": "PROPERTY_SEARCH",
    }

    orchestrator._resolve_runtime_context = AsyncMock(return_value={
        "vertical_ctx": {
            "client_exists": True,
            "vertical_id": 1,
            "vertical_slug": "realtor",
            "scoring_model_id": str(uuid4()),
        },
        "model_data": {"id": str(uuid4()), "version": 1, "criteria": []},
        "prompt_config": {"id": str(uuid4()), "version": 1},
        "client_prompt_text": "prompt ok",
        "chat_prompt_slug": "primary_chat",
        "realtor_search_state": previous_search_state.copy(),
    })
    orchestrator._plan_realtor_turn = AsyncMock(return_value={"intent": "CLARIFICATION"})
    orchestrator.repo.get_lead_by_conversation_id = AsyncMock(return_value=None)
    orchestrator.repo.get_or_create_lead = AsyncMock(return_value=uuid4())
    orchestrator.repo.get_or_create_conversation = AsyncMock()
    orchestrator.repo.set_conversation_context_snapshot = AsyncMock()
    orchestrator.repo.update_conversation = AsyncMock(return_value={"lead_messages": 1})

    mocker.patch("app.services.scoring_orchestrator.settings.scoring_bg_enabled", False)

    request = ChatV2Request(query_text="aceptan mascotas?", client_id=uuid4(), conversation_id=uuid4())

    response = await orchestrator.process_chat(request)

    assert response.answer == "¿Qué aspecto quieres precisar de la búsqueda?"
    snapshot_payload = orchestrator.repo.set_conversation_context_snapshot.await_args.kwargs["snapshot"]
    assert snapshot_payload["realtor_search_state"]["planner_last_property_query"] == previous_search_state["planner_last_property_query"]
    assert snapshot_payload["realtor_search_state"]["planner_last_sql"] == previous_search_state["planner_last_sql"]
    assert snapshot_payload["realtor_search_state"]["intent"] == previous_search_state["intent"]
    assert snapshot_payload["realtor_search_state"]["awaiting_property_confirmation"] is True


@pytest.mark.asyncio
async def test_process_chat_synthesizes_realtor_answer_from_executor_facts(mocker):
    db_session = AsyncMock()
    orchestrator = ScoringOrchestrator(db_session)
    orchestrator.repo = AsyncMock()
    orchestrator.job_service = AsyncMock()
    orchestrator.realtor_turn_executor = AsyncMock()

    orchestrator._resolve_runtime_context = AsyncMock(return_value={
        "vertical_ctx": {
            "client_exists": True,
            "vertical_id": 1,
            "vertical_slug": "realtor",
            "scoring_model_id": str(uuid4()),
        },
        "model_data": {"id": str(uuid4()), "version": 1, "criteria": []},
        "prompt_config": {"id": str(uuid4()), "version": 1},
        "client_prompt_text": "prompt ok",
        "chat_prompt_slug": "primary_chat",
        "realtor_search_state": {},
    })
    orchestrator._plan_realtor_turn = AsyncMock(return_value={
        "intent": "PROPERTY_SEARCH",
        "sql": "SELECT * FROM lead_properties WHERE client_id = '{client_id}' LIMIT 4",
        "search_summary": "casas en Heredia",
    })
    orchestrator.realtor_turn_executor.execute = AsyncMock(return_value={
        "handled": True,
        "status": "results",
        "operation": "PROPERTY_SEARCH",
        "components": [{"type": "property-card", "title": "Casa 1", "price": 100, "location": "Heredia"}],
        "facts": {"total_matches": 7, "visible_count": 1, "search_summary": "casas en Heredia"},
        "search_state": {"planner_last_property_query": "casas en heredia", "planner_last_sql": "SELECT ...", "intent": "PROPERTY_SEARCH", "search_summary": "casas en Heredia"},
    })
    orchestrator._generate_realtor_answer = AsyncMock(return_value="Encontré 7 casas en Heredia. Te muestro algunas para empezar.")
    orchestrator.repo.get_lead_by_conversation_id = AsyncMock(return_value=None)
    orchestrator.repo.get_or_create_lead = AsyncMock(return_value=uuid4())
    orchestrator.repo.get_or_create_conversation = AsyncMock()
    orchestrator.repo.set_conversation_context_snapshot = AsyncMock()
    orchestrator.repo.update_conversation = AsyncMock(return_value={"lead_messages": 1})

    mocker.patch("app.services.scoring_orchestrator.settings.scoring_bg_enabled", False)

    request = ChatV2Request(query_text="casas en heredia", client_id=uuid4(), conversation_id=uuid4())

    response = await orchestrator.process_chat(request)

    assert response.answer == "Encontré 7 casas en Heredia. Te muestro algunas para empezar."
    assert response.realtor_turn["search_summary"] == "casas en Heredia"
    assert response.components[0]["type"] == "property-card"
    snapshot_payload = orchestrator.repo.set_conversation_context_snapshot.await_args.kwargs["snapshot"]
    assert snapshot_payload["realtor_search_state"]["search_summary"] == "casas en Heredia"


@pytest.mark.asyncio
async def test_process_chat_persists_conversation_extraction_result_common_and_vertical(mocker):
    db_session = AsyncMock()
    orchestrator = ScoringOrchestrator(db_session)
    orchestrator.repo = AsyncMock()
    orchestrator.job_service = AsyncMock()
    orchestrator.realtor_turn_executor = AsyncMock()

    orchestrator._resolve_runtime_context = AsyncMock(return_value={
        "vertical_ctx": {
            "client_exists": True,
            "vertical_id": 1,
            "vertical_slug": "realtor",
            "scoring_model_id": str(uuid4()),
        },
        "model_data": {"id": str(uuid4()), "version": 1, "criteria": []},
        "prompt_config": {"id": str(uuid4()), "version": 1},
        "client_prompt_text": "prompt ok",
        "chat_prompt_slug": "primary_chat",
        "realtor_search_state": {},
        "conversation_extraction_result": {},
    })
    orchestrator._plan_realtor_turn = AsyncMock(return_value={
        "intent": "PROPERTY_SEARCH",
        "sql": "SELECT * FROM lead_properties WHERE client_id = '{client_id}' LIMIT 4",
        "search_summary": "casas en Heredia con dos habitaciones",
        "filters": {
            "desired_location": "Heredia",
            "property_type": "casa",
            "bedrooms_min": 2,
        },
    })
    orchestrator.realtor_turn_executor.execute = AsyncMock(return_value={
        "handled": True,
        "status": "results",
        "components": [{"type": "property-card"}],
        "facts": {
            "total_matches": 3,
            "visible_count": 1,
            "search_summary": "casas en Heredia con dos habitaciones",
        },
        "search_state": {
            "planner_last_property_query": "me llamo alvaro, busco casas en heredia con dos habitaciones",
            "planner_last_sql": "SELECT ...",
            "intent": "PROPERTY_SEARCH",
            "search_summary": "casas en Heredia con dos habitaciones",
            "filters": {
                "desired_location": "Heredia",
                "property_type": "casa",
                "bedrooms_min": 2,
            },
        },
    })
    orchestrator._generate_realtor_answer = AsyncMock(return_value="Encontré 3 casas en Heredia.")
    orchestrator.repo.get_lead_by_conversation_id = AsyncMock(return_value=None)
    orchestrator.repo.get_or_create_lead = AsyncMock(return_value=uuid4())
    orchestrator.repo.get_or_create_conversation = AsyncMock()
    orchestrator.repo.set_conversation_context_snapshot = AsyncMock()
    orchestrator.repo.update_conversation = AsyncMock(return_value={"lead_messages": 1})
    orchestrator.repo.update_lead_from_extraction = AsyncMock(return_value=True)

    mocker.patch("app.services.scoring_orchestrator.settings.scoring_bg_enabled", False)

    request = ChatV2Request(
        query_text="me llamo alvaro, busco casas en heredia con dos habitaciones",
        client_id=uuid4(),
        conversation_id=uuid4(),
    )

    await orchestrator.process_chat(request)

    snapshot_payload = orchestrator.repo.set_conversation_context_snapshot.await_args.kwargs["snapshot"]
    assert snapshot_payload["conversation_extraction_result"]["common"]["extracted_name"] == "alvaro"
    assert snapshot_payload["conversation_extraction_result"]["vertical"]["desired_location"] == "Heredia"
    assert snapshot_payload["conversation_extraction_result"]["vertical"]["property_type"] == "casa"
    assert snapshot_payload["conversation_extraction_result"]["vertical"]["bedrooms_min"] == 2


@pytest.mark.asyncio
async def test_resolve_realtor_answer_prompt_does_not_cache_guardrails_into_primary_prompt(mocker):
    orchestrator = ScoringOrchestrator(AsyncMock())
    orchestrator.repo = AsyncMock()
    orchestrator.repo.get_client_system_prompt = AsyncMock(side_effect=[None, None])

    mock_cache = mocker.patch("app.services.scoring_orchestrator.cache_service")
    mock_cache.get_client_chat_prompt = AsyncMock(side_effect=[None, None, "PROMPT PRIMARY RAW"])
    mock_cache.set_client_chat_prompt = AsyncMock()

    prompt = await orchestrator._resolve_realtor_answer_prompt(uuid4())

    assert prompt.startswith("PROMPT PRIMARY RAW")
    assert orchestrator._REALTOR_ANSWER_GUARDRAILS in prompt
    mock_cache.set_client_chat_prompt.assert_not_called()


@pytest.mark.asyncio
async def test_create_scorecard_with_engine_enriches_conversation_snapshot():
    orchestrator = ScoringOrchestrator(AsyncMock())
    repo = AsyncMock()
    db_session = AsyncMock()
    scorecard_id = uuid4()
    lead_id = uuid4()
    client_id = uuid4()
    conversation_id = uuid4()

    repo.upsert_scorecard = AsyncMock(return_value=scorecard_id)
    repo.create_score_items = AsyncMock()
    repo.update_lead_current_scorecard = AsyncMock()
    repo.update_lead_from_extraction = AsyncMock(return_value=True)
    repo.get_conversation_context_snapshot = AsyncMock(return_value={
        "vertical_ctx": {"vertical_slug": "realtor"},
        "conversation_extraction_result": {
            "common": {"extracted_name": "Alvaro"},
            "vertical": {"desired_location": "Heredia"},
        },
    })
    repo.set_conversation_context_snapshot = AsyncMock()

    scorecard_data = ScorecardV2(
        score_total=7.5,
        priority_label="Media",
        reasoning="ok",
        model_version=1,
        prompt_version=1,
        score_items=[],
    )

    await orchestrator._create_scorecard_with_engine(
        repo=repo,
        db_session=db_session,
        lead_id=lead_id,
        client_id=client_id,
        model_data={"id": str(uuid4()), "version": 1, "criteria": []},
        scorecard_data=scorecard_data,
        prompt_config={"id": str(uuid4()), "version": 1},
        result={
            "prompt_snapshot": "snapshot",
            "extraction_result": {
                "extracted_budget": "250000",
                "extracted_email": "alvaro@example.com",
            },
            "slot_state": {},
            "json_valid": True,
            "response_chars": 100,
            "fallback_used": False,
        },
        conversation_id=conversation_id,
    )

    snapshot_payload = repo.set_conversation_context_snapshot.await_args.kwargs["snapshot"]
    assert snapshot_payload["conversation_extraction_result"]["common"]["extracted_name"] == "Alvaro"
    assert snapshot_payload["conversation_extraction_result"]["common"]["extracted_budget"] == "250000"
    assert snapshot_payload["conversation_extraction_result"]["common"]["extracted_email"] == "alvaro@example.com"
    assert snapshot_payload["conversation_extraction_result"]["vertical"]["desired_location"] == "Heredia"


def test_build_scorecard_response_from_repo_dict():
    orchestrator = ScoringOrchestrator(AsyncMock())

    scorecard_id = uuid4()
    lead_id = uuid4()
    conversation_id = uuid4()
    model_id = uuid4()
    band_id = uuid4()
    now = datetime.now(timezone.utc)
    scorecard = {
        "id": scorecard_id,
        "lead_id": lead_id,
        "conversation_id": conversation_id,
        "model_id": model_id,
        "model_version": 2,
        "prompt_version": 4,
        "prompt_id": None,
        "score_total": 8.5,
        "priority_label": "high",
        "reasoning": "Bien calificado",
        "extraction_result": {"extracted_name": "Alice"},
        "created_at": now,
        "score_items": [
            {
                "criterion_key": "intent",
                "score": 9.0,
                "band_id": band_id,
                "explanation": "Alto interés",
                "extracted_data": {"confidence": 0.9},
                "created_at": now,
            }
        ],
    }

    response = orchestrator._build_scorecard_response(scorecard)

    assert response["id"] == str(scorecard_id)
    assert response["lead_id"] == str(lead_id)
    assert response["conversation_id"] == str(conversation_id)
    assert response["model_id"] == str(model_id)
    assert response["model_version"] == 2
    assert response["score_total"] == 8.5
    assert len(response["score_items"]) == 1
    assert response["score_items"][0]["criterion_key"] == "intent"
    assert response["score_items"][0]["band_id"] == str(band_id)


@pytest.mark.asyncio
async def test_get_scoring_ops_summary_clamps_window_and_uses_service():
    orchestrator = ScoringOrchestrator(AsyncMock())
    orchestrator.job_service = AsyncMock()
    orchestrator.job_service.get_ops_summary = AsyncMock(return_value={"window_minutes": 1440})

    result = await orchestrator.get_scoring_ops_summary(window_minutes=99999)

    assert result == {"window_minutes": 1440}
    orchestrator.job_service.get_ops_summary.assert_called_once_with(window_minutes=1440)


def test_select_chat_prompt_slug_uses_vertical_and_channel_metadata():
    orchestrator = ScoringOrchestrator(AsyncMock())

    slug = orchestrator._select_chat_prompt_slug(
        vertical_ctx={"vertical_slug": "realtor"},
        user_metadata={"channel": "meta_whatsapp"},
    )
    assert slug == "realtor_meta_whatsapp_v1"

    fallback_slug = orchestrator._select_chat_prompt_slug(
        vertical_ctx={"vertical_slug": "realtor"},
        user_metadata={"channel": "unknown-channel"},
    )
    assert fallback_slug == "realtor_web_v1"


@pytest.mark.asyncio
async def test_resolve_runtime_context_falls_back_to_primary_chat_when_prompt_slug_missing():
    orchestrator = ScoringOrchestrator(AsyncMock())
    orchestrator.repo = AsyncMock()
    orchestrator.repo.get_conversation_context_snapshot = AsyncMock(return_value=None)
    orchestrator.resolve_vertical_for_client = AsyncMock(return_value={
        "client_exists": True,
        "vertical_id": 1,
        "vertical_slug": "realtor",
        "scoring_model_id": str(uuid4()),
    })
    orchestrator.get_active_scoring_model = AsyncMock(return_value={"id": str(uuid4())})
    orchestrator.get_or_create_prompt = AsyncMock(return_value={"id": str(uuid4())})
    orchestrator.repo.get_client_system_prompt = AsyncMock(side_effect=[None, "primary prompt text"])

    request = ChatV2Request(
        query_text="hola",
        client_id=uuid4(),
        user_metadata={"channel": "meta_whatsapp"},
    )

    runtime_ctx = await orchestrator._resolve_runtime_context(request, conversation_id=uuid4())

    assert runtime_ctx["chat_prompt_slug"] == "primary_chat"
    assert runtime_ctx["client_prompt_text"] == "primary prompt text"
    assert orchestrator.repo.get_client_system_prompt.await_count == 2
    assert orchestrator.repo.get_client_system_prompt.await_args_list[0].kwargs["slug"] == "realtor_meta_whatsapp_v1"
    assert orchestrator.repo.get_client_system_prompt.await_args_list[1].kwargs["slug"] == "primary_chat"


@pytest.mark.asyncio
async def test_resolve_runtime_context_uses_prompt_slug_from_channel_when_available():
    orchestrator = ScoringOrchestrator(AsyncMock())
    orchestrator.repo = AsyncMock()
    orchestrator.repo.get_conversation_context_snapshot = AsyncMock(return_value=None)
    orchestrator.resolve_vertical_for_client = AsyncMock(return_value={
        "client_exists": True,
        "vertical_id": 1,
        "vertical_slug": "realtor",
        "scoring_model_id": str(uuid4()),
    })
    orchestrator.get_active_scoring_model = AsyncMock(return_value={"id": str(uuid4())})
    orchestrator.get_or_create_prompt = AsyncMock(return_value={"id": str(uuid4())})
    orchestrator.repo.get_client_system_prompt = AsyncMock(return_value="meta ig prompt")

    request = ChatV2Request(
        query_text="hola",
        client_id=uuid4(),
        user_metadata={"channel": "meta_ig"},
    )

    runtime_ctx = await orchestrator._resolve_runtime_context(request, conversation_id=uuid4())

    assert runtime_ctx["chat_prompt_slug"] == "realtor_meta_ig_v1"
    assert runtime_ctx["client_prompt_text"] == "meta ig prompt"
    orchestrator.repo.get_client_system_prompt.assert_awaited_once()
    assert orchestrator.repo.get_client_system_prompt.await_args.kwargs["slug"] == "realtor_meta_ig_v1"
