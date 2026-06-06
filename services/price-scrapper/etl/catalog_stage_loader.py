#!/usr/bin/env python3
"""Carga catalogos canonicos scrapeados en tablas stage de Postgres."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.business_date import business_date_key_from_iso
from etl.postgres_cli import parse_env, run_psql


def flatten_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.replace("\r", " ").replace("\n", " ")
    text = " ".join(text.split()).strip()
    return text or None


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def last_non_empty_line(value: str) -> str:
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("La salida de psql no devolvio filas utilizables.")
    return lines[-1]


def build_stage_run_row(
    *,
    chain_id: str,
    metadata: dict[str, Any],
    debug_output_dir: Path | None,
    run_kind: str,
    business_date_key: int,
    location_key: int | None = None,
    campaign_id: int | None = None,
) -> dict[str, Any]:
    return {
        "chain_id": chain_id,
        "run_kind": run_kind,
        "business_date_key": business_date_key,
        "location_key": location_key,
        "campaign_id": campaign_id,
        "source_engine": str(metadata.get("engine") or "").strip(),
        "pricing_scope": str(metadata.get("pricing_scope") or "").strip(),
        "catalog_id": flatten_text(str(metadata.get("catalog_id") or "")) or None,
        "run_status": "succeeded",
        "started_at": metadata.get("started_at"),
        "finished_at": metadata.get("finished_at"),
        "elapsed_seconds": metadata.get("elapsed_seconds"),
        "catalog_records": metadata.get("catalog_records") or 0,
        "unique_products": metadata.get("unique_products"),
        "duplicates_skipped": metadata.get("duplicates_skipped") or 0,
        "debug_output_dir": str(debug_output_dir) if debug_output_dir else None,
        "error_message": None,
        "raw_metadata": json_text(metadata),
    }


def build_failed_stage_run_row(
    *,
    chain_id: str,
    engine: str,
    pricing_scope: str,
    started_at: str,
    error_message: str,
    run_kind: str,
    business_date_key: int,
    location_key: int | None = None,
    campaign_id: int | None = None,
    raw_metadata: dict[str, Any] | None = None,
    debug_output_dir: Path | None = None,
) -> dict[str, Any]:
    finished_at = now_utc_iso()
    return {
        "chain_id": chain_id,
        "run_kind": run_kind,
        "business_date_key": business_date_key,
        "location_key": location_key,
        "campaign_id": campaign_id,
        "source_engine": engine,
        "pricing_scope": pricing_scope,
        "catalog_id": None,
        "run_status": "failed",
        "started_at": started_at,
        "finished_at": finished_at,
        "elapsed_seconds": None,
        "catalog_records": 0,
        "unique_products": 0,
        "duplicates_skipped": 0,
        "debug_output_dir": str(debug_output_dir) if debug_output_dir else None,
        "error_message": flatten_text(error_message),
        "raw_metadata": json_text(raw_metadata or {}),
    }


def build_stage_item_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        identity = record.get("identity") or {}
        taxonomy = record.get("taxonomy") or {}
        content = record.get("content") or {}
        measurement = record.get("measurement") or {}
        pricing = record.get("pricing") or {}
        availability = record.get("availability") or {}
        root_categories = taxonomy.get("root_categories") or []
        first_root = root_categories[0] if root_categories else {}

        product_name = (
            flatten_text(content.get("name"))
            or flatten_text(str(identity.get("sku") or identity.get("product_id") or ""))
            or "SIN_NOMBRE"
        )

        rows.append(
            {
                "catalog_row_number": index,
                "catalog_id": flatten_text(record.get("catalog_id")),
                "pricing_scope": flatten_text(record.get("pricing_scope")),
                "source_product_id": flatten_text(str(identity.get("product_id") or "")),
                "source_sku": flatten_text(str(identity.get("sku") or "")),
                "source_gtin": flatten_text(identity.get("ean")),
                "product_reference": flatten_text(identity.get("product_reference")),
                "reference_id": flatten_text(identity.get("reference_id")),
                "brand_name": flatten_text(identity.get("brand")),
                "brand_id": flatten_text(identity.get("brand_id")),
                "seller_id": flatten_text(identity.get("seller_id")),
                "seller_name": flatten_text(identity.get("seller_name")),
                "root_category_slug": flatten_text(first_root.get("slug")),
                "root_category_name": flatten_text(first_root.get("name")),
                "category_id": flatten_text(taxonomy.get("category_id")),
                "category_path": flatten_text(taxonomy.get("category_path")),
                "raw_categories": json_text(taxonomy.get("raw_categories") or []),
                "product_name": product_name,
                "product_description": flatten_text(content.get("description")),
                "product_url": flatten_text(content.get("link")),
                "image_url": flatten_text(content.get("image")),
                "quantity": measurement.get("quantity"),
                "unit": flatten_text(measurement.get("unit")),
                "measurement_unit": flatten_text(measurement.get("measurement_unit")),
                "unit_multiplier": measurement.get("unit_multiplier"),
                "currency_code": flatten_text(pricing.get("currency")),
                "price_amount": pricing.get("price"),
                "list_price_amount": pricing.get("list_price"),
                "price_without_discount_amount": pricing.get("price_without_discount"),
                "spot_price_amount": pricing.get("spot_price"),
                "has_discount": bool(pricing.get("has_discount")),
                "price_valid_until_text": flatten_text(pricing.get("price_valid_until")),
                "available_quantity": availability.get("available_quantity"),
                "raw_payload": json_text(record),
            }
        )
    return rows


def load_successful_catalog_stage_run(
    *,
    chain_id: str,
    metadata: dict[str, Any],
    records: list[dict[str, Any]],
    run_kind: str = "comparative",
    business_date_key: int | None = None,
    location_key: int | None = None,
    campaign_id: int | None = None,
    debug_output_dir: Path | None = None,
) -> tuple[int, int]:
    env = parse_env()
    effective_business_date_key = (
        int(business_date_key)
        if business_date_key is not None
        else business_date_key_from_iso(str(metadata.get("started_at") or metadata.get("finished_at")))
    )
    run_row = build_stage_run_row(
        chain_id=chain_id,
        metadata=metadata,
        debug_output_dir=debug_output_dir,
        run_kind=run_kind,
        business_date_key=effective_business_date_key,
        location_key=location_key,
        campaign_id=campaign_id,
    )
    item_rows = build_stage_item_rows(records)

    run_csv = io.StringIO()
    run_writer = csv.DictWriter(
        run_csv,
        fieldnames=[
            "chain_id",
            "run_kind",
            "business_date_key",
            "location_key",
            "campaign_id",
            "source_engine",
            "pricing_scope",
            "catalog_id",
            "run_status",
            "started_at",
            "finished_at",
            "elapsed_seconds",
            "catalog_records",
            "unique_products",
            "duplicates_skipped",
            "debug_output_dir",
            "error_message",
            "raw_metadata",
        ],
        lineterminator="\n",
    )
    run_writer.writeheader()
    run_writer.writerow(run_row)

    item_csv = io.StringIO()
    item_writer = csv.DictWriter(
        item_csv,
        fieldnames=[
            "catalog_row_number",
            "catalog_id",
            "pricing_scope",
            "source_product_id",
            "source_sku",
            "source_gtin",
            "product_reference",
            "reference_id",
            "brand_name",
            "brand_id",
            "seller_id",
            "seller_name",
            "root_category_slug",
            "root_category_name",
            "category_id",
            "category_path",
            "raw_categories",
            "product_name",
            "product_description",
            "product_url",
            "image_url",
            "quantity",
            "unit",
            "measurement_unit",
            "unit_multiplier",
            "currency_code",
            "price_amount",
            "list_price_amount",
            "price_without_discount_amount",
            "spot_price_amount",
            "has_discount",
            "price_valid_until_text",
            "available_quantity",
            "raw_payload",
        ],
        lineterminator="\n",
    )
    item_writer.writeheader()
    for row in item_rows:
        item_writer.writerow(row)

    sql = f"""
