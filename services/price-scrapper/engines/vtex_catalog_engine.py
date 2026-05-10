#!/usr/bin/env python3
"""Motor VTEX configurable para extraer catalogos por cadena y categorias raiz."""

from __future__ import annotations

import argparse
import base64
import json
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from etl.chain_runtime_db import load_catalog_runtime_payload
from etl.http_client import BrowserResponse, BrowserSession, create_browser_session, request_with_retry
from etl.normalize import normalize_ean
from etl.postgres_cli import parse_env


REQUEST_TIMEOUT = 30
PAGE_STEP = 20
SAFE_PAGE_FROM_LIMIT = 1020
MAX_ACCESSIBLE_RECORDS_PER_QUERY = SAFE_PAGE_FROM_LIMIT + PAGE_STEP + 1
CANONICAL_SCHEMA_VERSION = "canonical_product_v1"
CATALOG_METADATA_SCHEMA_VERSION = "catalog_metadata_v1"

PERSISTED_QUERY = {
    "version": 1,
    "sha256Hash": "31d3fa494df1fc41efef6d16dd96a96e6911b8aed7a037868699a1f3f4d365de",
    "sender": "vtex.store-resources@0.x",
    "provider": "vtex.search-graphql@0.x",
}

BASE_VARIABLES = {
    "hideUnavailableItems": False,
    "skusFilter": "ALL",
    "simulationBehavior": "default",
    "installmentCriteria": "MAX_WITHOUT_INTEREST",
    "productOriginVtex": False,
    "orderBy": "OrderByScoreDESC",
    "operator": "and",
    "fuzzy": "0",
    "searchState": None,
    "facetsBehavior": "Static",
    "categoryTreeBehavior": "default",
    "withFacets": False,
    "variant": "null-null",
}

UNIT_ALIASES = {
    "g": "g",
    "gr": "g",
    "kg": "kg",
    "mg": "mg",
    "ml": "ml",
    "cc": "ml",
    "cl": "cl",
    "l": "l",
    "lt": "l",
    "lts": "l",
    "oz": "oz",
    "lb": "lb",
    "un": "un",
    "und": "un",
    "uds": "un",
    "ud": "un",
    "pz": "un",
    "u": "un",
}

MEASURE_PATTERN = re.compile(
    r"(?P<quantity>\d+(?:[.,]\d+)?)\s*(?P<unit>kg|gr|g|mg|ml|cc|cl|lt|lts|l|oz|lb|und|uds|ud|un|pz|u)\b",
    re.IGNORECASE,
)
MULTIPACK_PATTERN = re.compile(
    r"(?P<count>\d+)\s*[xX]\s*(?P<quantity>\d+(?:[.,]\d+)?)\s*(?P<unit>kg|gr|g|mg|ml|cc|cl|lt|lts|l|oz|lb|und|uds|ud|un|pz|u)\b",
    re.IGNORECASE,
)
RELEVANT_PROPERTY_KEYWORDS = (
    "gramaje",
    "volumen",
    "peso",
    "neto",
    "contenido",
    "unidades",
    "unidad",
)


@dataclass(frozen=True)
class VTEXStoreConfig:
    store: str
    base_url: str
    display_name: str | None = None
    short_label: str | None = None
    catalog_id: str | None = None
    pricing_scope: str = "chain_public_online"
    pricing_context: dict[str, Any] | None = None
    sales_channel: str | None = None
    region_id: str | None = None

    @property
    def graphql_endpoint(self) -> str:
        return f"{self.base_url}/_v/segment/graphql/v1"

    @property
    def category_tree_endpoint(self) -> str:
        return f"{self.base_url}/api/catalog_system/pub/category/tree/{{depth}}"

    @property
    def resolved_display_name(self) -> str:
        return self.display_name or self.store

    @property
    def resolved_short_label(self) -> str:
        return self.short_label or self.resolved_display_name

    @property
    def resolved_catalog_id(self) -> str:
        return self.catalog_id or self.store

    @property
    def resolved_pricing_context(self) -> dict[str, Any]:
        return dict(self.pricing_context or {})


