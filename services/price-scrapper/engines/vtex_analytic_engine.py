#!/usr/bin/env python3
"""Engine analítico VTEX para verificar productos puntuales por tienda."""

from __future__ import annotations

import base64
import json
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from etl.http_client import BrowserSession, create_browser_session, request_with_retry


REQUEST_TIMEOUT = 30
PRODUCT_LD_JSON_PATTERN = re.compile(
    r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class VtexAnalyticTarget:
    product_key: int
    product_role: str
    gtin_raw: str | None
    brand_name: str | None
    product_name: str
    content_quantity: str | None
    content_unit: str | None
    listing_key: int
    source_product_id: str
    source_sku: str
    seller_id: str
    seller_name: str | None
    listing_name: str
    product_url: str
    image_url: str | None
    root_category_slug: str | None
    root_category_name: str | None


@dataclass(frozen=True)
class VtexAnalyticLocation:
    location_key: int
    location_name: str
    sales_channel: str
    region_id: str


@dataclass(frozen=True)
class VtexAnalyticChainConfig:
    chain_id: str
    display_name: str
    catalog_id: str
    base_url: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class VtexAnalyticScraper:
    def __init__(
        self,
        *,
        chain: VtexAnalyticChainConfig,
        location: VtexAnalyticLocation,
        sleep_min: float = 1.25,
        sleep_max: float = 3.00,
    ) -> None:
        self.chain = chain
        self.location = location
        self.sleep_min = sleep_min
        self.sleep_max = sleep_max
        self.started_at = utc_now_iso()
        self.started_monotonic = time.monotonic()
        self.request_counter = 0
        self.session = self._build_session()

    def _build_session(self) -> BrowserSession:
        session = create_browser_session(
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "es-CR,es;q=0.9,en;q=0.8",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Referer": f"{self.chain.base_url}/",
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
                ),
            }
        )
        segment_payload = {
            "campaigns": None,
            "channel": self.location.sales_channel,
            "priceTables": None,
            "regionId": self.location.region_id,
            "utm_campaign": None,
            "utm_source": None,
            "utmi_campaign": None,
            "currencyCode": "CRC",
            "currencySymbol": "₡",
            "countryCode": "CRI",
            "cultureInfo": "es-CR",
            "channelPrivacy": "public",
        }
        segment_b64 = base64.b64encode(
            json.dumps(segment_payload, separators=(",", ":")).encode("utf-8")
        ).decode("ascii")
        session.cookies.set("vtex_segment", segment_b64, domain=self.chain.base_url.removeprefix("https://"))
        return session

    def _sleep_if_needed(self) -> None:
        if self.request_counter <= 0:
            return
        time.sleep(random.uniform(self.sleep_min, self.sleep_max))

    def fetch_html(self, url: str) -> str:
        self._sleep_if_needed()
        response = request_with_retry(
            self.session,
            "GET",
            url,
            timeout=REQUEST_TIMEOUT,
        )
        self.request_counter += 1
        response.raise_for_status()
        return response.text

    def extract_product_ld_json(self, html: str) -> dict[str, Any]:
        for script_text in PRODUCT_LD_JSON_PATTERN.findall(html):
            try:
                payload = json.loads(script_text)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and payload.get("@type") == "Product":
                return payload
        raise RuntimeError("No se pudo encontrar Product JSON-LD en el PDP VTEX.")

    @staticmethod
    def derive_offer_payload(product_ld: dict[str, Any]) -> dict[str, Any]:
        offers = product_ld.get("offers") or {}
        if not isinstance(offers, dict):
            raise RuntimeError("El PDP VTEX no devolvió un bloque offers válido.")
        nested_offers = offers.get("offers") or []
        first_offer = nested_offers[0] if nested_offers else {}
        if not isinstance(first_offer, dict):
            first_offer = {}
        low_price = offers.get("lowPrice")
        price = first_offer.get("price", low_price)
        list_price = first_offer.get("priceSpecification", {}).get("price") if isinstance(first_offer.get("priceSpecification"), dict) else None
        availability = str(first_offer.get("availability") or "")
        is_in_stock = availability.endswith("/InStock")
        return {
            "currency": first_offer.get("priceCurrency") or offers.get("priceCurrency") or "CRC",
            "price": price,
            "list_price": list_price if list_price not in ("", None) else price,
            "price_without_discount": list_price if list_price not in ("", None) else price,
            "spot_price": None,
            "has_discount": (
                price is not None
                and list_price not in ("", None)
                and float(list_price) > float(price)
            ) if price is not None else False,
            "price_valid_until": first_offer.get("priceValidUntil"),
            "available_quantity": 1 if is_in_stock else 0,
            "availability_schema": availability,
            "seller_name_observed": ((first_offer.get("seller") or {}).get("name")),
        }

    def build_record(self, target: VtexAnalyticTarget, observed: dict[str, Any]) -> dict[str, Any]:
        return {
            "catalog_id": self.chain.catalog_id,
            "pricing_scope": "physical_store_online",
            "identity": {
                "product_id": target.source_product_id,
                "sku": target.source_sku,
                "ean": target.gtin_raw,
                "product_reference": None,
                "reference_id": None,
                "brand": target.brand_name,
                "brand_id": None,
                "seller_id": target.seller_id,
                "seller_name": target.seller_name or observed.get("seller_name_observed"),
            },
            "taxonomy": {
                "root_categories": [
                    {
                        "slug": target.root_category_slug,
                        "name": target.root_category_name,
                    }
                ] if target.root_category_slug or target.root_category_name else [],
                "category_id": None,
                "category_path": None,
                "raw_categories": [],
            },
            "content": {
                "name": target.listing_name or target.product_name,
                "description": None,
                "link": target.product_url,
                "image": target.image_url,
                "link_text": None,
            },
            "measurement": {
                "quantity": target.content_quantity,
                "unit": target.content_unit,
                "measurement_unit": None,
                "unit_multiplier": None,
            },
            "pricing": {
                "currency": observed.get("currency"),
                "price": observed.get("price"),
                "list_price": observed.get("list_price"),
                "price_without_discount": observed.get("price_without_discount"),
                "spot_price": observed.get("spot_price"),
                "has_discount": observed.get("has_discount", False),
                "price_valid_until": observed.get("price_valid_until"),
            },
            "availability": {
                "available_quantity": observed.get("available_quantity"),
            },
            "raw_debug": {
                "availability_schema": observed.get("availability_schema"),
                "location_key": self.location.location_key,
                "location_name": self.location.location_name,
                "sales_channel": self.location.sales_channel,
                "region_id": self.location.region_id,
                "availability_signal_kind": "binary_pdp_offer",
            },
        }

    def collect_records(self, targets: list[VtexAnalyticTarget]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        records: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        for target in targets:
            try:
                html = self.fetch_html(target.product_url)
                product_ld = self.extract_product_ld_json(html)
                observed = self.derive_offer_payload(product_ld)
                records.append(self.build_record(target, observed))
            except Exception as exc:
                errors.append(
                    {
                        "listing_key": target.listing_key,
                        "product_key": target.product_key,
                        "product_name": target.product_name,
                        "error": str(exc),
                    }
                )

        finished_at = utc_now_iso()
        metadata = {
            "engine": "vtex",
            "chain_id": self.chain.chain_id,
            "catalog_id": self.chain.catalog_id,
            "pricing_scope": "physical_store_online",
            "started_at": self.started_at,
            "finished_at": finished_at,
            "generated_at": finished_at,
            "elapsed_seconds": round(time.monotonic() - self.started_monotonic, 3),
            "catalog_records": len(records),
            "unique_products": len(records),
            "duplicates_skipped": 0,
            "location_key": self.location.location_key,
            "location_name": self.location.location_name,
            "campaign_record_errors": errors,
            "campaign_record_total_requested": len(targets),
            "campaign_record_total_succeeded": len(records),
            "campaign_record_total_failed": len(errors),
        }
        return records, metadata
