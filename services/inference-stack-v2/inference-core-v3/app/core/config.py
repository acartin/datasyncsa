from pydantic_settings import BaseSettings
import os
from pathlib import Path


class Settings(BaseSettings):
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api/v3"

    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/datasyncsa",
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis_cache_ttl: int = int(os.getenv("REDIS_CACHE_TTL", "300"))

    cache_enabled: bool = os.getenv("CACHE_ENABLED", "true").lower() == "true"
    cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "300"))

    google_api_key: str | None = os.getenv("GOOGLE_API_KEY")
    llm_model: str = os.getenv("LLM_MODEL", "gemini-2.5-flash-lite")
    llm_timeout_secs: int = int(os.getenv("LLM_TIMEOUT_SECS", "30"))
    llm_max_output_tokens: int = int(os.getenv("CHAT_LLM_MAX_OUTPUT_TOKENS", "512"))

    rag_retriever_url: str = os.getenv("RAG_RETRIEVER_V2_URL", "http://semantic-adapter-v2:8000")
    rag_retriever_search_path: str = os.getenv("RAG_RETRIEVER_V2_SEARCH_PATH", "/api/v2/search")

    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    internal_api_token: str = os.getenv("INTERNAL_API_TOKEN", "")

    scoring_bg_enabled: bool = os.getenv("SCORING_BG_ENABLED", "true").lower() == "true"
    scoring_job_max_attempts: int = int(os.getenv("SCORING_JOB_MAX_ATTEMPTS", "3"))
    scoring_job_debounce_secs: float = float(os.getenv("SCORING_JOB_DEBOUNCE_SECS", "1.5"))
    scoring_core_url: str = os.getenv("SCORING_CORE_URL", "http://scoring-core:8000")
    scoring_core_api_prefix: str = os.getenv(
        "SCORING_CORE_API_PREFIX",
        os.getenv("SCORING_API_PREFIX", "/api/v1"),
    )
    scoring_core_timeout_secs: float = float(os.getenv("SCORING_CORE_TIMEOUT_SECS", "8"))
    response_contracts_path: str = os.getenv(
        "RESPONSE_CONTRACTS_PATH",
        str(Path(__file__).resolve().parents[1] / "policies" / "response_contracts.json"),
    )

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore",
    }


settings = Settings()
