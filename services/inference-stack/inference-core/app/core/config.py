from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # API Keys
    GOOGLE_API_KEY: str

    # AI Configuration
    EMBEDDING_MODEL: str = "models/text-embedding-004"
    LLM_MODEL: str = "gemini-2.0-flash"

    # Database Configuration
    DB_HOST: str = "postgres"
    DB_PORT: int = 5432
    DB_NAME: str = "agentic"
    DB_USER: str = "acartin"
    DB_PASS: str = "Toyota_15"
    
    # We'll use a specific one for agentic if provided, otherwise derive it
    AGENTIC_DB_NAME: str = "agentic"

    # Microservices URLs
    SEMANTIC_ADAPTER_URL: str = "http://semantic-adapter:8000"

    # Environment
    ENV: str = "production"
    DEBUG: bool = False

    @property
    def semantic_db_url(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def agentic_db_url(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME if self.AGENTIC_DB_NAME == self.DB_NAME else self.AGENTIC_DB_NAME}"

    class Config:
        env_file = "../../.env"
        extra = "ignore"

settings = Settings()
