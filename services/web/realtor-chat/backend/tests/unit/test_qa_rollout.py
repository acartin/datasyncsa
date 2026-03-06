import pytest
import os
from unittest.mock import patch

from app.core.feature_flags import FeatureFlags, feature_flags
from app.core.test_matrix import (
    TEST_MATRIX,
    get_tests_for_channel,
    get_tests_for_vertical,
    get_test_matrix_summary,
    Channel,
    Vertical,
)


class TestFeatureFlags:
    def test_default_flags(self):
        assert feature_flags.CHANNEL_GATEWAY_ENABLED is True
        assert feature_flags.VERTICAL_ROUTING_ENABLED is True

    def test_meta_adapter_disabled_by_default(self):
        assert feature_flags.META_ADAPTER_ENABLED is False

    def test_external_api_disabled_by_default(self):
        assert feature_flags.EXTERNAL_API_V1_ENABLED is False

    def test_is_enabled_method(self):
        assert feature_flags.is_enabled("CHANNEL_GATEWAY_ENABLED") is True
        assert feature_flags.is_enabled("META_ADAPTER_ENABLED") is False

    def test_all_flags_returns_dict(self):
        flags = feature_flags.all_flags()
        assert isinstance(flags, dict)
        assert "CHANNEL_GATEWAY_ENABLED" in flags
        assert "VERTICAL_ROUTING_ENABLED" in flags


class TestTestMatrix:
    def test_matrix_has_all_channels(self):
        channels = {t.channel for t in TEST_MATRIX}
        assert Channel.WEB_HTML in channels
        assert Channel.META_WHATSAPP in channels
        assert Channel.META_IG in channels
        assert Channel.API in channels

    def test_matrix_has_all_verticals(self):
        verticals = {t.vertical for t in TEST_MATRIX}
        assert Vertical.REALTOR in verticals
        assert Vertical.GENERIC in verticals

    def test_web_html_tests(self):
        tests = get_tests_for_channel(Channel.WEB_HTML)
        assert len(tests) > 0

    def test_whatsapp_tests(self):
        tests = get_tests_for_channel(Channel.META_WHATSAPP)
        assert len(tests) > 0

    def test_realtor_tests(self):
        tests = get_tests_for_vertical(Vertical.REALTOR)
        assert len(tests) > 0

    def test_matrix_summary(self):
        summary = get_test_matrix_summary()
        assert summary["total_tests"] > 0
        assert "web_html" in summary["tests_by_channel"]
        assert "realtor" in summary["tests_by_vertical"]

    def test_each_channel_has_realtor_and_generic(self):
        for channel in [Channel.WEB_HTML, Channel.META_WHATSAPP, Channel.META_IG, Channel.API]:
            tests = get_tests_for_channel(channel)
            verticals = {t.vertical for t in tests}
            assert Vertical.REALTOR in verticals, f"{channel} missing realtor"
            assert Vertical.GENERIC in verticals, f"{channel} missing generic"

    def test_test_case_structure(self):
        for test in TEST_MATRIX:
            assert test.channel
            assert test.vertical
            assert test.test_type
            assert test.description
            assert test.expected_components
            assert test.expected_format


class TestRolloutPlan:
    def test_rollout_import(self):
        from app.core.rollout_plan import (
            ROLLOUT_CONFIG,
            should_enable_feature,
            CANARY_CLIENTS,
        )
        assert "CHANNEL_GATEWAY" in ROLLOUT_CONFIG

    def test_canary_clients_defined(self):
        from app.core.rollout_plan import CANARY_CLIENTS
        assert isinstance(CANARY_CLIENTS, list)
        assert len(CANARY_CLIENTS) > 0

    def test_should_enable_for_disabled_feature(self):
        from app.core.rollout_plan import should_enable_feature
        result = should_enable_feature("EXTERNAL_API_V1", "any-client")
        assert result is False

    def test_should_enable_for_enabled_feature(self):
        from app.core.rollout_plan import should_enable_feature
        result = should_enable_feature("CHANNEL_GATEWAY", "any-client")
        assert result is True

    def test_should_enable_canary_client(self):
        from app.core.rollout_plan import should_enable_feature, CANARY_CLIENTS
        for client in CANARY_CLIENTS:
            result = should_enable_feature("META_ADAPTER", client)
            assert result is True

    def test_should_block_listed_client(self):
        from app.core.rollout_plan import should_enable_feature
        result = should_enable_feature("EXTERNAL_API_V1", "blocked-client", default_enabled=True)
        assert result is False
