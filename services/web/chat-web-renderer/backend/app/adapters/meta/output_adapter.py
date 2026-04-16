import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from enum import Enum

logger = logging.getLogger("meta_adapter")

META_COMPONENT_LIMITS = {
    "quick_replies": 13,
    "list_elements": 10,
    "button_elements": 3,
}


class MetaChannel(str, Enum):
    WHATSAPP = "meta_whatsapp"
    INSTAGRAM = "meta_ig"


class MetaTextPayload(BaseModel):
    type: str = "text"
    text: str


class MetaImagePayload(BaseModel):
    type: str = "image"
    image: Dict[str, str]


class MetaButtonPayload(BaseModel):
    type: str = "button"
    payload: str
    title: str


class MetaListElement(BaseModel):
    title: str
    subtitle: Optional[str] = None
    payload: Optional[str] = None


class MetaOutputAdapter:
    """
    Adapter para transformar respuestas canónicas al formato Meta (WhatsApp/Instagram).
    
    Formatos soportados por canal:
    - meta_whatsapp: text, image, quick_replies, list
    - meta_ig: text, image, quick_replies
    
    Reglas de degradación:
    - property_card -> text o image (si hay URL)
    - gallery -> image (primera imagen) o text
    - map -> text (con coordinates)
    - calendar -> quick_replies o list
    """

    def __init__(self, channel: MetaChannel):
        self.channel = channel
        self.limits = META_COMPONENT_LIMITS

    def adapt(self, canonical_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transforma una respuesta canónica al formato Meta.
        
        Args:
            canonical_response: Diccionario con:
                - canonical_answer: str
                - intent: Optional[str]
                - payload.components: List[dict]
                - meta: dict
        
        Returns:
            Diccionario con formato Meta:
                - messaging_product: str
                - to: str
                - type: str
                - [text|image|interactive]: dict
        """
        canonical_answer = canonical_response.get("canonical_answer", "")
        components = canonical_response.get("payload", {}).get("components", [])
        
        meta_payloads: List[Dict[str, Any]] = []
        
        for component in components:
            adapted = self._adapt_component(component, canonical_answer)
            if adapted:
                meta_payloads.append(adapted)
        
        if not meta_payloads and canonical_answer:
            meta_payloads.append({"type": "text", "text": canonical_answer})
        
        return {
            "messaging_product": "whatsapp",
            **self._build_payload_container(meta_payloads),
        }

    def _adapt_component(
        self, 
        component: Dict[str, Any], 
        fallback_text: str
    ) -> Optional[Dict[str, Any]]:
        """Transforma un componente individual al formato Meta."""
        comp_type = component.get("type", "")
        
        if comp_type in ["chat", "chat_text"]:
            text = component.get("text", "") or fallback_text
            if text:
                return {"type": "text", "text": text}
        
        elif comp_type == "image":
            image_url = component.get("image_url") or component.get("url")
            if image_url:
                return {"type": "image", "image": {"link": image_url}}
            return {"type": "text", "text": component.get("text", "Imagen no disponible")}
        
        elif comp_type in ["property_card", "property-card"]:
            return self._adapt_property_card(component, fallback_text)
        
        elif comp_type in ["gallery", "photo-carousel"]:
            return self._adapt_gallery(component)
        
        elif comp_type in ["map", "property-map"]:
            return self._adapt_map(component)
        
        elif comp_type in ["calendar", "action-menu", "agenda"]:
            return self._adapt_action_menu(component, fallback_text)
        
        return None

    def _adapt_property_card(
        self, 
        card: Dict[str, Any], 
        fallback_text: str
    ) -> Dict[str, Any]:
        """Adapta una tarjeta de propiedad a formato Meta."""
        title = card.get("title", "Propiedad")
        price = card.get("price", 0)
        location = card.get("location", "")
        
        text = f"{title}\n"
        if price:
            text += f"Precio: ${price:,.0f}\n"
        if location:
            text += f"Ubicación: {location}"
        
        has_id = bool(card.get("id"))
        
        if self.channel == MetaChannel.WHATSAPP and has_id:
            buttons = [{"payload": f"PROPERTY_{card['id']}", "title": "Ver Detalles"}]
            return {
                "type": "interactive",
                "interactive": {
                    "type": "button",
                    "body": {"text": text[:1024]},
                    "action": {
                        "buttons": [
                            {"type": "button", "payload": b["payload"], "title": b["title"][:20]}
                            for b in buttons
                        ]
                    }
                }
            }
        
        return {"type": "text", "text": text[:4096]}

    def _adapt_gallery(self, gallery: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Adapta una galería a formato Meta (toma la primera imagen)."""
        images = gallery.get("images", [])
        image_url = gallery.get("image_url")
        
        if not image_url and images:
            image_url = images[0] if isinstance(images[0], str) else images[0].get("url")
        
        if image_url:
            return {"type": "image", "image": {"link": image_url}}
        
        return None

    def _adapt_map(self, map_comp: Dict[str, Any]) -> Dict[str, Any]:
        """Adapta un mapa a formato texto."""
        center = map_comp.get("center", {})
        lat = center.get("lat", 0)
        lng = center.get("lng", 0)
        
        text = f"📍 Ubicación: {map_comp.get('location', 'Ver mapa')}\n"
        text += f"https://www.google.com/maps?q={lat},{lng}"
        
        return {"type": "text", "text": text[:4096]}

    def _adapt_action_menu(
        self, 
        menu: Dict[str, Any], 
        fallback_text: str
    ) -> Optional[Dict[str, Any]]:
        """Adapta un menú de acciones a quick replies o list."""
        options = menu.get("options", [])
        body_text = str(menu.get("title") or fallback_text or "Opciones disponibles").strip()

        if not options:
            return {"type": "text", "text": body_text}

        if self.channel == MetaChannel.WHATSAPP:
            if len(options) <= self.limits["button_elements"]:
                return self._build_button_payload(options, body_text)
            return self._build_list_payload(options, body_text)

        return self._build_button_payload(options, body_text)

    def _build_button_payload(
        self, 
        options: List[Dict[str, Any]], 
        body_text: str
    ) -> Dict[str, Any]:
        """Construye payload de botones."""
        buttons = []
        for opt in options[:3]:
            buttons.append({
                "type": "button",
                "payload": opt.get("payload", ""),
                "title": opt.get("label", "")[:20]
            })
        
        return {
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body_text[:1024]},
                "action": {"buttons": buttons}
            }
        }

    def _build_list_payload(
        self, 
        options: List[Dict[str, Any]], 
        body_text: str
    ) -> Dict[str, Any]:
        """Construye payload de lista para WhatsApp."""
        elements = []
        for opt in options[:self.limits["list_elements"]]:
            elements.append({
                "title": opt.get("label", "")[:24],
                "subtitle": opt.get("description", "")[:72],
                "payload": opt.get("payload", "")
            })
        
        return {
            "type": "interactive",
            "interactive": {
                "type": "list",
                "header": {"type": "text", "text": "Opciones"},
                "body": {"text": body_text[:1024]},
                "action": {
                    "button": "Ver Opciones",
                    "sections": [{
                        "title": "Selecciona",
                        "rows": elements
                    }]
                }
            }
        }

    def _build_payload_container(
        self, 
        payloads: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Envuelve los payloads en el contenedor apropiado."""
        if len(payloads) == 1:
            return payloads[0]
        
        first = payloads[0]
        return first


def create_meta_adapter(channel: str) -> MetaOutputAdapter:
    """Factory para crear el adapter apropiado."""
    if channel == "meta_whatsapp":
        return MetaOutputAdapter(MetaChannel.WHATSAPP)
    elif channel == "meta_ig":
        return MetaOutputAdapter(MetaChannel.INSTAGRAM)
    else:
        raise ValueError(f"Unknown Meta channel: {channel}")