begin;
create temp table tmp_mkt_run_load (
  chain_id text,
  run_kind text,
  business_date_key integer,
  location_key bigint,
  campaign_id bigint,
  source_engine text,
  pricing_scope text,
  catalog_id text,
  run_status text,
  started_at timestamptz,
  finished_at timestamptz,
  elapsed_seconds numeric(12,3),
  catalog_records integer,
  unique_products integer,
  duplicates_skipped integer,
  debug_output_dir text,
  error_message text,
  raw_metadata jsonb
);

copy tmp_mkt_run_load (
  chain_id,
  run_kind,
  business_date_key,
  location_key,
  campaign_id,
  source_engine,
  pricing_scope,
  catalog_id,
  run_status,
  started_at,
  finished_at,
  elapsed_seconds,
  catalog_records,
  unique_products,
  duplicates_skipped,
  debug_output_dir,
  error_message,
  raw_metadata
) from stdin with (format csv, header true);
{run_csv.getvalue()}\\.

create temp table tmp_mkt_stage_catalog_item_load (
  catalog_row_number integer,
  catalog_id text,
  pricing_scope text,
  source_product_id text,
  source_sku text,
  source_gtin text,
  product_reference text,
  reference_id text,
  brand_name text,
  brand_id text,
  seller_id text,
  seller_name text,
  root_category_slug text,
  root_category_name text,
  category_id text,
  category_path text,
  raw_categories jsonb,
  product_name text,
  product_description text,
  product_url text,
  image_url text,
  quantity numeric(14,4),
  unit text,
  measurement_unit text,
  unit_multiplier numeric(14,4),
  currency_code char(3),
  price_amount numeric(12,2),
  list_price_amount numeric(12,2),
  price_without_discount_amount numeric(12,2),
  spot_price_amount numeric(12,2),
  has_discount boolean,
  price_valid_until_text text,
  available_quantity numeric(14,3),
  raw_payload jsonb
);

