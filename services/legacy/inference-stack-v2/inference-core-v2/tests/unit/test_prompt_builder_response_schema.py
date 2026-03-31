from app.services.prompt_builder import PromptBuilder


def test_build_response_schema_includes_dynamic_scores_contract():
    builder = PromptBuilder(custom_template="template")

    schema = builder.build_response_schema(
        criteria=[
            {"criterion_key": "engagement", "min_score": 0, "max_score": 10},
            {"criterion_key": "intent", "min_score": 0, "max_score": 10},
        ],
        extraction_fields=[
            {"key": "extracted_name", "type": "string", "description": "Lead name"},
        ],
    )

    assert "scores" in schema["properties"]
    assert set(schema["properties"]["scores"]["required"]) == {"engagement", "intent"}
    assert schema["properties"]["scores"]["properties"]["engagement"]["minimum"] == 0
    assert schema["properties"]["scores"]["properties"]["engagement"]["maximum"] == 10
    assert "scores" in schema["required"]
    assert "extracted_data" in schema["required"]


def test_build_response_schema_honors_override():
    builder = PromptBuilder(custom_template="template")
    override = {
        "type": "object",
        "properties": {
            "custom": {"type": "string"},
        },
        "required": ["custom"],
    }

    schema = builder.build_response_schema(
        criteria=[],
        extraction_fields=[],
        response_schema_override=override,
    )

    assert schema == override
