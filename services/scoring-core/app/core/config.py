from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = os.getenv("SCORING_API_PREFIX", "/api/v1")
    
    # Database
    database_url: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/datasyncsa")
    
    # Redis for caching
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_cache_ttl: int = int(os.getenv("REDIS_CACHE_TTL", "300"))
    
    # Caching configuration
    cache_enabled: bool = os.getenv("CACHE_ENABLED", "true").lower() == "true"
    cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "300"))
    
    # Feature flags
    scoring_v2_enabled: bool = os.getenv("SCORING_V2_ENABLED", "true").lower() == "true"
    
    # Gemini / LLM Configuration
    google_api_key: Optional[str] = os.getenv("GOOGLE_API_KEY")
    llm_model: str = os.getenv("LLM_MODEL", "gemini-2.5-flash-lite")
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    llm_max_retries: int = int(os.getenv("LLM_MAX_RETRIES", "3"))
    llm_timeout_secs: int = int(os.getenv("LLM_TIMEOUT_SECS", "30"))
    chat_llm_max_output_tokens: int = int(os.getenv("CHAT_LLM_MAX_OUTPUT_TOKENS") or "320")
    chat_history_context_max_chars: int = int(os.getenv("CHAT_HISTORY_CONTEXT_MAX_CHARS") or "1800")
    scoring_llm_timeout_secs: int = int(os.getenv("SCORING_LLM_TIMEOUT_SECS") or "8")
    scoring_llm_hard_timeout_secs: int = int(os.getenv("SCORING_LLM_HARD_TIMEOUT_SECS") or "10")
    scoring_llm_max_retries: int = int(os.getenv("SCORING_LLM_MAX_RETRIES") or "1")
    scoring_llm_max_output_tokens: int = int(os.getenv("SCORING_LLM_MAX_OUTPUT_TOKENS") or "512")
    chat_history_max_messages: int = int(os.getenv("CHAT_HISTORY_MAX_MESSAGES", "20"))
    rag_retriever_url: str = os.getenv("RAG_RETRIEVER_V2_URL", "http://semantic-adapter-v2:8000")
    rag_retriever_search_path: str = os.getenv("RAG_RETRIEVER_V2_SEARCH_PATH", "/api/v2/search")
    rag_retriever_timeout_secs: float = float(os.getenv("RAG_RETRIEVER_V2_TIMEOUT_SECS", "10.0"))
    rag_retriever_retries: int = int(os.getenv("RAG_RETRIEVER_V2_RETRIES", "2"))
    rag_top_k: int = int(os.getenv("RAG_TOP_K", "3"))
    
    # Background processing
    scoring_bg_enabled: bool = os.getenv("SCORING_BG_ENABLED", "true").lower() == "true"
    scoring_max_retries: int = int(os.getenv("SCORING_MAX_RETRIES", "3"))
    scoring_retry_delay_secs: int = int(os.getenv("SCORING_RETRY_DELAY_SECS", "5"))
    scoring_idle_close_secs: float = float(
        os.getenv("SCORING_IDLE_CLOSE_SECS") or os.getenv("SCORING_IDLE_DELAY_SECS") or "15.0"
    )
    # Backward-compatible alias used by existing code paths.
    scoring_idle_delay_secs: float = scoring_idle_close_secs
    scoring_worker_poll_secs: float = float(os.getenv("SCORING_WORKER_POLL_SECS") or "0.5")
    scoring_worker_concurrency: int = int(os.getenv("SCORING_WORKER_CONCURRENCY") or "1")
    scoring_job_max_attempts: int = int(os.getenv("SCORING_JOB_MAX_ATTEMPTS") or "3")
    scoring_job_lock_ttl_secs: int = int(os.getenv("SCORING_JOB_LOCK_TTL_SECS") or "120")
    scoring_job_debounce_secs: float = float(os.getenv("SCORING_JOB_DEBOUNCE_SECS") or "1.5")
    scoring_allow_heuristic_fallback: bool = (
        (os.getenv("SCORING_ALLOW_HEURISTIC_FALLBACK") or "false").lower() == "true"
    )
    
    # Security
    internal_api_token: Optional[str] = os.getenv("INTERNAL_API_TOKEN")

    # Logging
    llm_trace_root: str = os.getenv("LLM_TRACE_ROOT", "/tmp/datasyncsa-llm-trace")
    llm_trace_enabled: bool = os.getenv("LLM_TRACE_ENABLED", "true").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore"
    }


settings = Settings()
