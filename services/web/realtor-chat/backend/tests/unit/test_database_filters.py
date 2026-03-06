from app.core.database import DatabaseManager


def test_extract_property_filters_parses_location_price_and_rooms():
    manager = DatabaseManager()
    filters = manager.extract_property_filters(
        "Tienes casas en Tibas hasta $350,000 con 3 habitaciones y 2 banos?"
    )

    assert filters["location"] == "tibas"
    assert filters["max_price"] == 350000.0
    assert filters["bedrooms_min"] == 3.0
    assert filters["bathrooms_min"] == 2.0


def test_where_clause_includes_features_address_and_text_search():
    manager = DatabaseManager()
    where, params, _ = manager._build_property_where_clause(
        "64f357a0-98eb-44f1-9f41-6e615ed26180",
        "casas en santa ana",
    )

    where_sql = " ".join(where)
    assert "features->>'address'" in where_sql
    assert "features::text" in where_sql
    assert params[0] == "64f357a0-98eb-44f1-9f41-6e615ed26180"
