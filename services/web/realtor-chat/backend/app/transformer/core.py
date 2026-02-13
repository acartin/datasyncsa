import logging
import asyncio
from typing import Dict, Any, List, Union
from app.schemas.ui import (
    SDUIResponse, ChatMessage, PropertyCard, PropertyGrid, 
    ActionMenu, MortgageCalculator, BaseComponent, BrandingConfig
)
from app.core.database import db_manager

# Logger config
logger = logging.getLogger("transformer")

class SDUITransformer:
    """
    El 'Transformer' es el corazón polimórfico del Bridge.
    Toma la respuesta cruda de la IA (texto + sources) y decide qué 
    componentes visuales (Cards, Grids, Mapas) se deben renderizar.
    """

    async def transform(
        self,
        ai_response: Dict[str, Any],
        session_id: str,
        client_id: str = "default",
        include_fallback_text: bool = True,
    ) -> SDUIResponse:
        """
        Convierte el payload del Inference Core en una respuesta SDUI estructurada.
        """
        components: List[BaseComponent] = []
        
        # 1. Extraer el Texto Base (Siempre hay un mensaje de chat)
        ai_text = (ai_response.get("answer", "") or "").strip()
        if ai_text:
            components.append(ChatMessage(text=ai_text, sender="bot"))
        elif include_fallback_text:
            components.append(ChatMessage(text="Lo siento, no pude generar una respuesta.", sender="bot"))

        # 2. Procesar Fuentes (Sources) - Aquí ocurre la magia de "Grounding"
        # Si la IA cita propiedades, las convertimos en Cards visuales.
        sources = ai_response.get("sources", [])
        property_cards = await self._extract_properties_from_sources(sources)

        if property_cards:
            if len(property_cards) == 1:
                # Si es una sola, la mostramos directa
                components.append(property_cards[0])
                # Y quizás una calculadora para esa propiedad
                components.append(MortgageCalculator(property_price=property_cards[0].price))
            else:
                # Si son varias, usamos un Grid/Carrusel
                components.append(PropertyGrid(
                    title="Propiedades Relacionadas",
                    properties=property_cards
                ))

        # 3. Detectar Intenciones de Acción (Heurística simple por ahora)
        if ai_text and ("cita" in ai_text.lower() or "visita" in ai_text.lower()):
            components.append(ActionMenu(
                options=[
                    {"label": "📅 Agendar Visita", "payload": "SCHEDULE_VISIT"},
                    {"label": "📞 Hablar con Asesor", "payload": "CALL_AGENT"}
                ]
            ))

        # 4. Configuración de Branding (Multi-tenant Real)
        branding = await self._get_branding_for_client(client_id)

        return SDUIResponse(
            session_id=session_id,
            branding=branding,
            components=components
        )

    async def _get_branding_for_client(self, client_id: str) -> BrandingConfig:
        """
        Retorna la configuración visual adaptada al cliente desde la DB.
        """
        db_brand = await asyncio.to_thread(db_manager.get_branding, client_id)
        if not db_brand:
            return BrandingConfig()

        # Si tenemos branding en DB, mapeamos campos
        # lead_brand_configs: primary_color, secondary_color, project (como agent_name)
        return BrandingConfig(
            primary_color=db_brand.get("primary_color", "#4b38b3"),
            secondary_color=db_brand.get("secondary_color", "#6366f1"),
            surface_color=db_brand.get("surface_color"),
            text_on_primary=db_brand.get("text_on_primary", "#ffffff"),
            text_on_secondary=db_brand.get("text_on_secondary", "#ffffff"),
            text_on_surface=db_brand.get("text_on_surface", "#f8fafc"),
            
            # Fuentes
            font_heading_name=db_brand.get("font_heading_name", "Outfit"),
            font_heading_url=db_brand.get("font_heading_url"),
            font_body_name=db_brand.get("font_body_name", "Inter"),
            font_body_url=db_brand.get("font_body_url"),
            
            # Estética
            border_radius=db_brand.get("border_radius", "18px"),
            box_shadow_style=db_brand.get("box_shadow_style", "0 10px 25px rgba(0,0,0,0.1)"),
            
            # Logos (Base64)
            favicon_base64=db_brand.get("favicon_base64"),
            logo_header_base64=db_brand.get("logo_header_base64"),
            brand_wordmark_base64=db_brand.get("brand_wordmark_base64"),
            
            agent_name=db_brand.get("project", db_brand.get("agent_name", "Hommie AI"))
        )

    async def _extract_properties_from_sources(self, sources: List[Dict[str, Any]]) -> List[PropertyCard]:
        """
        Analiza los sources devueltos por RAG. Si encuentra metadatos de propiedades,
        crea los objetos PropertyCard correspondientes consultando la base de datos real.
        """
        cards = []
        prop_ids: List[Any] = []
        seen_ids = set()

        for source in sources:
            metadata = source.get("metadata", {})
            
            # Buscamos el ID de la propiedad (puede venir como 'id' o 'external_prop_id')
            prop_id = metadata.get("id") or metadata.get("id_propiedad")
            if prop_id and prop_id not in seen_ids:
                seen_ids.add(prop_id)
                prop_ids.append(prop_id)

        if not prop_ids:
            return cards

        # Ejecuta consultas de propiedades fuera del event loop principal
        prop_results = await asyncio.gather(
            *(asyncio.to_thread(db_manager.get_property, prop_id) for prop_id in prop_ids),
            return_exceptions=True,
        )

        for prop_data in prop_results:
            if isinstance(prop_data, Exception) or not prop_data:
                continue
            try:
                title = prop_data.get("title", "Propiedad Sugerida").replace("&#8211;", "-")
                card = PropertyCard(
                    id=str(prop_data.get("id")),
                    title=title,
                    price=float(prop_data.get("price", 0)),
                    location=f"{prop_data.get('address_city', '')}, {prop_data.get('address_state', '')}".strip(", "),
                    image_url=prop_data["images"][0] if prop_data.get("images") else None,
                    tags=prop_data.get("features", {}).get("highlights", []) if isinstance(prop_data.get("features"), dict) else [],
                )
                cards.append(card)
            except Exception as e:
                logger.warning(f"Error mapeando data de DB a PropertyCard: {e}")
                continue
        
        return cards
