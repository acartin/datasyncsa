import json
import logging
from typing import Optional, Dict, Any
from uuid import UUID

import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger("inference-core-v3.cache")


class CacheService:
    def __init__(self) -> None:
        self.client: Optional[redis.Redis] = None
        self.prefix = "inference_v3"
        self._is_connected = False

    async def connect(self) -> None:
        try:
            self.client = await redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await self.client.ping()
            self._is_connected = True
            logger.info("Redis cache connected")
        except Exception as exc:
            self._is_connected = False
            logger.warning("Redis cache disabled: %s", exc)

    async def disconnect(self) -> None:
        if self.client and self._is_connected:
            await self.client.close()
            self._is_connected = False
            logger.info("Redis cache disconnected")

    def is_enabled(self) -> bool:
        return settings.cache_enabled and self._is_connected

    def _build_key(self, key_type: str, *parts: Any) -> str:
        values = [self.prefix, key_type] + [str(v) for v in parts]
        return ":".join(values)

    async def get(self, key_or_type: str, *parts: Any) -> Optional[Dict[str, Any]]:
        if not self.is_enabled():
            return None

        # Backwards-compatible API:
        # - get(key_type, *parts)
        # - get(full_key)
        if parts:
            key = self._build_key(key_or_type, *parts)
        else:
            key = str(key_or_type)
        try:
            raw = await self.client.get(key)
            if not raw:
                return None
            return json.loads(raw)
        except Exception as exc:
            logger.error("Cache read failed key=%s: %s", key, exc)
            return None

    async def set(self, key_or_type: str, payload: Dict[str, Any], *parts: Any) -> bool:
        if not self.is_enabled():
            return False
        # Backwards-compatible API:
        # - set(key_type, payload, *parts)
        # - set(full_key, payload)
        if parts:
            key = self._build_key(key_or_type, *parts)
        else:
            key = str(key_or_type)
        try:
            await self.client.setex(key, settings.cache_ttl_seconds, json.dumps(payload, default=str))
            return True
        except Exception as exc:
            logger.error("Cache write failed key=%s: %s", key, exc)
            return False

    async def invalidate_prefix(self, pattern: str) -> bool:
        if not self.is_enabled():
            return False
        try:
            pattern = f"{self.prefix}{pattern}"
            keys = await self.client.keys(pattern)
            if keys:
                await self.client.delete(*keys)
            return True
        except Exception as exc:
            logger.error("Cache invalidate failed pattern=%s: %s", pattern, exc)
            return False

    async def invalidate_keys(self, *keys: str) -> int:
        if not self.is_enabled():
            return 0
        valid_keys = [key for key in keys if key]
        if not valid_keys:
            return 0
        try:
            deleted = await self.client.delete(*valid_keys)
            return int(deleted or 0)
        except Exception as exc:
            logger.error("Cache key delete failed keys=%s: %s", valid_keys, exc)
            return 0

    async def invalidate_tenant_runtime(self, client_id: str) -> int:
        if not self.is_enabled():
            return 0
        pattern = self._build_key("tenant_runtime", client_id, "*")
        try:
            keys = []
            async for key in self.client.scan_iter(match=pattern):
                keys.append(str(key))
            if not keys:
                return 0
            deleted = await self.client.delete(*keys)
            return int(deleted or 0)
        except Exception as exc:
            logger.error("Tenant runtime invalidation failed client_id=%s: %s", client_id, exc)
            return 0


cache_service = CacheService()
