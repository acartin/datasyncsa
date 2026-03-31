from app.services.turn_planning import RealtorFilterCarryoverGuard, RealtorSearchTransitionJudge, RealtorTurnPlanner


def test_realtor_turn_planner_new_search_replaces_previous_filters():
    planner = RealtorTurnPlanner()
    state = {
        "intent": "PROPERTY_SEARCH",
        "active_search_state": {
            "filters": {
                "desired_location": "Heredia",
                "property_type": "casa",
                "bedrooms_min": 2,
            }
        },
    }
    raw = {
        "intent": "PROPERTY_SEARCH",
        "search_transition": "new_search",
        "operation": "search",
        "result_mode": "show_cards",
        "turn_filters": {
            "desired_location": "Santo Domingo",
            "listing_intent": "rent",
        },
        "filters": {
            "desired_location": "Santo Domingo",
            "listing_intent": "rent",
        },
        "search_text": [],
    }

    result = planner._normalize(raw, state)

    assert result["user_goal"] == "search"
    assert result["query_scope"] == "new_query"
    assert result["continuity_mode"] == "replace"
    assert result["target_entity"] == "result_set"
    assert result["search_transition"] == "new_search"
    assert result["continuation_requested"] is False
    assert result["turn_filters"] == {
        "desired_location": "Santo Domingo",
        "listing_intent": "rent",
    }
    assert result["filters"] == {
        "desired_location": "Santo Domingo",
        "listing_intent": "rent",
    }


def test_realtor_turn_planner_refine_current_merges_filters():
    planner = RealtorTurnPlanner()
    state = {
        "intent": "PROPERTY_SEARCH",
        "active_search_state": {
            "filters": {
                "desired_location": "Heredia",
                "property_type": "casa",
            }
        },
    }
    raw = {
        "intent": "PROPERTY_SEARCH",
        "search_transition": "refine_current",
        "operation": "search",
        "result_mode": "show_cards",
        "turn_filters": {
            "bathrooms_min": 2,
        },
        "filters": {
            "bathrooms_min": 2,
        },
        "search_text": [],
    }

    result = planner._normalize(raw, state)

    assert result["user_goal"] == "search"
    assert result["query_scope"] == "active_search"
    assert result["continuity_mode"] == "refine"
    assert result["filters"] == {
        "desired_location": "Heredia",
        "property_type": "casa",
        "bathrooms_min": 2,
    }
    assert result["continuation_requested"] is False
    assert result["turn_filters"] == {
        "bathrooms_min": 2,
    }


def test_realtor_turn_planner_marks_shown_result_reference_as_answer():
    planner = RealtorTurnPlanner()
    state = {
        "intent": "PROPERTY_SEARCH",
        "active_search_state": {
            "filters": {
                "desired_location": "Heredia",
                "property_type": "casa",
            }
        },
    }
    raw = {
        "intent": "PROPERTY_SEARCH",
        "search_transition": "ask_about_current_results",
        "operation": "search",
        "result_mode": "show_cards",
        "reference_request": {
            "mode": "shown_result",
            "target": "last",
            "field": "bathrooms",
        },
    }

    result = planner._normalize(raw, state)

    assert result["user_goal"] == "reference_question"
    assert result["query_scope"] == "shown_result"
    assert result["target_entity"] == "single_shown_property"
    assert result["requested_field"] == "bathrooms"
    assert result["requested_fields"] == ["bathrooms"]
    assert result["operation"] == "answer"
    assert result["result_mode"] == "answer_only"
    assert result["search_transition"] == "ask_about_current_results"
    assert result["reference_request"]["field"] == "bathrooms"


