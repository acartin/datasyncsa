import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.models.chat_v2 import ChatV2Request
from app.services.scoring_orchestrator import ScoringOrchestrator


def test_default_vector_category_for_realtor_vertical():
    assert ScoringOrchestrator._default_vector_category_for_vertical("realtor") == "property"
    assert ScoringOrchestrator._default_vector_category_for_vertical("inmobiliaria") == "property"
    assert ScoringOrchestrator._default_vector_category_for_vertical("automotive") is None


@pytest.mark.asyncio
async def test_build_hybrid_context_uses_tenant_scoped_history():
    orchestrator = ScoringOrchestrator(AsyncMock())
    orchestrator.repo = AsyncMock()
    orchestrator.repo.get_conversation_messages = AsyncMock(
        return_value=[{"role": "user", "content": "Hola"}]
    )
    orchestrator._retrieve_vertical_vector_context = AsyncMock(return_value=[])
    orchestrator._retrieve_structured_business_context = AsyncMock(return_value={})

    request = ChatV2Request(query_text="Necesito una casa", client_id=uuid4())
    vertical_ctx = {"vertical_id": 1, "vertical_slug": "realtor"}
    conversation_id = uuid4()

    result = await orchestrator._build_hybrid_context(
        request=request,
        vertical_ctx=vertical_ctx,
        conversation_id=conversation_id,
    )

    assert result["history"] == [{"role": "user", "content": "Hola"}]
    assert result["vector_chunks"] == []
    assert result["structured_facts"] == {}
    orchestrator.repo.get_conversation_messages.assert_called_once()


@pytest.mark.asyncio
async def test_vector_context_uses_v2_retriever_with_realtor_category():
    orchestrator = ScoringOrchestrator(AsyncMock())
    orchestrator.hybrid_retriever.search = AsyncMock(return_value=[{"content_id": "x"}])
    request = ChatV2Request(query_text="apartamentos", client_id=uuid4(), filters={})
    vertical_ctx = {"vertical_slug": "realtor"}

    result = await orchestrator._retrieve_vertical_vector_context(request, vertical_ctx)

    assert result == [{"content_id": "x"}]
    orchestrator.hybrid_retriever.search.assert_called_once()
    _, kwargs = orchestrator.hybrid_retriever.search.call_args
    assert kwargs["filters"]["category"] == "property"


@pytest.mark.asyncio
async def test_generate_chat_response_includes_history_and_hybrid_placeholders():
    orchestrator = ScoringOrchestrator(AsyncMock())
    orchestrator.repo = AsyncMock()
    orchestrator.repo.get_client_system_prompt = AsyncMock(return_value="Sistema base")
    orchestrator.repo.get_conversation_messages = AsyncMock(
        return_value=[{"role": "user", "content": "Busco 2 habitaciones"}]
    )
    orchestrator._retrieve_vertical_vector_context = AsyncMock(return_value=[])
    orchestrator._retrieve_structured_business_context = AsyncMock(return_value={})

    llm_response = MagicMock()
    llm_response.text = "Respuesta generada"
    llm_client = MagicMock()
    llm_client.models.generate_content.return_value = llm_response
    orchestrator._llm_client = llm_client

    request = ChatV2Request(query_text="Presupuesto 200k", client_id=uuid4())
    vertical_ctx = {"vertical_id": 1, "vertical_slug": "realtor"}
    conversation_id = uuid4()

    answer = await orchestrator._generate_chat_response(
        request=request,
        vertical_ctx=vertical_ctx,
        conversation_id=conversation_id,
    )

    assert answer == "Respuesta generada"
    _, kwargs = llm_client.models.generate_content.call_args
    prompt = kwargs["contents"][0]
    assert "Usuario: Busco 2 habitaciones" in prompt
    assert "[sin resultados vectoriales]" in prompt
    assert "[sin contexto estructurado]" in prompt
    config = kwargs["config"]
    assert getattr(config, "max_output_tokens", None) is not None


def test_truncate_history_context_keeps_recent_tail():
    text = "A" * 2500
    truncated = ScoringOrchestrator._truncate_history_context(text, max_chars=1000)
    assert truncated.startswith("[historial truncado por longitud]")
    assert len(truncated) > 1000
    assert truncated.endswith("A" * 1000)


@pytest.mark.asyncio
async def test_structured_context_without_conversation_id_returns_hints_only():
    orchestrator = ScoringOrchestrator(AsyncMock())
    orchestrator.repo = AsyncMock()

    request = ChatV2Request(
        query_text="Quiero ver opciones",
        client_id=uuid4(),
        user_metadata={"brand_project": "demo", "source_property_ref": "prop-123"},
    )
    vertical_ctx = {"vertical_slug": "realtor", "vertical_name": "Real Estate"}

    result = await orchestrator._retrieve_structured_business_context(request, vertical_ctx)

    assert result["conversation_metrics"] is None
    assert result["lead_snapshot"] is None
    assert "property_inventory" in result["vertical_sql_placeholders"]
    assert result["realtor_hints"]["brand_project"] == "demo"
    assert result["realtor_hints"]["source_property_ref"] == "prop-123"
