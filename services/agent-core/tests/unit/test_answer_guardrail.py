from app.models.contracts import (
    GoalType,
    PropertyListing,
    RAGChunk,
    RAGResult,
    RealtorSQLResult,
    RealtorSearchSlots,
    SynthesizerOutput,
    ToolName,
    ToolResult,
)
from app.runtime.answer_guardrail import run_answer_guardrail


def test_rejects_unknown_evidence_id_without_context() -> None:
    result = run_answer_guardrail(
        goal=GoalType.answer,
        synthesizer_output=SynthesizerOutput(
            text="Respuesta",
            evidence_ids=["listing-123"],
            needs_cards=False,
        ),
        tool_results=[],
        context_snapshot=None,
    )
    assert result.accepted is False
    assert result.reject_code is not None
    assert result.reject_code.value == "hallucinated_listing_id"


def test_accepts_referential_evidence_from_context_when_no_tools() -> None:
    result = run_answer_guardrail(
        goal=GoalType.answer,
        synthesizer_output=SynthesizerOutput(
            text="La última casa cuesta eso.",
            evidence_ids=["listing-123"],
            needs_cards=False,
        ),
        tool_results=[],
        context_snapshot={
            "last_tool_results": [
                {
                    "tool_name": "realtor_sql",
                    "status": "ok",
                    "realtor": {
                        "listings": [{"listing_id": "listing-123"}],
                        "sql_executed": "SELECT ...",
                    },
                }
            ]
        },
    )
    assert result.accepted is True
    assert result.reject_code is None


def test_current_tool_results_do_not_accept_stale_context_ids() -> None:
    current_tool_result = ToolResult(
        tool_name=ToolName.realtor_sql,
        status="ok",
        realtor=RealtorSQLResult(
            listings=[
                PropertyListing(
                    listing_id="new-listing",
                    title="Nueva propiedad",
                    city="Curridabat",
                    price=100000,
                    currency="USD",
                    property_type="house",
                )
            ],
            total_found=1,
            sql_executed="SELECT ...",
            slots_used=RealtorSearchSlots(features=[]),
        ),
    )

    result = run_answer_guardrail(
        goal=GoalType.realtor_refine,
        synthesizer_output=SynthesizerOutput(
            text="Resultado actual",
            evidence_ids=["old-listing"],
            needs_cards=False,
        ),
        tool_results=[current_tool_result],
        context_snapshot={
            "last_tool_results": [
                {
                    "tool_name": "realtor_sql",
                    "status": "ok",
                    "realtor": {
                        "listings": [{"listing_id": "old-listing"}],
                        "sql_executed": "SELECT OLD ...",
                    },
                }
            ]
        },
    )
    assert result.accepted is False
    assert result.reject_code is not None
    assert result.reject_code.value == "hallucinated_listing_id"


def test_rag_autofills_evidence_ids_only_when_missing() -> None:
    output = SynthesizerOutput(
        text="Soy un asesor inmobiliario virtual.",
        evidence_ids=[],
        needs_cards=False,
    )
    result = run_answer_guardrail(
        goal=GoalType.rag,
        synthesizer_output=output,
        tool_results=[
            ToolResult(
                tool_name=ToolName.rag,
                status="ok",
                rag=RAGResult(
                    chunks=[
                        RAGChunk(chunk_id="chunk-1", doc_id="doc-1", content="a", score=0.9),
                        RAGChunk(chunk_id="chunk-2", doc_id="doc-2", content="b", score=0.8),
                        RAGChunk(chunk_id="chunk-3", doc_id="doc-3", content="c", score=0.7),
                    ],
                    query_used="a que te dedicas",
                ),
            )
        ],
        context_snapshot=None,
    )
    assert result.accepted is True
    assert output.evidence_ids == ["chunk-1", "chunk-2"]


def test_rag_does_not_replace_existing_evidence_ids() -> None:
    output = SynthesizerOutput(
        text="Respuesta con evidencia.",
        evidence_ids=["chunk-2"],
        needs_cards=False,
    )
    result = run_answer_guardrail(
        goal=GoalType.rag,
        synthesizer_output=output,
        tool_results=[
            ToolResult(
                tool_name=ToolName.rag,
                status="ok",
                rag=RAGResult(
                    chunks=[
                        RAGChunk(chunk_id="chunk-1", doc_id="doc-1", content="a", score=0.9),
                        RAGChunk(chunk_id="chunk-2", doc_id="doc-2", content="b", score=0.8),
                    ],
                    query_used="a que te dedicas",
                ),
            )
        ],
        context_snapshot=None,
    )
    assert result.accepted is True
    assert output.evidence_ids == ["chunk-2"]


