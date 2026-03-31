from app.services.answer_synthesizer import answer_synthesizer


def test_rewrite_presentation_conflict_when_cards_are_already_visible():
    state = {
        "components": [{"id": "a"}, {"id": "b"}],
        "last_result_set": {
            "search_summary": "casas en Heredia",
            "total_matches": 2,
            "visible_count": 2,
        },
        "followup_plan": {
            "question": "¿Tienes alguna preferencia de precio?",
        },
    }

    violating_answer = "Encontré 2 casas en Heredia. ¿Te gustaría que te las muestre?"

    assert answer_synthesizer._violates_presentation_contract(violating_answer, state) is True
    rewritten = answer_synthesizer._rewrite_presentation_conflict(state)
    assert "¿Te gustaría que te las muestre" not in rewritten
    assert "Aquí te muestro" in rewritten
    assert "¿Tienes alguna preferencia de precio?" in rewritten


def test_grounded_answer_takes_precedence_for_reference_resolution():
    state = {
        "execution_facts": {
            "reference_answer": "La última propiedad que te mostré tiene 2 baños.",
        },
        "followup_plan": {
            "question": "¿Te gustaría que filtre por número de baños?",
        },
    }

    assert (
        answer_synthesizer._grounded_answer(state)
        == "La última propiedad que te mostré tiene 2 baños. ¿Te gustaría que filtre por número de baños?"
    )


def test_grounded_answer_trims_duplicated_followup_prefix():
    state = {
        "execution_facts": {
            "reference_answer": "La última propiedad que te mostré tiene 2 baños.",
        },
        "followup_plan": {
            "question": "La última propiedad que te mostré tiene 2 baños. ¿Te gustaría ver más detalles?",
        },
    }

    assert (
        answer_synthesizer._grounded_answer(state)
        == "La última propiedad que te mostré tiene 2 baños. ¿Te gustaría ver más detalles?"
    )


def test_grounded_answer_drops_followup_that_repeats_same_reference_field():
    state = {
        "execution_facts": {
            "reference_answer": "La última propiedad que te mostré tiene un precio de $265,000.",
            "reference_resolution": {
                "field": "price",
                "fields": ["price"],
            },
        },
        "followup_plan": {
            "question": "¿Te gustaría saber el precio de esa casa o prefieres que busquemos otras opciones?",
        },
    }

    assert (
        answer_synthesizer._grounded_answer(state)
        == "La última propiedad que te mostré tiene un precio de $265,000."
    )


def test_enforce_followup_contract_appends_missing_required_question():
    state = {
        "followup_plan": {
            "should_ask": True,
            "question": "Por cierto, ¿cómo te gustaría que te llame?",
        }
    }

    assert (
        answer_synthesizer._enforce_followup_contract(
            "Encontré 33 propiedades en Heredia. Te muestro algunas de las opciones disponibles.",
            state,
        )
        == "Encontré 33 propiedades en Heredia. Te muestro algunas de las opciones disponibles. Por cierto, ¿cómo te gustaría que te llame?"
    )


def test_enforce_followup_contract_does_not_duplicate_same_question_with_different_prefix():
    state = {
        "followup_plan": {
            "should_ask": True,
            "question": "Por cierto, ¿cómo te gustaría que te llame?",
        }
    }

    assert (
        answer_synthesizer._enforce_followup_contract(
            "Encontré 33 propiedades en Heredia. Te muestro 4 para empezar. ¿Cómo te gustaría que te llame?",
            state,
        )
        == "Encontré 33 propiedades en Heredia. Te muestro 4 para empezar. ¿Cómo te gustaría que te llame?"
    )


def test_enforce_followup_contract_does_not_duplicate_semantic_followup():
    state = {
        "followup_plan": {
            "should_ask": True,
            "question": "¿Te gustaría que ajustemos la búsqueda por precio o número de habitaciones?",
        }
    }

    assert (
        answer_synthesizer._enforce_followup_contract(
            "Claro, encontré algunas propiedades en Heredia. Podemos ajustar la búsqueda por precio o número de habitaciones.",
            state,
        )
        == "Claro, encontré algunas propiedades en Heredia. Podemos ajustar la búsqueda por precio o número de habitaciones."
    )


def test_enforce_followup_contract_replaces_multiple_question_variants_with_single_planned_question():
    state = {
        "followup_plan": {
            "should_ask": True,
            "question": "¿Cuál es tu presupuesto aproximado?",
        }
    }

    assert (
        answer_synthesizer._enforce_followup_contract(
            "Encontré 24 casas con dos habitaciones, Ana. Te muestro 4 para empezar. ¿Cuál es tu presupuesto aproximado? ¿Cuál es tu presupuesto aproximado, Ana?",
            state,
        )
        == "Encontré 24 casas con dos habitaciones, Ana. Te muestro 4 para empezar. ¿Cuál es tu presupuesto aproximado?"
    )


def test_rewrite_absent_components_conflict_strips_show_language_when_no_cards():
    state = {"components": [], "followup_plan": {}}

    assert answer_synthesizer._violates_absent_components_contract(
        "Tu presupuesto es de $100,000. ¿Te gustaría que busquemos otras opciones o te muestro la casa que encontré?",
        state,
    ) is True
    assert (
        answer_synthesizer._rewrite_absent_components_conflict(
            "Tu presupuesto es de $100,000. ¿Te gustaría que busquemos otras opciones o te muestro la casa que encontré?",
            state,
        )
        == "Tu presupuesto es de $100,000."
    )


def test_normalize_surface_text_removes_duplicate_sentences():
    assert (
        answer_synthesizer._normalize_surface_text(
            "No vendemos helados, nos especializamos en bienes raíces. No vendemos helados, nos especializamos en bienes raíces."
        )
        == "No vendemos helados, nos especializamos en bienes raíces."
    )