copy tmp_mkt_stage_catalog_item_load (
  catalog_row_number,
  catalog_id,
  pricing_scope,
  source_product_id,
  source_sku,
  source_gtin,
  product_reference,
  reference_id,
  brand_name,
  brand_id,
  seller_id,
  seller_name,
  root_category_slug,
  root_category_name,
  category_id,
  category_path,
  raw_categories,
  product_name,
  product_description,
  product_url,
  image_url,
  quantity,
  unit,
  measurement_unit,
  unit_multiplier,
  currency_code,
  price_amount,
  list_price_amount,
  price_without_discount_amount,
  spot_price_amount,
  has_discount,
  price_valid_until_text,
  available_quantity,
  raw_payload
) from stdin with (format csv, header true);
{item_csv.getvalue()}\\.

create temp table tmp_inserted_run as
with inserted_run as (
  insert into public.mkt_run (
    chain_key,
    location_key,
    run_kind,
    business_date_key,
    campaign_id,
    source_engine,
    pricing_scope,
    catalog_id,
    run_status,
    started_at,
    finished_at,
    elapsed_seconds,
    catalog_records,
    unique_products,
    duplicates_skipped,
    debug_output_dir,
    error_message,
    raw_metadata
  )
  select
    c.chain_key,
    t.location_key,
    t.run_kind,
    t.business_date_key,
    t.campaign_id,
    t.source_engine,
    t.pricing_scope,
    t.catalog_id,
    t.run_status,
    t.started_at,
    t.finished_at,
    t.elapsed_seconds,
    t.catalog_records,
    t.unique_products,
    t.duplicates_skipped,
    t.debug_output_dir,
    t.error_message,
    t.raw_metadata
  from tmp_mkt_run_load as t
  join public.mkt_dim_chain as c
    on c.chain_id = t.chain_id
  where not exists (
    select 1
    from public.mkt_run existing
    where existing.business_date_key = t.business_date_key
      and existing.run_kind = t.run_kind
      and existing.run_status = 'succeeded'
      and existing.chain_key = c.chain_key
      and coalesce(existing.location_key, -1) = coalesce(t.location_key, -1)
      and coalesce(existing.campaign_id, -1) = coalesce(t.campaign_id, -1)
  )
  returning run_key, chain_key
)
select * from inserted_run;

create temp table tmp_effective_run as
select run_key, chain_key, false as reused_existing
from tmp_inserted_run
union all
select existing.run_key, existing.chain_key, true as reused_existing
from tmp_mkt_run_load as t
join public.mkt_dim_chain as c
  on c.chain_id = t.chain_id
join public.mkt_run as existing
  on existing.business_date_key = t.business_date_key
 and existing.run_kind = t.run_kind
 and existing.run_status = 'succeeded'
 and existing.chain_key = c.chain_key
 and coalesce(existing.location_key, -1) = coalesce(t.location_key, -1)
 and coalesce(existing.campaign_id, -1) = coalesce(t.campaign_id, -1)
where not exists (select 1 from tmp_inserted_run)
limit 1;

insert into public.mkt_stage_catalog_item (
  run_key,
  chain_key,
  catalog_row_number,
  catalog_id,
  pricing_scope,
  source_product_id,
  source_sku,
  source_gtin,
  product_reference,
  reference_id,
  brand_name,
  brand_id,
  seller_id,
  seller_name,
  root_category_slug,
  root_category_name,
  category_id,
  category_path,
  raw_categories,
  product_name,
  product_description,
  product_url,
  image_url,
  quantity,
  unit,
  measurement_unit,
  unit_multiplier,
  currency_code,
  price_amount,
  list_price_amount,
  price_without_discount_amount,
  spot_price_amount,
  has_discount,
  price_valid_until_text,
  available_quantity,
  raw_payload
)
select
  r.run_key,
  r.chain_key,
  t.catalog_row_number,
  t.catalog_id,
  t.pricing_scope,
  t.source_product_id,
  t.source_sku,
  t.source_gtin,
  t.product_reference,
  t.reference_id,
  t.brand_name,
  t.brand_id,
  t.seller_id,
  t.seller_name,
  t.root_category_slug,
  t.root_category_name,
  t.category_id,
  t.category_path,
  t.raw_categories,
  t.product_name,
  t.product_description,
  t.product_url,
  t.image_url,
  t.quantity,
  t.unit,
  t.measurement_unit,
  t.unit_multiplier,
  t.currency_code,
  t.price_amount,
  t.list_price_amount,
  t.price_without_discount_amount,
  t.spot_price_amount,
  t.has_discount,
  t.price_valid_until_text,
  t.available_quantity,
  t.raw_payload
