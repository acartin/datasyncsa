import os
import httpx
import logging
from typing import Dict, Any

# Logger config
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("inference_bridge")


class InferenceClient:
    """
    El 'Cable' que conecta el Bridge con el Cerebro de IA (Inference Core).
    Se encarga de enviar el payload con metadatos y recibir la respuesta plana.
    Opera exclusivamente con Inference Core V2.
    """

    def __init__(self):
        self.timeout = int(os.getenv("INFERENCE_TIMEOUT", 60))
        self.connect_timeout = float(os.getenv("INFERENCE_CONNECT_TIMEOUT", 5))
        self.default_client_id = os.getenv("DEFAULT_CLIENT_ID", "")
        self.base_url = os.getenv("INFERENCE_V2_URL", "http://inference-core-v2:8000") + "/api/v2"
        logger.info(f"🔌 InferenceClient conectado a Inference Core V2: {self.base_url} (Timeout: {self.timeout}s)")

    async def chat(self, user_query: str, session: Dict[str, Any]) -> Dict[str, Any]:
        """
        Envía un mensaje al Core AI.
        
        :param user_query: El texto que escribió el usuario.
        :param session: Diccionario con metadatos de la sesión (conversation_id, lead_id, etc.)
        """
        return await self._chat_v2(user_query, session)

    async def _chat_v2(self, user_query: str, session: Dict[str, Any]) -> Dict[str, Any]:
        """
        Envía un mensaje al Inference Core V2.
        """
        url = f"{self.base_url}/chat"
        
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
        user_metadata = {k: v for k, v in user_metadata.items() if v is not None}

        payload = {
            "queryText": user_query,
            "clientId": session.get("client_id", self.default_client_id),
            "conversationId": session.get("conversation_id"),
            "userMetadata": user_metadata if user_metadata else None
        }
        payload = {k: v for k, v in payload.items() if v is not None}

        try:
            timeout = httpx.Timeout(timeout=self.timeout, connect=self.connect_timeout)
            async with httpx.AsyncClient(timeout=timeout) as client:
                logger.info(f"📤 Enviando mensaje al Core V2: {user_query[:50]}...")
                response = await client.post(url, json=payload)
                response.raise_for_status()
                
                data = response.json()
                logger.info("📥 Respuesta recibida del Core V2.")
                return self._normalize_v2_response(data)

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Error HTTP del Core V2: {e.response.status_code} - {e.response.text}")
            raise ValueError(f"Error del servidor de IA: {e.response.status_code}")

        except httpx.TimeoutException as e:
            logger.error(f"❌ Timeout con Core V2 ({self.timeout}s): {repr(e)}")
            raise TimeoutError("El servicio de IA tardó demasiado en responder.")

        except httpx.RequestError as e:
            logger.error(f"❌ Error de conexión con el Core V2: {repr(e)}")
            raise ConnectionError("No se pudo conectar con el cerebro de IA V2.")

        except Exception as e:
            logger.error(f"❌ Error inesperado en el Bridge V2: {str(e)}")
            raise

    def _normalize_v2_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normaliza la respuesta de V2 al formato esperado por el transformer.
        """
        normalized = {
            "answer": data.get("answer", ""),
            "sources": data.get("sources", []),
            "conversation_id": str(data.get("conversationId", data.get("conversation_id", ""))),
        }
        
        if data.get("leadId") or data.get("lead_id"):
            normalized["lead_id"] = str(data.get("leadId") or data.get("lead_id"))
        
        if data.get("scorecard"):
            scorecard = data["scorecard"]
            normalized["scorecard"] = {
                "score_total": scorecard.get("scoreTotal", scorecard.get("score_total")),
                "priority_label": scorecard.get("priorityLabel", scorecard.get("priority_label")),
                "reasoning": scorecard.get("reasoning"),
                "score_items": scorecard.get("scoreItems", scorecard.get("score_items", [])),
                "model_version": scorecard.get("modelVersion", scorecard.get("model_version")),
                "prompt_version": scorecard.get("promptVersion", scorecard.get("prompt_version")),
            }
        
        if data.get("scorecardId") or data.get("scorecard_id"):
            normalized["scorecard_id"] = str(data.get("scorecardId") or data.get("scorecard_id"))

        if data.get("scoringStatus") or data.get("scoring_status"):
            normalized["scoring_status"] = str(data.get("scoringStatus") or data.get("scoring_status"))
        if data.get("scoringJobId") or data.get("scoring_job_id"):
            normalized["scoring_job_id"] = str(data.get("scoringJobId") or data.get("scoring_job_id"))
        if data.get("scoringEta") or data.get("scoring_eta"):
            normalized["scoring_eta"] = str(data.get("scoringEta") or data.get("scoring_eta"))
        
        return normalized
