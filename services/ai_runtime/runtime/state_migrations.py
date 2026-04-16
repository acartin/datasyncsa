"""Schema migrations for serialized graph state payloads."""

from __future__ import annotations

import logging
from typing import Any, Callable

from services.ai_runtime.domain.state import CURRENT_SCHEMA_VERSION

logger = logging.getLogger(__name__)

Migration = Callable[[dict[str, Any]], dict[str, Any]]

_MIGRATIONS: dict[int, Migration] = {}


def register_migration(from_version: int) -> Callable[[Migration], Migration]:
    """Register a migration from ``from_version`` to ``from_version + 1``."""

    def decorator(func: Migration) -> Migration:
        if from_version in _MIGRATIONS:
            raise ValueError(f"Migration from v{from_version} already registered")
        _MIGRATIONS[from_version] = func
        return func

    return decorator


def apply_migrations(payload: dict[str, Any]) -> dict[str, Any]:
    """Apply every pending schema migration to a persisted payload."""

    current = int(payload.get("schema_version", 0))
    while current < CURRENT_SCHEMA_VERSION:
        migration = _MIGRATIONS.get(current)
        if migration is None:
            logger.warning(
                "no migration registered from v%s; filling schema_version to current",
                current,
            )
            payload["schema_version"] = CURRENT_SCHEMA_VERSION
            return payload
        payload = migration(payload)
        current += 1
        payload["schema_version"] = current
    return payload


@register_migration(from_version=0)
def _migrate_v0_to_v1(payload: dict[str, Any]) -> dict[str, Any]:
    """v0 -> v1 introduces explicit ``schema_version`` without reshaping payload."""

    return payload
