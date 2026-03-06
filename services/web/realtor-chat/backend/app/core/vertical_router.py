import os
import time
import asyncio
import logging
from typing import Dict, Any, Optional, Tuple
from app.core.database import db_manager

logger = logging.getLogger("vertical_router")

VERTICAL_CACHE_TTL_SECONDS = int(os.getenv("VERTICAL_CACHE_TTL_SECONDS", "300"))

FALLBACK_VERTICAL = "generic"
VALID_VERTICALS = ["realtor", "generic"]
REALTOR_ALIASES = {"realtor", "real-estate", "real_estate", "inmobiliaria"}
GENERIC_ALIASES = {"generic"}


def normalize_vertical_slug(vertical_slug: Optional[str]) -> str:
    raw = (vertical_slug or "").strip().lower()
    if raw in REALTOR_ALIASES:
        return "realtor"
    if raw in GENERIC_ALIASES:
        return "generic"
    return FALLBACK_VERTICAL


class VerticalResolver:
    """
    Resuelve el vertical (realtor vs generic) para un client_id dado.
    """

    def __init__(self):
        self._cache: Dict[str, Tuple[str, float]] = {}

    def _get_cache(self, client_id: str) -> Optional[str]:
        if client_id in self._cache:
            vertical, timestamp = self._cache[client_id]
            if time.monotonic() - timestamp < VERTICAL_CACHE_TTL_SECONDS:
                return vertical
            del self._cache[client_id]
        return None

    def _set_cache(self, client_id: str, vertical: str) -> None:
        self._cache[client_id] = (vertical, time.monotonic())

    async def resolve_vertical_async(self, client_id: str) -> str:
        """
        Resuelve el vertical de forma async para no bloquear el event loop.
        """
        if not client_id:
            return FALLBACK_VERTICAL

        cached = self._get_cache(client_id)
        if cached:
            return cached

        try:
            context = await asyncio.to_thread(db_manager.get_client_vertical_context, client_id)
            if not context or not context.get("client_exists"):
                logger.warning(f"Client {client_id} not found, using fallback vertical")
                vertical = FALLBACK_VERTICAL
            else:
                source_slug = context.get("vertical_slug")
                vertical = normalize_vertical_slug(source_slug)
                if vertical == FALLBACK_VERTICAL and (source_slug or "").strip().lower() not in GENERIC_ALIASES:
                    logger.warning(f"Invalid vertical '{source_slug}' for {client_id}, using fallback")

            self._set_cache(client_id, vertical)
            return vertical

        except Exception as e:
            logger.error(f"Error resolving vertical for {client_id}: {e}")
            return FALLBACK_VERTICAL

    def resolve_vertical(self, client_id: str) -> str:
        """
        Resuelve el vertical de forma síncrona (para backward compatibility).
        """
        if not client_id:
            return FALLBACK_VERTICAL

        cached = self._get_cache(client_id)
        if cached:
            return cached

        try:
            context = db_manager.get_client_vertical_context(client_id)
            if not context or not context.get("client_exists"):
                logger.warning(f"Client {client_id} not found, using fallback vertical")
                vertical = FALLBACK_VERTICAL
            else:
                source_slug = context.get("vertical_slug")
                vertical = normalize_vertical_slug(source_slug)
                if vertical == FALLBACK_VERTICAL and (source_slug or "").strip().lower() not in GENERIC_ALIASES:
                    logger.warning(f"Invalid vertical '{source_slug}' for {client_id}, using fallback")

            self._set_cache(client_id, vertical)
            return vertical

        except Exception as e:
            logger.error(f"Error resolving vertical for {client_id}: {e}")
            return FALLBACK_VERTICAL

    def clear_cache(self, client_id: Optional[str] = None) -> None:
        if client_id:
            self._cache.pop(client_id, None)
        else:
            self._cache.clear()


class VerticalRouter:
    """
    Selecciona el strategy handler en runtime basado en vertical + channel.
    """

    def __init__(self):
        self.resolver = VerticalResolver()
        self._strategies: Dict[Tuple[str, str], Any] = {}

    def register_strategy(self, vertical_slug: str, channel: str, handler: Any) -> None:
        key = (vertical_slug, channel)
        self._strategies[key] = handler
        logger.info(f"Registered strategy for vertical='{vertical_slug}' channel='{channel}'")

    def get_handler(self, client_id: str, channel: str) -> Any:
        vertical = self.resolver.resolve_vertical(client_id)
        
        key = (vertical, channel)
        handler = self._strategies.get(key)
        
        if handler:
            return handler
        
        fallback_key = (FALLBACK_VERTICAL, channel)
        handler = self._strategies.get(fallback_key)
        
        if handler:
            logger.warning(
                f"No handler for vertical='{vertical}' channel='{channel}' "
                f"for client {client_id}, using fallback '{FALLBACK_VERTICAL}'"
            )
            return handler
        
        generic_any_channel = self._get_any_channel_handler(FALLBACK_VERTICAL)
        if generic_any_channel:
            return generic_any_channel
        
        return None

    async def get_handler_async(self, client_id: str, channel: str) -> Any:
        vertical = await self.resolver.resolve_vertical_async(client_id)

        key = (vertical, channel)
        handler = self._strategies.get(key)

        if handler:
            return handler

        fallback_key = (FALLBACK_VERTICAL, channel)
        handler = self._strategies.get(fallback_key)

        if handler:
            logger.warning(
                f"No handler for vertical='{vertical}' channel='{channel}' "
                f"for client {client_id}, using fallback '{FALLBACK_VERTICAL}'"
            )
            return handler

        generic_any_channel = self._get_any_channel_handler(FALLBACK_VERTICAL)
        if generic_any_channel:
            return generic_any_channel

        return None

    def _get_any_channel_handler(self, vertical: str) -> Any:
        for key, handler in self._strategies.items():
            if key[0] == vertical:
                return handler
        return None

    def resolve_vertical_for_client(self, client_id: str) -> str:
        return self.resolver.resolve_vertical(client_id)

    async def resolve_vertical_for_client_async(self, client_id: str) -> str:
        return await self.resolver.resolve_vertical_async(client_id)

vertical_resolver = VerticalResolver()
vertical_router = VerticalRouter()