@dataclass(frozen=True)
class RootCategorySelection:
    name: str
    slug: str
    url: str
    enabled: bool = True


@dataclass
class PlannedCategory:
    root_category: RootCategorySelection
    name: str
    url: str
    segments: list[str]
    records_filtered: int
    depth: int
    has_children: bool
    overflow: bool = False


@dataclass(frozen=True)
class StoreRuntimeContext:
    config: VTEXStoreConfig
    root_categories: list[RootCategorySelection]
    default_output_dir: Path


def resolve_output_dir_from_payload(payload: dict[str, Any]) -> Path:
    raw_value = payload.get("default_output_dir")
    if raw_value:
        output_dir = Path(str(raw_value))
        if output_dir.is_absolute():
            return output_dir
        return Path(__file__).resolve().parents[1] / output_dir
    chain_id = str(payload.get("chain_id") or "").strip()
    if not chain_id:
        raise ValueError("No fue posible resolver output_dir: falta chain_id en payload.")
    return Path(__file__).resolve().parents[1] / "output" / "chains" / chain_id


def compact_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def encode_json_base64(payload: dict[str, Any]) -> str:
    return base64.b64encode(compact_json(payload).encode("utf-8")).decode("ascii")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_number(value: Any) -> int | float | None:
    if value is None or value == "":
        return None
    number = float(value)
    return int(number) if number.is_integer() else round(number, 4)


def normalize_unit(value: str | None) -> str | None:
    if not value:
        return None
    return UNIT_ALIASES.get(value.strip().lower(), value.strip().lower())


def normalize_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def to_float(value: str) -> float:
    return float(value.replace(",", "."))


def extract_measure_from_text(text: str | None) -> tuple[int | float | None, str | None]:
    if not text:
        return None, None

    multipack_match = MULTIPACK_PATTERN.search(text)
    if multipack_match:
        count = int(multipack_match.group("count"))
        quantity = to_float(multipack_match.group("quantity"))
        unit = normalize_unit(multipack_match.group("unit"))
        return normalize_number(count * quantity), unit

    matches = list(MEASURE_PATTERN.finditer(text))
    if matches:
        last_match = matches[-1]
        quantity = normalize_number(to_float(last_match.group("quantity")))
        unit = normalize_unit(last_match.group("unit"))
        return quantity, unit

    return None, None


def extract_measure_from_properties(properties: list[dict[str, Any]] | None) -> tuple[int | float | None, str | None]:
    for prop in properties or []:
        name = (prop.get("name") or "").strip().lower()
        values = prop.get("values") or []
        if not values:
            continue

        if "total unidades por producto" in name:
            numeric_value = re.search(r"\d+(?:[.,]\d+)?", str(values[0]))
            if numeric_value:
                return normalize_number(to_float(numeric_value.group(0))), "un"

        if not any(keyword in name for keyword in RELEVANT_PROPERTY_KEYWORDS):
            continue

        for value in values:
            quantity, unit = extract_measure_from_text(str(value))
            if quantity is not None and unit is not None:
                return quantity, unit

    return None, None


def normalize_category_path(categories: list[str] | None, fallback_name: str) -> str:
    if not categories:
        return fallback_name
    parts = [part.strip() for part in categories[0].strip("/").split("/") if part.strip()]
    return " > ".join(parts) if parts else fallback_name


def absolute_product_link(base_url: str, link: str | None) -> str | None:
    if not link:
        return None
    if link.startswith("http://") or link.startswith("https://"):
        return link
    return f"{base_url}{link}"


def preferred_seller(item: dict[str, Any]) -> dict[str, Any] | None:
    sellers = item.get("sellers") or []
    for seller in sellers:
        if seller.get("sellerDefault"):
            return seller
    return sellers[0] if sellers else None


