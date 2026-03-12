from app.services.realtor_context_resolver import realtor_context_resolver


def test_realtor_context_resolver_answers_active_filter_summary_without_cards():
    state = {
        "tool_plan": [
            {
                "user_goal": "search_state",
                "requested_fields": ["filters"],
            }
        ],
        "active_search_state": {
            "filters": {
                "desired_location": "Heredia",
                "bathrooms_min": 2,
            },
            "search_summary": "casas en Heredia",
        },
        "last_result_set": {},
    }

    result = realtor_context_resolver.resolve(state)

    assert result["execution_facts"]["status"] == "results"
    assert result["components"] == []
    assert "Heredia" in result["grounded_answer"]
    assert "baños" in result["grounded_answer"]


def test_realtor_context_resolver_acknowledges_budget_capture_reply():
    state = {
        "tool_plan": [
            {
                "user_goal": "capture_reply",
                "capture_reply": {
                    "field": "budget",
                    "value": 300000,
                },
            }
        ],
        "last_result_set": {},
    }

    result = realtor_context_resolver.resolve(state)

    assert result["execution_facts"]["status"] == "results"
    assert "$300,000" in result["grounded_answer"]
