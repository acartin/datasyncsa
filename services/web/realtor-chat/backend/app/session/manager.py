import os
import json
import logging
import redis.asyncio as redis
from typing import Dict, Any, Optional

# Logger config
logger = logging.getLogger("session_manager")

SESSION_TTL_DEFAULT = 60 * 60 * 24  # 24 horas


def build_session_key(client_id: str, channel: Optional[str] = None, channel_user_id: Optional[str] = None) -> str:
    """
    Construye la key de sesión:
    - Legacy: session:{client_id}
    - New: session:{client_id}:{channel}:{channel_user_id}
    """
    if channel and channel_user_id:
        return f"session:{client_id}:{channel}:{channel_user_id}"
    return f"session:{client_id}"


class SessionManager:
    """
    Gestor de Memoria Efímera (Redis).
    Mantiene el contexto de la conversación (IDs, UTMs, Estado UI) vivo entre peticiones.
    """

    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        try:
            self.ttl = int(os.getenv("SESSION_TTL_SECONDS", str(SESSION_TTL_DEFAULT)))
        except (ValueError, TypeError):
            self.ttl = SESSION_TTL_DEFAULT
        self._redis = None

    async def _get_connection(self):
        """Lazy connection to Redis"""
        if not self._redis:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
            logger.info(f"💾 Conectado a Redis: {self.redis_url}")
        return self._redis

    async def get_session(self, session_id: str) -> Dict[str, Any]:
        """Recupera el contexto de la sesión"""
        if not session_id:
            return {}
            
        r = await self._get_connection()
        data = await r.get(f"session:{session_id}")
        
        if data:
            return json.loads(data)
        return {}

    async def update_session(self, session_id: str, data: Dict[str, Any]):
        """Actualiza la sesión con nuevos datos (merge)"""
        if not session_id:
            return

        r = await self._get_connection()
        key = f"session:{session_id}"
        
        # Recuperar estado actual para hacer merge
        current_data = await self.get_session(session_id)
        current_data.update(data)
        
        # Guardar con TTL renovado
        await r.setex(key, self.ttl, json.dumps(current_data))
        logger.debug(f"💾 Sesión actualizada: {session_id}")

    async def delete_session(self, session_id: str) -> bool:
        """Deletes a session key for a client/session id."""
        if not session_id:
            return False
        r = await self._get_connection()
        deleted = await r.delete(f"session:{session_id}")
        return bool(deleted)

    async def close(self):
        """Cierra la conexión (útil para shutdowns)"""
        if self._redis:
            await self._redis.close()

    async def get_session_multichannel(
        self,
        client_id: str,
        channel: str,
        channel_user_id: str,
    ) -> Dict[str, Any]:
        """
        Recupera el contexto de la sesión por clave compuesta.
        """
        if not client_id or not channel or not channel_user_id:
            return {}

        key = build_session_key(client_id, channel, channel_user_id)
        r = await self._get_connection()
        data = await r.get(key)

        if data:
            return json.loads(data)
        return {}

    async def upsert_session(
        self,
        client_id: str,
        channel: str,
        channel_user_id: str,
        data: Dict[str, Any],
    ) -> None:
        """
        Crea o actualiza una sesión con clave compuesta.
        """
        if not client_id or not channel or not channel_user_id:
            return

        key = build_session_key(client_id, channel, channel_user_id)
        r = await self._get_connection()

        current_data = await self._get_session_by_key(key)
        current_data.update(data)

        await r.setex(key, self.ttl, json.dumps(current_data))
        logger.debug(f"💾 Sesión upsertada: {key}")

    async def delete_session_multichannel(
        self,
        client_id: str,
        channel: str,
        channel_user_id: str,
    ) -> bool:
        """
        Elimina sesión por clave compuesta.
        """
        if not client_id or not channel or not channel_user_id:
            return False

        key = build_session_key(client_id, channel, channel_user_id)
        r = await self._get_connection()
        deleted = await r.delete(key)
        return bool(deleted)

    async def _get_session_by_key(self, key: str) -> Dict[str, Any]:
        """Helper interno para obtener sesión por key directa."""
        r = await self._get_connection()
        data = await r.get(key)
        if data:
            return json.loads(data)
        return {}

    async def get_all_session_keys(self, pattern: str = "session:*") -> list[str]:
        """Lista todas las keys de sesión que matcheen el patrón (útil para debugging)."""
        r = await self._get_connection()
        keys = await r.keys(pattern)
        return keys
