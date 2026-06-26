#!/usr/bin/env python3
"""Motor configurable para extraer catalogos via Algolia (ej: Auto Mercado)."""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from etl.chain_runtime_db import load_catalog_runtime_payload
from etl.http_client import set_rate_limiter
from etl.normalize import normalize_ean
from etl.postgres_cli import parse_env


REQUEST_TIMEOUT = 60
PAGE_SIZE = 1000
CANONICAL_SCHEMA_VERSION = "canonical_product_v1"
CATALOG_METADATA_SCHEMA_VERSION = "catalog_metadata_v1"

MEASURE_PATTERN = re.compile(
    r"(?P<quantity>\d+(?:[.,]\d+)?)\s*(?P<unit>kg|gr|g|mg|ml|cc|cl|lt|lts|l|oz|lb|und|uds|ud|un|pz|u|pack|paquete|bolsa|unidad|litro|kilogramo|mililitro)\b",
    re.IGNORECASE,
)
MULTIPACK_PATTERN = re.compile(
    r"(?P<count>\d+)\s*[xX]\s*(?P<quantity>\d+(?:[.,]\d+)?)\s*(?P<unit>kg|gr|g|mg|ml|cc|cl|lt|lts|l|oz|lb|und|uds|ud|un|pz|u)\b",
    re.IGNORECASE,
)

UNIT_ALIASES = {
    "g": "g", "gr": "g", "kg": "kg", "mg": "mg",
    "ml": "ml", "cc": "ml", "cl": "cl", "l": "l", "lt": "l", "lts": "l",
    "oz": "oz", "lb": "lb",
    "un": "un", "und": "un", "uds": "un", "ud": "un", "pz": "un", "u": "un",
    "paquete": "un", "pack": "un", "bolsa": "un",
}
UNIT_STANDARDIZE = {
    "paquete": "un", "pack": "un", "bolsa": "un",
    "litro": "l", "kilogramo": "kg", "mililitro": "ml",
}


@dataclass(frozen=True)
class AlgoliaConfig:
    store: str
    display_name: str
    short_label: str
    catalog_id: str
    base_url: str
    pricing_scope: str
    algolia_app_id: str
    algolia_api_key: str
    algolia_index: str

    @property
    def resolved_display_name(self) -> str:
        return self.display_name or self.store

    @property
    def resolved_short_label(self) -> str:
        return self.short_label or self.resolved_display_name

    @property
    def resolved_catalog_id(self) -> str:
        return self.catalog_id or self.store


@dataclass(frozen=True)
class StoreRuntimeContext:
    config: AlgoliaConfig
    default_output_dir: Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_number(value: Any) -> int | float | None:
    if value is None:
        return None
    try:
        number = float(value)
        return int(number) if number.is_integer() else round(number, 4)
    except (TypeError, ValueError):
        return None


