import os
import httpx
import logging
from typing import Dict, Any

# Logger config
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("inference_bridge")


class InferenceClient:
    """
    El cable que conecta el renderer con el runtime conversacional activo.
    Se encarga de enviar el payload con metadatos y recibir la respuesta plana.
    Opera contra el runtime activo del asistente.
    """

    def __init__(self):
        self.timeout = int(os.getenv("INFERENCE_TIMEOUT", 60))
        self.connect_timeout = float(os.getenv("INFERENCE_CONNECT_TIMEOUT", 5))
        self.default_client_id = os.getenv("DEFAULT_CLIENT_ID", "")
        inference_url = os.getenv(
            "AI_RUNTIME_API",
            os.getenv(
                "AGENT_CORE_API",
                os.getenv("INFERENCE_API_URL", os.getenv("INFERENCE_V2_URL", "http://ai-runtime:8000")),
            ),
        )
        api_prefix = os.getenv(
            "AI_RUNTIME_API_PREFIX",
            os.getenv(
                "AGENT_CORE_API_PREFIX",
                os.getenv("INFERENCE_API_PREFIX", os.getenv("INFERENCE_V2_API_PREFIX", "/api/v1")),
            ),
        )
        self.base_url = inference_url.rstrip("/") + api_prefix
        logger.info("🔌 InferenceClient conectado a %s (Timeout: %ss)", self.base_url, self.timeout)

    async def chat(self, user_query: str, session: Dict[str, Any]) -> Dict[str, Any]:
        """
        Envía un mensaje al Core AI.
        
        :param user_query: El texto que escribió el usuario.
        :param session: Diccionario con metadatos de la sesión (conversation_id, lead_id, etc.)
        """
        url = f"{self.base_url}/chat"
        trace_id = str(session.get("debug_trace_id") or "-")
        
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
                logger.info(
                    "📤 Enviando mensaje al Core: trace_id=%s client_id=%s conversation_id=%s channel=%s channel_user_id=%s text=%s",
                    trace_id,
                    session.get("client_id"),
                    session.get("conversation_id"),
                    session.get("channel"),
                    session.get("channel_user_id"),
                    user_query[:50],
                )
                response = await client.post(url, json=payload)
                response.raise_for_status()
                
                data = response.json()
                logger.info(
                    "📥 Respuesta recibida del Core: trace_id=%s conversation_id=%s answer_chars=%s components=%s",
                    trace_id,
                    data.get("conversationId", data.get("conversation_id")),
                    len((data.get("answer") or "").strip()),
                    len(data.get("components") or []),
                )
                return self._normalize_v2_response(data)

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Error HTTP del Core: {e.response.status_code} - {e.response.text}")
            raise ValueError(f"Error del servidor de IA: {e.response.status_code}")

        except httpx.TimeoutException as e:
            logger.error(f"❌ Timeout con Core ({self.timeout}s): {repr(e)}")
            raise TimeoutError("El servicio de IA tardó demasiado en responder.")

        except httpx.RequestError as e:
            logger.error(f"❌ Error de conexión con el Core: {repr(e)}")
            raise ConnectionError("No se pudo conectar con el cerebro de IA.")

        except Exception as e:
            logger.error(f"❌ Error inesperado en el bridge: {str(e)}")
            raise

    def _normalize_v2_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normaliza la respuesta del core al formato esperado por el transformer.
        """
        normalized = {
            "answer": data.get("answer", ""),
            "sources": data.get("sources", []),
            "components": data.get("components", []),
            "intent": data.get("intent"),
            "conversation_id": str(data.get("conversationId", data.get("conversation_id", ""))),
        }
        
        if "realtorTurn" in data or "realtor_turn" in data:
            normalized["realtor_turn"] = data.get("realtor_turn") or data.get("realtorTurn")
        
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

        if data.get("metadata"):
            normalized["metadata"] = data.get("metadata")
        
        return normalized
