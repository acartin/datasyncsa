from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../../.env", extra="ignore")

    # API Keys
    GOOGLE_API_KEY: str

    # AI Configuration
    EMBEDDING_MODEL: str = "models/gemini-embedding-001"
    LLM_MODEL: str = "gemini-2.0-flash"

    # Database Configuration
    DATABASE_URL: Optional[str] = None
    DB_HOST: str = "postgres"
    DB_PORT: int = 5432
    DB_NAME: str = "agentic"
    DB_USER: str = "postgres"
    DB_PASS: str = ""
    
    # We'll use a specific one for agentic if provided, otherwise derive it
    AGENTIC_DB_NAME: str = "agentic"

    # Microservices URLs
    SEMANTIC_ADAPTER_URL: str = "http://semantic-adapter:8000"
    SEMANTIC_TIMEOUT_SECS: float = 10.0
    SEMANTIC_RETRIES: int = 2

    # CORS
    CORS_ALLOW_ORIGINS: str = "http://localhost:8086,http://localhost:8087,http://192.168.0.37:8086,http://192.168.0.37:8087"

    # Environment
    ENV: str = "production"
    DEBUG: bool = False

    @property
    def semantic_db_url(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def agentic_db_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"postgresql://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME if self.AGENTIC_DB_NAME == self.DB_NAME else self.AGENTIC_DB_NAME}"

    @property
    def cors_allow_origins(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ALLOW_ORIGINS.split(",") if origin.strip()]

settings = Settings()
