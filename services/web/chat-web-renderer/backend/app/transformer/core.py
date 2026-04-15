import logging
import asyncio
import re
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
        brand_project: Union[str, None] = None,
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
        branding = await self._get_branding_for_client(client_id, brand_project)

        return SDUIResponse(
            session_id=session_id,
            branding=branding,
            components=components
        )

    def parse_canonical_components(self, canonical_components: List[Dict[str, Any]]) -> List[BaseComponent]:
        components: List[BaseComponent] = []
        for payload in canonical_components or []:
            if not isinstance(payload, dict):
                continue
            card_type = str(payload.get("card_type") or "").strip().lower()
            comp_type = str(payload.get("type") or "").strip().lower()

            # Agent-core realtor cards arrive as card_type=property_card.
            if card_type == "property_card" or comp_type == "property-card":
                card = self._map_agent_core_property_card(payload)
                if card:
                    components.append(card)
                continue

            if comp_type == "chat":
                text = str(payload.get("text") or "").strip()
                if text:
                    components.append(ChatMessage(text=text, sender="bot"))
                continue

        return components

    async def _get_branding_for_client(self, client_id: str, brand_project: Union[str, None]) -> BrandingConfig:
        """
        Retorna la configuración visual adaptada al cliente desde la DB.
        """
        db_brand = await asyncio.to_thread(db_manager.get_branding, client_id, brand_project)
        if not db_brand:
            return BrandingConfig()

        agent_name = self._normalize_agent_name(
            db_brand.get("agent_name"),
            db_brand.get("project"),
        )

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
            font_heading_name=db_brand.get("font_heading_name", "Cormorant Garamond"),
            font_heading_url=db_brand.get("font_heading_url"),
            font_body_name=db_brand.get("font_body_name", "DM Sans"),
            font_body_url=db_brand.get("font_body_url"),
            
            # Estética
            border_radius=db_brand.get("border_radius", "18px"),
            box_shadow_style=db_brand.get("box_shadow_style", "0 10px 25px rgba(0,0,0,0.1)"),
            
            # Logos (Base64)
            favicon_base64=db_brand.get("favicon_base64"),
            logo_header_base64=db_brand.get("logo_header_base64"),
            brand_wordmark_base64=db_brand.get("brand_wordmark_base64"),

            agent_name=agent_name,
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
            
            # El runtime y el contrato canonico operan solo con el UUID interno.
            prop_id = metadata.get("id")
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
            card = self._map_property_data_to_card(prop_data)
            if card:
                cards.append(card)
        
        return cards

    async def search_properties_for_query(
        self,
        client_id: str,
        query_text: str,
        limit: int = 4,
        include_terms: bool = True,
    ) -> List[PropertyCard]:
        properties = await asyncio.to_thread(
            db_manager.search_properties,
            client_id,
            query_text,
            limit,
            include_terms,
        )
        cards: List[PropertyCard] = []
        for prop_data in properties or []:
            card = self._map_property_data_to_card(prop_data)
            if card:
                cards.append(card)
        return cards

    async def count_properties_for_query(self, client_id: str, query_text: str, include_terms: bool = True) -> int:
        return await asyncio.to_thread(db_manager.count_properties, client_id, query_text, include_terms)

    async def get_property_price_stats_for_query(self, client_id: str, query_text: str, include_terms: bool = False) -> Dict[str, Any]:
        return await asyncio.to_thread(db_manager.get_property_price_stats, client_id, query_text, include_terms)

    async def extract_property_filters_for_query(self, query_text: str) -> Dict[str, Any]:
        return await asyncio.to_thread(db_manager.extract_property_filters, query_text)

    def _first_non_empty(self, *values: Any) -> Any:
        for value in values:
            if value is None:
                continue
            if isinstance(value, str):
                cleaned = value.strip()
                if cleaned:
                    return cleaned
                continue
            if isinstance(value, list):
                if value:
                    return value
                continue
            return value
        return None

    def _normalize_list(self, *sources: Any) -> List[str]:
        seen: set[str] = set()
        values: List[str] = []

        def push(raw_value: Any) -> None:
            if raw_value is None:
                return
            value = str(raw_value).strip()
            if not value:
                return
            key = value.lower()
            if key in seen:
                return
            seen.add(key)
            values.append(value)

        for source in sources:
            if isinstance(source, list):
                for item in source:
                    push(item)
            elif isinstance(source, str):
                for item in source.split(","):
                    push(item)

        return values

    def _coerce_int(self, value: Any) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(float(value))
        except Exception:
            digits = re.sub(r"[^0-9.]", "", str(value))
            if not digits:
                return None
            try:
                return int(float(digits))
            except Exception:
                return None

    def _coerce_float(self, value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except Exception:
            digits = re.sub(r"[^0-9.]", "", str(value))
            if not digits:
                return None
            try:
                return float(digits)
            except Exception:
                return None

    def _strip_html(self, value: Any) -> str | None:
        if value is None:
            return None
        text = re.sub(r"<[^>]+>", " ", str(value))
        text = re.sub(r"\s+", " ", text).strip()
        return text or None

    def _build_price_note(self, listing_type: Any) -> str:
        value = str(listing_type or "").strip().lower()
        if any(token in value for token in ("alquiler", "renta", "rent")):
            return "Precio de alquiler"
        if any(token in value for token in ("venta", "sale")):
            return "Precio de venta"
        return "Precio publicado"

    def _humanize_badge(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        normalized = re.sub(r"\s+", " ", text.replace("_", " ")).strip()
        normalized_lower = normalized.lower()
        if normalized_lower == "default" or normalized_lower.startswith("default "):
            return None
        return normalized.title()

    def _normalize_agent_name(self, *candidates: Any) -> str:
        for candidate in candidates:
            if candidate is None:
                continue
            text = re.sub(r"\s+", " ", str(candidate).strip())
            if not text:
                continue
            lowered = text.lower()
            if lowered == "default" or lowered.startswith("default "):
                continue
            return text
        return ""

    def _build_badges(self, features: Dict[str, Any], payload: Dict[str, Any] | None = None) -> tuple[str | None, str | None]:
        source = payload or {}
        badge_main = self._humanize_badge(
            self._first_non_empty(source.get("badge_main"), features.get("badge_main"))
        )
        if not badge_main and (features.get("is_featured") or source.get("is_featured")):
            badge_main = "Destacada"

        badge_sub = self._humanize_badge(
            self._first_non_empty(
                source.get("badge_sub"),
                features.get("badge_sub"),
                features.get("listing_type"),
                features.get("property_type"),
            )
        )
        return badge_main, badge_sub

    def _map_property_data_to_card(self, prop_data: Dict[str, Any]) -> Union[PropertyCard, None]:
        try:
            title = (prop_data.get("title") or "Propiedad Sugerida").replace("&#8211;", "-")
            features = prop_data.get("features") if isinstance(prop_data.get("features"), dict) else {}
            location = self._first_non_empty(
                features.get("address"),
                f"{prop_data.get('address_city', '')}, {prop_data.get('address_state', '')}".strip(", "),
            )
            images = [str(url).strip() for url in (prop_data.get("images") or []) if str(url).strip()]
            amenities = self._normalize_list(features.get("amenities"))
            tags = self._normalize_list(features.get("highlights"), amenities)
            description = self._strip_html(prop_data.get("description") or features.get("description"))
            bedrooms_clean = self._coerce_int(self._first_non_empty(features.get("bedrooms_clean"), features.get("bedrooms"), prop_data.get("bedrooms")))
            bathrooms_clean = self._coerce_float(self._first_non_empty(features.get("bathrooms_clean"), features.get("bathrooms"), prop_data.get("bathrooms")))
            sqm_clean = self._coerce_int(self._first_non_empty(features.get("sqm_clean"), prop_data.get("area_sqm")))
            garage_clean = self._coerce_int(self._first_non_empty(features.get("garage_clean"), features.get("garage")))
            badge_main, badge_sub = self._build_badges(features)
            price_note = self._build_price_note(features.get("listing_type"))
            feature_payload = dict(features)
            if location:
                feature_payload.setdefault("address", location)
            if bedrooms_clean is not None:
                feature_payload["bedrooms_clean"] = bedrooms_clean
            if bathrooms_clean is not None:
                feature_payload["bathrooms_clean"] = bathrooms_clean
            if sqm_clean is not None:
                feature_payload["sqm_clean"] = sqm_clean
            if garage_clean is not None:
                feature_payload["garage_clean"] = garage_clean
            if amenities:
                feature_payload["amenities"] = amenities
            if description:
                feature_payload.setdefault("description", description)
            return PropertyCard(
                id=str(prop_data.get("id")),
                title=title,
                price=float(prop_data.get("price", 0) or 0),
                currency=str(prop_data.get("currency_id") or "USD"),
                price_note=price_note,
                location=location,
                image_url=images[0] if images else None,
                image_urls=images,
                photo_count=len(images),
                public_url=prop_data.get("public_url"),
                features=feature_payload,
                tags=tags[:8],
                amenities=amenities[:8],
                description=description,
                badge_main=badge_main,
                badge_sub=badge_sub,
                bedrooms_clean=bedrooms_clean,
                bathrooms_clean=bathrooms_clean,
                sqm_clean=sqm_clean,
                garage_clean=garage_clean,
            )
        except Exception as e:
            logger.warning(f"Error mapeando data de DB a PropertyCard: {e}")
            return None

    def _map_agent_core_property_card(self, payload: Dict[str, Any]) -> Union[PropertyCard, None]:
        try:
            title = str(payload.get("title") or "Propiedad sugerida").replace("&#8211;", "-")
            property_id = str(payload.get("id") or "").strip()
            features = payload.get("features") if isinstance(payload.get("features"), dict) else {}
            location = self._first_non_empty(
                payload.get("location"),
                payload.get("neighborhood"),
                payload.get("city"),
                features.get("address"),
                features.get("province"),
            )
            rooms = self._first_non_empty(payload.get("rooms"), features.get("bedrooms"))
            area_display = self._first_non_empty(payload.get("area_display"), features.get("area_display"))
            image_urls = [
                str(url).strip()
                for url in (payload.get("image_urls") or [])
                if str(url).strip()
            ]
            image_url = self._first_non_empty(payload.get("image_url"), image_urls[0] if image_urls else None)
            if image_url and not image_urls:
                image_urls = [image_url]
            amenities = self._normalize_list(payload.get("amenities"), features.get("amenities"))
            tags = self._normalize_list(payload.get("tags"), payload.get("amenities"), features.get("highlights"), amenities)
            if rooms:
                tags = self._normalize_list(tags, [f"{rooms} hab"])
            if area_display:
                tags = self._normalize_list(tags, [area_display])
            bedrooms_clean = self._coerce_int(self._first_non_empty(payload.get("bedrooms_clean"), features.get("bedrooms_clean"), rooms))
            bathrooms_clean = self._coerce_float(self._first_non_empty(payload.get("bathrooms_clean"), features.get("bathrooms_clean"), payload.get("bathrooms"), features.get("bathrooms")))
            sqm_clean = self._coerce_int(self._first_non_empty(payload.get("sqm_clean"), features.get("sqm_clean"), area_display))
            garage_clean = self._coerce_int(self._first_non_empty(payload.get("garage_clean"), features.get("garage_clean"), payload.get("garage"), features.get("garage")))
            description = self._strip_html(
                self._first_non_empty(
                    payload.get("description"),
                    payload.get("description_html"),
                    features.get("description"),
                )
            )
            badge_main, badge_sub = self._build_badges(features, payload)
            price_note = self._first_non_empty(
                payload.get("price_note"),
                features.get("price_note"),
            ) or self._build_price_note(self._first_non_empty(payload.get("listing_type"), features.get("listing_type")))
            feature_payload = dict(features)
            if location:
                feature_payload.setdefault("address", location)
            if area_display:
                feature_payload.setdefault("area_display", area_display)
            if bedrooms_clean is not None:
                feature_payload["bedrooms_clean"] = bedrooms_clean
            if bathrooms_clean is not None:
                feature_payload["bathrooms_clean"] = bathrooms_clean
            if sqm_clean is not None:
                feature_payload["sqm_clean"] = sqm_clean
            if garage_clean is not None:
                feature_payload["garage_clean"] = garage_clean
            if amenities:
                feature_payload["amenities"] = amenities
            if description:
                feature_payload.setdefault("description", description)
            return PropertyCard(
                id=property_id or None,
                title=title,
                price=self._parse_price_value(payload),
                currency=str(payload.get("currency") or "USD"),
                price_note=price_note,
                location=location or None,
                image_url=image_url,
                image_urls=image_urls,
                photo_count=self._coerce_int(payload.get("photo_count")) or len(image_urls),
                public_url=payload.get("cta_url") or payload.get("public_url"),
                features=feature_payload,
                tags=tags[:8],
                amenities=amenities[:8],
                description=description,
                badge_main=badge_main,
                badge_sub=badge_sub,
                bedrooms_clean=bedrooms_clean,
                bathrooms_clean=bathrooms_clean,
                sqm_clean=sqm_clean,
                garage_clean=garage_clean,
            )
        except Exception as exc:
            logger.warning("Error mapping canonical property card: %s", exc)
            return None

    def _parse_price_value(self, payload: Dict[str, Any]) -> float:
        value = payload.get("price")
        if value is not None:
            try:
                return float(value)
            except Exception:
                pass
        display = str(payload.get("price_display") or "")
        numeric = re.sub(r"[^0-9.]", "", display)
        if not numeric:
            return 0.0
        try:
            return float(numeric)
        except Exception:
            return 0.0