def test_realtor_filter_carryover_guard_can_drop_unmentioned_filters_for_new_search():
    guard = RealtorFilterCarryoverGuard()
    plan = {
        "search_transition": "refine_current",
        "filters": {
            "desired_location": "Santo Domingo",
            "listing_intent": "rent",
            "property_type": "casa",
            "bedrooms_min": 2,
            "garage_min": 1,
        },
        "turn_filters": {
            "desired_location": "Santo Domingo",
            "listing_intent": "rent",
        },
        "reasoning": "planner raw",
    }
    active_filters = {
        "desired_location": "Heredia",
        "property_type": "casa",
        "bedrooms_min": 2,
        "garage_min": 1,
    }
    raw = {
        "effective_query_scope": "new_query",
        "effective_continuity_mode": "replace",
        "effective_target_entity": "result_set",
        "filter_keep_map": {
            "desired_location": True,
            "listing_intent": True,
            "property_type": False,
            "bedrooms_min": False,
            "garage_min": False,
        },
        "reasoning": "new base search detected",
    }

    result = guard._normalize(raw, plan, active_filters)

    assert result["query_scope"] == "new_query"
    assert result["continuity_mode"] == "replace"
    assert result["search_transition"] == "new_search"
    assert result["turn_filters"] == {
        "desired_location": "Santo Domingo",
        "listing_intent": "rent",
    }
    assert result["filters"] == {
        "desired_location": "Santo Domingo",
        "listing_intent": "rent",
    }
    assert result["search_summary"] is None


def test_realtor_search_transition_judge_normalizes_field_policy():
    judge = RealtorSearchTransitionJudge()
    plan = {
        "search_transition": "refine_current",
        "query_scope": "new_query",
        "continuity_mode": "replace",
        "target_entity": "result_set",
        "filters": {
            "desired_location": "Santo Domingo",
            "listing_intent": "rent",
            "property_type": "casa",
            "bedrooms_min": 2,
        },
        "turn_filters": {
            "desired_location": "Santo Domingo",
            "listing_intent": "rent",
        },
    }
    active_filters = {
        "desired_location": "Heredia",
        "property_type": "casa",
        "bedrooms_min": 2,
    }
    raw = {
        "effective_query_scope": "new_query",
        "effective_continuity_mode": "replace",
        "effective_target_entity": "result_set",
        "filter_keep_map": {
            "desired_location": True,
            "listing_intent": True,
            "property_type": False,
            "bedrooms_min": False,
        },
        "reasoning": "new base search",
    }

    result = judge._normalize(raw, plan, active_filters)

    assert result["effective_query_scope"] == "new_query"
    assert result["effective_continuity_mode"] == "replace"
    assert result["effective_target_entity"] == "result_set"
    assert result["filter_keep_map"] == {
        "desired_location": True,
        "listing_intent": True,
        "property_type": False,
        "bedrooms_min": False,
    }


def test_realtor_filter_carryover_guard_refine_current_keeps_previous_and_applies_turn_filters():
    guard = RealtorFilterCarryoverGuard()
    plan = {
        "search_transition": "refine_current",
        "query_scope": "active_search",
        "continuity_mode": "refine",
        "target_entity": "result_set",
        "filters": {
            "desired_location": "Heredia",
            "property_type": "casa",
            "bedrooms_min": 2,
            "bathrooms_min": 1,
        },
        "turn_filters": {
            "bathrooms_min": 1,
        },
        "clear_filters": [],
        "reasoning": "planner refine",
        "search_summary": "casas en heredia",
    }
    active_filters = {
        "desired_location": "Heredia",
        "property_type": "casa",
        "bedrooms_min": 2,
    }
    decision = {
        "effective_query_scope": "active_search",
        "effective_continuity_mode": "refine",
        "effective_target_entity": "result_set",
        "filter_keep_map": {
            "desired_location": True,
            "property_type": False,
            "bedrooms_min": True,
            "bathrooms_min": True,
        },
        "reasoning": "drop property type only",
    }

    result = guard._normalize(decision, plan, active_filters)

    assert result["query_scope"] == "active_search"
    assert result["continuity_mode"] == "refine"
    assert result["filters"] == {
        "desired_location": "Heredia",
        "bedrooms_min": 2,
        "bathrooms_min": 1,
    }


def test_realtor_turn_planner_supports_search_state_answer_only_contract():
    planner = RealtorTurnPlanner()
    state = {
        "intent": "PROPERTY_SEARCH",
        "active_search_state": {
            "filters": {
                "desired_location": "Heredia",
                "bathrooms_min": 2,
            }
        },
    }
    raw = {
        "intent": "PROPERTY_SEARCH",
        "user_goal": "search_state",
        "query_scope": "active_search",
        "target_entity": "search_state",
        "requested_fields": ["filters"],
        "operation": "answer",
    }

    result = planner._normalize(raw, state)

    assert result["user_goal"] == "search_state"
    assert result["query_scope"] == "active_search"
    assert result["target_entity"] == "search_state"
    assert result["operation"] == "answer"
    assert result["result_mode"] == "answer_only"
    assert result["requested_fields"] == ["filters"]


