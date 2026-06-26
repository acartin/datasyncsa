#!/usr/bin/env python3
"""Cliente HTTP compartido basado en curl_cffi para scraping conservador.

Soporta proxy residencial (BrightData via .env), rate limiter global por dominio
y simulacion de comportamiento humano (jitter, breaks estructurales, rotacion de headers).
"""

from __future__ import annotations

import logging
import os
import random
import re
import threading
import time
from collections.abc import Iterable
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, TypedDict, get_args

from curl_cffi import requests
from curl_cffi.requests.impersonate import BrowserTypeLiteral


DEFAULT_IMPERSONATE = "chrome136"
DEFAULT_RETRY_STATUSES = (429, 500, 502, 503, 504)
DEFAULT_RATE_PER_SECOND = 5.0
DEFAULT_RATE_BURST = 1
DEFAULT_CIRCUIT_COOLDOWN_SECONDS = 1800.0
SERVICE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_DIR.parents[1]
ENV_PATH = REPO_ROOT / ".env"
SUPPORTED_IMPERSONATES = {str(value) for value in get_args(BrowserTypeLiteral)}

BrowserSession = requests.Session
BrowserResponse = requests.Response
_LOGGER = logging.getLogger(__name__)

_ENV_CACHE: dict[str, str] | None = None
_ENV_LOCK = threading.Lock()


def _load_dotenv() -> dict[str, str]:
    global _ENV_CACHE
    if _ENV_CACHE is not None:
        return _ENV_CACHE
    with _ENV_LOCK:
        if _ENV_CACHE is not None:
            return _ENV_CACHE
        values: dict[str, str] = {}
        if ENV_PATH.exists():
            for raw_line in ENV_PATH.read_text().splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
        _ENV_CACHE = values
        return values


def _env_value(key: str, default: str = "") -> str:
    value = os.environ.get(key)
    if value is not None:
        return value
    return _load_dotenv().get(key, default)


def _env_bool(key: str, default: bool) -> bool:
    raw = _env_value(key)
    if raw == "":
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"{key} debe ser booleano: true/false")


def _env_float(key: str, default: float) -> float:
    raw = _env_value(key)
    if raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        raise ValueError(f"{key} debe ser numerico: {raw!r}") from None


def _env_int(key: str, default: int) -> int:
    raw = _env_value(key)
    if raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"{key} debe ser entero: {raw!r}") from None

# -- Rate limiter global por dominio ---------------------------

_RATE_LIMITERS: dict[str, TokenBucket] = {}
_RATE_LOCK = threading.Lock()
_DEFAULT_RATE = _env_float("PRICE_SCRAPPER_HTTP_DEFAULT_RATE_PER_SECOND", DEFAULT_RATE_PER_SECOND)
_DEFAULT_BURST = _env_int("PRICE_SCRAPPER_HTTP_RATE_BURST", DEFAULT_RATE_BURST)


class DomainCircuitOpen(RuntimeError):
    """Raised when a domain is paused because it returned blocking signals."""

    def __init__(self, *, domain: str, reason: str, retry_after_seconds: float) -> None:
        self.domain = domain
        self.reason = reason
        self.retry_after_seconds = retry_after_seconds
        super().__init__(
            f"Circuit breaker abierto para dominio {domain!r}: {reason}; "
            f"reintentar en {round(retry_after_seconds, 1)}s"
        )


class TokenBucket:
    """Token bucket rate limiter thread-safe."""

    def __init__(self, rate: float = DEFAULT_RATE_PER_SECOND, burst: int = DEFAULT_RATE_BURST) -> None:
        if rate <= 0:
            raise ValueError("rate debe ser > 0")
        if burst <= 0:
            raise ValueError("burst debe ser > 0")
        self.rate = rate
        self.burst = burst
        self._lock = threading.Lock()
        self._tokens: float = float(burst)
        self._last: float = time.monotonic()

    def wait(self) -> float:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            self._tokens = min(self._tokens + elapsed * self.rate, float(self.burst))
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                self._last = now
                return 0.0
            needed = (1.0 - self._tokens) / self.rate
            self._tokens = 0.0
            self._last = now + needed
        time.sleep(needed)
        return needed


