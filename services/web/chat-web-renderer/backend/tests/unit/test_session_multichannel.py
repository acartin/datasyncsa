import pytest

from app.session.manager import SessionManager, build_session_key, SESSION_TTL_DEFAULT


class TestBuildSessionKey:
    def test_legacy_key(self):
        key = build_session_key("client-123")
        assert key == "session:client-123"

    def test_multichannel_key_web_html(self):
        key = build_session_key("client-123", "web_html", "user-abc")
        assert key == "session:client-123:web_html:user-abc"

    def test_multichannel_key_whatsapp(self):
        key = build_session_key("client-456", "meta_whatsapp", "wa_50688887777")
        assert key == "session:client-456:meta_whatsapp:wa_50688887777"

    def test_multichannel_key_instagram(self):
        key = build_session_key("client-789", "meta_ig", "ig_user_123")
        assert key == "session:client-789:meta_ig:ig_user_123"

    def test_multichannel_key_api(self):
        key = build_session_key("client-999", "api", "api_user_token")
        assert key == "session:client-999:api:api_user_token"

    def test_partial_params_returns_legacy(self):
        key = build_session_key("client-123", channel="web_html")
        assert key == "session:client-123"


class TestSessionManagerTTL:
    def test_default_ttl(self):
        manager = SessionManager()
        assert manager.ttl == SESSION_TTL_DEFAULT

    def test_custom_ttl_from_env(self, monkeypatch):
        monkeypatch.setenv("SESSION_TTL_SECONDS", "3600")
        manager = SessionManager()
        assert manager.ttl == 3600

    def test_invalid_ttl_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("SESSION_TTL_SECONDS", "invalid")
        manager = SessionManager()
        assert manager.ttl == SESSION_TTL_DEFAULT


class TestSessionKeyIsolation:
    def test_same_client_different_channel_different_keys(self):
        key1 = build_session_key("client-123", "web_html", "user-abc")
        key2 = build_session_key("client-123", "meta_whatsapp", "user-abc")
        assert key1 != key2

    def test_same_client_same_channel_different_user_different_keys(self):
        key1 = build_session_key("client-123", "web_html", "user-1")
        key2 = build_session_key("client-123", "web_html", "user-2")
        assert key1 != key2

    def test_different_client_same_channel_same_user_different_keys(self):
        key1 = build_session_key("client-1", "web_html", "user-abc")
        key2 = build_session_key("client-2", "web_html", "user-abc")
        assert key1 != key2

    def test_all_combinations_unique(self):
        keys = [
            build_session_key("c1", "web_html", "u1"),
            build_session_key("c1", "web_html", "u2"),
            build_session_key("c1", "meta_whatsapp", "u1"),
            build_session_key("c1", "meta_ig", "u1"),
            build_session_key("c1", "api", "u1"),
            build_session_key("c2", "web_html", "u1"),
        ]
        assert len(keys) == len(set(keys))
