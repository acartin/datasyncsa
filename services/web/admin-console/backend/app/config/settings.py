import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="allow")

    # Security
    secret_key: str = os.getenv("SECRET_KEY", "change-me-in-production")

    # Database Credentials - Explicitly loaded to avoid Pydantic mapping issues
    db_host: str = os.getenv("DB_HOST", "postgres")
    db_port: str = os.getenv("DB_PORT", "5432")
    db_database: str = os.getenv("DB_NAME", "agentic")
    db_username: str = os.getenv("DB_USER", "postgres")
    db_password: str = os.getenv("DB_PASS", "")
    db_connection: str = "pgsql"
    database_url_raw: str = os.getenv("DATABASE_URL", "")

    # CORS
    allowed_origins: str = os.getenv("ALLOWED_ORIGINS", "http://localhost:8085,http://127.0.0.1:8085")

    @property
    def database_url(self) -> str:
        """Constructs the Asyncpg connection URL."""
        if self.database_url_raw:
            if self.database_url_raw.startswith("postgresql://"):
                return self.database_url_raw.replace("postgresql://", "postgresql+asyncpg://", 1)
            return self.database_url_raw
        return f"postgresql+asyncpg://{self.db_username}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_database}"

    @property
    def cors_allow_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

settings = Settings()
