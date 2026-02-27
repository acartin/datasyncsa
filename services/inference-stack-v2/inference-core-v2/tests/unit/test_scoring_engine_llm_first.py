from app.services.scoring_engine import ScoringEngine


def test_extract_scores_and_explanations_defaults_missing_criteria():
    engine = ScoringEngine()
    criteria = [
        {"criterion_key": "intent", "min_score": 0, "max_score": 10},
        {"criterion_key": "timeline", "min_score": 0, "max_score": 10},
    ]
    payload = {
        "scores": {"intent": 8},
        "reasoning": "Lead con alta senal de avance",
    }

    scores, explanations, missing = engine._extract_scores_and_explanations(
        criteria=criteria,
        payload=payload,
    )

    assert scores["intent"] == 8.0
    assert scores["timeline"] == 0.0
    assert "timeline" in missing
    assert "default conservador" in explanations["timeline"].lower()


def test_extract_scores_and_explanations_uses_contract_missing_default_range():
    engine = ScoringEngine()
    criteria = [
        {"criterion_key": "intent", "min_score": 0, "max_score": 10},
        {"criterion_key": "timeline", "min_score": 0, "max_score": 10},
    ]
    payload = {
        "scores": {"intent": 8},
        "reasoning": "Lead con alta senal de avance",
    }

    scores, explanations, missing = engine._extract_scores_and_explanations(
        criteria=criteria,
        payload=payload,
        missing_score_policy={"global": {"min": 1.0, "max": 2.0}},
    )

    assert scores["intent"] == 8.0
    assert scores["timeline"] == 1.5
    assert "timeline" in missing
    assert "default conservador 1.5" in explanations["timeline"].lower()


def test_parse_extraction_schema_uses_response_schema_override_and_fields():
    engine = ScoringEngine()
    extraction_schema = {
        "scoring_contract": {
            "missing_evidence_default_range": {"min": 1, "max": 2}
        },
        "response_schema": {
            "type": "object",
            "properties": {
                "scores": {"type": "object"},
                "extracted_data": {
                    "type": "object",
                    "properties": {
                        "extracted_email": {"type": "string"},
                    },
                },
            },
            "required": ["scores", "extracted_data"],
        }
    }

    parsed = engine._parse_extraction_schema_config(extraction_schema)

    assert parsed["response_schema_override"] == extraction_schema["response_schema"]
    assert parsed["extraction_fields"][0]["key"] == "extracted_email"
    assert parsed["missing_score_policy"]["global"] == {"min": 1.0, "max": 2.0}


def test_extract_scores_and_explanations_uses_criterion_default_over_global():
    engine = ScoringEngine()
    criteria = [
        {"criterion_key": "intent", "min_score": 0, "max_score": 10},
        {"criterion_key": "timeline", "min_score": 0, "max_score": 10},
    ]
    payload = {"scores": {}}

    scores, _, missing = engine._extract_scores_and_explanations(
        criteria=criteria,
        payload=payload,
        missing_score_policy={
            "global": {"min": 1.0, "max": 2.0},
            "by_criterion": {
                "timeline": {"value": 0.5},
            },
            "fallback_mode": "min_score",
        },
    )

    assert scores["intent"] == 1.5
    assert scores["timeline"] == 0.5
    assert missing == ["intent", "timeline"]


def test_scoring_engine_caps_timeout_and_uses_output_token_limit(mocker):
    mocker.patch("app.services.scoring_engine.settings.scoring_llm_timeout_secs", 60)
    mocker.patch("app.services.scoring_engine.settings.scoring_llm_hard_timeout_secs", 10)
    mocker.patch("app.services.scoring_engine.settings.scoring_llm_max_output_tokens", 700)

    engine = ScoringEngine()

    assert engine._timeout == 10
    assert engine._max_output_tokens == 700
