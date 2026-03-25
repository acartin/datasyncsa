"""Shared PostgreSQL repository helpers."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from services.ai_runtime.runtime.settings import settings


def _normalize_async_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    return database_url


def build_engine(database_url: str | None = None) -> AsyncEngine:
    """Create the shared async engine for runtime repositories."""

    normalized_url = _normalize_async_database_url(database_url or settings.database_url)
    return create_async_engine(normalized_url, future=True, pool_pre_ping=True)