def infer_quantity_and_unit(product: dict[str, Any], item: dict[str, Any]) -> tuple[int | float | None, str | None]:
    quantity, unit = extract_measure_from_properties(product.get("properties"))
    if quantity is not None and unit is not None:
        return quantity, unit

    text_candidates = [
        item.get("nameComplete"),
        item.get("name"),
        product.get("productName"),
        product.get("description"),
    ]
    for candidate in text_candidates:
        quantity, unit = extract_measure_from_text(candidate)
        if quantity is not None and unit is not None:
            return quantity, unit

    measurement_unit = normalize_unit(item.get("measurementUnit"))
    unit_multiplier = normalize_number(item.get("unitMultiplier"))
    if measurement_unit and unit_multiplier is not None:
        return unit_multiplier, measurement_unit

    return 1, "un"


def first_reference_id(item: dict[str, Any]) -> str | None:
    references = item.get("referenceId")
    if isinstance(references, list):
        for reference in references:
            if not isinstance(reference, dict):
                continue
            value = normalize_string(reference.get("Value") or reference.get("value"))
            if value:
                return value
    if isinstance(references, dict):
        return normalize_string(references.get("Value") or references.get("value"))
    return None


def has_discount(price: int | float | None, *candidates: int | float | None) -> bool:
    if price is None:
        return False
    return any(candidate is not None and candidate > price for candidate in candidates)


def canonical_product_record(
    config: VTEXStoreConfig,
    category: PlannedCategory,
    product: dict[str, Any],
    item: dict[str, Any],
) -> dict[str, Any]:
    seller = preferred_seller(item)
    offer = seller.get("commertialOffer") if seller else {}
    quantity, unit = infer_quantity_and_unit(product, item)
    measurement_unit = normalize_unit(item.get("measurementUnit"))
    unit_multiplier = normalize_number(item.get("unitMultiplier"))
    price = normalize_number(offer.get("Price"))
    list_price = normalize_number(offer.get("ListPrice"))
    price_without_discount = normalize_number(offer.get("PriceWithoutDiscount"))
    spot_price = normalize_number(offer.get("spotPrice"))
    available_quantity = normalize_number(offer.get("AvailableQuantity"))
    images = item.get("images") or []

    return {
        "schema_version": CANONICAL_SCHEMA_VERSION,
        "catalog_id": config.resolved_catalog_id,
        "pricing_scope": config.pricing_scope,
        "store": {
            "store_id": config.store,
            "display_name": config.resolved_display_name,
            "short_label": config.resolved_short_label,
            "base_url": config.base_url,
        },
        "identity": {
            "product_id": str(product.get("productId") or ""),
            "sku": str(item.get("itemId") or ""),
            "ean": normalize_ean(item.get("ean")),
            "product_reference": normalize_string(product.get("productReference")),
            "reference_id": first_reference_id(item),
            "brand": normalize_string(product.get("brand")),
            "brand_id": normalize_string(product.get("brandId")),
            "seller_id": normalize_string(seller.get("sellerId")) if seller else None,
            "seller_name": normalize_string(seller.get("sellerName")) if seller else None,
        },
        "taxonomy": {
            "category_path": normalize_category_path(product.get("categories"), category.root_category.name),
            "category_id": normalize_string(product.get("categoryId")),
            "root_categories": [
                {
                    "name": category.root_category.name,
                    "slug": category.root_category.slug,
                }
            ],
            "raw_categories": product.get("categories") or [],
        },
        "content": {
            "name": product.get("productName") or item.get("nameComplete") or item.get("name") or "",
            "description": normalize_string(product.get("description")),
            "link": absolute_product_link(config.base_url, product.get("link")),
            "link_text": normalize_string(product.get("linkText")),
            "image": images[0].get("imageUrl") if images else None,
        },
        "measurement": {
            "quantity": quantity,
            "unit": unit,
            "measurement_unit": measurement_unit,
            "unit_multiplier": unit_multiplier,
        },
        "pricing": {
            "currency": "CRC",
            "price": price,
            "list_price": list_price,
            "price_without_discount": price_without_discount,
            "spot_price": spot_price,
            "has_discount": has_discount(price, list_price, price_without_discount),
            "price_valid_until": normalize_string(offer.get("PriceValidUntil")),
        },
        "availability": {
            "available_quantity": available_quantity,
        },
        "attributes": {
            "properties": product.get("properties") or [],
            "specification_groups": product.get("specificationGroups") or [],
            "selected_properties": item.get("selectedProperties") or [],
            "variations": product.get("variations") or [],
            "cluster_highlights": product.get("clusterHighlights") or {},
            "product_clusters": product.get("productClusters") or {},
            "discount_highlights": offer.get("DiscountHighLight") or [],
            "teasers": offer.get("teasers") or [],
        },
    }


