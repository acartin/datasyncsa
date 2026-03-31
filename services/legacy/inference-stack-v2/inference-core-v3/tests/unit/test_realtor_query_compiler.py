from app.services.realtor_query_compiler import RealtorQueryCompiler


def test_compile_property_search_uses_real_schema_fields_only():
    compiler = RealtorQueryCompiler(search_limit=4)
    result = compiler.compile(
        client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
        plan={
            "intent": "PROPERTY_SEARCH",
            "operation": "search",
            "result_mode": "show_cards",
            "filters": {
                "desired_location": "Heredia",
                "property_type": "casa",
                "bedrooms_min": 2,
                "garage_min": 2,
            },
            "search_text": ["aceptan mascotas"],
            "sort_by": "price_asc",
            "search_summary": "casas en Heredia con 2 habitaciones y cochera",
        },
    )

    sql = result["sql"]
    assert sql.startswith("SELECT id, client_id, title, description, features, price, public_url FROM lead_properties")
    assert "client_id = '64f357a0-98eb-44f1-9f41-6e615ed26180'" in sql
    assert "COALESCE(price, 0) > 0" in sql
    assert "title ILIKE '%Heredia%'" in sql
    assert "COALESCE(features->>'address', '') ILIKE '%Heredia%'" in sql
    assert "description ILIKE '%Heredia%'" not in sql
    assert "features::text ILIKE '%Heredia%'" not in sql
    assert "features::text ILIKE '%aceptan mascotas%'" in sql
    assert "bedrooms_clean" in sql
    assert "LIMIT 4" in sql


def test_compile_inventory_returns_count_query_without_limit():
    compiler = RealtorQueryCompiler(search_limit=4)
    result = compiler.compile(
        client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
        plan={
            "intent": "PROPERTY_INVENTORY",
            "operation": "inventory",
            "result_mode": "count_only",
            "filters": {"property_type": "apartamento"},
            "search_text": [],
            "sort_by": "relevant",
            "search_summary": "apartamentos",
        },
    )

    sql = result["sql"]
    assert sql.startswith("SELECT COUNT(*) AS total FROM lead_properties")
    assert "LIMIT" not in sql


def test_compile_price_range_returns_stats_query():
    compiler = RealtorQueryCompiler(search_limit=4)
    result = compiler.compile(
        client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
        plan={
            "intent": "PROPERTY_PRICE_RANGE",
            "operation": "price_range",
            "result_mode": "stats_only",
            "filters": {"desired_location": "Escazu", "price_max": 500000},
            "search_text": [],
            "sort_by": "relevant",
            "search_summary": "rango de precios en Escazu",
        },
    )

    sql = result["sql"]
    assert "MIN(price) AS min_price" in sql
    assert "MAX(price) AS max_price" in sql
    assert "COUNT(*) AS count" in sql
    assert "price <= 500000" in sql


def test_compile_listing_intent_buy_uses_sale_terms_instead_of_literal_buy():
    compiler = RealtorQueryCompiler(search_limit=4)
    result = compiler.compile(
        client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
        plan={
            "intent": "PROPERTY_SEARCH",
            "operation": "search",
            "result_mode": "show_cards",
            "filters": {"listing_intent": "buy"},
            "search_text": [],
            "sort_by": "relevant",
            "search_summary": "propiedades en compra",
        },
    )

    sql = result["sql"]
    assert "%buy%" not in sql
    assert "%venta%" in sql
