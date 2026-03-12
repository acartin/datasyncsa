from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services.realtor_turn_executor import RealtorTurnExecutor


class _DummyMappings:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _DummyResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return _DummyMappings(self._rows)


@pytest.mark.asyncio
async def test_execute_invalid_sql_returns_execution_error_without_hitting_db():
    db_session = AsyncMock()
    executor = RealtorTurnExecutor(db_session, search_limit=4)
    client_id = uuid4()

    result = await executor.execute(
        realtor_turn={
            "intent": "PROPERTY_SEARCH",
            "sql": "DELETE FROM lead_properties",
            "search_summary": "casas en Heredia",
        },
        user_query="casas en heredia",
        client_id=client_id,
    )

    assert result["handled"] is True
    assert result["status"] == "execution_error"
    assert result["components"] == []
    assert result["facts"]["error_code"] == "INVALID_SQL"
    db_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_execute_property_search_returns_structured_facts_and_components():
    db_session = AsyncMock()
    db_session.execute = AsyncMock(
        side_effect=[
            _DummyResult(
                [
                    {
                        "id": 101,
                        "title": "Casa familiar en Heredia",
                        "description": "<p>Hermosa casa</p>",
                        "features": {
                            "property_id_internal": "ZP-101",
                            "address": "Heredia, Costa Rica",
                            "bedrooms_clean": 3,
                            "bathrooms_clean": 2,
                            "garage": "2",
                            "sqm_clean": 180,
                        },
                        "price": 250000,
                    }
                ]
            ),
            _DummyResult([{"total": 7}]),
        ]
    )
    executor = RealtorTurnExecutor(db_session, search_limit=4)
    executor._get_images_map = AsyncMock(return_value={"101": "https://img.example/1.jpg"})
    client_id = uuid4()

    result = await executor.execute(
        realtor_turn={
            "intent": "PROPERTY_SEARCH",
            "sql": (
                "SELECT id, title, description, features, price "
                f"FROM lead_properties WHERE client_id = '{client_id}' AND COALESCE(price, 0) > 0 LIMIT 4"
            ),
            "search_summary": "casas en Heredia",
            "filters": {
                "desired_location": "Heredia",
                "property_type": "casa",
                "bedrooms_min": 3,
            },
        },
        user_query="casas en heredia",
        client_id=client_id,
    )

    assert result["handled"] is True
    assert result["status"] == "results"
    assert result["facts"]["total_matches"] == 7
    assert result["facts"]["visible_count"] == 1
    assert result["facts"]["search_summary"] == "casas en Heredia"
    assert result["components"][0]["type"] == "property-card"
    assert result["components"][0]["title"] == "Casa familiar en Heredia"
    assert result["components"][0]["image_url"] == "https://img.example/1.jpg"
    assert result["search_state"]["filters"]["desired_location"] == "Heredia"
    assert result["search_state"]["filters"]["bedrooms_min"] == 3


@pytest.mark.asyncio
async def test_execute_price_range_empty_returns_empty_status():
    db_session = AsyncMock()
    db_session.execute = AsyncMock(return_value=_DummyResult([]))
    executor = RealtorTurnExecutor(db_session, search_limit=4)
    client_id = uuid4()

    result = await executor.execute(
        realtor_turn={
            "intent": "PROPERTY_PRICE_RANGE",
            "sql": (
                "SELECT MIN(price) AS min_price, MAX(price) AS max_price, COUNT(*) AS total "
                f"FROM lead_properties WHERE client_id = '{client_id}' AND COALESCE(price, 0) > 0"
            ),
            "search_summary": "casas en Curridabat",
        },
        user_query="precio de casas en curridabat",
        client_id=client_id,
    )

    assert result["handled"] is True
    assert result["status"] == "empty"
    assert result["facts"]["count"] == 0
    assert result["facts"]["search_summary"] == "casas en Curridabat"


@pytest.mark.asyncio
async def test_get_images_map_rolls_back_when_optional_lookup_fails():
    db_session = AsyncMock()
    db_session.execute = AsyncMock(side_effect=Exception("missing table"))
    db_session.rollback = AsyncMock()
    executor = RealtorTurnExecutor(db_session, search_limit=4)

    images = await executor._get_images_map(["ZP-1"])

    assert images == {}
    db_session.rollback.assert_awaited_once()


def test_validate_sql_allows_bedrooms_clean_and_bathrooms_clean_filters():
    client_id = str(uuid4())
    sql = (
        "SELECT * FROM lead_properties "
        f"WHERE client_id = '{client_id}' "
        "AND COALESCE(price, 0) > 0 "
        "AND features->>'bedrooms_clean' = '2' "
        "AND features->>'bathrooms_clean' = '2'"
    )

    assert RealtorTurnExecutor._validate_sql(sql, client_id) is True
