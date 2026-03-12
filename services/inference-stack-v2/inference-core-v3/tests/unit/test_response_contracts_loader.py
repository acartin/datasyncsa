from app.services.response_contracts_loader import response_contracts_loader


def test_response_contracts_loader_exposes_answer_and_followup_sections():
    contracts = response_contracts_loader.load()

    assert "answer_synthesizer" in contracts
    assert "lead_followup_planner" in contracts


def test_response_contracts_loader_exposes_expected_policy_keys():
    answer_contracts = response_contracts_loader.get_section("answer_synthesizer")
    followup_contracts = response_contracts_loader.get_section("lead_followup_planner")

    assert "no_component_show_markers" in answer_contracts
    assert "presentation_permission_patterns" in answer_contracts
    assert "reference_field_markers" in answer_contracts

    assert "field_goal_map" in followup_contracts
    assert "capture_goal_priority" in followup_contracts
    assert "default_capture_questions" in followup_contracts
