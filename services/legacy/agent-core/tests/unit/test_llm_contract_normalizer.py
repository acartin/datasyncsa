from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.llm_contract_normalizer import normalize_router_decision


def test_normalize_router_decision_maps_realtor_parameters_to_realtor_slots() -> None:
    raw = {
        "goal": "realtor_search",
        "confidence": 0.9,
        "tool_calls": [
            {
                "tool_name": "realtor_sql",
                "parameters": {
                    "city": "Heredia",
                    "min_rooms": 3,
                    "max_rooms": 3,
                    "unexpected": "ignored",
                },
            }
        ],
        "missing_slots": [],
        "clarify_message": None,
        "response_mode": "text_only",
    }

    normalized = normalize_router_decision(raw)
    call = normalized["tool_calls"][0]
    assert call.get("realtor_slots") == {
        "city": "Heredia",
        "min_rooms": 3,
        "max_rooms": 3,
    }


def test_normalize_router_decision_ignores_non_slot_parameters() -> None:
    raw = {
        "goal": "realtor_search",
        "confidence": 0.9,
        "tool_calls": [
            {
                "tool_name": "realtor_sql",
                "parameters": {
                    "query": "SELECT * FROM lead_properties",
                },
            }
        ],
        "missing_slots": [],
        "clarify_message": None,
        "response_mode": "text_only",
    }

    normalized = normalize_router_decision(raw)
    call = normalized["tool_calls"][0]
    assert "realtor_slots" not in call


def test_normalize_router_decision_maps_spanish_property_type_aliases() -> None:
    raw = {
        "goal": "realtor_search",
        "confidence": 0.9,
        "tool_calls": [
            {
                "tool_name": "realtor_sql",
                "realtor_slots": {
                    "city": "Heredia",
                    "property_type": "casa",
                },
            }
        ],
        "missing_slots": [],
        "clarify_message": None,
        "response_mode": "text_only",
    }

    normalized = normalize_router_decision(raw)
    call = normalized["tool_calls"][0]
    assert call.get("realtor_slots", {}).get("property_type") == "house"


def test_normalize_router_decision_maps_rag_query_aliases_to_rag_payload() -> None:
    raw = {
        "goal": "rag",
        "confidence": 0.9,
        "tool_calls": [
            {
                "tool_name": "rag",
                "rag_query": "consulta informativa general",
                "top_k": 4,
            }
        ],
        "missing_slots": [],
        "clarify_message": None,
        "response_mode": "text_only",
    }

    normalized = normalize_router_decision(raw)
    call = normalized["tool_calls"][0]
    assert call.get("rag", {}).get("query_text") == "consulta informativa general"
    assert call.get("rag", {}).get("top_k") == 4


def test_normalize_router_decision_coerces_null_features_to_empty_list() -> None:
    raw = {
        "goal": "realtor_search",
        "confidence": 0.9,
        "tool_calls": [
            {
                "tool_name": "realtor_sql",
                "realtor_slots": {
                    "city": "Heredia",
                    "property_type": "house",
                    "features": None,
                },
            }
        ],
        "missing_slots": [],
        "clarify_message": None,
        "response_mode": "text_plus_cards",
    }

    normalized = normalize_router_decision(raw)
    call = normalized["tool_calls"][0]
    assert call.get("realtor_slots", {}).get("features") == []
