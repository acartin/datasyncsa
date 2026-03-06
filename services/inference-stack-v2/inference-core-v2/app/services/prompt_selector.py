"""
Prompt Selector for Chat by Vertical + Channel

This module defines the strategy for selecting the appropriate chat prompt
based on vertical (realtor/generic) and channel (web_html, meta_whatsapp, etc.).

The separation of concerns:
- Prompt: decides semantics, intent extraction, response style
- Backend (realtor_policy/generic_policy): decides render/UI components
"""

import logging
from typing import Dict, Any, Optional, List
from typing import Literal

logger = logging.getLogger("prompt_selector")

CHANNEL_LITERAL = Literal["web_html", "meta_whatsapp", "meta_ig", "api"]
VERTICAL_LITERAL = Literal["realtor", "generic"]

DEFAULT_PROMPT_SLUGS = {
    ("realtor", "web_html"): "realtor_web_v1",
    ("realtor", "meta_whatsapp"): "realtor_meta_whatsapp_v1",
    ("realtor", "meta_ig"): "realtor_meta_ig_v1",
    ("realtor", "api"): "realtor_api_v1",
    ("generic", "web_html"): "generic_web_v1",
    ("generic", "meta_whatsapp"): "generic_meta_whatsapp_v1",
    ("generic", "meta_ig"): "generic_meta_ig_v1",
    ("generic", "api"): "generic_api_v1",
}

REALTOR_ALIASES = {"realtor", "real-estate", "real_estate", "inmobiliaria"}
GENERIC_ALIASES = {"generic"}


class PromptSelector:
    """
    Selects the appropriate prompt slug based on vertical and channel.
    
    The prompt defines:
    - Semantic style (formal/casual)
    - Intent extraction patterns
    - Response structure expectations
    - Domain-specific terminology
    
    The backend policy defines:
    - UI components to render
    - Channel-specific formatting
    - Fallback behavior
    """

    def __init__(self):
        self._cache: Dict[str, str] = {}

    @staticmethod
    def normalize_vertical(vertical: str) -> str:
        raw = (vertical or "").strip().lower()
        if raw in REALTOR_ALIASES:
            return "realtor"
        if raw in GENERIC_ALIASES:
            return "generic"
        return "generic"

    def get_prompt_slug(self, vertical: str, channel: str) -> str:
        """
        Get the prompt slug for the given vertical + channel combination.
        
        Args:
            vertical: "realtor" or "generic"
            channel: "web_html", "meta_whatsapp", "meta_ig", or "api"
        
        Returns:
            Prompt slug (e.g., "realtor_web_v1")
        
        Raises:
            ValueError: If vertical or channel is invalid
        """
        normalized_vertical = self.normalize_vertical(vertical)
        if normalized_vertical == "generic" and (vertical or "").strip().lower() not in GENERIC_ALIASES:
            logger.warning(f"Unknown vertical '{vertical}', falling back to 'generic'")
        vertical = normalized_vertical
        
        if channel not in ["web_html", "meta_whatsapp", "meta_ig", "api"]:
            logger.warning(f"Unknown channel '{channel}', falling back to 'api'")
            channel = "api"
        
        cache_key = f"{vertical}:{channel}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        slug = DEFAULT_PROMPT_SLUGS.get((vertical, channel), "generic_web_v1")
        self._cache[cache_key] = slug
        
        logger.info(f"Selected prompt slug '{slug}' for vertical='{vertical}' channel='{channel}'")
        return slug

    def clear_cache(self) -> None:
        """Clear the prompt slug cache."""
        self._cache.clear()