def set_rate_limiter(domain: str, rate: float | None = None, burst: int | None = None) -> None:
    """Configura rate limiter para un dominio si no existe."""
    if rate is None:
        rate = _DEFAULT_RATE
    if burst is None:
        burst = _DEFAULT_BURST
    with _RATE_LOCK:
        if domain not in _RATE_LIMITERS:
            _RATE_LIMITERS[domain] = TokenBucket(rate=rate, burst=burst)


def _extract_domain(url: str) -> str:
    match = re.search(r"://([^/]+)", url)
    return match.group(1) if match else "default"


def _acquire_rate_token(url: str) -> None:
    domain = _extract_domain(url)
    limiter = _RATE_LIMITERS.get(domain)
    if limiter is not None:
        limiter.wait()


# -- Circuit breaker por dominio -------------------------------

class DomainCircuitState(TypedDict):
    consecutive_403: int
    consecutive_429: int
    opened_until: float
    reason: str


_CIRCUITS: dict[str, DomainCircuitState] = {}
_CIRCUIT_LOCK = threading.Lock()
_CIRCUIT_ENABLED = _env_bool("PRICE_SCRAPPER_HTTP_CIRCUIT_BREAKER_ENABLED", True)
_CIRCUIT_403_THRESHOLD = _env_int("PRICE_SCRAPPER_HTTP_CIRCUIT_403_THRESHOLD", 1)
_CIRCUIT_429_THRESHOLD = _env_int("PRICE_SCRAPPER_HTTP_CIRCUIT_429_THRESHOLD", 2)
_CIRCUIT_COOLDOWN_SECONDS = _env_float(
    "PRICE_SCRAPPER_HTTP_CIRCUIT_COOLDOWN_SECONDS",
    DEFAULT_CIRCUIT_COOLDOWN_SECONDS,
)
_RETRY_AFTER_FALLBACK_SECONDS = _env_float("PRICE_SCRAPPER_HTTP_429_RETRY_AFTER_FALLBACK_SECONDS", 60.0)


def _empty_circuit_state() -> DomainCircuitState:
    return {
        "consecutive_403": 0,
        "consecutive_429": 0,
        "opened_until": 0.0,
        "reason": "",
    }


def _validate_circuit_config() -> None:
    if _CIRCUIT_403_THRESHOLD < 0:
        raise ValueError("PRICE_SCRAPPER_HTTP_CIRCUIT_403_THRESHOLD debe ser >= 0")
    if _CIRCUIT_429_THRESHOLD < 0:
        raise ValueError("PRICE_SCRAPPER_HTTP_CIRCUIT_429_THRESHOLD debe ser >= 0")
    if _CIRCUIT_COOLDOWN_SECONDS < 0:
        raise ValueError("PRICE_SCRAPPER_HTTP_CIRCUIT_COOLDOWN_SECONDS debe ser >= 0")
    if _RETRY_AFTER_FALLBACK_SECONDS < 0:
        raise ValueError("PRICE_SCRAPPER_HTTP_429_RETRY_AFTER_FALLBACK_SECONDS debe ser >= 0")


def _open_circuit_locked(
    state: DomainCircuitState,
    *,
    now: float,
    reason: str,
    cooldown_seconds: float,
) -> None:
    state["opened_until"] = max(state["opened_until"], now + cooldown_seconds)
    state["reason"] = reason


def _raise_if_circuit_open(domain: str) -> None:
    if not _CIRCUIT_ENABLED:
        return
    now = time.monotonic()
    with _CIRCUIT_LOCK:
        state = _CIRCUITS.get(domain)
        if state is None or state["opened_until"] <= now:
            return
        retry_after_seconds = max(0.0, state["opened_until"] - now)
        reason = state["reason"] or "dominio pausado por politica HTTP"
    raise DomainCircuitOpen(
        domain=domain,
        reason=reason,
        retry_after_seconds=retry_after_seconds,
    )


