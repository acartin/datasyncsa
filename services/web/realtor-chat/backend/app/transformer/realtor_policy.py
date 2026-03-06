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

logger = logging.getLogger("realtor_policy")

REALTOR_VERTICAL = "realtor"
FALLBACK_COMPONENT = "chat_text"

COMPONENT_TYPE_MAPPING = {
    "chat_text": "chat",
    "property_card": "property-card",
    "property_grid": "property-grid",
    "gallery": "photo-carousel",
    "map": "property-map",
    "calendar": "action-menu",
    "mortgage_calculator": "mortgage-calculator",
}


class RealtorRendererPolicy:
    """
    Política de renderizado para el vertical 'realtor'.
    Garantiza que solo se emitan componentes permitidos según la policy central.
    """

    def __init__(self, channel: str = "web_html"):
        self.channel = channel
        self.allowed_components: List[str] = get_allowed_components(REALTOR_VERTICAL, channel)
        logger.info(f"RealtorRendererPolicy initialized for channel '{channel}' with allowed: {self.allowed_components}")

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
                logger.info(f"Component type '{comp_type}' not allowed for channel '{self.channel}', converting to chat_text")
                filtered.extend(self._degrade_to_text(component))

        return filtered

    def _get_policy_component_type(self, component: BaseComponent) -> str:
        """Mapea el tipo de componente SDUI al tipo de la policy."""
        sdui_type = component.type

        for policy_type, mapped_type in COMPONENT_TYPE_MAPPING.items():
            if sdui_type == mapped_type:
                return policy_type

        return "chat_text"

    def _degrade_to_text(self, component: BaseComponent) -> List[BaseComponent]:
        """
        Degrada un componente no soportado a chat_text.
        """
        if isinstance(component, ChatMessage):
            return [component]

        text = "Aquí tienes información adicional."
        if isinstance(component, PropertyCard):
            text = f"Propiedad: {component.title} - ${component.price:,.0f}"
        elif isinstance(component, PropertyGrid):
            text = f"Tenemos {len(component.properties)} propiedades relacionadas."
        elif isinstance(component, PropertyMap):
            text = "Aquí tienes la ubicación en el mapa."
        elif isinstance(component, PhotoCarousel):
            text = f"Tenemos {len(component.images)} fotos adicionales."
        elif isinstance(component, ActionMenu):
            text = "Tenemos opciones disponibles para ti."
        elif isinstance(component, MortgageCalculator):
            text = f"Precio de propiedad: ${component.property_price:,.0f}"

        return [ChatMessage(text=text, sender="bot")]

    def build_response(
        self,
        ai_text: str,
        components: List[BaseComponent],
        session_id: str,
    ) -> Dict[str, Any]:
        """
        Construye el payload final de respuesta, siempre incluyendo chat_text.
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
                "vertical": REALTOR_VERTICAL,
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
            policy_type = None
            for ptype, ctype in COMPONENT_TYPE_MAPPING.items():
                if ctype == comp_type:
                    policy_type = ptype
                    break

            if policy_type and policy_type not in self.allowed_components:
                logger.warning(f"Invalid component {comp_type} in final response")
                return False

        return True


def create_realtor_policy(channel: str) -> RealtorRendererPolicy:
    return RealtorRendererPolicy(channel=channel)
