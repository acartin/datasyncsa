from __future__ import annotations

from app.core.config import settings
from app.models.contracts import (
    CardModel,
    PropertyCard,
    PropertyListing,
    RAGSourceCard,
    SearchSummaryCard,
    ToolResult,
)
from app.runtime.runtime_registry import get_card_registry_config


def card_renderer(tool_results: list[ToolResult], vertical: str) -> list[CardModel]:
    cards: list[CardModel] = []
    try:
        card_registry = get_card_registry_config()
    except Exception:
        return cards

    vertical_key = vertical.lower().strip() if vertical else "generic"
    vertical_config = card_registry.verticals.get(vertical_key) or card_registry.verticals.get("generic")
    if vertical_config is None:
        return cards

    allowed_cards = {name for name in vertical_config.allowed_cards if name in card_registry.cards}

    for tr in tool_results:
        if tr.status != "ok":
            continue
        if "search_summary" in allowed_cards and tr.realtor and tr.realtor.listings:
            listings = tr.realtor.listings
            cards.append(
                SearchSummaryCard(
                    total_found=tr.realtor.total_found,
                    city=tr.realtor.slots_used.city or "Todas",
                    price_range=_build_price_range(listings),
                )
            )
        if "property_card_expanded" in allowed_cards and tr.realtor and tr.realtor.listings:
            listings = tr.realtor.listings
            max_cards = max(0, int(settings.realtor_property_card_limit))
            for listing in listings[:max_cards]:
                cards.append(_render_property_card(listing))
        if "rag_source" in allowed_cards and tr.rag and tr.rag.chunks:
            for chunk in tr.rag.chunks:
                cards.append(
                    RAGSourceCard(
                        doc_id=chunk.doc_id,
                        title=f"Documento {chunk.doc_id[:8]}",
                        excerpt=chunk.content[:180],
                        source_url=chunk.source_url,
                    )
                )

    return cards


def _render_property_card(listing: PropertyListing) -> PropertyCard:
    price = listing.price
    currency = listing.currency or "USD"
    room_label = listing.rooms
    area_label = f"{listing.area_m2:.1f} m²" if listing.area_m2 is not None else None

    return PropertyCard(
        listing_id=listing.listing_id,
        title=listing.title,
        price_display=f"{currency} {price:,.0f}",
        rooms=room_label,
        area_display=area_label,
        neighborhood=listing.neighborhood,
        image_url=(listing.image_urls[0] if listing.image_urls else None),
        cta_url=listing.listing_url,
    )


def _build_price_range(listings: list[PropertyListing]) -> str | None:
    if not listings:
        return None
    prices = [listing.price for listing in listings if listing.price]
    if not prices:
        return None
    if len(prices) == 1:
        return f"{_currency(listings[0])} {prices[0]:,.0f}"
    return f"{min(prices):,d} – {max(prices):,d} ({_currency(listings[0])})"


def _currency(listing: PropertyListing) -> str:
    return listing.currency or "USD"