def _parse_retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return max(0.0, float(text))
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return max(0.0, parsed.timestamp() - time.time())


def _response_header(response: BrowserResponse, name: str) -> str | None:
    headers = getattr(response, "headers", None)
    if not headers:
        return None
    try:
        return headers.get(name) or headers.get(name.lower()) or headers.get(name.upper())
    except AttributeError:
        return None


def _record_response_for_circuit(domain: str, response: BrowserResponse) -> float | None:
    if not _CIRCUIT_ENABLED:
        return None

    status_code = int(response.status_code)
    retry_after_seconds = _parse_retry_after_seconds(_response_header(response, "Retry-After"))
    now = time.monotonic()
    should_open = False
    reason = ""
    cooldown_seconds = _CIRCUIT_COOLDOWN_SECONDS

    with _CIRCUIT_LOCK:
        state = _CIRCUITS.setdefault(domain, _empty_circuit_state())
        if status_code == 403 and _CIRCUIT_403_THRESHOLD > 0:
            state["consecutive_403"] += 1
            state["consecutive_429"] = 0
            should_open = state["consecutive_403"] >= _CIRCUIT_403_THRESHOLD
            reason = f"HTTP 403 persistente ({state['consecutive_403']} evento(s))"
        elif status_code == 429 and _CIRCUIT_429_THRESHOLD > 0:
            state["consecutive_429"] += 1
            state["consecutive_403"] = 0
            should_open = state["consecutive_429"] >= _CIRCUIT_429_THRESHOLD
            reason = f"HTTP 429 persistente ({state['consecutive_429']} evento(s))"
            if retry_after_seconds is not None:
                cooldown_seconds = max(cooldown_seconds, retry_after_seconds)
        else:
            state["consecutive_403"] = 0
            state["consecutive_429"] = 0
            state["reason"] = ""
            return retry_after_seconds

        if should_open:
            _open_circuit_locked(
                state,
                now=now,
                reason=reason,
                cooldown_seconds=cooldown_seconds,
            )
            retry_after_seconds = max(0.0, state["opened_until"] - now)

    if should_open:
        raise DomainCircuitOpen(
            domain=domain,
            reason=reason,
            retry_after_seconds=retry_after_seconds or 0.0,
        )
    return retry_after_seconds


# -- Behavioral simulation (jitter + breaks + browser profiles) --

class BrowserProfile(TypedDict):
    impersonate: str
    user_agent: str
    accept_language: str


_ACCEPT_LANGUAGE_POOL = [
    "es-CR,es;q=0.9,en;q=0.8",
    "es-CR,es;q=0.8,en;q=0.7",
    "es-419,es;q=0.9,en;q=0.8",
    "es,en;q=0.9,en-US;q=0.8",
    "es-CR,es-419;q=0.9,es;q=0.8,en;q=0.7",
]


def _chrome_profile(impersonate: str, version: int, accept_language: str) -> BrowserProfile:
    return {
        "impersonate": impersonate,
        "user_agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            f"(KHTML, like Gecko) Chrome/{version}.0.0.0 Safari/537.36"
        ),
        "accept_language": accept_language,
    }


_BROWSER_PROFILE_CANDIDATES = [
    _chrome_profile("chrome136", 136, _ACCEPT_LANGUAGE_POOL[0]),
    _chrome_profile("chrome136", 136, _ACCEPT_LANGUAGE_POOL[1]),
    _chrome_profile("chrome136", 136, _ACCEPT_LANGUAGE_POOL[2]),
    _chrome_profile("chrome133a", 133, _ACCEPT_LANGUAGE_POOL[3]),
    _chrome_profile("chrome131", 131, _ACCEPT_LANGUAGE_POOL[4]),
]
_BROWSER_PROFILE_POOL = [
    profile
    for profile in _BROWSER_PROFILE_CANDIDATES
    if profile["impersonate"] in SUPPORTED_IMPERSONATES
] or [_chrome_profile(DEFAULT_IMPERSONATE, 136, _ACCEPT_LANGUAGE_POOL[0])]

