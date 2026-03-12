from app.services.shown_results_reference_resolver import shown_results_reference_resolver


def test_resolves_last_shown_property_bathrooms():
    state = {
        "tool_plan": [
            {
                "reference_request": {
                    "mode": "shown_result",
                    "target": "last",
                    "field": "bathrooms",
                }
            }
        ],
        "last_shown_components": [
            {
                "id": "prop-1",
                "title": "Casa A",
                "location": "Heredia",
                "features": {"bathrooms": 2, "bedrooms": 3, "garage": 1},
                "price": 150000,
            },
            {
                "id": "prop-2",
                "title": "Casa B",
                "location": "Santo Domingo",
                "features": {"bathrooms": 4, "bedrooms": 5, "garage": 2},
                "price": 220000,
            },
        ],
        "last_result_set": {
            "filters": {"desired_location": "Santo Domingo"},
        },
    }

    result = shown_results_reference_resolver.resolve(state)

    assert result["execution_facts"]["status"] == "results"
    assert result["reference_resolution"]["property"]["id"] == "prop-2"
    assert result["reference_resolution"]["field"] == "bathrooms"
    assert result["reference_resolution"]["value"] == 4
    assert result["grounded_answer"] == "La última propiedad que te mostré tiene 4 baños."


def test_clarifies_when_no_shown_results_exist():
    state = {
        "tool_plan": [
            {
                "reference_request": {
                    "mode": "shown_result",
                    "target": "last",
                    "field": "bathrooms",
                }
            }
        ],
        "last_shown_components": [],
        "last_result_set": {},
    }

    result = shown_results_reference_resolver.resolve(state)

    assert result["execution_facts"]["status"] == "clarify"
    assert "No tengo una propiedad mostrada" in result["last_result_set"]["clarification"]


def test_resolves_all_known_fields_for_last_shown_property():
    state = {
        "tool_plan": [
            {
                "reference_request": {
                    "mode": "shown_result",
                    "target": "last",
                    "fields": ["all_known_fields"],
                }
            }
        ],
        "last_shown_components": [
            {
                "id": "prop-2",
                "title": "Casa B",
                "location": "Curridabat",
                "features": {"bathrooms": 2.5, "bedrooms": 3, "garage": 3},
                "price": 265000,
            },
        ],
        "last_result_set": {
            "filters": {"desired_location": "Curridabat"},
        },
    }

    result = shown_results_reference_resolver.resolve(state)

    assert result["execution_facts"]["status"] == "results"
    assert result["reference_resolution"]["field"] == "all_known_fields"
    assert result["reference_resolution"]["values"]["price"] == 265000
    assert result["reference_resolution"]["values"]["bathrooms"] == 2.5
    assert "Curridabat" in result["grounded_answer"]
    assert "$265,000" in result["grounded_answer"]