def test_rag_keeps_rejecting_invalid_claimed_ids() -> None:
    output = SynthesizerOutput(
        text="Respuesta con cita inválida.",
        evidence_ids=["chunk-x"],
        needs_cards=False,
    )
    result = run_answer_guardrail(
        goal=GoalType.rag,
        synthesizer_output=output,
        tool_results=[
            ToolResult(
                tool_name=ToolName.rag,
                status="ok",
                rag=RAGResult(
                    chunks=[
                        RAGChunk(chunk_id="chunk-1", doc_id="doc-1", content="a", score=0.9),
                    ],
                    query_used="a que te dedicas",
                ),
            )
        ],
        context_snapshot=None,
    )
    assert result.accepted is False
    assert result.reject_code is not None
    assert result.reject_code.value == "hallucinated_listing_id"


def test_rag_rewrites_restart_phrase_when_prior_context_exists() -> None:
    output = SynthesizerOutput(
        text="Soy un asesor inmobiliario virtual. ¿En qué puedo ayudarte hoy?",
        evidence_ids=[],
        needs_cards=False,
    )
    result = run_answer_guardrail(
        goal=GoalType.rag,
        synthesizer_output=output,
        tool_results=[
            ToolResult(
                tool_name=ToolName.rag,
                status="ok",
                rag=RAGResult(
                    chunks=[
                        RAGChunk(chunk_id="chunk-1", doc_id="doc-1", content="a", score=0.9),
                    ],
                    query_used="a que te dedicas",
                ),
            )
        ],
        context_snapshot={
            "conversation_state": {
                "presentation_state": {"cards_shown_ever": True},
                "lead_progression_state": {"user_turn_count": 1, "assistant_turn_count": 1},
            }
        },
    )
    assert result.accepted is True
    assert "¿En qué puedo ayudarte hoy?" not in output.text
    assert "¿qué presupuesto y plazo de compra manejas?" in output.text
    assert output.evidence_ids == ["chunk-1"]


def test_rag_keeps_phrase_when_no_prior_context() -> None:
    output = SynthesizerOutput(
        text="Soy un asesor inmobiliario virtual. ¿En qué puedo ayudarte hoy?",
        evidence_ids=[],
        needs_cards=False,
    )
    result = run_answer_guardrail(
        goal=GoalType.rag,
        synthesizer_output=output,
        tool_results=[
            ToolResult(
                tool_name=ToolName.rag,
                status="ok",
                rag=RAGResult(
                    chunks=[
                        RAGChunk(chunk_id="chunk-1", doc_id="doc-1", content="a", score=0.9),
                    ],
                    query_used="a que te dedicas",
                ),
            )
        ],
        context_snapshot={},
    )
    assert result.accepted is True
    assert output.text.endswith("¿En qué puedo ayudarte hoy?")
    assert output.evidence_ids == ["chunk-1"]


def test_name_declaration_rewrites_to_greeting() -> None:
    output = SynthesizerOutput(
        text="No tengo ese dato.",
        evidence_ids=[],
        needs_cards=False,
    )
    result = run_answer_guardrail(
        goal=GoalType.answer,
        synthesizer_output=output,
        tool_results=[],
        context_snapshot={
            "last_user_turn": "me llamo alvaro",
            "conversation_state": {},
        },
    )
    assert result.accepted is True
    assert "Mucho gusto, alvaro" in output.text


def test_name_recall_uses_recent_history_name() -> None:
    output = SynthesizerOutput(
        text="No recuerdo tu nombre.",
        evidence_ids=[],
        needs_cards=False,
    )
    result = run_answer_guardrail(
        goal=GoalType.answer,
        synthesizer_output=output,
        tool_results=[],
        context_snapshot={
            "last_user_turn": "recuerdas como me llamo?",
            "recent_history": [
                {"role": "user", "content": "me llamo Alvaro"},
                {"role": "assistant", "content": "Mucho gusto."},
            ],
        },
    )
    assert result.accepted is True
    assert output.text == "Sí, te llamas Alvaro."