_REQUEST_COUNTER = 0
_COUNTER_LOCK = threading.Lock()
_CONFIG_LOGGED = False
_CONFIG_LOG_LOCK = threading.Lock()

_JITTER_MIN = _env_float("PRICE_SCRAPPER_HTTP_JITTER_MIN_SECONDS", 1.0)
_JITTER_MAX = _env_float("PRICE_SCRAPPER_HTTP_JITTER_MAX_SECONDS", 3.0)
_BREAK_INTERVAL = _env_int("PRICE_SCRAPPER_HTTP_BREAK_INTERVAL_REQUESTS", 100)
_BREAK_MIN = _env_float("PRICE_SCRAPPER_HTTP_BREAK_MIN_SECONDS", 30.0)
_BREAK_MAX = _env_float("PRICE_SCRAPPER_HTTP_BREAK_MAX_SECONDS", 60.0)
_HEADER_ROTATION_SCOPE = _env_value("PRICE_SCRAPPER_HTTP_HEADER_ROTATION_SCOPE", "session").lower()
_HEADER_ROTATION_ENABLED = _env_bool("PRICE_SCRAPPER_HTTP_ROTATE_HEADERS", True)
_BEHAVIORAL_ENABLED = _env_bool("PRICE_SCRAPPER_HTTP_BEHAVIORAL_ENABLED", True)
_LOG_CONFIG = _env_bool("PRICE_SCRAPPER_HTTP_LOG_CONFIG", False)


def _validate_behavioral_config(
    *,
    jitter_min: float,
    jitter_max: float,
    break_interval: int,
    break_min: float,
    break_max: float,
    header_rotation_scope: str,
) -> None:
    if jitter_min < 0 or jitter_max < 0:
        raise ValueError("jitter_min y jitter_max deben ser >= 0")
    if jitter_min > jitter_max:
        raise ValueError("jitter_min no puede ser mayor que jitter_max")
    if break_interval < 0:
        raise ValueError("break_interval debe ser >= 0")
    if break_min < 0 or break_max < 0:
        raise ValueError("break_min y break_max deben ser >= 0")
    if break_min > break_max:
        raise ValueError("break_min no puede ser mayor que break_max")
    if header_rotation_scope not in {"session", "request"}:
        raise ValueError("header_rotation_scope debe ser 'session' o 'request'")
    if _DEFAULT_RATE <= 0:
        raise ValueError("PRICE_SCRAPPER_HTTP_DEFAULT_RATE_PER_SECOND debe ser > 0")
    if _DEFAULT_BURST <= 0:
        raise ValueError("PRICE_SCRAPPER_HTTP_RATE_BURST debe ser > 0")


def configure_behavioral(
    *,
    jitter_min: float = 1.0,
    jitter_max: float = 3.0,
    break_interval: int = 100,
    break_min: float = 30.0,
    break_max: float = 60.0,
    rotate_headers: bool = True,
    header_rotation_scope: str = "session",
    enabled: bool = True,
) -> None:
    header_rotation_scope = header_rotation_scope.lower()
    _validate_behavioral_config(
        jitter_min=jitter_min,
        jitter_max=jitter_max,
        break_interval=break_interval,
        break_min=break_min,
        break_max=break_max,
        header_rotation_scope=header_rotation_scope,
    )
    global _JITTER_MIN, _JITTER_MAX, _BREAK_INTERVAL, _BREAK_MIN, _BREAK_MAX
    global _HEADER_ROTATION_ENABLED, _HEADER_ROTATION_SCOPE, _BEHAVIORAL_ENABLED
    _JITTER_MIN = jitter_min
    _JITTER_MAX = jitter_max
    _BREAK_INTERVAL = break_interval
    _BREAK_MIN = break_min
    _BREAK_MAX = break_max
    _HEADER_ROTATION_ENABLED = rotate_headers
    _HEADER_ROTATION_SCOPE = header_rotation_scope
    _BEHAVIORAL_ENABLED = enabled