def normalize_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_unit(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    standardized = UNIT_STANDARDIZE.get(normalized)
    if standardized:
        return standardized
    return UNIT_ALIASES.get(normalized, normalized)


def to_float(value: str) -> float:
    return float(value.replace(",", "."))


def extract_measure_from_text(text: str | None) -> tuple[int | float | None, str | None]:
    if not text:
        return None, None
    text_clean = text.strip().lower()

    multipack_match = MULTIPACK_PATTERN.search(text_clean)
    if multipack_match:
        count = int(multipack_match.group("count"))
        quantity = to_float(multipack_match.group("quantity"))
        unit = normalize_unit(multipack_match.group("unit"))
        return normalize_number(count * quantity), unit

    for pattern in [r"(\d+(?:[.,]\d+)?)\s*x\s*(\d+)", r"(\d+)\s*un\b"]:
        alt_match = re.search(pattern, text_clean)
        if alt_match:
            groups = alt_match.groups()
            if len(groups) == 2:
                return normalize_number(to_float(groups[0]) * int(groups[1])), "un"

    matches = list(MEASURE_PATTERN.finditer(text_clean))
    if matches:
        last_match = matches[-1]
        quantity = normalize_number(to_float(last_match.group("quantity")))
        unit = normalize_unit(last_match.group("unit"))
        return quantity, unit

    return None, None


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


def load_chain_runtime_context(chain_id: str) -> StoreRuntimeContext:
    payload = load_catalog_runtime_payload(parse_env(), chain_id)
    return runtime_context_from_payload(payload)


def runtime_context_from_payload(payload: dict[str, Any]) -> StoreRuntimeContext:
    chain_id = str(payload.get("chain_id") or "").strip()
    extras = dict(payload.get("engine_extras") or {})

    config = AlgoliaConfig(
        store=chain_id,
        display_name=payload.get("display_name") or chain_id,
        short_label=payload.get("short_label") or payload.get("display_name") or chain_id,
        catalog_id=payload.get("catalog_id") or chain_id,
        base_url=str(payload.get("base_url") or "").strip(),
        pricing_scope=payload.get("pricing_scope") or "chain_public_online",
        algolia_app_id=str(extras.get("algolia_app_id") or "").strip(),
        algolia_api_key=str(extras.get("algolia_api_key") or "").strip(),
        algolia_index=str(extras.get("algolia_index") or "Product_CatalogueV2").strip(),
    )

    return StoreRuntimeContext(
        config=config,
        default_output_dir=resolve_output_dir_from_payload(payload),
    )


def infer_quantity_and_unit(product_presentation: str | None) -> tuple[int | float | None, str | None]:
    return extract_measure_from_text(product_presentation)


def canonical_product_record(
    config: AlgoliaConfig,
    product: dict[str, Any],
) -> dict[str, Any]:
    store_detail = product.get("storeDetail") or {}
    store_codes = sorted(store_detail.keys())

    first_store_pricing: dict[str, Any] = {}
    for code in store_codes:
        info = store_detail[code]
        if isinstance(info, dict):
            first_store_pricing = info
            break

    price = normalize_number(first_store_pricing.get("amount"))
    base_price = normalize_number(first_store_pricing.get("basePrice"))
    begin_discount = normalize_string(first_store_pricing.get("beginDateDiscount"))

    quantity, unit = infer_quantity_and_unit(product.get("productPresentation"))

    hierarchical = product.get("hierarchicalCategories") or {}
    category_path = hierarchical.get("lvl2") or hierarchical.get("lvl1") or hierarchical.get("lvl0")
    categories_raw = product.get("categoryPageId") or []

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
            "product_id": str(product.get("objectID") or product.get("ObjectID") or ""),
            "sku": normalize_string(product.get("productNumber")),
            "ean": normalize_ean(product.get("upcLink")),
            "product_reference": None,
            "reference_id": normalize_string(product.get("productNumber")),
            "brand": normalize_string(product.get("marca")),
            "brand_id": None,
            "seller_id": normalize_string(product.get("supplierId")),
            "seller_name": normalize_string(product.get("supplier")),
        },
        "taxonomy": {
            "category_path": category_path,
            "category_id": normalize_string(product.get("parentProductidCode")),
            "root_categories": [
                {"name": categories_raw[0], "slug": categories_raw[0].lower().replace(" ", "-")}
            ] if categories_raw else [],
            "raw_categories": categories_raw,
        },
        "content": {
            "name": normalize_string(product.get("ecomDescription"))
            or normalize_string(product.get("descriptiveParagraph"))
            or "",
            "description": normalize_string(product.get("descriptiveParagraph")),
            "link": None,
            "link_text": normalize_string(product.get("parentProductid_URL")),
            "image": normalize_string(product.get("imageUrl")),
        },
        "measurement": {
            "quantity": quantity,
            "unit": unit,
            "measurement_unit": None,
            "unit_multiplier": None,
        },
        "pricing": {
            "currency": "CRC",
            "price": price,
            "list_price": base_price if base_price is not None else price,
            "price_without_discount": base_price if base_price is not None else price,
            "spot_price": None,
            "has_discount": bool(product.get("hasDiscount"))
            or (base_price is not None and price is not None and base_price > price),
            "price_valid_until": begin_discount,
        },
        "availability": {
            "available_quantity": 1 if product.get("productAvailable") else 0,
        },
        "attributes": {
            "algolia_raw": product,
            "store_detail": store_detail,
            "catecom": normalize_string(product.get("catecom")),
            "product_presentation": normalize_string(product.get("productPresentation")),
            "product_available": bool(product.get("productAvailable")),
            "is_new_product": bool(product.get("isNewProduct")),
            "has_discount": bool(product.get("hasDiscount")),
            "exclusivo": bool(product.get("exclusivo")),
            "importado": bool(product.get("importado")),
            "marca_privada": product.get("marcaPrivada"),
            "is_collectable": bool(product.get("isCollectable")),
            "is_raffle": bool(product.get("isRaffle")),
            "is_hydroponic": bool(product.get("isHydroponic")),
            "season_indicator": product.get("seasonIndicator"),
            "selling_from": product.get("sellingFrom"),
        },
    }