from tmp_mkt_stage_catalog_item_load as t
cross join tmp_inserted_run as r;

select
  r.run_key,
  case
    when r.reused_existing then 0
    else coalesce((
    select count(*)
    from public.mkt_stage_catalog_item as i
    where i.run_key = r.run_key
  ), 0)
  end as inserted_items
from tmp_effective_run as r;
commit;
"""

    output = run_psql(env, sql=sql, tuples_only=True)
    run_key, inserted_items = last_non_empty_line(output).split("\t", 1)
    return int(run_key), int(inserted_items)


def load_failed_catalog_stage_run(
    *,
    chain_id: str,
    engine: str,
    pricing_scope: str,
    started_at: str,
    error_message: str,
    run_kind: str = "comparative",
    business_date_key: int | None = None,
    location_key: int | None = None,
    campaign_id: int | None = None,
    raw_metadata: dict[str, Any] | None = None,
    debug_output_dir: Path | None = None,
) -> int:
    env = parse_env()
    run_row = build_failed_stage_run_row(
        chain_id=chain_id,
        engine=engine,
        pricing_scope=pricing_scope,
        started_at=started_at,
        error_message=error_message,
        run_kind=run_kind,
        business_date_key=(
            int(business_date_key)
            if business_date_key is not None
            else business_date_key_from_iso(started_at)
        ),
        location_key=location_key,
        campaign_id=campaign_id,
        raw_metadata=raw_metadata,
        debug_output_dir=debug_output_dir,
    )

    run_csv = io.StringIO()
    run_writer = csv.DictWriter(
        run_csv,
        fieldnames=[
            "chain_id",
            "run_kind",
            "business_date_key",
            "location_key",
            "campaign_id",
            "source_engine",
            "pricing_scope",
            "catalog_id",
            "run_status",
            "started_at",
            "finished_at",
            "elapsed_seconds",
            "catalog_records",
            "unique_products",
            "duplicates_skipped",
            "debug_output_dir",
            "error_message",
            "raw_metadata",
        ],
        lineterminator="\n",
    )
    run_writer.writeheader()
    run_writer.writerow(run_row)

    sql = f"""
begin;
create temp table tmp_mkt_run_load (
  chain_id text,
  run_kind text,
  business_date_key integer,
  location_key bigint,
  campaign_id bigint,
  source_engine text,
  pricing_scope text,
  catalog_id text,
  run_status text,
  started_at timestamptz,
  finished_at timestamptz,
  elapsed_seconds numeric(12,3),
  catalog_records integer,
  unique_products integer,
  duplicates_skipped integer,
  debug_output_dir text,
  error_message text,
  raw_metadata jsonb
);

copy tmp_mkt_run_load (
  chain_id,
  run_kind,
  business_date_key,
  location_key,
  campaign_id,
  source_engine,
  pricing_scope,
  catalog_id,
  run_status,
  started_at,
  finished_at,
  elapsed_seconds,
  catalog_records,
  unique_products,
  duplicates_skipped,
  debug_output_dir,
  error_message,
  raw_metadata
) from stdin with (format csv, header true);
{run_csv.getvalue()}\\.

create temp table tmp_inserted_run as
with inserted_run as (
  insert into public.mkt_run (
    chain_key,
    location_key,
    run_kind,
    business_date_key,
    campaign_id,
    source_engine,
    pricing_scope,
    catalog_id,
    run_status,
    started_at,
    finished_at,
    elapsed_seconds,
    catalog_records,
    unique_products,
    duplicates_skipped,
    debug_output_dir,
    error_message,
    raw_metadata
  )
  select
    c.chain_key,
    t.location_key,
    t.run_kind,
    t.business_date_key,
    t.campaign_id,
    t.source_engine,
    t.pricing_scope,
    t.catalog_id,
    t.run_status,
    t.started_at,
    t.finished_at,
    t.elapsed_seconds,
    t.catalog_records,
    t.unique_products,
    t.duplicates_skipped,
    t.debug_output_dir,
    t.error_message,
    t.raw_metadata
  from tmp_mkt_run_load as t
  join public.mkt_dim_chain as c
    on c.chain_id = t.chain_id
  returning run_key
)
select * from inserted_run;

select run_key
from tmp_inserted_run;
commit;
"""

    output = run_psql(env, sql=sql, tuples_only=True)
    return int(last_non_empty_line(output))