def _find_browser_profile(impersonate: str | None) -> BrowserProfile | None:
    if not impersonate:
        return None
    for profile in _BROWSER_PROFILE_POOL:
        if profile["impersonate"] == impersonate:
            return profile
    return None


def _random_browser_profile() -> BrowserProfile:
    return random.choice(_BROWSER_PROFILE_POOL)


def _apply_browser_profile(session: BrowserSession, profile: BrowserProfile) -> None:
    session.headers["User-Agent"] = profile["user_agent"]
    session.headers["Accept-Language"] = profile["accept_language"]


def _rotate_session_headers(
    session: BrowserSession,
    request_kwargs: dict[str, Any],
    *,
    allow_request_impersonate: bool,
) -> None:
    if not _HEADER_ROTATION_ENABLED:
        return
    if _HEADER_ROTATION_SCOPE == "session" and getattr(session, "_price_scrapper_headers_rotated", False):
        return
    if _HEADER_ROTATION_SCOPE == "session":
        profile = getattr(session, "_price_scrapper_browser_profile", None) or _random_browser_profile()
    else:
        explicit_impersonate = None if allow_request_impersonate else request_kwargs.get("impersonate")
        profile = _random_browser_profile()
        if explicit_impersonate:
            matched_profile = _find_browser_profile(str(explicit_impersonate))
            if matched_profile is None:
                return
            profile = matched_profile
        if allow_request_impersonate:
            request_kwargs["impersonate"] = profile["impersonate"]
    _apply_browser_profile(session, profile)
    if _HEADER_ROTATION_SCOPE == "session":
        setattr(session, "_price_scrapper_browser_profile", profile)
        setattr(session, "_price_scrapper_headers_rotated", True)


def _behavioral_delay() -> None:
    if not _BEHAVIORAL_ENABLED:
        return
    delay = random.uniform(_JITTER_MIN, _JITTER_MAX)
    time.sleep(delay)


def _structural_break() -> None:
    if not _BEHAVIORAL_ENABLED or _BREAK_INTERVAL == 0:
        return
    global _REQUEST_COUNTER
    with _COUNTER_LOCK:
        _REQUEST_COUNTER += 1
        if _REQUEST_COUNTER % _BREAK_INTERVAL != 0:
            return
    duration = random.uniform(_BREAK_MIN, _BREAK_MAX)
    time.sleep(duration)


_validate_behavioral_config(
    jitter_min=_JITTER_MIN,
    jitter_max=_JITTER_MAX,
    break_interval=_BREAK_INTERVAL,
    break_min=_BREAK_MIN,
    break_max=_BREAK_MAX,
    header_rotation_scope=_HEADER_ROTATION_SCOPE,
)
_validate_circuit_config()


def get_http_client_settings() -> dict[str, object]:
    """Devuelve configuracion efectiva sin credenciales ni URLs con secretos."""
    return {
        "brightdata_proxy_enabled": _brightdata_proxy_enabled(),
        "brightdata_verify_tls": _brightdata_verify_tls(),
        "behavioral_enabled": _BEHAVIORAL_ENABLED,
        "jitter_min_seconds": _JITTER_MIN,
        "jitter_max_seconds": _JITTER_MAX,
        "break_interval_requests": _BREAK_INTERVAL,
        "break_min_seconds": _BREAK_MIN,
        "break_max_seconds": _BREAK_MAX,
        "rotate_headers": _HEADER_ROTATION_ENABLED,
        "header_rotation_scope": _HEADER_ROTATION_SCOPE,
        "default_rate_per_second": _DEFAULT_RATE,
        "rate_burst": _DEFAULT_BURST,
        "circuit_breaker_enabled": _CIRCUIT_ENABLED,
        "circuit_403_threshold": _CIRCUIT_403_THRESHOLD,
        "circuit_429_threshold": _CIRCUIT_429_THRESHOLD,
        "circuit_cooldown_seconds": _CIRCUIT_COOLDOWN_SECONDS,
        "retry_after_fallback_seconds": _RETRY_AFTER_FALLBACK_SECONDS,
    }


