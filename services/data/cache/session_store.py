"""Session state store with tenant-prefixed keys."""

from __future__ import annotations

import json

import redis.asyncio as redis

from services.ai_runtime.runtime.settings import settings


class SessionStore:
    """Stores graph state using the canonical multitenant key pattern."""

    def __init__(self, redis_url: str | None = None):
        self.client = redis.from_url(redis_url or settings.redis_url, decode_responses=True)

    @staticmethod
    def build_key(client_id: str, session_id: str) -> str:
        return f"{client_id}:session:{session_id}:state"

    async def get_state(self, client_id: str, session_id: str) -> dict[str, object] | None:
        raw = await self.client.get(self.build_key(client_id, session_id))
        return json.loads(raw) if raw else None

    async def set_state(self, client_id: str, session_id: str, payload: dict[str, object], ttl: int) -> None:
        await self.client.set(self.build_key(client_id, session_id), json.dumps(payload, default=str), ex=ttl)

    async def delete_by_client(self, client_id: str) -> int:
        pattern = f"{client_id}:session:*:state"
        keys = [key async for key in self.client.scan_iter(match=pattern)]
        if not keys:
            return 0
        deleted = await self.client.delete(*keys)
        return int(deleted or 0)