def test_realtor_turn_planner_maps_budget_capture_reply_to_refined_search():
    planner = RealtorTurnPlanner()
    state = {
        "intent": "PROPERTY_SEARCH",
        "query_text": "300000",
        "lead_progression_state": {"last_asked_field": "budget"},
        "active_search_state": {
            "filters": {
                "desired_location": "Curridabat",
                "property_type": "casa",
                "bathrooms_min": 2,
                "garage_min": 2,
            }
        },
    }
    raw = {
        "user_goal": "capture_reply",
        "capture_reply": {
            "field": "budget",
            "value": 300000,
        },
    }

    result = planner._normalize(raw, state)

    assert result["user_goal"] == "capture_reply"
    assert result["capture_reply"] == {"field": "budget", "value": 300000}
    assert result["query_scope"] == "active_search"
    assert result["continuity_mode"] == "refine"
    assert result["operation"] == "search"
    assert result["result_mode"] == "show_cards"
    assert result["turn_filters"]["price_max"] == 300000
    assert result["search_summary"] is None


def test_realtor_filter_carryover_guard_forces_new_search_without_explicit_continuity():
    guard = RealtorFilterCarryoverGuard()
    plan = {
        "search_transition": "refine_current",
        "query_scope": "new_query",
        "continuity_mode": "refine",
        "target_entity": "result_set",
        "continuation_requested": False,
        "filters": {
            "garage_min": 1,
            "bedrooms_min": 2,
            "property_type": "casa",
            "desired_location": "santo domingo",
            "listing_intent": "rent",
        },
        "turn_filters": {
            "desired_location": "santo domingo",
            "listing_intent": "rent",
        },
        "clear_filters": [],
        "reasoning": "planner refine",
        "search_summary": "casas en santo domingo en renta",
    }
    active_filters = {
        "garage_min": 1,
        "bedrooms_min": 2,
        "property_type": "casa",
    }
    decision = {
        "effective_query_scope": "new_query",
        "effective_continuity_mode": "refine",
        "effective_target_entity": "result_set",
        "filter_keep_map": {
            "garage_min": True,
            "bedrooms_min": True,
            "property_type": True,
            "desired_location": True,
            "listing_intent": True,
        },
        "reasoning": "llm tried to retain everything",
    }

    result = guard._normalize(decision, plan, active_filters)

    assert result["continuity_mode"] == "replace"
    assert result["search_transition"] == "new_search"
    assert result["filters"] == {
        "desired_location": "santo domingo",
        "listing_intent": "rent",
    }
    assert result["search_summary"] is None


def test_realtor_turn_planner_inventory_on_active_search_stays_on_result_set():
    planner = RealtorTurnPlanner()
    state = {
        "intent": "PROPERTY_INVENTORY",
        "active_search_state": {
            "filters": {
                "desired_location": "Heredia",
                "property_type": "casa",
                "listing_intent": "buy",
            }
        },
    }
    raw = {
        "intent": "PROPERTY_INVENTORY",
        "user_goal": "inventory",
        "query_scope": "active_search",
        "continuity_mode": "reuse_current_set",
        "target_entity": "result_set",
        "requested_field": "count",
        "filters": {
            "desired_location": "Heredia",
            "property_type": "casa",
            "listing_intent": "buy",
        },
        "turn_filters": {
            "desired_location": "Heredia",
            "property_type": "casa",
        },
        "operation": "inventory",
        "result_mode": "count_only",
    }

    result = planner._normalize(raw, state)

    assert result["intent"] == "PROPERTY_INVENTORY"
    assert result["user_goal"] == "inventory"
    assert result["query_scope"] == "active_search"
    assert result["continuity_mode"] == "reuse_current_set"
    assert result["target_entity"] == "result_set"
    assert result["requested_field"] == "count"
    assert result["reference_request"] == {}
    assert result["operation"] == "inventory"