def _log_config_once() -> None:
    if not _LOG_CONFIG:
        return
    global _CONFIG_LOGGED
    with _CONFIG_LOG_LOCK:
        if _CONFIG_LOGGED:
            return
        _CONFIG_LOGGED = True
    _LOGGER.info("price-scrapper HTTP settings: %s", get_http_client_settings())


# -- Proxy auto-desde .env -------------------------------------

def _build_proxies_from_env() -> dict[str, str] | None:
    if not _brightdata_proxy_enabled():
        return None
    cid = _env_value("BRIGHTDATA_CUSTOMER_ID")
    zone = _env_value("BRIGHTDATA_ZONE")
    pwd = _env_value("BRIGHTDATA_ZONE_PASSWORD")
    if not (cid and zone and pwd):
        return None
    country = _env_value("BRIGHTDATA_COUNTRY")
    username = f"brd-customer-{cid}-zone-{zone}"
    if country:
        username += f"-country-{country.lower()}"
    proxy = f"http://{username}:{pwd}@brd.superproxy.io:33335"
    return {"http": proxy, "https": proxy}


def _brightdata_proxy_enabled() -> bool:
    if not _env_bool("BRIGHTDATA_PROXY_ENABLED", True):
        return False
    return bool(
        _env_value("BRIGHTDATA_CUSTOMER_ID")
        and _env_value("BRIGHTDATA_ZONE")
        and _env_value("BRIGHTDATA_ZONE_PASSWORD")
    )


def _brightdata_verify_tls() -> bool:
    return _env_bool("BRIGHTDATA_VERIFY_TLS", False)


# -- API publica -----------------------------------------------

def create_browser_session(
    *,
    headers: dict[str, str] | None = None,
    impersonate: str | None = None,
    proxies: dict[str, str] | None = None,
) -> BrowserSession:
    _log_config_once()
    if proxies is None:
        proxies = _build_proxies_from_env()
    profile: BrowserProfile | None = None
    session_impersonate = impersonate or DEFAULT_IMPERSONATE
    if _HEADER_ROTATION_ENABLED:
        profile = _find_browser_profile(impersonate) if impersonate else _random_browser_profile()
        if profile is not None:
            session_impersonate = profile["impersonate"]
    session = requests.Session(impersonate=session_impersonate, proxies=proxies)
    if headers:
        session.headers.update(headers)
    if profile is not None and _HEADER_ROTATION_SCOPE == "session":
        _apply_browser_profile(session, profile)
        setattr(session, "_price_scrapper_browser_profile", profile)
        setattr(session, "_price_scrapper_headers_rotated", True)
    elif _HEADER_ROTATION_ENABLED and impersonate:
        setattr(session, "_price_scrapper_headers_rotated", True)
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
    if _brightdata_proxy_enabled() and not _brightdata_verify_tls() and "verify" not in kwargs:
        kwargs["verify"] = False

    domain = _extract_domain(url)
    retry_statuses = tuple(retry_statuses)
    last_response: BrowserResponse | None = None
    allow_request_impersonate = "impersonate" not in kwargs

    for attempt in range(1, attempts + 1):
        _raise_if_circuit_open(domain)
        _rotate_session_headers(
            session,
            kwargs,
            allow_request_impersonate=allow_request_impersonate,
        )
        _behavioral_delay()
        _structural_break()
        _acquire_rate_token(url)
        response = session.request(method, url, timeout=timeout, **kwargs)
        last_response = response
        retry_after_seconds = _record_response_for_circuit(domain, response)
        if response.status_code not in retry_statuses or attempt >= attempts:
            return response
        sleep_seconds = backoff_factor * attempt
        if response.status_code == 429:
            if retry_after_seconds is None:
                sleep_seconds = max(sleep_seconds, _RETRY_AFTER_FALLBACK_SECONDS)
            else:
                sleep_seconds = max(sleep_seconds, retry_after_seconds)
        time.sleep(sleep_seconds)

    if last_response is None:
        raise RuntimeError(f"No se obtuvo respuesta HTTP para {method.upper()} {url}")
    return last_response
