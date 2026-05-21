import os
from functools import lru_cache


def _csv_env(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


class Settings:
    app_name: str = os.getenv("MARKET_WATCH_APP_NAME", "Market Watch API")
    app_version: str = os.getenv("MARKET_WATCH_APP_VERSION", "0.1.0")
    api_prefix: str = os.getenv("MARKET_WATCH_API_PREFIX", "/api/v1")
    database_url: str = os.getenv("DATABASE_URL", "")
    api_token: str = os.getenv("MARKET_WATCH_API_TOKEN", "")
    demo_client_id: str = os.getenv("MARKET_WATCH_DEMO_CLIENT_ID", "")
    demo_role: str = os.getenv("MARKET_WATCH_DEMO_ROLE", "system-admin")
    superset_base_url: str = os.getenv("MARKET_WATCH_SUPERSET_BASE_URL", "")
    keycloak_issuer_url: str = os.getenv("MARKET_WATCH_KEYCLOAK_ISSUER_URL", "")
    allowed_origins: list[str] = _csv_env(
        "MARKET_WATCH_ALLOWED_ORIGINS",
        "http://localhost:8099,http://127.0.0.1:8099",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