class ChatPromptTemplate:
    """
    Defines structured placeholders for improved intent extraction.
    
    These placeholders should be used in prompt templates to ensure
    consistent intent extraction regardless of channel.
    """
    
    PLACEHOLDER_INTENT = "{INTENT}"
    PLACEHOLDER_ENTITIES = "{ENTITIES}"
    PLACEHOLDER_CHANNEL = "{CHANNEL}"
    PLACEHOLDER_VERTICAL = "{VERTICAL}"
    PLACEHOLDER_USER_CONTEXT = "{USER_CONTEXT}"
    
    @staticmethod
    def get_system_prompt_template(
        vertical: str,
        channel: str,
    ) -> str:
        """
        Get the system prompt template for the given vertical + channel.
        
        This template defines the semantic behavior:
        - How to interpret user messages
        - What intent patterns to look for
        - How to structure the response
        """
        base_template = """Eres un asistente de chat para {vertical_display}.
        
Contexto del canal: {channel_description}
Tu rol es: {role_description}

Instrucciones de respuesta:
{response_instructions}

Ejemplos de intenciones que debes detectar:
{intent_examples}

Cuando respondas, estructura tu respuesta para facilitar la extracción de:
- Intención principal del usuario
- Entidades mencionadas (ubicaciones, precios, características)
- Próxima acción recomendada
"""

        vertical_configs = {
            "realtor": {
                "display": "bienes raíces / real estate",
                "role": "experto en propiedades inmobiliarias",
                "intents": [
                    "property_search - buscar propiedades",
                    "property_details - ver detalles de propiedad",
                    "schedule_visit - agendar visita",
                    "mortgage_info - información de financiamiento",
                    "compare_properties - comparar propiedades",
                ],
                "response_style": "Incluye detalles relevantes de propiedades cuando sea apropiado.",
            },
            "generic": {
                "display": "atención general al cliente",
                "role": "asistente de atención al cliente",
                "intents": [
                    "general_query - consulta general",
                    "support_request - solicitud de soporte",
                    "information_request - solicitud de información",
                ],
                "response_style": "Proporciona información clara y concisa.",
            },
        }

        channel_configs = {
            "web_html": {
                "description": "Interfaz web HTML con soporte completo de componentes UI",
                "style": "Puedes sugerir componentes UI ricos cuando sea útil.",
            },
            "meta_whatsapp": {
                "description": "WhatsApp de Meta (limitado a texto, imágenes, listas, quick replies)",
                "style": "Usa formato conciso. Puedes sugerir quick replies.",
            },
            "meta_ig": {
                "description": "Instagram Direct (limitado a texto, imágenes, quick replies)",
                "style": "Usa formato conciso y visual cuando sea posible.",
            },
            "api": {
                "description": "API externa (respuesta JSON estructurada)",
                "style": "Proporciona respuesta estructurada con intención clara.",
            },
        }

        v_config = vertical_configs.get(vertical, vertical_configs["generic"])
        c_config = channel_configs.get(channel, channel_configs["api"])

        return base_template.format(
            vertical_display=v_config["display"],
            channel_description=c_config["description"],
            role_description=v_config["role"],
            response_instructions=v_config["response_style"],
            intent_examples="\n".join(f"- {i}" for i in v_config["intents"]),
        )

    @staticmethod
    def get_intent_extraction_prompt(user_message: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Get a structured prompt for intent extraction.
        
        This can be used when you need to explicitly extract intent
        from a user message for downstream processing.
        """
        parts = [
            f"Usuario dice: {user_message}",
        ]
        
        if context:
            if context.get("channel"):
                parts.append(f"Canal: {context['channel']}")
            if context.get("vertical"):
                parts.append(f"Vertical: {context['vertical']}")
            if context.get("conversation_history"):
                history = context["conversation_history"][-3:]
                parts.append(f"Historial reciente: {' | '.join(history)}")
        
        parts.append("""
Based on the above, extract:
1. PRIMARY_INTENT: The main user intent
2. ENTITIES: Key entities mentioned (locations, prices, features)
3. NEXT_ACTION: Recommended next action
4. CONFIDENCE: Your confidence in this analysis (0-1)
""")
        
        return "\n".join(parts)


prompt_selector = PromptSelector()
