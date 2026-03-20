from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.tools.sql_translator import slots_to_sql


def test_compile_includes_canonical_numeric_filters_for_realtor_slots() -> None:
    sql, params = slots_to_sql.compile(
        tenant_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
        slots={
            "city": "Heredia",
            "min_rooms": 3,
            "max_rooms": 4,
            "min_bathrooms": 2.5,
            "max_bathrooms": 3.0,
            "min_garage": 2,
            "max_garage": 3,
            "min_area_m2": 180,
            "max_area_m2": 260,
        },
    )

    assert "bedrooms_clean" in sql
    assert "bathrooms_clean" in sql
    assert "garage_clean" in sql
    assert "sqm_clean" in sql
    assert "COALESCE(p.price, 0) > 0" in sql

    assert ":min_rooms" in sql and params["min_rooms"] == 3
    assert ":max_rooms" in sql and params["max_rooms"] == 4
    assert ":min_bathrooms" in sql and params["min_bathrooms"] == 2.5
    assert ":max_bathrooms" in sql and params["max_bathrooms"] == 3.0
    assert ":min_garage" in sql and params["min_garage"] == 2
    assert ":max_garage" in sql and params["max_garage"] == 3
    assert ":min_area_m2" in sql and params["min_area_m2"] == 180.0
    assert ":max_area_m2" in sql and params["max_area_m2"] == 260.0


def test_compile_keeps_textual_filters_and_features() -> None:
    sql, params = slots_to_sql.compile(
        tenant_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
        slots={
            "city": "San Jose",
            "neighborhood": "Escazu",
            "property_type": "house",
            "features": ["Piscina", "Seguridad 24/7"],
        },
    )

    assert ":city_q" in sql and params["city_q"] == "%san jose%"
    assert ":neighborhood_q" in sql and params["neighborhood_q"] == "%escazu%"
    property_type_params = {
        key: value
        for key, value in params.items()
        if key.startswith("property_type_q_")
    }
    assert ":property_type_q_0" in sql
    assert "%house%" in property_type_params.values()
    assert "%casa%" in property_type_params.values()
    assert ":feature_0" in sql and params["feature_0"] == "%piscina%"
    assert ":feature_1" in sql and params["feature_1"] == "%seguridad 24/7%"


def test_compile_keeps_unknown_property_type_as_single_term() -> None:
    sql, params = slots_to_sql.compile(
        tenant_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
        slots={
            "property_type": "penthouse",
        },
    )

    property_type_params = {
        key: value
        for key, value in params.items()
        if key.startswith("property_type_q_")
    }
    assert ":property_type_q_0" in sql
    assert property_type_params == {"property_type_q_0": "%penthouse%"}
