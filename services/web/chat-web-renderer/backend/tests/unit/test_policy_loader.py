import pytest
from unittest.mock import patch, mock_open
import json

from app.transformer.policy_loader import PolicyLoader, get_allowed_components


class TestPolicyLoader:
    def setup_method(self):
        PolicyLoader.clear_cache()

    def test_load_policy_returns_dict(self):
        policy = PolicyLoader.load_policy()
        assert isinstance(policy, dict)
        assert policy.get("contract") == "ChatVerticalPolicyV1"

    def test_get_allowed_components_realtor_web_html(self):
        components = get_allowed_components("realtor", "web_html")
        assert "chat_text" in components
        assert "property_card" in components
        assert "property_grid" in components
        assert "gallery" in components
        assert "map" in components
        assert "calendar" in components

    def test_get_allowed_components_realtor_meta_whatsapp(self):
        components = get_allowed_components("realtor", "meta_whatsapp")
        assert "chat_text" in components
        assert "image" in components
        assert "quick_replies" in components
        assert "list" in components

    def test_get_allowed_components_realtor_api(self):
        components = get_allowed_components("realtor", "api")
        assert "chat_text" in components
        assert "property_card" in components
        assert "gallery" in components
        assert "map" in components
        assert "calendar" in components

    def test_get_allowed_components_generic_web_html(self):
        components = get_allowed_components("generic", "web_html")
        assert "chat_text" in components
        assert "agenda" in components
        assert "image" in components

    def test_get_allowed_components_healthcare_web_html(self):
        components = get_allowed_components("healthcare", "web_html")
        assert "chat_text" in components
        assert "agenda" in components
        assert "image" in components

    def test_unknown_vertical_falls_back_to_generic_policy(self):
        components = get_allowed_components("unknown_vertical", "web_html")
        assert "chat_text" in components
        assert "agenda" in components

    def test_fallback_for_unknown_channel(self):
        components = get_allowed_components("realtor", "unknown_channel")
        assert "chat_text" in components

    def test_cache_is_used(self):
        PolicyLoader.clear_cache()
        with patch("builtins.open", mock_open(read_data='{"contract": "test"}')):
            policy1 = PolicyLoader.load_policy()
            policy2 = PolicyLoader.load_policy()
        assert policy1 == policy2

    def test_clear_cache(self):
        PolicyLoader._cache = {"test": "data"}
        PolicyLoader.clear_cache()
        assert PolicyLoader._cache is None
