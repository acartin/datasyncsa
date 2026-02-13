import os
import json
import logging
import redis.asyncio as redis
from typing import Dict, Any, Optional

# Logger config
logger = logging.getLogger("session_manager")

class SessionManager:
    """
    Gestor de Memoria Efímera (Redis).
    Mantiene el contexto de la conversación (IDs, UTMs, Estado UI) vivo entre peticiones.
    """

    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        self.ttl = 60 * 60 * 24  # 24 horas de vida para la sesión
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

    async def close(self):
        """Cierra la conexión (útil para shutdowns)"""
        if self._redis:
            await self._redis.close()
