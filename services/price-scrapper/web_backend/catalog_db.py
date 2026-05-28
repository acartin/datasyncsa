#!/usr/bin/env python3
"""Carga bundles de catálogo desde Postgres para la web local."""

from __future__ import annotations

import csv
import io
import json
import time
from dataclasses import dataclass
from typing import Any

from etl.postgres_cli import parse_env, run_psql


@dataclass
class CatalogBundleCache:
    ttl_seconds: float = 120.0
    loaded_monotonic: float = 0.0
    payload: dict[str, Any] | None = None

    def get(self) -> dict[str, Any] | None:
        if self.payload is None:
            return None
        age = time.monotonic() - self.loaded_monotonic
        if age > self.ttl_seconds:
            return None
        return self.payload

    def set(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.loaded_monotonic = time.monotonic()


CATALOG_BUNDLE_CACHE = CatalogBundleCache()
PRODUCT_CATALOG_CACHE = CatalogBundleCache()


def _parse_copy_csv(output: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(output))
    return [dict(row) for row in reader]


def _parse_bool_text(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"t", "true", "1", "yes", "y"}


def _load_chain_runs(env: dict[str, str]) -> list[dict[str, Any]]:
    output = run_psql(
        env,
        sql="""
copy (
  select
    c.chain_id,
    c.chain_name,
    coalesce(c.short_label, c.chain_name) as short_label,
    r.run_key,
    coalesce(r.catalog_id, c.chain_id) as catalog_id,
    r.run_started_at::text as started_at,
    r.run_finished_at::text as finished_at,
    r.catalog_records::text as catalog_records,
    r.run_metadata::text as raw_metadata
  from public.mkt_dim_chain as c
  left join lateral (
    select
      run_key,
      catalog_id,
      run_started_at,
      run_finished_at,
      catalog_records,
      run_metadata
    from public.mw_fact_comparative_listing_snapshot
    where chain_key = c.chain_key
    order by run_started_at desc, run_key desc
    limit 1
  ) as r on true
  where c.is_active = true
  order by c.chain_id
) to stdout with (format csv, header true);
""",
    )
    rows = _parse_copy_csv(output)
    payload_rows: list[dict[str, Any]] = []
    for row in rows:
        metadata = json.loads(row["raw_metadata"]) if row["raw_metadata"] else {}
        payload_rows.append(
            {
                "chain_id": row["chain_id"],
                "chain_name": row["chain_name"],
                "short_label": row["short_label"],
                "run_key": int(row["run_key"])
                if row["run_key"]
                else None,
                "catalog_id": row["catalog_id"],
                "started_at": row["started_at"] or None,
                "finished_at": row["finished_at"] or None,
                "catalog_records": int(row["catalog_records"]) if row["catalog_records"] else 0,
                "metadata": metadata,
            }
        )
    return payload_rows


def _load_snapshot_rows_for_runs(env: dict[str, str], run_keys: list[int]) -> list[dict[str, str]]:
    if not run_keys:
        return []
    run_keys_sql = ", ".join(str(run_key) for run_key in sorted(set(run_keys)))
    output = run_psql(
        env,
        sql=f"""
copy (
  select
    f.run_key::text as run_key,
    f.source_product_id,
    f.source_sku,
    f.gtin_norm as source_gtin,
    f.brand_name,
    coalesce(f.listing_name, f.product_name) as product_name,
    f.price_amount::text as price_amount,
    f.list_price_amount::text as list_price_amount,
    f.has_discount::text as has_discount,
    f.content_unit as unit,
    f.content_quantity::text as quantity,
    coalesce(f.root_category_name, f.root_category_slug, '') as category,
    f.product_url,
    f.image_url,
    f.pricing_scope
  from public.mw_fact_comparative_listing_snapshot as f
  where f.run_key in ({run_keys_sql})
  order by f.run_key, f.chain_key, f.source_product_id, f.source_sku
) to stdout with (format csv, header true);
""",
    )
    return _parse_copy_csv(output)


def _bundle_from_chain_run(row: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(row["metadata"] or {})
    metadata.setdefault("chain_id", row["chain_id"])
    metadata.setdefault("display_name", row["chain_name"])
    metadata.setdefault("short_label", row["short_label"])
    metadata.setdefault("catalog_id", row["catalog_id"])
    metadata.setdefault("started_at", row["started_at"])
    metadata.setdefault("finished_at", row["finished_at"])
    metadata.setdefault("catalog_records", row["catalog_records"])
    metadata["run_key"] = row["run_key"]

    return {
        "id": row["catalog_id"],
        "label": row["chain_name"],
        "shortLabel": row["short_label"],
        "chain": row["chain_id"],
        "source": "/api/catalog-bundles",
        "products": [],
        "metadata": metadata,
    }


def _normalize_stage_item(row: dict[str, str]) -> dict[str, Any]:
    def maybe_number(value: str | None) -> float | None:
        if value in (None, ""):
            return None
        return float(value)

    return {
        "chain": "",
        "product_id": row["source_product_id"] or "",
        "sku": row["source_sku"] or "",
        "name": row["product_name"] or "",
        "brand": row["brand_name"] or "",
        "ean": row["source_gtin"] or None,
        "price": maybe_number(row["price_amount"]),
        "list_price": maybe_number(row["list_price_amount"]),
        "has_discount": _parse_bool_text(row["has_discount"]),
        "unit": row["unit"] or None,
        "quantity": maybe_number(row["quantity"]),
        "category": row["category"] or "",
        "link": row["product_url"] or None,
        "image": row["image_url"] or None,
        "pricing_scope": row["pricing_scope"] or None,
    }


def fetch_catalog_bundles_from_db(*, force_refresh: bool = False) -> dict[str, Any]:
    if not force_refresh:
        cached = CATALOG_BUNDLE_CACHE.get()
        if cached is not None:
            return cached

    env = parse_env()
    chain_runs = _load_chain_runs(env)
    bundles: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    bundles_by_run_key: dict[int, dict[str, Any]] = {}

    for row in chain_runs:
        if row["run_key"] is None:
            failures.append(
                {
                    "id": row["catalog_id"],
                    "label": row["chain_name"],
                    "shortLabel": row["short_label"],
                    "chain": row["chain_id"],
                    "error": "No hay una corrida succeeded en mkt_run para esta cadena.",
                }
            )
            continue
        bundle = _bundle_from_chain_run(row)
        bundles.append(bundle)
        bundles_by_run_key[row["run_key"]] = bundle

    snapshot_rows = _load_snapshot_rows_for_runs(env, list(bundles_by_run_key))
    for row in snapshot_rows:
        run_key = int(row["run_key"])
        bundle = bundles_by_run_key.get(run_key)
        if bundle is None:
            continue
        product = _normalize_stage_item(row)
        product["chain"] = bundle["chain"]
        bundle["products"].append(product)

    payload = {
        "bundles": bundles,
        "failures": failures,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    CATALOG_BUNDLE_CACHE.set(payload)
    return payload


def _sql_literal(value: str) -> str:
    return value.replace("'", "''")


def _load_active_chains(env: dict[str, str]) -> list[dict[str, Any]]:
    output = run_psql(
        env,
        sql="""
copy (
  select
    chain_id,
    chain_name,
    coalesce(short_label, chain_name) as short_label
  from public.mkt_dim_chain
  where is_active = true
  order by chain_id
) to stdout with (format csv, header true);
""",
    )
    return _parse_copy_csv(output)


def _load_product_catalog_rows(env: dict[str, str]) -> list[dict[str, str]]:
    output = run_psql(
        env,
        sql="""
copy (
  with latest_runs as (
    select distinct on (v.chain_key)
      v.run_key,
      v.chain_key
    from public.mw_fact_comparative_listing_snapshot as v
    join public.mkt_dim_chain as c
      on c.chain_key = v.chain_key
    where c.is_active = true
    order by v.chain_key, v.run_started_at desc, v.run_key desc
  ),
  latest_snapshots as (
    select
      v.product_key,
      v.chain_id,
      v.source_product_id,
      v.source_sku,
      v.listing_name,
      v.product_url,
      v.image_url,
      coalesce(v.root_category_name, v.root_category_slug, '') as category,
      v.price_amount,
      v.list_price_amount,
      v.has_discount,
      row_number() over (
        partition by v.product_key
        order by
          case
            when v.price_amount is not null and v.price_amount > 0 then 0
            else 1
          end,
          case
            when v.available_quantity is not null and v.available_quantity > 0 then 0
            else 1
          end,
          (v.price_amount is null),
          v.price_amount,
          v.chain_id,
          v.listing_key
      ) as product_rank
    from public.mw_fact_comparative_listing_snapshot as v
    join latest_runs as r
      on r.run_key = v.run_key
  ),
  chain_rollup as (
    select
      product_key,
      count(distinct chain_id)::text as available_chain_count,
      json_agg(distinct chain_id order by chain_id)::text as available_chains
    from latest_snapshots
    group by product_key
  ),
  product_aliases as (
    select
      product_key,
      array_to_json(array_remove(array_agg(distinct listing_name), null))::text as listing_aliases,
      array_to_json(array_remove(array_agg(distinct source_product_id), null))::text as source_product_ids,
      array_to_json(array_remove(array_agg(distinct source_sku), null))::text as source_skus
    from latest_snapshots
    group by product_key
  )
  select
    p.product_key::text as product_key,
    p.gtin_norm,
    p.brand_name,
    p.product_name,
    p.content_quantity::text as content_quantity,
    p.content_unit,
    coalesce(cr.available_chain_count, '0') as available_chain_count,
    coalesce(cr.available_chains, '[]') as available_chains,
    rep.source_product_id,
    rep.source_sku,
    rep.listing_name,
    rep.product_url,
    rep.image_url,
    rep.category,
    rep.price_amount::text as price_amount,
    rep.list_price_amount::text as list_price_amount,
    rep.has_discount::text as has_discount,
    coalesce(pa.listing_aliases, '[]') as listing_aliases,
    coalesce(pa.source_product_ids, '[]') as source_product_ids,
    coalesce(pa.source_skus, '[]') as source_skus
  from public.mkt_dim_product as p
  left join chain_rollup as cr
    on cr.product_key = p.product_key
  left join product_aliases as pa
    on pa.product_key = p.product_key
  left join latest_snapshots as rep
    on rep.product_key = p.product_key
   and rep.product_rank = 1
  where p.is_active = true
  order by p.product_name, p.product_key
) to stdout with (format csv, header true);
""",
    )
    return _parse_copy_csv(output)


def _normalize_catalog_product(row: dict[str, str]) -> dict[str, Any]:
    def maybe_number(value: str | None) -> float | None:
        if value in (None, ""):
            return None
        return float(value)

    available_chains = json.loads(row["available_chains"]) if row["available_chains"] else []
    listing_aliases = json.loads(row["listing_aliases"]) if row["listing_aliases"] else []
    source_product_ids = json.loads(row["source_product_ids"]) if row["source_product_ids"] else []
    source_skus = json.loads(row["source_skus"]) if row["source_skus"] else []
    available_chain_count = int(row["available_chain_count"] or 0)
    chain_label = (
        f"{available_chain_count} cadena"
        if available_chain_count == 1
        else f"{available_chain_count} cadenas"
    )

    return {
        "product_key": int(row["product_key"]),
        "chain": "",
        "product_id": row["source_product_id"] or row["gtin_norm"] or "",
        "sku": row["source_sku"] or "",
        "name": row["product_name"] or "",
        "brand": row["brand_name"] or "",
        "ean": row["gtin_norm"] or None,
        "price": maybe_number(row["price_amount"]),
        "list_price": maybe_number(row["list_price_amount"]),
        "has_discount": _parse_bool_text(row["has_discount"]),
        "unit": row["content_unit"] or None,
        "quantity": maybe_number(row["content_quantity"]),
        "category": row["category"] or "",
        "link": row["product_url"] or None,
        "image": row["image_url"] or None,
        "pricing_scope": "comparative",
        "available_chain_count": available_chain_count,
        "available_chains": available_chains,
        "aliases": {
            "listing_names": listing_aliases,
            "source_product_ids": source_product_ids,
            "source_skus": source_skus,
        },
        "_catalogId": "all",
        "_catalogLabel": chain_label,
        "_catalogShortLabel": chain_label,
        "_catalogSource": "/api/product-catalog",
        "_searchIndex": "",
    }


def fetch_product_catalog_from_db(*, force_refresh: bool = False) -> dict[str, Any]:
    if not force_refresh:
        cached = PRODUCT_CATALOG_CACHE.get()
        if cached is not None:
            return cached

    env = parse_env()
    chains = [
        {
            "chain_id": row["chain_id"],
            "label": row["chain_name"],
            "shortLabel": row["short_label"],
        }
        for row in _load_active_chains(env)
    ]
    products = [_normalize_catalog_product(row) for row in _load_product_catalog_rows(env)]
    payload = {
        "products": products,
        "chains": chains,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    PRODUCT_CATALOG_CACHE.set(payload)
    return payload


def _resolve_product_identity(
    env: dict[str, str],
    *,
    product_key: int | None = None,
    ean: str | None = None,
) -> dict[str, Any] | None:
    conditions: list[str] = []
    if product_key is not None:
        conditions.append(f"product_key = {int(product_key)}")
    if ean:
        conditions.append(f"gtin_norm = '{_sql_literal(ean.strip())}'")
    if not conditions:
        return None

    output = run_psql(
        env,
        sql=f"""
copy (
  select
    product_key::text as product_key,
    gtin_norm,
    brand_name,
    product_name,
    content_quantity::text as content_quantity,
    content_unit
  from public.mkt_dim_product
  where {' or '.join(conditions)}
  order by product_key
  limit 1
) to stdout with (format csv, header true);
""",
    )
    rows = _parse_copy_csv(output)
    if not rows:
        return None

    row = rows[0]
    return {
        "product_key": int(row["product_key"]),
        "name": row["product_name"] or "",
        "brand": row["brand_name"] or "",
        "ean": row["gtin_norm"] or None,
        "quantity": float(row["content_quantity"]) if row["content_quantity"] else None,
        "unit": row["content_unit"] or None,
    }


def _load_product_comparison_rows(env: dict[str, str], *, product_key: int) -> list[dict[str, str]]:
    output = run_psql(
        env,
        sql=f"""
copy (
  with latest_runs as (
    select distinct on (v.chain_key)
      v.run_key,
      v.chain_key
    from public.mw_fact_comparative_listing_snapshot as v
    join public.mkt_dim_chain as c
      on c.chain_key = v.chain_key
    where c.is_active = true
    order by v.chain_key, v.run_started_at desc, v.run_key desc
  ),
  ranked as (
    select
      v.chain_id,
      v.chain_name,
      v.chain_short_label as short_label,
      v.run_key,
      v.pricing_scope,
      v.run_started_at::text as run_started_at,
      v.run_finished_at::text as run_finished_at,
      v.source_product_id,
      v.source_sku,
      v.seller_id,
      v.seller_name,
      v.listing_name,
      v.product_url,
      v.image_url,
      coalesce(v.root_category_name, v.root_category_slug, '') as category,
      v.price_amount::text as price_amount,
      v.list_price_amount::text as list_price_amount,
      v.has_discount::text as has_discount,
      v.available_quantity::text as available_quantity,
      v.currency_code,
      row_number() over (
        partition by v.chain_key
        order by (v.price_amount is null), v.price_amount, v.listing_key
      ) as chain_rank
    from latest_runs as r
    join public.mw_fact_comparative_listing_snapshot as v
      on v.run_key = r.run_key
     and v.product_key = {int(product_key)}
  )
  select
    chain_id,
    chain_name,
    short_label,
    run_key::text as run_key,
    pricing_scope,
    run_started_at,
    run_finished_at,
    source_product_id,
    source_sku,
    seller_id,
    seller_name,
    listing_name,
    product_url,
    image_url,
    category,
    price_amount,
    list_price_amount,
    has_discount,
    available_quantity,
    currency_code
  from ranked
  where chain_rank = 1
  order by chain_id
) to stdout with (format csv, header true);
""",
    )
    return _parse_copy_csv(output)


def _normalize_comparison_match(
    row: dict[str, str],
    *,
    product: dict[str, Any],
) -> dict[str, Any]:
    def maybe_number(value: str | None) -> float | None:
        if value in (None, ""):
            return None
        return float(value)

    return {
        "product_key": product["product_key"],
        "chain": row["chain_id"],
        "product_id": row["source_product_id"] or product["ean"] or "",
        "sku": row["source_sku"] or "",
        "name": row["listing_name"] or product["name"],
        "brand": product["brand"] or "",
        "ean": product["ean"],
        "price": maybe_number(row["price_amount"]),
        "list_price": maybe_number(row["list_price_amount"]),
        "has_discount": _parse_bool_text(row["has_discount"]),
        "unit": product["unit"],
        "quantity": product["quantity"],
        "category": row["category"] or "",
        "link": row["product_url"] or None,
        "image": row["image_url"] or None,
        "pricing_scope": row["pricing_scope"] or None,
        "_catalogId": row["chain_id"],
        "_catalogLabel": row["chain_name"],
        "_catalogShortLabel": row["short_label"],
        "_catalogSource": "/api/product-comparison",
        "_generatedAt": row["run_finished_at"] or row["run_started_at"] or None,
        "_searchIndex": "",
    }


def fetch_product_comparison_from_db(
    *,
    product_key: int | None = None,
    ean: str | None = None,
) -> dict[str, Any]:
    env = parse_env()
    product = _resolve_product_identity(env, product_key=product_key, ean=ean)
    if product is None:
        raise RuntimeError("No encontré el producto solicitado en mkt_dim_product.")

    matches = [
        _normalize_comparison_match(row, product=product)
        for row in _load_product_comparison_rows(env, product_key=product["product_key"])
    ]
    return {
        "product": product,
        "matches": matches,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
