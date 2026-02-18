import os
import httpx
import logging
from typing import Dict, Any, Optional

# Logger config
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("inference_bridge")

class InferenceClient:
    """
    El 'Cable' que conecta el Bridge con el Cerebro de IA (Inference Core).
    Se encarga de enviar el payload con metadatos y recibir la respuesta plana.
    """

    def __init__(self):
        # Cargar configuración desde environment (inyectado por docker-compose/.env)
        self.base_url = os.getenv("INFERENCE_CORE_URL", "http://inference-core:8003/api/v1")
        self.timeout = int(os.getenv("INFERENCE_TIMEOUT", 60))
        self.default_client_id = os.getenv("DEFAULT_CLIENT_ID", "")
        
        logger.info(f"🔌 InferenceClient conectado a: {self.base_url} (Timeout: {self.timeout}s)")

    async def chat(self, user_query: str, session: Dict[str, Any]) -> Dict[str, Any]:
        """
        Envía un mensaje al Core AI.
        
        :param user_query: El texto que escribió el usuario.
        :param session: Diccionario con metadatos de la sesión (conversation_id, lead_id, etc.)
        """
        url = f"{self.base_url}/chat"
        
        # Construcción del Payload (Schema Match con Inference Core)
        # Schema esperado: { queryText, clientId, conversationId, userMetadata: {...} }
        
        user_metadata = {
            "lead_id": session.get("lead_id"),
            "brand_project": session.get("brand_project"),
            "utm_source": session.get("utm_source"),
            "utm_medium": session.get("utm_medium"),
            "utm_campaign": session.get("utm_campaign"),
            "utm_content": session.get("utm_content"),
            "utm_term": session.get("utm_term"),
            "gclid": session.get("gclid"),
            "fbclid": session.get("fbclid"),
            "ttclid": session.get("ttclid"),
            "msclkid": session.get("msclkid"),
            "li_fat_id": session.get("li_fat_id"),
            "gbraid": session.get("gbraid"),
            "wbraid": session.get("wbraid"),
            "referrer_url": session.get("referrer_url"),
            "source_property_ref": session.get("source_property_ref"),
            "landing_page_url": session.get("landing_page_url")
        }
        # Limpiar metadatos nulos
        user_metadata = {k: v for k, v in user_metadata.items() if v is not None}

        payload = {
            "queryText": user_query,
            "clientId": session.get("client_id", self.default_client_id),
            "conversationId": session.get("conversation_id"),
            "userMetadata": user_metadata if user_metadata else None
        }

        # Limpiar claves de nivel superior nulas (excepto las requeridas)
        payload = {k: v for k, v in payload.items() if v is not None}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info(f"📤 Enviando mensaje al Core: {user_query[:50]}...")
                response = await client.post(url, json=payload)
                response.raise_for_status()
                
                data = response.json()
                logger.info("📥 Respuesta recibida del Core.")
                return data

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Error HTTP del Core: {e.response.status_code} - {e.response.text}")
            raise ValueError(f"Error del servidor de IA: {e.response.status_code}")

        except httpx.RequestError as e:
            logger.error(f"❌ Error de conexión con el Core: {str(e)}")
            raise ConnectionError("No se pudo conectar con el cerebro de IA.")

        except Exception as e:
            logger.error(f"❌ Error inesperado en el Bridge: {str(e)}")
            raise
