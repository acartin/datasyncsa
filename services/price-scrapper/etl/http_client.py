#!/usr/bin/env python3
"""Cliente HTTP compartido basado en curl_cffi para scraping conservador."""

from __future__ import annotations

import time
from collections.abc import Iterable
from typing import Any

from curl_cffi import requests


DEFAULT_IMPERSONATE = "chrome136"
DEFAULT_RETRY_STATUSES = (429, 500, 502, 503, 504)

BrowserSession = requests.Session
BrowserResponse = requests.Response


def create_browser_session(
    *,
    headers: dict[str, str] | None = None,
    impersonate: str = DEFAULT_IMPERSONATE,
) -> BrowserSession:
    session = requests.Session(impersonate=impersonate)
    if headers:
        session.headers.update(headers)
    return session


def request_with_retry(
    session: BrowserSession,
    method: str,
    url: str,
    *,
    timeout: int | float,
    attempts: int = 3,
    backoff_factor: float = 1.0,
    retry_statuses: Iterable[int] = DEFAULT_RETRY_STATUSES,
    **kwargs: Any,
) -> BrowserResponse:
    retry_statuses = tuple(retry_statuses)
    last_response: BrowserResponse | None = None

    for attempt in range(1, attempts + 1):
        response = session.request(method, url, timeout=timeout, **kwargs)
        last_response = response
        if response.status_code not in retry_statuses or attempt >= attempts:
            return response
        time.sleep(backoff_factor * attempt)

    if last_response is None:
        raise RuntimeError(f"No se obtuvo respuesta HTTP para {method.upper()} {url}")
    return last_response
