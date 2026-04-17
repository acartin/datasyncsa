"""Environment-backed settings for the AI runtime."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class AISettings:
    app_name: str = os.getenv("AI_RUNTIME_APP_NAME", "datasyncsa-ai-runtime")
    api_prefix: str = os.getenv("AI_RUNTIME_API_PREFIX", "/api/v1")
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    database_url: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@postgres:5432/postgres")
    session_ttl_seconds: int = int(os.getenv("AI_SESSION_TTL_SECONDS", "3600"))
    request_timeout_seconds: int = int(os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "30"))
    mail_provider: str = os.getenv("AI_MAIL_PROVIDER", "placeholder")
    llm_provider: str = os.getenv("AI_LLM_PROVIDER", "auto")
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    llm_default_model: str = os.getenv(
        "LLM_DEFAULT_MODEL",
        os.getenv("LLM_MODEL", "gemini-2.5-flash-lite"),
    )
    llm_analyze_turn_model: str = os.getenv(
        "LLM_ANALYZE_TURN_MODEL",
        os.getenv("LLM_DEFAULT_MODEL", os.getenv("LLM_MODEL", "gemini-2.5-flash-lite")),
    )
    llm_timeout_seconds: int = int(os.getenv("LLM_TIMEOUT_SECS", "30"))
    llm_context_cache_enabled: bool = os.getenv("LLM_CONTEXT_CACHE_ENABLED", "true").lower() == "true"
    llm_context_cache_ttl_seconds: int = int(os.getenv("LLM_CONTEXT_CACHE_TTL_SECONDS", "1800"))
    llm_context_cache_min_stable_chars: int = int(os.getenv("LLM_CONTEXT_CACHE_MIN_STABLE_CHARS", "2000"))
    turn_trace_enabled: bool = os.getenv("AI_TURN_TRACE_ENABLED", "true").lower() == "true"
    turn_trace_dir: str = os.getenv("AI_TURN_TRACE_DIR", "/app/log/turn-traces")
    scoring_core_api: str = os.getenv("SCORING_CORE_API", "http://scoring-core:8000").rstrip("/")
    scoring_core_api_prefix: str = os.getenv("SCORING_CORE_API_PREFIX", "/api/v1")
    scoring_enqueue_enabled: bool = os.getenv("SCORING_ENQUEUE_ENABLED", "true").lower() == "true"
    scoring_enqueue_timeout_secs: float = float(os.getenv("SCORING_ENQUEUE_TIMEOUT_SECS", "2.0"))
    internal_api_token: str = os.getenv("INTERNAL_API_TOKEN", "")


settings = AISettings()
