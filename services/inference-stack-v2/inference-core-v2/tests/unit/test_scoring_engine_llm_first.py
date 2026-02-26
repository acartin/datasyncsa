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
    assert scores["timeline"] == 5.0
    assert "timeline" in missing
    assert "default conservador" in explanations["timeline"].lower()


def test_parse_extraction_schema_uses_response_schema_override_and_fields():
    engine = ScoringEngine()
    extraction_schema = {
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
