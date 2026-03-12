from uuid import UUID

import pytest

from app.services.realtor_search_executor import RealtorSearchExecutor


class FailingSession:
    async def execute(self, *args, **kwargs):
        raise Exception("invalid input syntax for type integer: 20+")

    async def rollback(self):
        return None


class CountingInventoryExecutor(RealtorSearchExecutor):
    def __init__(self):
        super().__init__(db_session=FailingSession(), search_limit=4)
        self.seen_sql = []

    async def _run_sql(self, sql: str):
        self.seen_sql.append(sql)
        return [{"total": 1}]


class MappingExecutor(RealtorSearchExecutor):
    def __init__(self):
        super().__init__(db_session=FailingSession(), search_limit=4)

    async def _get_images_map(self, property_ids):
        return {str(property_ids[0]): "https://example.com/image.jpg"} if property_ids else {}


def test_materialize_sql_rewrites_cast_numeric_filters():
    executor = RealtorSearchExecutor(db_session=FailingSession(), search_limit=4)
    sql = (
        "SELECT id, title FROM lead_properties "
        "WHERE client_id = {client_id} "
        "AND CAST(features->>'bedrooms_clean' AS INTEGER) = 2 "
        "AND CAST(features->>'garage' AS INTEGER) >= 1 "
        "AND COALESCE(price, 0) > 0 "
        "LIMIT {search_limit}"
    )

    materialized = executor._materialize_sql(
        sql,
        "64f357a0-98eb-44f1-9f41-6e615ed26180",
    )

    assert "CAST(features->>'bedrooms_clean' AS INTEGER)" not in materialized
    assert "CAST(features->>'garage' AS INTEGER)" not in materialized
    assert "regexp_replace" in materialized
    assert "client_id = '64f357a0-98eb-44f1-9f41-6e615ed26180'" in materialized


def test_materialize_sql_rewrites_pseudo_columns_to_features_json():
    executor = RealtorSearchExecutor(db_session=FailingSession(), search_limit=4)
    sql = (
        "SELECT * FROM lead_properties "
        "WHERE client_id = {client_id} "
        "AND bedrooms_clean = 2 "
        "AND garage >= 1 "
        "AND address ILIKE '%Heredia%' "
        "AND COALESCE(price, 0) > 0"
    )

    materialized = executor._materialize_sql(
        sql,
        "64f357a0-98eb-44f1-9f41-6e615ed26180",
    )

    assert " bedrooms_clean = 2 " not in materialized
    assert " garage >= 1 " not in materialized
    assert " address ILIKE " not in materialized
    assert "features->>'bedrooms_clean'" in materialized
    assert "features->>'garage'" in materialized
    assert "features->>'address'" in materialized


def test_materialize_sql_rewrites_property_type_to_text_search():
    executor = RealtorSearchExecutor(db_session=FailingSession(), search_limit=4)
    sql = (
        "SELECT * FROM lead_properties "
        "WHERE client_id = {client_id} "
        "AND property_type = 'casa' "
        "AND COALESCE(price, 0) > 0"
    )

    materialized = executor._materialize_sql(
        sql,
        "64f357a0-98eb-44f1-9f41-6e615ed26180",
    )

    assert "property_type = 'casa'" not in materialized
    assert "title ILIKE '%casa%'" in materialized
    assert "description ILIKE '%casa%'" not in materialized
    assert "features::text ILIKE '%casa%'" not in materialized


def test_materialize_sql_applies_declared_property_type_filter_guard():
    executor = RealtorSearchExecutor(db_session=FailingSession(), search_limit=4)
    sql = (
        "SELECT * FROM lead_properties "
        "WHERE client_id = {client_id} "
        "AND features ->> 'bedrooms_clean' = '2' "
        "AND COALESCE(price, 0) > 0 "
        "LIMIT 20"
    )

    materialized = executor._materialize_sql(
        sql,
        "64f357a0-98eb-44f1-9f41-6e615ed26180",
        {"property_type": "casa"},
    )

    assert "features ->> 'bedrooms_clean' = '2'" in materialized
    assert "title ILIKE '%casa%'" in materialized


def test_materialize_sql_does_not_corrupt_json_key_literals():
    executor = RealtorSearchExecutor(db_session=FailingSession(), search_limit=4)
    sql = (
        "SELECT * FROM lead_properties "
        "WHERE client_id = {client_id} "
        "AND features ->> 'bedrooms_clean' = '2' "
        "AND COALESCE(price, 0) > 0"
    )

    materialized = executor._materialize_sql(
        sql,
        "64f357a0-98eb-44f1-9f41-6e615ed26180",
    )

    assert "features ->> 'bedrooms_clean' = '2'" in materialized
    assert "features ->> 'COALESCE(" not in materialized


@pytest.mark.asyncio
async def test_execute_returns_execution_error_when_sql_runtime_fails():
    executor = RealtorSearchExecutor(db_session=FailingSession(), search_limit=4)

    result = await executor.execute(
        realtor_turn={
            "intent": "PROPERTY_SEARCH",
            "sql": (
                "SELECT id, title FROM lead_properties "
                "WHERE client_id = {client_id} "
                "AND COALESCE(price, 0) > 0 "
                "AND CAST(features->>'bedrooms_clean' AS INTEGER) = 2"
            ),
            "search_summary": "casas con 2 habitaciones",
            "filters": {
                "bedrooms_min": 2,
                "property_type": "casa",
            },
        },
        user_query="casas con 2 habitaciones",
        client_id=UUID("64f357a0-98eb-44f1-9f41-6e615ed26180"),
    )

    assert result["status"] == "execution_error"
    assert result["facts"]["error_code"] == "SQL_EXECUTION_ERROR"
    assert result["search_state"]["filters"]["bedrooms_min"] == 2


@pytest.mark.asyncio
async def test_inventory_intent_returns_count_without_components():
    executor = CountingInventoryExecutor()

    result = await executor.execute(
        realtor_turn={
            "intent": "PROPERTY_INVENTORY",
            "sql": (
                "SELECT id, title FROM lead_properties "
                "WHERE client_id = {client_id} "
                "AND COALESCE(price, 0) > 0"
            ),
            "search_summary": "casas con dos habitaciones y dos cocheras",
            "filters": {
                "property_type": "casa",
            },
        },
        user_query="solo esa tienes?",
        client_id=UUID("64f357a0-98eb-44f1-9f41-6e615ed26180"),
    )

    assert any("COUNT(*)" in sql for sql in executor.seen_sql)
    assert result["status"] == "results"
    assert result["components"] == []
    assert result["facts"]["total_matches"] == 1
    assert result["facts"]["visible_count"] == 0


@pytest.mark.asyncio
async def test_rows_to_property_components_includes_public_url():
    executor = MappingExecutor()

    components = await executor._rows_to_property_components(
        [
            {
                "id": "row-1",
                "title": "Casa Premium",
                "price": 350000,
                "public_url": "https://example.com/original-listing",
                "features": {
                    "address": "Escazú, San José",
                    "property_id_internal": "ZP-1",
                    "bedrooms_clean": 3,
                    "bathrooms_clean": 2,
                    "garage": "2",
                },
            }
        ]
    )

    assert len(components) == 1
    assert components[0]["type"] == "property-card"
    assert components[0]["public_url"] == "https://example.com/original-listing"
