#!/usr/bin/env python3
"""Motor Instaleap configurable para extraer catalogos por tienda y categorias raiz.

Instaleap es la plataforma headless detras de cadenas como Megasuper. La API
publica de GraphQL en `nextgentheadless.instaleap.io/api/v3` expone la operacion
`getProductsByCategory` que recibe `{clientId, storeReference, categoryReference}`
y pagina via `currentPage` / `pageSize`. Con `categoryReference` en nivel raiz
(p.ej. "01") el endpoint devuelve toda la subcategoria recursivamente.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from store_catalog_config import (
    get_store_definition,
    load_store_config,
    normalize_ean,
    resolve_output_dir,
)


REQUEST_TIMEOUT = 60
DEFAULT_PAGE_SIZE = 100
CANONICAL_SCHEMA_VERSION = "canonical_product_v1"
CATALOG_METADATA_SCHEMA_VERSION = "catalog_metadata_v1"

PRODUCTS_BY_CATEGORY_QUERY = """
query GetProductsByCategory($getProductsByCategoryInput: GetProductsByCategoryInput!) {
  getProductsByCategory(getProductsByCategoryInput: $getProductsByCategoryInput) {
    category {
      name
      reference
      level
      path
      hasChildren
      slug
      categoryNamesPath
      products {
        name
        sku
        ean
        brand
        description
        price
        previousPrice
        priceBeforeTaxes
        taxTotal
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
        categories {
          name
          reference
        }
        categoriesData {
          name
          reference
        }
        promotions {
          type
          description
          isActive
        }
      }
    }
    pagination {
      page
      pages
      total {
        value
        relation
      }
    }
  }
}
""".strip()

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


@dataclass(frozen=True)
class InstaleapStoreConfig:
    store: str
    base_url: str
    client_id: str
    store_reference: str
    graphql_endpoint: str
    display_name: str | None = None
    short_label: str | None = None
    catalog_id: str | None = None
    pricing_scope: str = "default_store_online"
    pricing_context: dict[str, Any] | None = None
    currency: str = "CRC"
    locale: str = "es-CR"
    store_internal_id: str | None = None

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
    category_reference: str | None = None


@dataclass(frozen=True)
class StoreRuntimeContext:
    config: InstaleapStoreConfig
    root_categories: list[RootCategorySelection]
    default_output_dir: Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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


def first_image(values: Any) -> str | None:
    return first_non_empty(values)


def category_path_for_record(
    category_names_path: str | None,
    fallback: str,
) -> str:
    if not category_names_path:
        return fallback
    parts = [part.strip() for part in category_names_path.strip("/").split("/") if part.strip()]
    return " > ".join(parts) if parts else fallback


def has_active_promotion(product: dict[str, Any]) -> bool:
    promotion = product.get("promotion") or {}
    if isinstance(promotion, dict) and promotion.get("isActive"):
        return True
    promotions = product.get("promotions") or []
    if isinstance(promotions, list):
        for promo in promotions:
            if isinstance(promo, dict) and promo.get("isActive"):
                return True
    return False


def canonical_product_record(
    config: InstaleapStoreConfig,
    root_category: RootCategorySelection,
    response_category: dict[str, Any],
    product: dict[str, Any],
) -> dict[str, Any]:
    sku = normalize_string(product.get("sku")) or ""
    ean = normalize_ean(product.get("ean"))
    name = normalize_string(product.get("name")) or ""
    description = normalize_string(product.get("description"))
    price = normalize_number(product.get("price"))
    previous_price = normalize_number(product.get("previousPrice"))
    promotion_price_per_sub = normalize_number(product.get("promotionPricePerSubUnit"))
    price_per_sub = normalize_number(product.get("pricePerSubUnit"))
    stock = normalize_number(product.get("stock"))
    sub_qty = normalize_number(product.get("subQty"))
    measurement_unit = normalize_unit(product.get("subUnit") or product.get("unit"))

    quantity, unit = extract_measure_from_text(name)
    if quantity is None or unit is None:
        if sub_qty is not None and measurement_unit:
            quantity, unit = sub_qty, measurement_unit
        else:
            quantity, unit = sub_qty if sub_qty is not None else 1, measurement_unit or "un"

    promotion_active = has_active_promotion(product)
    discount_vs_previous = previous_price is not None and price is not None and previous_price > price
    has_discount = bool(promotion_active or discount_vs_previous)

    response_path = response_category.get("categoryNamesPath")
    category_path = category_path_for_record(response_path, root_category.name)

    raw_categories: list[str] = []
    for source_key in ("categoriesData", "categories"):
        for entry in product.get(source_key) or []:
            if not isinstance(entry, dict):
                continue
            category_name = normalize_string(entry.get("name"))
            if category_name and category_name not in raw_categories:
                raw_categories.append(category_name)

    response_category_id = normalize_string(response_category.get("reference"))
    for entry in product.get("categoriesData") or []:
        if isinstance(entry, dict):
            ref = normalize_string(entry.get("reference"))
            if ref:
                response_category_id = response_category_id or ref
                break

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
            "product_id": sku,
            "sku": sku,
            "ean": ean,
            "product_reference": normalize_string(product.get("slug")),
            "reference_id": ean,
            "brand": normalize_string(product.get("brand")),
            "brand_id": None,
            "seller_id": config.store_reference,
            "seller_name": config.resolved_display_name,
        },
        "taxonomy": {
            "category_path": category_path,
            "category_id": response_category_id,
            "root_categories": [
                {
                    "name": root_category.name,
                    "slug": root_category.slug,
                }
            ],
            "raw_categories": raw_categories,
        },
        "content": {
            "name": name,
            "description": description,
            "link": absolute_product_link(config.base_url, product.get("slug")),
            "link_text": normalize_string(product.get("slug")),
            "image": first_image(product.get("photosUrl")),
        },
        "measurement": {
            "quantity": quantity,
            "unit": unit,
            "measurement_unit": measurement_unit,
            "unit_multiplier": sub_qty,
        },
        "pricing": {
            "currency": config.currency,
            "price": price,
            "list_price": previous_price,
            "price_without_discount": previous_price,
            "spot_price": promotion_price_per_sub or price_per_sub,
            "has_discount": has_discount,
            "price_valid_until": None,
        },
        "availability": {
            "available_quantity": stock,
        },
        "attributes": {
            "properties": [],
            "specification_groups": [],
            "selected_properties": [],
            "variations": [],
            "cluster_highlights": {},
            "product_clusters": {},
            "discount_highlights": [],
            "teasers": [],
        },
    }


def absolute_product_link(base_url: str, slug: str | None) -> str | None:
    slug_value = normalize_string(slug)
    if not slug_value:
        return None
    if slug_value.startswith("http://") or slug_value.startswith("https://"):
        return slug_value
    return f"{base_url}/p/{slug_value.lstrip('/')}"


def load_store_runtime_context(store_id: str) -> StoreRuntimeContext:
    definition = get_store_definition(store_id)
    if definition.engine != "instaleap":
        raise RuntimeError(
            f"Store {store_id!r} no esta configurada como Instaleap (engine={definition.engine!r})."
        )

    payload = load_store_config(store_id)
    extras = {**(definition.extras or {}), **(payload.get("engine_extras") or {})}

    if "client_id" not in extras or "store_reference" not in extras:
        raise RuntimeError(
            f"engine_extras incompleto para {store_id!r}. Se requieren client_id y store_reference."
        )

    categories_payload = payload.get("categories") or []
    root_categories = [
        RootCategorySelection(
            name=category.get("name") or str(category.get("slug") or ""),
            slug=str(category.get("slug") or "").strip(),
            url=category.get("url") or f"{definition.base_url}/{category.get('slug')}",
            enabled=bool(category.get("enabled")),
            category_reference=normalize_string(category.get("category_reference")),
        )
        for category in categories_payload
        if str(category.get("slug") or "").strip()
    ]

    config = InstaleapStoreConfig(
        store=definition.store_id,
        display_name=payload.get("display_name") or definition.display_name,
        short_label=payload.get("short_label") or definition.short_label,
        catalog_id=payload.get("catalog_id") or definition.catalog_id,
        base_url=payload.get("base_url") or definition.base_url,
        pricing_scope=payload.get("pricing_scope") or definition.pricing_scope,
        pricing_context=payload.get("pricing_context") or definition.pricing_context,
        client_id=str(extras["client_id"]),
        store_reference=str(extras["store_reference"]),
        graphql_endpoint=str(
            extras.get("graphql_endpoint") or "https://nextgentheadless.instaleap.io/api/v3"
        ),
        currency=str(extras.get("currency") or "CRC"),
        locale=str(extras.get("locale") or "es-CR"),
        store_internal_id=normalize_string(extras.get("store_internal_id")),
    )

    return StoreRuntimeContext(
        config=config,
        root_categories=root_categories,
        default_output_dir=resolve_output_dir(payload, definition),
    )


class InstaleapCatalogScraper:
    def __init__(
        self,
        *,
        config: InstaleapStoreConfig,
        root_categories: list[RootCategorySelection],
        output_dir: Path,
        page_size: int = DEFAULT_PAGE_SIZE,
        sleep_min: float = 0.45,
        sleep_max: float = 1.10,
        max_categories: int | None = None,
        max_pages_per_category: int | None = None,
        selected_root_slugs: list[str] | None = None,
    ) -> None:
        self.config = config
        self.root_categories = root_categories
        self.output_dir = output_dir
        self.page_size = page_size
        self.sleep_min = sleep_min
        self.sleep_max = sleep_max
        self.max_categories = max_categories
        self.max_pages_per_category = max_pages_per_category
        self.selected_root_slugs = [slug.strip() for slug in selected_root_slugs or [] if slug.strip()]
        self.started_at = utc_now_iso()
        self.started_monotonic = time.monotonic()
        self.session = self._build_session()
        self.request_counter = 0
        self.catalog: dict[str, dict[str, Any]] = {}
        self.duplicates = 0
        self.category_runs: list[dict[str, Any]] = []
        self.missing_root_categories: list[dict[str, Any]] = []

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=(429, 502, 503, 504),
            allowed_methods=("POST",),
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)

        session.headers.update(
            {
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "es-CR,es;q=0.9,en;q=0.8",
                "Cache-Control": "no-cache",
                "Content-Type": "application/json",
                "Origin": self.config.base_url,
                "Referer": f"{self.config.base_url}/",
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
                ),
            }
        )
        return session

    def _sleep_if_needed(self) -> None:
        if self.request_counter <= 0:
            return
        time.sleep(random.uniform(self.sleep_min, self.sleep_max))

    def fetch_products_page(
        self,
        category_reference: str,
        current_page: int,
        page_size: int,
    ) -> dict[str, Any]:
        variables = {
            "getProductsByCategoryInput": {
                "clientId": self.config.client_id,
                "storeReference": self.config.store_reference,
                "categoryReference": category_reference,
                "currentPage": current_page,
                "pageSize": page_size,
            }
        }
        body = {
            "operationName": "GetProductsByCategory",
            "variables": variables,
            "query": PRODUCTS_BY_CATEGORY_QUERY,
        }

        self._sleep_if_needed()
        response = self.session.post(
            self.config.graphql_endpoint,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            timeout=REQUEST_TIMEOUT,
        )
        self.request_counter += 1
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            raise RuntimeError(
                "Error de Instaleap: "
                + json.dumps(payload["errors"], ensure_ascii=False)[:1200]
            )
        result = (payload.get("data") or {}).get("getProductsByCategory")
        if not isinstance(result, dict):
            raise RuntimeError(
                "Respuesta GraphQL invalida: faltan datos de getProductsByCategory."
            )
        return result

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

    def resolve_category_reference(self, root_category: RootCategorySelection) -> str | None:
        if root_category.category_reference:
            return root_category.category_reference

        slug_tail = root_category.slug.strip().split("/")[-1]
        if slug_tail.isdigit():
            return slug_tail

        return None

    def scrape_root_category(
        self,
        root_category: RootCategorySelection,
        index: int,
        total_root_categories: int,
    ) -> None:
        category_reference = self.resolve_category_reference(root_category)
        if not category_reference:
            self.missing_root_categories.append(
                {
                    "name": root_category.name,
                    "slug": root_category.slug,
                    "url": root_category.url,
                    "reason": "categoryReference no definido en la config",
                }
            )
            return

        current_page = 1
        pages_scraped = 0
        inserted_here = 0
        total_records: int | None = None
        total_pages: int | None = None

        while True:
            if self.max_pages_per_category is not None and pages_scraped >= self.max_pages_per_category:
                break

            data = self.fetch_products_page(category_reference, current_page, self.page_size)
            response_category = data.get("category") or {}
            pagination = data.get("pagination") or {}
            products = response_category.get("products") or []

            if total_records is None:
                total_block = pagination.get("total") or {}
                total_records = total_block.get("value") if isinstance(total_block, dict) else None
            if total_pages is None:
                total_pages = pagination.get("pages")

            if pages_scraped == 0:
                printable_total = total_records if total_records is not None else "?"
                printable_pages = total_pages if total_pages is not None else "?"
                print(
                    f"[{index}/{total_root_categories}] {root_category.name} (ref {category_reference}) | "
                    f"{printable_total} registros | {printable_pages} paginas",
                    flush=True,
                )

            for product in products:
                record = canonical_product_record(self.config, root_category, response_category, product)
                dedupe_key = record["identity"]["sku"] or record["identity"]["product_id"]
                if not dedupe_key:
                    continue
                if dedupe_key in self.catalog:
                    self.duplicates += 1
                    continue
                self.catalog[dedupe_key] = record
                inserted_here += 1

            pages_scraped += 1

            if not products:
                break
            if total_pages is not None and current_page >= total_pages:
                break
            current_page += 1

        self.category_runs.append(
            {
                "root_category_slug": root_category.slug,
                "root_category_name": root_category.name,
                "category_reference": category_reference,
                "url": root_category.url,
                "records_filtered": total_records,
                "pages_scraped": pages_scraped,
                "inserted_records": inserted_here,
            }
        )

    def write_outputs(self) -> tuple[Path, Path]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        catalog_path = self.output_dir / "catalog.json"
        metadata_path = self.output_dir / "metadata.json"

        records = list(self.catalog.values())
        finished_at = utc_now_iso()
        elapsed_seconds = round(time.monotonic() - self.started_monotonic, 3)
        effective_roots = self.effective_root_categories()

        metadata = {
            "schema_version": CATALOG_METADATA_SCHEMA_VERSION,
            "catalog_schema_version": CANONICAL_SCHEMA_VERSION,
            "catalog_id": self.config.resolved_catalog_id,
            "store": self.config.store,
            "display_name": self.config.resolved_display_name,
            "short_label": self.config.resolved_short_label,
            "base_url": self.config.base_url,
            "engine": "instaleap",
            "engine_endpoint": self.config.graphql_endpoint,
            "engine_client_id": self.config.client_id,
            "engine_store_reference": self.config.store_reference,
            "engine_store_internal_id": self.config.store_internal_id,
            "pricing_scope": self.config.pricing_scope,
            "pricing_context": self.config.resolved_pricing_context,
            "started_at": self.started_at,
            "finished_at": finished_at,
            "elapsed_seconds": elapsed_seconds,
            "generated_at": finished_at,
            "catalog_records": len(records),
            "unique_products": len({record["identity"]["sku"] for record in records if record["identity"]["sku"]}),
            "duplicates_skipped": self.duplicates,
            "page_size": self.page_size,
            "selected_root_category_slugs": self.selected_root_slugs,
            "enabled_root_categories": [
                {
                    "name": category.name,
                    "slug": category.slug,
                    "url": category.url,
                    "category_reference": category.category_reference,
                    "enabled": category.enabled,
                }
                for category in effective_roots
            ],
            "missing_root_categories": self.missing_root_categories,
            "category_runs": self.category_runs,
        }

        catalog_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        return catalog_path, metadata_path

    def run(self) -> tuple[Path, Path]:
        effective_roots = self.effective_root_categories()
        if self.max_categories is not None:
            effective_roots = effective_roots[: self.max_categories]

        if not effective_roots:
            raise RuntimeError(
                "No se encontraron categorias raiz habilitadas para procesar. "
                "Revisa los JSON en config/stores/*.json."
            )

        print(
            f"Se planificaron {len(effective_roots)} categorias raiz para "
            f"{self.config.resolved_display_name} (clientId={self.config.client_id}, "
            f"storeReference={self.config.store_reference})."
        )

        for index, root_category in enumerate(effective_roots, start=1):
            self.scrape_root_category(root_category, index, len(effective_roots))

        return self.write_outputs()


def default_output_dir_for_store(store_id: str) -> Path:
    return load_store_runtime_context(store_id).default_output_dir


def build_store_scraper(store_id: str, args: argparse.Namespace) -> InstaleapCatalogScraper:
    runtime = load_store_runtime_context(store_id)
    output_dir = args.output_dir or runtime.default_output_dir
    return InstaleapCatalogScraper(
        config=runtime.config,
        root_categories=runtime.root_categories,
        output_dir=output_dir,
        page_size=args.page_size,
        sleep_min=args.sleep_min,
        sleep_max=args.sleep_max,
        max_categories=args.max_categories,
        max_pages_per_category=args.max_pages_per_category,
        selected_root_slugs=args.root_category_slug,
    )


def run_store_scraper(store_id: str, args: argparse.Namespace) -> tuple[Path, Path]:
    scraper = build_store_scraper(store_id, args)
    return scraper.run()


def build_arg_parser(*, description: str, default_output_dir: Path | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output_dir,
        help=(
            f"Directorio de salida. Default: {default_output_dir}"
            if default_output_dir is not None
            else "Directorio de salida. Si se omite, usa el definido en config/stores/<store>.json."
        ),
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=DEFAULT_PAGE_SIZE,
        help="Tamano de pagina para getProductsByCategory.",
    )
    parser.add_argument(
        "--sleep-min",
        type=float,
        default=0.45,
        help="Sleep minimo entre requests.",
    )
    parser.add_argument(
        "--sleep-max",
        type=float,
        default=1.10,
        help="Sleep maximo entre requests.",
    )
    parser.add_argument(
        "--max-categories",
        type=int,
        default=None,
        help="Limita la cantidad de categorias raiz a procesar. Util para smoke tests.",
    )
    parser.add_argument(
        "--max-pages-per-category",
        type=int,
        default=None,
        help="Limita paginas por categoria raiz. Util para smoke tests.",
    )
    parser.add_argument(
        "--root-category-slug",
        action="append",
        default=None,
        help=(
            "Limita la corrida a una o varias categorias raiz por slug. "
            "Si se usa, puede ejecutar categorias aunque esten disabled en el JSON."
        ),
    )
    return parser
