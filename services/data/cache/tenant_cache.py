"""Tenant runtime cache helpers."""

from __future__ import annotations

import json

import redis.asyncio as redis

from services.ai_runtime.runtime.settings import settings


class TenantCache:
    """Caches tenant config and agents independently from session state."""

    def __init__(self, redis_url: str | None = None):
        self.client = redis.from_url(redis_url or settings.redis_url, decode_responses=True)

    @staticmethod
    def build_config_key(client_id: str) -> str:
        return f"{client_id}:config"

    @staticmethod
    def build_agents_key(client_id: str) -> str:
        return f"{client_id}:agents"

    async def get_config(self, client_id: str) -> dict[str, object] | None:
        raw = await self.client.get(self.build_config_key(client_id))
        return json.loads(raw) if raw else None

    async def set_config(self, client_id: str, payload: dict[str, object], ttl: int) -> None:
        await self.client.set(self.build_config_key(client_id), json.dumps(payload, default=str), ex=ttl)

    async def get_agents(self, client_id: str) -> list[dict[str, object]] | None:
        raw = await self.client.get(self.build_agents_key(client_id))
        return json.loads(raw) if raw else None

    async def set_agents(self, client_id: str, payload: list[dict[str, object]], ttl: int) -> None:
        await self.client.set(self.build_agents_key(client_id), json.dumps(payload, default=str), ex=ttl)

    async def delete_client_runtime(self, client_id: str) -> int:
        keys = [self.build_config_key(client_id), self.build_agents_key(client_id)]
        deleted = await self.client.delete(*keys)
        return int(deleted or 0)