def category_segments_from_url(url: str) -> list[str]:
    path = urlparse(url).path.strip("/")
    return [segment for segment in path.split("/") if segment]


def root_slug_from_node(node: dict[str, Any]) -> str | None:
    url = node.get("url")
    if not url:
        return None
    segments = category_segments_from_url(url)
    return segments[0] if segments else None


def find_category_node_by_name(nodes: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    expected = name.strip().lower()
    for node in nodes:
        if (node.get("name") or "").strip().lower() == expected:
            return node
        found = find_category_node_by_name(node.get("children") or [], name)
        if found:
            return found
    return None


def load_chain_runtime_context(chain_id: str) -> StoreRuntimeContext:
    payload = load_catalog_runtime_payload(parse_env(), chain_id)
    return runtime_context_from_payload(payload)


def runtime_context_from_payload(payload: dict[str, Any]) -> StoreRuntimeContext:
    chain_id = str(payload.get("chain_id") or "").strip()
    categories_payload = payload.get("categories") or []
    base_url = str(payload.get("base_url") or "").strip()
    if not base_url:
        raise ValueError(f"La config/runtime de {chain_id!r} no define base_url.")

    root_categories = [
        RootCategorySelection(
            name=category.get("name") or str(category.get("slug") or ""),
            slug=str(category.get("slug") or "").strip(),
            url=category.get("url") or f"{base_url}/{category.get('slug')}",
            enabled=bool(category.get("enabled")),
        )
        for category in categories_payload
        if str(category.get("slug") or "").strip()
    ]

    extras = dict(payload.get("engine_extras") or {})
    sales_channel_raw = extras.get("sales_channel")
    sales_channel = str(sales_channel_raw) if sales_channel_raw is not None else None
    region_id_raw = extras.get("region_id")
    region_id = str(region_id_raw) if region_id_raw else None

    config = VTEXStoreConfig(
        store=chain_id,
        display_name=payload.get("display_name") or chain_id,
        short_label=payload.get("short_label") or payload.get("display_name") or chain_id,
        catalog_id=payload.get("catalog_id") or chain_id,
        base_url=base_url,
        pricing_scope=payload.get("pricing_scope") or "chain_public_online",
        pricing_context=payload.get("pricing_context") or {},
        sales_channel=sales_channel,
        region_id=region_id,
    )

    return StoreRuntimeContext(
        config=config,
        root_categories=root_categories,
        default_output_dir=resolve_output_dir_from_payload(payload),
    )


class VTEXCatalogScraper:
    def __init__(
        self,
        *,
        config: VTEXStoreConfig,
        root_categories: list[RootCategorySelection],
        output_dir: Path,
        page_step: int = PAGE_STEP,
        sleep_min: float = 1.25,
        sleep_max: float = 3.00,
        request_mode: str = "auto",
        category_tree_depth: int = 10,
        max_categories: int | None = None,
        max_pages_per_category: int | None = None,
        selected_root_slugs: list[str] | None = None,
    ) -> None:
        self.config = config
        self.root_categories = root_categories
        self.output_dir = output_dir
        self.page_step = page_step
        self.sleep_min = sleep_min
        self.sleep_max = sleep_max
        self.request_mode = request_mode
        self.category_tree_depth = category_tree_depth
        self.max_categories = max_categories
        self.max_pages_per_category = max_pages_per_category
        self.selected_root_slugs = [slug.strip() for slug in selected_root_slugs or [] if slug.strip()]
        self.started_at = utc_now_iso()
        self.started_monotonic = time.monotonic()
        self.session = self._build_session()
        self.request_counter = 0
        self.resolved_graphql_mode: str | None = None
        self.catalog: dict[str, dict[str, Any]] = {}
        self.duplicates = 0
        self.overflow_categories: list[dict[str, Any]] = []
        self.category_runs: list[dict[str, Any]] = []
        self.missing_root_categories: list[dict[str, Any]] = []

    def _build_session(self) -> BrowserSession:
        referer_slug = ""
        if self.root_categories:
            referer_slug = self.root_categories[0].slug

        referer = f"{self.config.base_url}/{referer_slug}" if referer_slug else self.config.base_url
        session = create_browser_session(
            headers={
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "es-CR,es;q=0.9,en;q=0.8",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Referer": referer,
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
                ),
            }
        )

        if self.config.sales_channel:
            segment_payload = {
                "campaigns": None,
                "channel": self.config.sales_channel,
                "priceTables": None,
                "regionId": self.config.region_id,
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
            cookie_domain = urlparse(self.config.base_url).netloc
            session.cookies.set("vtex_segment", segment_b64, domain=cookie_domain)
        return session

    def _sleep_if_needed(self) -> None:
        if self.request_counter <= 0:
            return
        time.sleep(random.uniform(self.sleep_min, self.sleep_max))

    def _get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        allow_http_error: bool = False,
    ) -> tuple[BrowserResponse, dict[str, Any]]:
        self._sleep_if_needed()
        response = request_with_retry(
            self.session,
            "GET",
            url,
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
        self.request_counter += 1
        if not allow_http_error:
            response.raise_for_status()
        return response, response.json()

    def _base_graphql_params(self, variables: dict[str, Any], mode: str) -> dict[str, str]:
        extensions = {"persistedQuery": PERSISTED_QUERY}
        if mode == "base64":
            variables_value = encode_json_base64(variables)
            extensions_value = encode_json_base64(extensions)
        else:
            variables_value = compact_json(variables)
            extensions_value = compact_json(extensions)

        params = {
            "workspace": "master",
            "maxAge": "short",
            "appsEtag": "remove",
            "domain": "store",
            "locale": "es-CR",
            "operationName": "productSearchV3",
            "variables": variables_value,
            "extensions": extensions_value,
        }
        if self.config.sales_channel:
            params["sc"] = self.config.sales_channel
        return params

    def _looks_like_base64_transport_error(self, payload: dict[str, Any]) -> bool:
        messages = " ".join(str(error.get("message", "")) for error in payload.get("errors") or [])
        return "Unexpected token" in messages and "not valid JSON" in messages

    def fetch_graphql_page(self, segments: list[str], from_index: int, to_index: int) -> dict[str, Any]:
        selected_facets: list[dict[str, Any]] = [{"key": "c", "value": value} for value in segments]
        if self.config.region_id:
            selected_facets.append({"key": "region-id", "value": self.config.region_id})

        variables = {
            **BASE_VARIABLES,
            "map": ",".join(["c"] * len(segments)),
            "query": "/".join(segments),
            "from": from_index,
            "to": to_index,
            "selectedFacets": selected_facets,
        }

        modes = [self.resolved_graphql_mode] if self.resolved_graphql_mode else []
        if not modes:
            if self.config.sales_channel:
                modes = ["json"]
            elif self.request_mode == "auto":
                modes = ["base64", "json"]
            else:
                modes = [self.request_mode]

        last_payload: dict[str, Any] | None = None
        for mode in modes:
            params = self._base_graphql_params(variables, mode)
            response, payload = self._get_json(
                self.config.graphql_endpoint,
                params=params,
                allow_http_error=True,
            )
            last_payload = payload
            search_result = payload.get("data", {}).get("productSearch")
            if search_result is not None:
                self.resolved_graphql_mode = mode
                return search_result
            if mode == "base64" and self._looks_like_base64_transport_error(payload):
                continue
            if response.status_code >= 400:
                break
            break

        raise RuntimeError(
            "No fue posible obtener una pagina valida del endpoint GraphQL. "
            f"Ultima respuesta: {json.dumps(last_payload, ensure_ascii=False)[:1200]}"
        )

    def fetch_category_tree(self) -> list[dict[str, Any]]:
        _, tree = self._get_json(self.config.category_tree_endpoint.format(depth=self.category_tree_depth))
        if not isinstance(tree, list):
            raise RuntimeError("El arbol publico de categorias no devolvio una lista valida.")
        return tree

    def effective_root_categories(self) -> list[RootCategorySelection]:
        if not self.selected_root_slugs:
            return [category for category in self.root_categories if category.enabled]

        selected = []
        requested = set(self.selected_root_slugs)
        seen: set[str] = set()
        for category in self.root_categories:
            if category.slug in requested and category.slug not in seen:
                selected.append(category)
                seen.add(category.slug)
        return selected

    def find_root_node(self, tree: list[dict[str, Any]], category: RootCategorySelection) -> dict[str, Any] | None:
        for node in tree:
            if root_slug_from_node(node) == category.slug:
                return node
        return find_category_node_by_name(tree, category.name)

    def plan_categories(
        self,
        node: dict[str, Any],
        *,
        root_category: RootCategorySelection,
        depth: int = 0,
    ) -> list[PlannedCategory]:
        segments = category_segments_from_url(node["url"])
        probe = self.fetch_graphql_page(segments, 0, 0)
        records_filtered = int(probe.get("recordsFiltered") or 0)
        children = node.get("children") or []

        if records_filtered == 0:
            return []

        if records_filtered > MAX_ACCESSIBLE_RECORDS_PER_QUERY and children:
            planned: list[PlannedCategory] = []
            for child in children:
                planned.extend(self.plan_categories(child, root_category=root_category, depth=depth + 1))
            return planned

        overflow = records_filtered > MAX_ACCESSIBLE_RECORDS_PER_QUERY and not children
        category = PlannedCategory(
            root_category=root_category,
            name=node.get("name") or "/".join(segments),
            url=node["url"],
            segments=segments,
            records_filtered=records_filtered,
            depth=depth,
            has_children=bool(children),
            overflow=overflow,
        )
        if overflow:
            self.overflow_categories.append(
                {
                    "root_category_slug": root_category.slug,
                    "root_category_name": root_category.name,
                    "name": category.name,
                    "url": category.url,
                    "records_filtered": category.records_filtered,
                }
            )
        return [category]

    def plan_enabled_categories(self, tree: list[dict[str, Any]]) -> list[PlannedCategory]:
        effective_roots = self.effective_root_categories()
        planned_categories: list[PlannedCategory] = []

        for root_category in effective_roots:
            node = self.find_root_node(tree, root_category)
            if node is None:
                self.missing_root_categories.append(
                    {
                        "name": root_category.name,
                        "slug": root_category.slug,
                        "url": root_category.url,
                    }
                )
                continue
            planned_categories.extend(self.plan_categories(node, root_category=root_category, depth=0))

        return planned_categories

    def scrape_category(self, category: PlannedCategory, category_index: int, total_categories: int) -> None:
        pages_scraped = 0
        inserted_here = 0
        max_pages = (category.records_filtered + self.page_step - 1) // self.page_step
        print(
            f"[{category_index}/{total_categories}] {category.root_category.name} > {category.name} | "
            f"{category.records_filtered} registros | hasta {max_pages} paginas",
            flush=True,
        )

        start = 0
        while start < category.records_filtered and start <= SAFE_PAGE_FROM_LIMIT:
            if self.max_pages_per_category is not None and pages_scraped >= self.max_pages_per_category:
                break

            end = start + self.page_step
            page = self.fetch_graphql_page(category.segments, start, end)
            products = page.get("products") or []
            if not products:
                break

            for product in products:
                items = product.get("items") or []
                for item in items:
                    record = canonical_product_record(self.config, category, product, item)
                    dedupe_key = f"{record['identity']['product_id']}::{record['identity']['sku']}"
                    if dedupe_key in self.catalog:
                        self.duplicates += 1
                        continue
                    self.catalog[dedupe_key] = record
                    inserted_here += 1

            pages_scraped += 1
            start += self.page_step

        self.category_runs.append(
            {
                "root_category_slug": category.root_category.slug,
                "root_category_name": category.root_category.name,
                "name": category.name,
                "url": category.url,
                "depth": category.depth,
                "records_filtered": category.records_filtered,
                "pages_scraped": pages_scraped,
                "inserted_records": inserted_here,
                "overflow": category.overflow,
            }
        )

    def build_output_payloads(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        records = list(self.catalog.values())
        finished_at = utc_now_iso()
        elapsed_seconds = round(time.monotonic() - self.started_monotonic, 3)
        effective_roots = self.effective_root_categories()

        metadata = {
            "schema_version": CATALOG_METADATA_SCHEMA_VERSION,
            "catalog_schema_version": CANONICAL_SCHEMA_VERSION,
            "catalog_id": self.config.resolved_catalog_id,
            "chain_id": self.config.store,
            "engine": "vtex",
            "display_name": self.config.resolved_display_name,
            "short_label": self.config.resolved_short_label,
            "base_url": self.config.base_url,
            "pricing_scope": self.config.pricing_scope,
            "pricing_context": self.config.resolved_pricing_context,
            "started_at": self.started_at,
            "finished_at": finished_at,
            "elapsed_seconds": elapsed_seconds,
            "generated_at": finished_at,
            "catalog_records": len(records),
            "unique_products": len({record["identity"]["product_id"] for record in records}),
            "duplicates_skipped": self.duplicates,
            "request_mode_requested": self.request_mode,
            "request_mode_resolved": self.resolved_graphql_mode,
            "page_step": self.page_step,
            "safe_page_from_limit": SAFE_PAGE_FROM_LIMIT,
            "max_accessible_records_per_query": MAX_ACCESSIBLE_RECORDS_PER_QUERY,
            "selected_root_category_slugs": self.selected_root_slugs,
            "enabled_root_categories": [
                {
                    "name": category.name,
                    "slug": category.slug,
                    "url": category.url,
                    "enabled": category.enabled,
                }
                for category in effective_roots
            ],
            "missing_root_categories": self.missing_root_categories,
            "category_runs": self.category_runs,
            "overflow_categories": self.overflow_categories,
        }

        return records, metadata

    def write_outputs(
        self,
        records: list[dict[str, Any]],
        metadata: dict[str, Any],
    ) -> tuple[Path, Path]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        catalog_path = self.output_dir / "catalog.json"
        metadata_path = self.output_dir / "metadata.json"

        catalog_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        return catalog_path, metadata_path

    def collect_catalog(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        tree = self.fetch_category_tree()
        planned_categories = self.plan_enabled_categories(tree)

        if self.max_categories is not None:
            planned_categories = planned_categories[: self.max_categories]

        total_categories = len(planned_categories)
        if total_categories == 0:
            raise RuntimeError(
                "No se encontraron categorias habilitadas con productos para procesar. "
                "Revisa la configuracion runtime de categorias raiz para la cadena."
            )

        print(
            f"Se planificaron {total_categories} categorias con datos para {self.config.resolved_display_name}. "
            f"Modo GraphQL resuelto: {self.resolved_graphql_mode or 'pendiente'}"
        )

        for index, category in enumerate(planned_categories, start=1):
            self.scrape_category(category, index, total_categories)

        return self.build_output_payloads()

    def run(self) -> tuple[Path, Path]:
        records, metadata = self.collect_catalog()
        return self.write_outputs(records, metadata)


def default_output_dir_for_chain(chain_id: str) -> Path:
    return load_chain_runtime_context(chain_id).default_output_dir


def build_chain_scraper(chain_id: str, args: argparse.Namespace) -> VTEXCatalogScraper:
    runtime = load_chain_runtime_context(chain_id)
    return build_chain_scraper_from_runtime(runtime, args)


def build_chain_scraper_from_payload(
    payload: dict[str, Any],
    args: argparse.Namespace,
) -> VTEXCatalogScraper:
    runtime = runtime_context_from_payload(payload)
    return build_chain_scraper_from_runtime(runtime, args)


def build_chain_scraper_from_runtime(
    runtime: StoreRuntimeContext,
    args: argparse.Namespace,
) -> VTEXCatalogScraper:
    output_dir = args.output_dir or runtime.default_output_dir
    return VTEXCatalogScraper(
        config=runtime.config,
        root_categories=runtime.root_categories,
        output_dir=output_dir,
        page_step=args.page_step,
        sleep_min=args.sleep_min,
        sleep_max=args.sleep_max,
        request_mode=args.request_mode,
        category_tree_depth=args.category_tree_depth,
        max_categories=args.max_categories,
        max_pages_per_category=args.max_pages_per_category,
        selected_root_slugs=args.root_category_slug,
    )


def run_chain_scraper(chain_id: str, args: argparse.Namespace) -> tuple[Path, Path]:
    scraper = build_chain_scraper(chain_id, args)
    return scraper.run()


def run_chain_scraper_to_memory(
    chain_id: str,
    args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    scraper = build_chain_scraper(chain_id, args)
    return scraper.collect_catalog()


def build_arg_parser(*, description: str, default_output_dir: Path | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output_dir,
        help=(
            f"Directorio de salida. Default: {default_output_dir}"
            if default_output_dir is not None
            else "Directorio de salida. Si se omite, usa el runtime configurado para la cadena."
        ),
    )
    parser.add_argument(
        "--request-mode",
        choices=("auto", "json", "base64"),
        default="auto",
        help="Modo del payload GraphQL. 'auto' intenta base64 y cae a json si VTEX lo rechaza.",
    )
    parser.add_argument(
        "--sleep-min",
        type=float,
        default=1.25,
        help="Sleep minimo entre requests.",
    )
    parser.add_argument(
        "--sleep-max",
        type=float,
        default=3.00,
        help="Sleep maximo entre requests.",
    )
    parser.add_argument(
        "--page-step",
        type=int,
        default=PAGE_STEP,
        help="Salto de paginacion entre parametros from/to.",
    )
    parser.add_argument(
        "--category-tree-depth",
        type=int,
        default=10,
        help="Profundidad del arbol publico de categorias.",
    )
    parser.add_argument(
        "--max-categories",
        type=int,
        default=None,
        help="Limita la cantidad de subcategorias planificadas a procesar. Util para smoke tests.",
    )
    parser.add_argument(
        "--max-pages-per-category",
        type=int,
        default=None,
        help="Limita paginas por categoria. Util para smoke tests.",
    )
    parser.add_argument(
        "--root-category-slug",
        action="append",
        default=None,
        help=(
            "Limita la corrida a una o varias categorias raiz por slug. "
            "Si se usa, puede ejecutar categorias aunque esten deshabilitadas en la configuracion runtime."
        ),
    )
    return parser
