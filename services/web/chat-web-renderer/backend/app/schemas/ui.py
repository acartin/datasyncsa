from typing import List, Optional, Union, Dict
from pydantic import BaseModel, Field

class BaseComponent(BaseModel):
    type: str
    id: Optional[str] = None

class ChatMessage(BaseComponent):
    type: str = "chat"
    text: str
    sender: str  # "bot" or "user"

class PropertyCard(BaseComponent):
    type: str = "property-card"
    title: str
    price: float
    location: Optional[str] = None
    image_url: Optional[str] = None
    public_url: Optional[str] = None
    features: Dict[str, Union[int, float, str]] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)

class MortgageCalculator(BaseComponent):
    type: str = "mortgage-calculator"
    property_price: float
    default_interest: float = 8.5
    allow_custom_input: bool = True

class PropertyGrid(BaseComponent):
    type: str = "property-grid"
    title: str
    properties: List[PropertyCard]
    layout: str = "horizontal"

class PropertyMap(BaseComponent):
    type: str = "property-map"
    center: Dict[str, float]  # {"lat": ..., "lng": ...}
    zoom: int = 15
    pois: List[Dict[str, Union[float, str]]] = Field(default_factory=list)
    interactive: bool = True

class ActionMenu(BaseComponent):
    type: str = "action-menu"
    title: Optional[str] = None
    options: List[Dict[str, str]]  # [{"label": "Ver Más", "payload": "HOUSE_123"}]

class PhotoCarousel(BaseComponent):
    type: str = "photo-carousel"
    images: List[str]
    show_thumbnails: bool = False

class BrandingConfig(BaseModel):
    primary_color: str = "#4b38b3"
    secondary_color: str = "#6366f1"
    surface_color: Optional[str] = None
    text_on_primary: Optional[str] = "#ffffff"
    text_on_secondary: Optional[str] = "#ffffff"
    text_on_surface: Optional[str] = "#f8fafc"
    
    # Fuentes
    font_heading_name: Optional[str] = "Outfit"
    font_heading_url: Optional[str] = None
    font_body_name: Optional[str] = "Inter"
    font_body_url: Optional[str] = None
    
    # Estética
    border_radius: Optional[str] = "18px"
    box_shadow_style: Optional[str] = "0 10px 25px rgba(0,0,0,0.1)"
    
    # Logos (Base64)
    favicon_base64: Optional[str] = None
    logo_header_base64: Optional[str] = None
    brand_wordmark_base64: Optional[str] = None
    
    agent_name: str = "Hommie AI"

class SDUIResponse(BaseModel):
    session_id: str
    branding: Optional[BrandingConfig] = None
    components: List[Union[ChatMessage, PropertyCard, MortgageCalculator, PropertyGrid, PropertyMap, ActionMenu, PhotoCarousel]]
