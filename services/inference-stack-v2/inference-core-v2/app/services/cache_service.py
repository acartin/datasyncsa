import json
import logging
from typing import Optional, Any, Dict
from uuid import UUID
import redis.asyncio as redis
from app.core.config import settings


logger = logging.getLogger("inference-core-v2.cache")


class CacheService:
    """Redis-based caching service for scoring configuration"""
    
    def __init__(self):
        self.client: Optional[redis.Redis] = None
        self.prefix = "inference_v2:"
        self._is_connected = False
    
    async def connect(self):
        """Establish connection to Redis"""
        try:
            self.client = await redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self.client.ping()
            self._is_connected = True
            logger.info("Redis cache connected successfully")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Cache will be disabled.")
            self._is_connected = False
    
    async def disconnect(self):
        """Close Redis connection"""
        if self.client and self._is_connected:
            await self.client.close()
            self._is_connected = False
            logger.info("Redis cache disconnected")
    
    def is_enabled(self) -> bool:
        """Check if caching is enabled and connected"""
        return settings.cache_enabled and self._is_connected
    
    def _build_key(self, key_type: str, *args) -> str:
        """Build cache key with prefix"""
        parts = [self.prefix, key_type] + [str(arg) for arg in args]
        return ":".join(parts)
    
    async def get_active_model(self, client_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get active scoring model from cache
        
        Args:
            client_id: Tenant/client ID
        
        Returns:
            Cached model configuration or None if not cached
        """
        if not self.is_enabled():
            return None
        
        cache_key = self._build_key(
            "active_model",
            str(client_id),
        )
        
        try:
            cached = await self.client.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for active model: {cache_key}")
                return json.loads(cached)
            logger.debug(f"Cache miss for active model: {cache_key}")
            return None
        except Exception as e:
            logger.error(f"Error reading from cache: {e}")
            return None
    
    async def set_active_model(
        self, 
        client_id: UUID,
        model_data: Dict[str, Any]
    ) -> bool:
        """
        Cache active scoring model configuration
        
        Args:
            client_id: Tenant/client ID
            model_data: Model configuration to cache
        
        Returns:
            True if cached successfully
        """
        if not self.is_enabled():
            return False
        
        cache_key = self._build_key(
            "active_model",
            str(client_id),
        )
        
        try:
            await self.client.setex(
                cache_key,
                settings.cache_ttl_seconds,
                json.dumps(model_data, default=str)
            )
            logger.debug(f"Cached active model: {cache_key}")
            return True
        except Exception as e:
            logger.error(f"Error writing to cache: {e}")
            return False
    
    async def invalidate_active_model(
        self, 
        client_id: UUID,
    ) -> bool:
        """
        Invalidate cached active model
        
        Args:
            client_id: Tenant/client ID
        
        Returns:
            True if invalidated successfully
        """
        if not self.is_enabled():
            return False
        
        cache_key = self._build_key(
            "active_model",
            str(client_id),
        )
        
        try:
            await self.client.delete(cache_key)
            logger.debug(f"Invalidated cached model: {cache_key}")
            return True
        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")
            return False
    
    async def invalidate_all_models(self) -> bool:
        """Invalidate all cached models"""
        if not self.is_enabled():
            return False
        
        try:
            pattern = f"{self.prefix}active_model:*"
            keys = await self.client.keys(pattern)
            if keys:
                await self.client.delete(*keys)
                logger.debug(f"Invalidated {len(keys)} cached models")
            return True
        except Exception as e:
            logger.error(f"Error invalidating all models: {e}")
            return False


# Global cache service instance
cache_service = CacheService()
