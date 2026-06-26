#!/usr/bin/env python3
"""Engine analítico Instaleap para verificar productos puntuales por tienda."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from etl.http_client import BrowserSession, create_browser_session, request_with_retry, set_rate_limiter


REQUEST_TIMEOUT = 30
GET_PRODUCTS_BY_SKU_QUERY = """
query GetProductsBySKU($getProductsBySKUInput: GetProductsBySKUInput!) {
  getProductsBySKU(getProductsBySKUInput: $getProductsBySKUInput) {
    name
    sku
    ean
    brand
    description
    price
    previousPrice
    promotionPricePerSubUnit
    pricePerSubUnit
    unit
    subUnit
    subQty
    maxQty
    minQty
    stock
    isActive
    isAvailable
    slug
    photosUrl
    boost
    location
    hasAgeRestriction
    type
    promotion {
      description
      type
      isActive
    }
    promotions {
      type
      description
      isActive
    }
  }
}
""".strip()


@dataclass(frozen=True)
class InstaleapAnalyticTarget:
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
class InstaleapAnalyticLocation:
    location_key: int
    location_name: str
    store_reference: str
    store_id: str | None


@dataclass(frozen=True)
class InstaleapAnalyticChainConfig:
    chain_id: str
    display_name: str
    catalog_id: str
    base_url: str
    client_id: str
    graphql_endpoint: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_number(value: Any) -> int | float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return int(number) if number.is_integer() else round(number, 4)


def first_non_empty(values: Any) -> str | None:
    if values is None:
        return None
    if isinstance(values, list):
        for value in values:
            text = normalize_string(value)
            if text:
                return text
        return None
    return normalize_string(values)


class InstaleapAnalyticScraper:
    def __init__(
        self,
        *,
        chain: InstaleapAnalyticChainConfig,
        location: InstaleapAnalyticLocation,
        sleep_min: float = 0.0,
        sleep_max: float = 0.0,
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
        domain = self.chain.graphql_endpoint.removeprefix("https://").removeprefix("http://").split("/")[0]
        set_rate_limiter(domain)
        return create_browser_session(
            headers={
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "es-CR,es;q=0.9,en;q=0.8",
                "Cache-Control": "no-cache",
                "Content-Type": "application/json",
                "Origin": self.chain.base_url,
                "Referer": f"{self.chain.base_url}/",
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
                ),
            }
        )

    def _sleep_if_needed(self) -> None:
        return

    def fetch_products_by_skus(self, skus: list[str]) -> list[dict[str, Any]]:
        payload = {
            "operationName": "GetProductsBySKU",
            "query": GET_PRODUCTS_BY_SKU_QUERY,
            "variables": {
                "getProductsBySKUInput": {
                    "clientId": self.chain.client_id,
                    "storeReference": self.location.store_reference,
                    "skus": skus,
                }
            },
        }
        self._sleep_if_needed()
        response = request_with_retry(
            self.session,
            "GET",
            self.chain.graphql_endpoint,
            timeout=REQUEST_TIMEOUT,
            verify=False,
            params={
                "operationName": payload["operationName"],
                "query": payload["query"],
                "variables": json.dumps(payload["variables"], separators=(",", ":")),
            },
        )
        self.request_counter += 1
        response.raise_for_status()
        data = response.json()
        if data.get("errors"):
            raise RuntimeError(
                "Instaleap GetProductsBySKU devolvió errores: "
                + json.dumps(data["errors"], ensure_ascii=False)[:1200]
            )
        products = (data.get("data") or {}).get("getProductsBySKU") or []
        if not isinstance(products, list):
            raise RuntimeError("Respuesta inválida de Instaleap: getProductsBySKU no es lista.")
        return products

    def build_record(
        self,
        target: InstaleapAnalyticTarget,
        observed: dict[str, Any],
    ) -> dict[str, Any]:
        price = normalize_number(observed.get("price"))
        previous_price = normalize_number(observed.get("previousPrice"))
        promotion_price_per_sub = normalize_number(observed.get("promotionPricePerSubUnit"))
        price_per_sub = normalize_number(observed.get("pricePerSubUnit"))
        stock = normalize_number(observed.get("stock"))
        sub_qty = normalize_number(observed.get("subQty"))
        has_discount = bool(
            previous_price is not None
            and price is not None
            and float(previous_price) > float(price)
        )
        product_url = target.product_url
        slug = normalize_string(observed.get("slug"))
        if not product_url and slug:
            product_url = f"{self.chain.base_url}/p/{slug.lstrip('/')}"

        return {
            "catalog_id": self.chain.catalog_id,
            "pricing_scope": "physical_store_online",
            "identity": {
                "product_id": target.source_product_id,
                "sku": normalize_string(observed.get("sku")) or target.source_sku,
                "ean": first_non_empty(observed.get("ean")) or target.gtin_raw,
                "product_reference": None,
                "reference_id": None,
                "brand": normalize_string(observed.get("brand")) or target.brand_name,
                "brand_id": None,
                "seller_id": self.location.store_reference,
                "seller_name": self.location.location_name,
            },
            "taxonomy": {
                "root_categories": [
                    {
                        "slug": target.root_category_slug,
                        "name": target.root_category_name,
                    }
                ]
                if target.root_category_slug or target.root_category_name
                else [],
                "category_id": None,
                "category_path": None,
                "raw_categories": [],
            },
            "content": {
                "name": target.listing_name or normalize_string(observed.get("name")) or target.product_name,
                "description": normalize_string(observed.get("description")),
                "link": product_url,
                "image": first_non_empty(observed.get("photosUrl")) or target.image_url,
                "link_text": None,
            },
            "measurement": {
                "quantity": target.content_quantity or sub_qty,
                "unit": target.content_unit or normalize_string(observed.get("subUnit")) or normalize_string(observed.get("unit")),
                "measurement_unit": normalize_string(observed.get("unit")),
                "unit_multiplier": sub_qty,
            },
            "pricing": {
                "currency": "CRC",
                "price": price,
                "list_price": previous_price if previous_price is not None else price,
                "price_without_discount": previous_price if previous_price is not None else price,
                "spot_price": promotion_price_per_sub or price_per_sub,
                "has_discount": has_discount,
                "price_valid_until": None,
            },
            "availability": {
                "available_quantity": stock,
            },
            "raw_debug": {
                "location_key": self.location.location_key,
                "location_name": self.location.location_name,
                "store_reference": self.location.store_reference,
                "store_id": self.location.store_id,
                "is_active": observed.get("isActive"),
                "is_available": observed.get("isAvailable"),
                "stock_signal_kind": "instaleap_store_stock",
            },
        }

    def collect_records(self, targets: list[InstaleapAnalyticTarget]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        records: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        targets_by_sku: dict[str, InstaleapAnalyticTarget] = {}
        for target in targets:
            sku = normalize_string(target.source_sku)
            if sku and sku not in targets_by_sku:
                targets_by_sku[sku] = target

        if not targets_by_sku:
            raise RuntimeError("No hay SKUs válidos para consultar en Instaleap.")

        observed_products = self.fetch_products_by_skus(list(targets_by_sku))
        observed_by_sku = {
            normalize_string(product.get("sku")): product
            for product in observed_products
            if normalize_string(product.get("sku"))
        }

        for sku, target in targets_by_sku.items():
            observed = observed_by_sku.get(sku)
            if not observed:
                errors.append(
                    {
                        "listing_key": target.listing_key,
                        "product_key": target.product_key,
                        "product_name": target.product_name,
                        "sku": sku,
                        "error": "SKU no devuelto por GetProductsBySKU para esta tienda.",
                    }
                )
                continue
            try:
                records.append(self.build_record(target, observed))
            except Exception as exc:
                errors.append(
                    {
                        "listing_key": target.listing_key,
                        "product_key": target.product_key,
                        "product_name": target.product_name,
                        "sku": sku,
                        "error": str(exc),
                    }
                )

        finished_at = utc_now_iso()
        metadata = {
            "engine": "instaleap",
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