def test_ambiguous_rooms_question_rewrites_to_clarify_reference() -> None:
    output = SynthesizerOutput(
        text="Las casas tienen habitaciones.",
        evidence_ids=[],
        needs_cards=False,
    )
    result = run_answer_guardrail(
        goal=GoalType.answer,
        synthesizer_output=output,
        tool_results=[],
        context_snapshot={
            "last_user_turn": "de cuantas habitaciones son?",
            "last_answer_envelope": {
                "cards": [
                    {"card_type": "property_card", "listing_id": "listing-1", "rooms": 3},
                    {"card_type": "property_card", "listing_id": "listing-2", "rooms": 4},
                ]
            },
        },
    )
    assert result.accepted is True
    assert output.text == "¿Te refieres a la primera, segunda o última casa que te mostré?"


def test_price_of_last_property_rewrites_with_card_price() -> None:
    output = SynthesizerOutput(
        text="No puedo recuperar el precio.",
        evidence_ids=[],
        needs_cards=False,
    )
    result = run_answer_guardrail(
        goal=GoalType.answer,
        synthesizer_output=output,
        tool_results=[],
        context_snapshot={
            "last_user_turn": "cual es el precio de la ultima casa?",
            "last_answer_envelope": {
                "evidence_ids": ["listing-1", "listing-2"],
                "cards": [
                    {
                        "card_type": "property_card",
                        "listing_id": "listing-1",
                        "price_display": "USD 100,000",
                    },
                    {
                        "card_type": "property_card",
                        "listing_id": "listing-2",
                        "price_display": "USD 200,000",
                    },
                ],
            },
        },
    )
    assert result.accepted is True
    assert output.text == "La propiedad que me indicaste tiene un precio de USD 200,000."
    assert "listing-2" in output.evidence_ids


def test_cards_permission_phrase_is_rewritten_to_next_step_question() -> None:
    output = SynthesizerOutput(
        text="Te comparto algunas opciones en Heredia. ¿Te gustaría ver más detalles?",
        evidence_ids=["listing-1"],
        needs_cards=True,
    )
    result = run_answer_guardrail(
        goal=GoalType.realtor_search,
        synthesizer_output=output,
        tool_results=[
            ToolResult(
                tool_name=ToolName.realtor_sql,
                status="ok",
                realtor=RealtorSQLResult(
                    listings=[
                        PropertyListing(
                            listing_id="listing-1",
                            title="Casa",
                            city="Heredia",
                            price=100000,
                            currency="USD",
                            property_type="house",
                        )
                    ],
                    total_found=1,
                    sql_executed="SELECT ...",
                    slots_used=RealtorSearchSlots(features=[]),
                ),
            )
        ],
        context_snapshot={"last_user_turn": "en heredia"},
    )
    assert result.accepted is True
    assert "¿Te gustaría ver más detalles?" not in output.text
    assert "¿Quieres que te comparta más opciones similares" in output.text


def test_needs_cards_is_disabled_when_no_realtor_listings() -> None:
    output = SynthesizerOutput(
        text="Respuesta de texto",
        evidence_ids=[],
        needs_cards=True,
    )
    result = run_answer_guardrail(
        goal=GoalType.answer,
        synthesizer_output=output,
        tool_results=[],
        context_snapshot={"last_user_turn": "recuerdas como me llamo?"},
    )
    assert result.accepted is True
    assert output.needs_cards is False


def test_price_rewrite_can_use_cached_property_cards_from_conversation_state() -> None:
    output = SynthesizerOutput(
        text="No puedo recuperar el precio.",
        evidence_ids=[],
        needs_cards=False,
    )
    result = run_answer_guardrail(
        goal=GoalType.answer,
        synthesizer_output=output,
        tool_results=[],
        context_snapshot={
            "last_user_turn": "cual es el precio de la ultima casa?",
            "conversation_state": {
                "presentation_state": {
                    "last_property_cards": [
                        {
                            "card_type": "property_card",
                            "listing_id": "listing-a",
                            "price_display": "USD 90,000",
                        },
                        {
                            "card_type": "property_card",
                            "listing_id": "listing-b",
                            "price_display": "USD 150,000",
                        },
                    ]
                }
            },
        },
    )
    assert result.accepted is True
    assert output.text == "La propiedad que me indicaste tiene un precio de USD 150,000."
