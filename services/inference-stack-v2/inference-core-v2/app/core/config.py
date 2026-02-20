from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api/v2"
    
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
    llm_model: str = os.getenv("LLM_MODEL", "gemini-2.0-flash")
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    llm_max_retries: int = int(os.getenv("LLM_MAX_RETRIES", "3"))
    llm_timeout_secs: int = int(os.getenv("LLM_TIMEOUT_SECS", "30"))
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
    
    # Security
    internal_api_token: Optional[str] = os.getenv("INTERNAL_API_TOKEN")
    
    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore"
    }


settings = Settings()