class AlgoliaCatalogScraper:
    def __init__(
        self,
        *,
        config: AlgoliaConfig,
        output_dir: Path,
        max_pages: int | None = None,
        page_size: int = PAGE_SIZE,
    ) -> None:
        self.config = config
        self.output_dir = output_dir
        self.max_pages = max_pages
        self.page_size = page_size
        self.started_at = utc_now_iso()
        self.started_monotonic = time.monotonic()
        self.catalog: dict[str, dict[str, Any]] = {}
        self.duplicates = 0

    def _build_session(self) -> requests.Session:
        domain = self.config.base_url.removeprefix("https://").removeprefix("http://").split("/")[0]
        if domain:
            set_rate_limiter(domain)
        session = requests.Session()
        session.headers.update({
            "X-Algolia-API-Key": self.config.algolia_api_key,
            "X-Algolia-Application-Id": self.config.algolia_app_id,
            "Content-Type": "application/json",
        })
        session.verify = False
        return session

    def _algolia_endpoint(self) -> str:
        return f"https://{self.config.algolia_app_id}-dsn.algolia.net/1/indexes/{self.config.algolia_index}/query"

    def fetch_page(self, session: requests.Session, page: int) -> dict[str, Any]:
        response = session.post(
            self._algolia_endpoint(),
            json={"params": f"query=&hitsPerPage={self.page_size}&page={page}"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    def _fetch_category_page(
        self, session: requests.Session, category: str, page: int = 0
    ) -> dict[str, Any]:
        response = session.post(
            self._algolia_endpoint(),
            json={"params": f"query=&hitsPerPage={self.page_size}&page={page}&facetFilters=[\"categoryPageId:{category}\"]"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    def _fetch_categories(self, session: requests.Session) -> dict[str, int]:
        response = session.post(
            self._algolia_endpoint(),
            json={"params": "query=&hitsPerPage=0&facets=[\"categoryPageId\"]&maxValuesPerFacet=1000"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return (response.json().get("facets") or {}).get("categoryPageId") or {}

    def _ingest_hits(self, hits: list[dict[str, Any]]) -> None:
        for product in hits:
            record = canonical_product_record(self.config, product)
            dedupe_key = record["identity"]["product_id"]
            if dedupe_key in self.catalog:
                self.duplicates += 1
                continue
            self.catalog[dedupe_key] = record

    def collect_catalog(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        session = self._build_session()
        total_hits: int | None = None

        if self.max_pages is not None:
            return self._collect_by_pagination(session)

        return self._collect_full_catalog(session)

    def _collect_by_pagination(self, session: requests.Session) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        page = 0
        pages_scraped = 0
        total_hits = None

        while pages_scraped < self.max_pages:
            payload = self.fetch_page(session, page)
            if total_hits is None:
                total_hits = payload.get("nbHits", 0)
                print(f"[{self.config.store}] Total productos: {total_hits}", flush=True)

            hits = payload.get("hits") or []
            if not hits:
                break

            self._ingest_hits(hits)
            pages_scraped += 1
            page += 1

        if not self.catalog:
            raise RuntimeError("No se obtuvieron productos del indice Algolia.")

        return self._build_result(total_hits, pages_scraped)

    def _collect_full_catalog(self, session: requests.Session) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        categories = self._fetch_categories(session)
        total_hits = sum(categories.values())
        pages_scraped = 0

        roots = {k: v for k, v in categories.items() if ">" not in k}
        l1_subs = {k: v for k, v in categories.items() if k.count(">") == 1}

        query_groups: list[tuple[str, int]] = []
        for cat, count in roots.items():
            if count <= self.page_size:
                query_groups.append((cat, count))
            else:
                subs = {k: v for k, v in l1_subs.items() if k.startswith(f"{cat} >")}
                if subs:
                    query_groups.extend(sorted(subs.items(), key=lambda x: -x[1]))
                else:
                    query_groups.append((cat, count))

        query_groups.sort(key=lambda x: -x[1])

        print(
            f"[{self.config.store}] Total: ~{total_hits} productos en {len(query_groups)} grupos de categoria",
            flush=True,
        )

        for idx, (category, expected) in enumerate(query_groups):
            payload = self._fetch_category_page(session, category, page=0)
            hits = payload.get("hits") or []
            self._ingest_hits(hits)
            pages_scraped += 1

            if (idx + 1) % 10 == 0 or idx == len(query_groups) - 1:
                print(
                    f"  [{idx+1}/{len(query_groups)}] '{category[:50]}' -> "
                    f"{len(hits)} hits | acumulados: {len(self.catalog)}",
                    flush=True,
                )

        if not self.catalog:
            raise RuntimeError("No se obtuvieron productos del indice Algolia.")

        return self._build_result(total_hits, pages_scraped)

    def _build_result(
        self, total_hits: int | None, pages_scraped: int
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        elapsed_seconds = round(time.monotonic() - self.started_monotonic, 3)
        records = list(self.catalog.values())
        finished_at = utc_now_iso()

        metadata = {
            "schema_version": CATALOG_METADATA_SCHEMA_VERSION,
            "catalog_schema_version": CANONICAL_SCHEMA_VERSION,
            "catalog_id": self.config.resolved_catalog_id,
            "chain_id": self.config.store,
            "engine": "algolia",
            "display_name": self.config.resolved_display_name,
            "short_label": self.config.resolved_short_label,
            "base_url": self.config.base_url,
            "pricing_scope": self.config.pricing_scope,
            "started_at": self.started_at,
            "finished_at": finished_at,
            "generated_at": finished_at,
            "elapsed_seconds": elapsed_seconds,
            "catalog_records": len(records),
            "unique_products": len({r["identity"]["product_id"] for r in records}),
            "duplicates_skipped": self.duplicates,
            "page_size": self.page_size,
            "pages_scraped": pages_scraped,
            "total_algolia_hits": total_hits,
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

    def run(self) -> tuple[Path, Path]:
        records, metadata = self.collect_catalog()
        return self.write_outputs(records, metadata)


def build_chain_scraper(chain_id: str, args: argparse.Namespace) -> AlgoliaCatalogScraper:
    runtime = load_chain_runtime_context(chain_id)
    output_dir = args.output_dir or runtime.default_output_dir
    return AlgoliaCatalogScraper(
        config=runtime.config,
        output_dir=output_dir,
        max_pages=args.max_pages,
        page_size=args.page_size or PAGE_SIZE,
    )


def run_chain_scraper(chain_id: str, args: argparse.Namespace) -> tuple[Path, Path]:
    scraper = build_chain_scraper(chain_id, args)
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
            else "Directorio de salida."
        ),
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Limita paginas a procesar (util para smoke tests).",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=PAGE_SIZE,
        help=f"Productos por pagina Algolia (max 1000, default {PAGE_SIZE}).",
    )
    return parser
