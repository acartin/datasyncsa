#!/usr/bin/env python3
"""Unit tests for the shared price-scrapper HTTP client."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from etl import http_client


class FakeResponse:
    def __init__(self, status_code: int = 200, headers: dict[str, str] | None = None) -> None:
        self.status_code = status_code
        self.headers = headers or {}


class FakeSession:
    def __init__(self, responses: list[FakeResponse] | None = None) -> None:
        self.headers: dict[str, str] = {}
        self.calls: list[dict[str, object]] = []
        self._responses = list(responses or [FakeResponse()])

    def request(self, method: str, url: str, timeout: int | float, **kwargs: object) -> FakeResponse:
        self.calls.append({"method": method, "url": url, "timeout": timeout, "kwargs": dict(kwargs)})
        if len(self._responses) > 1:
            return self._responses.pop(0)
        return self._responses[0]


class HttpClientBehaviorTests(unittest.TestCase):
    def setUp(self) -> None:
        with http_client._CIRCUIT_LOCK:
            http_client._CIRCUITS.clear()
        http_client.configure_behavioral(
            jitter_min=0,
            jitter_max=0,
            break_interval=0,
            break_min=0,
            break_max=0,
            rotate_headers=True,
            header_rotation_scope="session",
            enabled=False,
        )

    def tearDown(self) -> None:
        with http_client._CIRCUIT_LOCK:
            http_client._CIRCUITS.clear()
        http_client.configure_behavioral()

    def test_configure_behavioral_rejects_invalid_ranges(self) -> None:
        with self.assertRaises(ValueError):
            http_client.configure_behavioral(jitter_min=2, jitter_max=1)
        with self.assertRaises(ValueError):
            http_client.configure_behavioral(break_interval=-1)
        with self.assertRaises(ValueError):
            http_client.configure_behavioral(header_rotation_scope="invalid")

    def test_browser_profile_pool_only_uses_supported_impersonates(self) -> None:
        self.assertTrue(http_client._BROWSER_PROFILE_POOL)
        unsupported = [
            profile["impersonate"]
            for profile in http_client._BROWSER_PROFILE_POOL
            if profile["impersonate"] not in http_client.SUPPORTED_IMPERSONATES
        ]
        self.assertEqual(unsupported, [])
        self.assertNotIn(
            "chrome133",
            {profile["impersonate"] for profile in http_client._BROWSER_PROFILE_POOL},
        )

    def test_session_scope_applies_one_stable_browser_profile(self) -> None:
        http_client.configure_behavioral(
            jitter_min=0,
            jitter_max=0,
            break_interval=0,
            break_min=0,
            break_max=0,
            rotate_headers=True,
            header_rotation_scope="session",
            enabled=False,
        )
        session = FakeSession()

        with patch.object(http_client.random, "choice", side_effect=http_client._BROWSER_PROFILE_POOL[:2]):
            http_client.request_with_retry(session, "GET", "https://example.test/a", timeout=1)
            first_user_agent = session.headers["User-Agent"]
            http_client.request_with_retry(session, "GET", "https://example.test/b", timeout=1)

        self.assertEqual(session.headers["User-Agent"], first_user_agent)
        self.assertEqual(len(session.calls), 2)

    def test_request_scope_keeps_user_agent_and_impersonate_aligned(self) -> None:
        http_client.configure_behavioral(
            jitter_min=0,
            jitter_max=0,
            break_interval=0,
            break_min=0,
            break_max=0,
            rotate_headers=True,
            header_rotation_scope="request",
            enabled=False,
        )
        session = FakeSession([FakeResponse(500), FakeResponse(200)])
        profiles = [http_client._BROWSER_PROFILE_POOL[0], http_client._BROWSER_PROFILE_POOL[1]]

        with patch.object(http_client.random, "choice", side_effect=profiles), patch.object(http_client.time, "sleep"):
            response = http_client.request_with_retry(
                session,
                "GET",
                "https://example.test/retry",
                timeout=1,
                retry_statuses=(500,),
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(session.calls), 2)
        for call, profile in zip(session.calls, profiles, strict=True):
            kwargs = call["kwargs"]
            self.assertEqual(kwargs["impersonate"], profile["impersonate"])
        self.assertEqual(session.headers["User-Agent"], profiles[-1]["user_agent"])

    def test_explicit_unknown_impersonate_preserves_caller_headers(self) -> None:
        session = http_client.create_browser_session(
            headers={"User-Agent": "custom-agent", "Accept-Language": "es-CR"},
            impersonate="safari15_3",
            proxies={},
        )

        http_client._rotate_session_headers(session, {}, allow_request_impersonate=True)

        self.assertEqual(session.headers["User-Agent"], "custom-agent")
        self.assertEqual(session.headers["Accept-Language"], "es-CR")

    def test_brightdata_sets_verify_false_by_default(self) -> None:
        session = FakeSession()
        env = {
            "BRIGHTDATA_PROXY_ENABLED": "true",
            "BRIGHTDATA_CUSTOMER_ID": "customer",
            "BRIGHTDATA_ZONE": "zone",
            "BRIGHTDATA_ZONE_PASSWORD": "password",
            "BRIGHTDATA_VERIFY_TLS": "false",
        }

        with patch.dict(os.environ, env, clear=False):
            http_client.request_with_retry(session, "GET", "https://example.test", timeout=1)

        self.assertEqual(session.calls[0]["kwargs"]["verify"], False)

    def test_brightdata_verify_true_does_not_override_verify(self) -> None:
        session = FakeSession()
        env = {
            "BRIGHTDATA_PROXY_ENABLED": "true",
            "BRIGHTDATA_CUSTOMER_ID": "customer",
            "BRIGHTDATA_ZONE": "zone",
            "BRIGHTDATA_ZONE_PASSWORD": "password",
            "BRIGHTDATA_VERIFY_TLS": "true",
        }

        with patch.dict(os.environ, env, clear=False):
            http_client.request_with_retry(session, "GET", "https://example.test", timeout=1)

        self.assertNotIn("verify", session.calls[0]["kwargs"])

    def test_403_opens_domain_circuit_and_blocks_later_requests(self) -> None:
        first_session = FakeSession([FakeResponse(403)])

        with self.assertRaises(http_client.DomainCircuitOpen) as raised:
            http_client.request_with_retry(first_session, "GET", "https://blocked.example/path", timeout=1)

        self.assertEqual(raised.exception.domain, "blocked.example")
        self.assertEqual(len(first_session.calls), 1)

        second_session = FakeSession()
        with self.assertRaises(http_client.DomainCircuitOpen):
            http_client.request_with_retry(second_session, "GET", "https://blocked.example/other", timeout=1)

        self.assertEqual(len(second_session.calls), 0)

    def test_429_respects_retry_after_before_retrying(self) -> None:
        session = FakeSession(
            [
                FakeResponse(429, headers={"Retry-After": "7"}),
                FakeResponse(200),
            ]
        )

        with patch.object(http_client.time, "sleep") as sleep_mock:
            response = http_client.request_with_retry(
                session,
                "GET",
                "https://limited.example/path",
                timeout=1,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(session.calls), 2)
        sleep_mock.assert_called_with(7.0)

    def test_repeated_429_opens_domain_circuit(self) -> None:
        session = FakeSession(
            [
                FakeResponse(429, headers={"Retry-After": "2"}),
                FakeResponse(429, headers={"Retry-After": "3"}),
                FakeResponse(200),
            ]
        )

        with patch.object(http_client.time, "sleep"):
            with self.assertRaises(http_client.DomainCircuitOpen) as raised:
                http_client.request_with_retry(
                    session,
                    "GET",
                    "https://limited.example/path",
                    timeout=1,
                )

        self.assertEqual(raised.exception.domain, "limited.example")
        self.assertEqual(len(session.calls), 2)

        second_session = FakeSession()
        with self.assertRaises(http_client.DomainCircuitOpen):
            http_client.request_with_retry(second_session, "GET", "https://limited.example/other", timeout=1)

        self.assertEqual(len(second_session.calls), 0)


if __name__ == "__main__":
    unittest.main()
