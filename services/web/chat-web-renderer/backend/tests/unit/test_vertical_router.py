import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from app.core.vertical_router import (
    VerticalResolver,
    VerticalRouter,
    FALLBACK_VERTICAL,
    VALID_VERTICALS,
    normalize_vertical_slug,
)


class TestVerticalResolver:
    def test_fallback_for_empty_client_id(self):
        resolver = VerticalResolver()
        assert resolver.resolve_vertical("") == FALLBACK_VERTICAL

    def test_fallback_for_none_client_id(self):
        resolver = VerticalResolver()
        assert resolver.resolve_vertical(None) == FALLBACK_VERTICAL  # type: ignore

    @patch("app.core.vertical_router.db_manager")
    def test_returns_realtor_when_configured(self, mock_db):
        mock_db.get_client_vertical_context.return_value = {
            "client_exists": True,
            "vertical_id": 1,
            "scoring_model_id": "model-123",
            "vertical_slug": "realtor",
            "vertical_name": "Real Estate",
        }
        resolver = VerticalResolver()
        assert resolver.resolve_vertical("client-123") == "realtor"

    @patch("app.core.vertical_router.db_manager")
    def test_maps_real_estate_slug_to_realtor(self, mock_db):
        mock_db.get_client_vertical_context.return_value = {
            "client_exists": True,
            "vertical_id": 1,
            "scoring_model_id": "model-123",
            "vertical_slug": "real-estate",
            "vertical_name": "Real Estate",
        }
        resolver = VerticalResolver()
        assert resolver.resolve_vertical("client-123") == "realtor"

    @patch("app.core.vertical_router.db_manager")
    def test_returns_generic_when_configured(self, mock_db):
        mock_db.get_client_vertical_context.return_value = {
            "client_exists": True,
            "vertical_id": 2,
            "scoring_model_id": "model-456",
            "vertical_slug": "generic",
            "vertical_name": "Generic",
        }
        resolver = VerticalResolver()
        assert resolver.resolve_vertical("client-456") == "generic"

    @patch("app.core.vertical_router.db_manager")
    def test_fallback_when_client_not_found(self, mock_db):
        mock_db.get_client_vertical_context.return_value = {
            "client_exists": False,
            "vertical_id": None,
            "scoring_model_id": None,
            "vertical_slug": None,
            "vertical_name": None,
        }
        resolver = VerticalResolver()
        assert resolver.resolve_vertical("unknown-client") == FALLBACK_VERTICAL

    @patch("app.core.vertical_router.db_manager")
    def test_fallback_on_db_error(self, mock_db):
        mock_db.get_client_vertical_context.side_effect = Exception("DB error")
        resolver = VerticalResolver()
        assert resolver.resolve_vertical("client-error") == FALLBACK_VERTICAL

    @patch("app.core.vertical_router.db_manager")
    def test_fallback_for_invalid_vertical(self, mock_db):
        mock_db.get_client_vertical_context.return_value = {
            "client_exists": True,
            "vertical_id": 99,
            "scoring_model_id": None,
            "vertical_slug": "unknown_vertical",
            "vertical_name": "Unknown",
        }
        resolver = VerticalResolver()
        assert resolver.resolve_vertical("client-invalid") == FALLBACK_VERTICAL

    def test_clear_cache_specific_client(self):
        resolver = VerticalResolver()
        resolver._cache["client-1"] = ("realtor", 0)
        resolver._cache["client-2"] = ("generic", 0)
        
        resolver.clear_cache("client-1")
        
        assert "client-1" not in resolver._cache
        assert "client-2" in resolver._cache

    def test_clear_cache_all(self):
        resolver = VerticalResolver()
        resolver._cache["client-1"] = ("realtor", 0)
        resolver._cache["client-2"] = ("generic", 0)
        
        resolver.clear_cache()
        
        assert len(resolver._cache) == 0


class TestVerticalRouter:
    def test_fallback_for_unknown_vertical(self):
        router = VerticalRouter()
        fallback_handler = MagicMock()
        router.register_strategy(FALLBACK_VERTICAL, "api", fallback_handler)
        
        with patch.object(router.resolver, "resolve_vertical", return_value="unknown"):
            result = router.get_handler("client-unknown", "api")
            
        assert result == fallback_handler

    def test_resolve_vertical_for_client_delegates_to_resolver(self):
        router = VerticalRouter()
        
        with patch.object(router.resolver, "resolve_vertical", return_value="realtor") as mock_resolve:
            result = router.resolve_vertical_for_client("client-123")
            
        assert result == "realtor"
        mock_resolve.assert_called_once_with("client-123")

    def test_different_clients_route_to_different_strategies(self):
        router = VerticalRouter()
        realtor_handler = MagicMock()
        generic_handler = MagicMock()
        
        router.register_strategy("realtor", "web_html", realtor_handler)
        router.register_strategy("generic", "web_html", generic_handler)
        
        with patch.object(router.resolver, "resolve_vertical") as mock_resolve:
            mock_resolve.side_effect = lambda cid: "realtor" if "realtor" in cid else "generic"
            
            result_realtor = router.get_handler("client-realtor-1", "web_html")
            result_generic = router.get_handler("client-generic-1", "web_html")
            
        assert result_realtor == realtor_handler
        assert result_generic == generic_handler

    def test_same_vertical_different_channels_return_distinct_handlers(self):
        router = VerticalRouter()
        web_handler = MagicMock()
        api_handler = MagicMock()

        router.register_strategy("realtor", "web_html", web_handler)
        router.register_strategy("realtor", "api", api_handler)

        with patch.object(router.resolver, "resolve_vertical", return_value="realtor"):
            assert router.get_handler("client-1", "web_html") == web_handler
            assert router.get_handler("client-1", "api") == api_handler

    @pytest.mark.asyncio
    async def test_get_handler_async_uses_async_resolver(self):
        router = VerticalRouter()
        web_handler = MagicMock()
        router.register_strategy("realtor", "web_html", web_handler)
        router.resolver.resolve_vertical_async = AsyncMock(return_value="realtor")

        result = await router.get_handler_async("client-1", "web_html")

        assert result == web_handler
        router.resolver.resolve_vertical_async.assert_awaited_once_with("client-1")

    @pytest.mark.asyncio
    async def test_resolve_vertical_for_client_async_delegates_to_resolver(self):
        router = VerticalRouter()
        router.resolver.resolve_vertical_async = AsyncMock(return_value="realtor")

        result = await router.resolve_vertical_for_client_async("client-123")

        assert result == "realtor"
        router.resolver.resolve_vertical_async.assert_awaited_once_with("client-123")


class TestValidVerticals:
    def test_valid_verticals_contains_realtor_and_generic(self):
        assert "realtor" in VALID_VERTICALS
        assert "generic" in VALID_VERTICALS

    def test_fallback_is_generic(self):
        assert FALLBACK_VERTICAL == "generic"

    def test_normalize_real_estate_alias(self):
        assert normalize_vertical_slug("real-estate") == "realtor"
