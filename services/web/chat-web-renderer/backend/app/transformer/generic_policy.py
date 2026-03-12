import logging
from typing import Dict, Any, List, Union
from app.transformer.policy_loader import PolicyLoader, get_allowed_components
from app.schemas.ui import (
    BaseComponent,
    ChatMessage,
    PropertyCard,
    PropertyGrid,
    PropertyMap,
    PhotoCarousel,
    ActionMenu,
    MortgageCalculator,
)

logger = logging.getLogger("generic_policy")

REALTOR_VERTICAL = "realtor"
GENERIC_VERTICAL = "generic"

SDUI_TO_POLICY_TYPES = {
    "photo-carousel": ["gallery", "image"],
    "property-card": ["property_card"],
    "property-grid": ["property_grid"],
    "property-map": ["map"],
    "action-menu": ["calendar", "agenda"],
    "mortgage-calculator": ["mortgage_calculator"],
    "chat": ["chat_text"],
    "mortgage-calculator": ["mortgage_calculator"],
}


class GenericRendererPolicy:
    """
    Política de renderizado para el vertical 'generic'.
    Salida limitada a: agenda, image, chat_text.
    """

    def __init__(self, channel: str = "web_html"):
        self.channel = channel
        self.allowed_components: List[str] = get_allowed_components(GENERIC_VERTICAL, channel)
        logger.info(f"GenericRendererPolicy initialized for channel '{channel}' with allowed: {self.allowed_components}")

    def filter_components(
        self,
        ai_response: Dict[str, Any],
        extracted_components: List[BaseComponent],
    ) -> List[BaseComponent]:
        """
        Filtra componentes extraídos según whitelist de la policy.
        Si un componente no está permitido, lo degrada a chat_text.
        """
        filtered: List[BaseComponent] = []

        for component in extracted_components:
            comp_type = self._get_policy_component_type(component)
            if comp_type in self.allowed_components:
                filtered.append(component)
            else:
                logger.info(f"Component type '{comp_type}' not allowed for channel '{self.channel}' (generic), converting to chat_text")
                filtered.extend(self._degrade_to_text(component))

        return filtered

    def _get_policy_component_type(self, component: BaseComponent) -> str:
        """Mapea el tipo de componente SDUI al tipo de la policy."""
        sdui_type = component.type

        policy_types = SDUI_TO_POLICY_TYPES.get(sdui_type, [])
        
        for policy_type in policy_types:
            if policy_type in self.allowed_components:
                return policy_type

        return sdui_type

    def _degrade_to_text(self, component: BaseComponent) -> List[BaseComponent]:
        """
        Degrada un componente no soportado a chat_text.
        """
        if isinstance(component, ChatMessage):
            return [component]

        text = "Información adicional disponible."
        if isinstance(component, PropertyCard):
            text = "Tenemos propiedades disponibles. ¿Te gustaría más información?"
        elif isinstance(component, PropertyGrid):
            text = "Tenemos varias opciones disponibles."
        elif isinstance(component, PropertyMap):
            text = "Tenemos ubicaciones disponibles."
        elif isinstance(component, PhotoCarousel):
            text = "Tenemos imágenes adicionales disponibles."
        elif isinstance(component, ActionMenu):
            text = "Tenemos opciones disponibles para ti."
        elif isinstance(component, MortgageCalculator):
            text = "Tenemos información de financiamiento disponible."

        return [ChatMessage(text=text, sender="bot")]

    def build_response(
        self,
        ai_text: str,
        components: List[BaseComponent],
        session_id: str,
    ) -> Dict[str, Any]:
        """
        Construye el payload final de respuesta para generic.
        """
        final_components: List[BaseComponent] = []

        if ai_text:
            final_components.append(ChatMessage(text=ai_text, sender="bot"))

        final_components.extend(components)

        filtered = self.filter_components({"answer": ai_text}, final_components)

        return {
            "session_id": session_id,
            "components": [c.model_dump() for c in filtered],
            "meta": {
                "vertical": GENERIC_VERTICAL,
                "channel": self.channel,
                "allowed_components": self.allowed_components,
            },
        }

    def validate_response(self, response: Dict[str, Any]) -> bool:
        """
        Valida que la respuesta solo contenga componentes permitidos.
        """
        components = response.get("components", [])
        for comp in components:
            comp_type = comp.get("type")
            policy_types = SDUI_TO_POLICY_TYPES.get(comp_type, ["chat_text"])
            
            allowed = any(pt in self.allowed_components for pt in policy_types)
            if not allowed:
                logger.warning(f"Invalid component {comp_type} in final response (generic)")
                return False

        return True


def create_generic_policy(channel: str) -> GenericRendererPolicy:
    return GenericRendererPolicy(channel=channel)
