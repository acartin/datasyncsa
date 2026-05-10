#!/usr/bin/env python3
"""Transform y load de snapshots desde stage de catálogo."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from etl.postgres_cli import run_psql
from etl.stage_product_transform import resolve_stage_run_keys


@dataclass(frozen=True)
class StageSnapshotSourceRow:
    source_stage_catalog_item_key: int
    stage_catalog_run_key: int
    business_date_key: int
    chain_key: int
    location_key: int | None
    chain_id: str
    source_product_id: str
    source_sku: str
    seller_id: str
    seller_name: str | None
    listing_name: str
    source_gtin: str | None
    snapshot_ts: str
    currency_code: str | None
    has_discount: bool
    price_amount: str | None
    list_price_amount: str | None
    price_without_discount_amount: str | None
    spot_price_amount: str | None
    available_quantity: str | None
    price_valid_until_text: str | None
    listing_key: int | None
    product_key: int | None


@dataclass(frozen=True)
class ListingSnapshotCandidate:
    source_stage_catalog_item_key: int
    stage_catalog_run_key: int
    date_key: int
    chain_key: int
    location_key: int | None
    product_key: int
    listing_key: int
    snapshot_ts: str
    currency_code: str | None
    is_listed: bool
    is_available: bool | None
    has_discount: bool
    price_amount: str | None
    list_price_amount: str | None
    price_without_discount_amount: str | None
    spot_price_amount: str | None
    available_quantity: str | None
    price_valid_until_text: str | None


@dataclass(frozen=True)
class ListingSnapshotReview:
    review_reason: str
    source_stage_catalog_item_key: int
    stage_catalog_run_key: int
    chain_key: int
    source_product_id: str
    source_sku: str
    seller_id: str
    seller_name: str | None
    sample_listing_name: str
    source_gtin: str | None
    snapshot_ts: str
    review_payload: dict[str, Any]


@dataclass(frozen=True)
class ListingSnapshotTransformResult:
    stage_run_keys: list[int]
    stage_rows_read: int
    candidate_rows: list[ListingSnapshotCandidate]
    review_rows: list[ListingSnapshotReview]


@dataclass(frozen=True)
class ListingSnapshotStageWriteSummary:
    candidate_count: int
    review_count: int


@dataclass(frozen=True)
class ListingSnapshotLoadSummary:
    candidate_count: int
    loaded_rows: int
    fact_total: int
    truncated_first: bool


def flatten_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.replace("\r", " ").replace("\n", " ")
    text = " ".join(text.split()).strip()
    return text or None


def _parse_copy_csv(output: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(output))
    return [dict(row) for row in reader]


def parse_decimal_text(value: str | None) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return None


def derive_is_available(available_quantity: str | None) -> bool | None:
    quantity = parse_decimal_text(available_quantity)
    if quantity is None:
        return None
    return quantity > 0


def fetch_stage_snapshot_source_rows(
    env: dict[str, str],
    *,
    stage_run_keys: Iterable[int],
) -> list[StageSnapshotSourceRow]:
    run_keys = sorted({int(run_key) for run_key in stage_run_keys})
    if not run_keys:
        raise RuntimeError("Debes indicar al menos una stage run para transformar snapshots.")

    run_keys_sql = ", ".join(str(run_key) for run_key in run_keys)
    output = run_psql(
        env,
        sql=f"""
copy (
  select
    i.stage_catalog_item_key,
    i.run_key as stage_catalog_run_key,
    r.business_date_key,
    i.chain_key,
    r.location_key,
    c.chain_id,
    i.source_product_id,
    i.source_sku,
    coalesce(i.seller_id, '') as seller_id,
    i.seller_name,
    i.product_name,
    i.source_gtin,
    coalesce(r.finished_at, r.started_at)::text as snapshot_ts,
    i.currency_code,
    i.has_discount::text as has_discount,
    i.price_amount::text as price_amount,
    i.list_price_amount::text as list_price_amount,
    i.price_without_discount_amount::text as price_without_discount_amount,
    i.spot_price_amount::text as spot_price_amount,
    i.available_quantity::text as available_quantity,
    i.price_valid_until_text,
    l.listing_key::text as listing_key,
    l.product_key::text as product_key
  from public.mkt_stage_catalog_item as i
  join public.mkt_run as r
    on r.run_key = i.run_key
  join public.mkt_dim_chain as c
    on c.chain_key = i.chain_key
  left join public.mkt_dim_listing as l
    on l.chain_key = i.chain_key
   and l.source_product_id = i.source_product_id
   and l.source_sku = i.source_sku
   and l.seller_id = coalesce(i.seller_id, '')
  where i.run_key in ({run_keys_sql})
  order by i.run_key, i.catalog_row_number
) to stdout with (format csv, header true);
""",
    )

    rows: list[StageSnapshotSourceRow] = []
    for payload in _parse_copy_csv(output):
        rows.append(
            StageSnapshotSourceRow(
                source_stage_catalog_item_key=int(payload["stage_catalog_item_key"]),
                stage_catalog_run_key=int(payload["stage_catalog_run_key"]),
                business_date_key=int(payload["business_date_key"]),
                chain_key=int(payload["chain_key"]),
                location_key=int(payload["location_key"]) if payload["location_key"] else None,
                chain_id=payload["chain_id"].strip(),
                source_product_id=payload["source_product_id"].strip(),
                source_sku=payload["source_sku"].strip(),
                seller_id=(payload["seller_id"] or "").strip(),
                seller_name=flatten_text(payload["seller_name"]),
                listing_name=flatten_text(payload["product_name"]) or "SIN_NOMBRE",
                source_gtin=flatten_text(payload["source_gtin"]),
                snapshot_ts=payload["snapshot_ts"].strip(),
                currency_code=flatten_text(payload["currency_code"]),
                has_discount=payload["has_discount"] == "t",
                price_amount=flatten_text(payload["price_amount"]),
                list_price_amount=flatten_text(payload["list_price_amount"]),
                price_without_discount_amount=flatten_text(
                    payload["price_without_discount_amount"]
                ),
                spot_price_amount=flatten_text(payload["spot_price_amount"]),
                available_quantity=flatten_text(payload["available_quantity"]),
                price_valid_until_text=flatten_text(payload["price_valid_until_text"]),
                listing_key=int(payload["listing_key"]) if payload["listing_key"] else None,
                product_key=int(payload["product_key"]) if payload["product_key"] else None,
            )
        )
    return rows


def build_listing_snapshot_transform_result(
    rows: list[StageSnapshotSourceRow],
    *,
    stage_run_keys: Iterable[int],
) -> ListingSnapshotTransformResult:
    candidates: list[ListingSnapshotCandidate] = []
    reviews: list[ListingSnapshotReview] = []

    for row in rows:
        if row.listing_key is None or row.product_key is None:
            reviews.append(
                ListingSnapshotReview(
                    review_reason="missing_listing_match",
                    source_stage_catalog_item_key=row.source_stage_catalog_item_key,
                    stage_catalog_run_key=row.stage_catalog_run_key,
                    chain_key=row.chain_key,
                    source_product_id=row.source_product_id,
                    source_sku=row.source_sku,
                    seller_id=row.seller_id,
                    seller_name=row.seller_name,
                    sample_listing_name=row.listing_name,
                    source_gtin=row.source_gtin,
                    snapshot_ts=row.snapshot_ts,
                    review_payload={
                        "chain_id": row.chain_id,
                        "source_product_id": row.source_product_id,
                        "source_sku": row.source_sku,
                        "seller_id": row.seller_id,
                        "seller_name": row.seller_name,
                        "source_gtin": row.source_gtin,
                    },
                )
            )
            continue

        candidates.append(
            ListingSnapshotCandidate(
                source_stage_catalog_item_key=row.source_stage_catalog_item_key,
                stage_catalog_run_key=row.stage_catalog_run_key,
                date_key=row.business_date_key,
                chain_key=row.chain_key,
                location_key=row.location_key,
                product_key=row.product_key,
                listing_key=row.listing_key,
                snapshot_ts=row.snapshot_ts,
                currency_code=row.currency_code,
                is_listed=True,
                is_available=derive_is_available(row.available_quantity),
                has_discount=row.has_discount,
                price_amount=row.price_amount,
                list_price_amount=row.list_price_amount,
                price_without_discount_amount=row.price_without_discount_amount,
                spot_price_amount=row.spot_price_amount,
                available_quantity=row.available_quantity,
                price_valid_until_text=row.price_valid_until_text,
            )
        )

    return ListingSnapshotTransformResult(
        stage_run_keys=sorted({int(run_key) for run_key in stage_run_keys}),
        stage_rows_read=len(rows),
        candidate_rows=candidates,
        review_rows=reviews,
    )


def replace_stage_listing_snapshot_transform_tables(
    env: dict[str, str],
    result: ListingSnapshotTransformResult,
) -> ListingSnapshotStageWriteSummary:
    candidate_csv = io.StringIO()
    candidate_writer = csv.DictWriter(
        candidate_csv,
        fieldnames=[
            "source_stage_catalog_item_key",
            "stage_catalog_run_key",
            "date_key",
            "chain_key",
            "location_key",
            "product_key",
            "listing_key",
            "snapshot_ts",
            "currency_code",
            "is_listed",
            "is_available",
            "has_discount",
            "price_amount",
            "list_price_amount",
            "price_without_discount_amount",
            "spot_price_amount",
            "available_quantity",
            "price_valid_until_text",
        ],
        lineterminator="\n",
    )
    candidate_writer.writeheader()
    for row in result.candidate_rows:
        candidate_writer.writerow(
            {
                "source_stage_catalog_item_key": row.source_stage_catalog_item_key,
                "stage_catalog_run_key": row.stage_catalog_run_key,
                "date_key": row.date_key,
                "chain_key": row.chain_key,
                "location_key": row.location_key,
                "product_key": row.product_key,
                "listing_key": row.listing_key,
                "snapshot_ts": row.snapshot_ts,
                "currency_code": row.currency_code,
                "is_listed": row.is_listed,
                "is_available": row.is_available,
                "has_discount": row.has_discount,
                "price_amount": row.price_amount,
                "list_price_amount": row.list_price_amount,
                "price_without_discount_amount": row.price_without_discount_amount,
                "spot_price_amount": row.spot_price_amount,
                "available_quantity": row.available_quantity,
                "price_valid_until_text": row.price_valid_until_text,
            }
        )

    review_csv = io.StringIO()
    review_writer = csv.DictWriter(
        review_csv,
        fieldnames=[
            "review_reason",
            "source_stage_catalog_item_key",
            "stage_catalog_run_key",
            "chain_key",
            "source_product_id",
            "source_sku",
            "seller_id",
            "seller_name",
            "sample_listing_name",
            "source_gtin",
            "snapshot_ts",
            "review_payload",
        ],
        lineterminator="\n",
    )
    review_writer.writeheader()
    for row in result.review_rows:
        review_writer.writerow(
            {
                "review_reason": row.review_reason,
                "source_stage_catalog_item_key": row.source_stage_catalog_item_key,
                "stage_catalog_run_key": row.stage_catalog_run_key,
                "chain_key": row.chain_key,
                "source_product_id": row.source_product_id,
                "source_sku": row.source_sku,
                "seller_id": row.seller_id,
                "seller_name": row.seller_name,
                "sample_listing_name": row.sample_listing_name,
                "source_gtin": row.source_gtin,
                "snapshot_ts": row.snapshot_ts,
                "review_payload": json.dumps(row.review_payload, ensure_ascii=False),
            }
        )

    sql = f"""
begin;
truncate table public.mkt_stage_listing_snapshot_candidate restart identity;
truncate table public.mkt_stage_listing_snapshot_review restart identity;

create temp table tmp_stage_listing_snapshot_candidate_load (
  source_stage_catalog_item_key bigint,
  stage_catalog_run_key bigint,
  date_key integer,
  chain_key integer,
  location_key bigint,
  product_key bigint,
  listing_key bigint,
  snapshot_ts timestamptz,
  currency_code char(3),
  is_listed boolean,
  is_available boolean,
  has_discount boolean,
  price_amount numeric(12,2),
  list_price_amount numeric(12,2),
  price_without_discount_amount numeric(12,2),
  spot_price_amount numeric(12,2),
  available_quantity numeric(14,3),
  price_valid_until_text text
);

copy tmp_stage_listing_snapshot_candidate_load (
  source_stage_catalog_item_key,
  stage_catalog_run_key,
  date_key,
  chain_key,
  location_key,
  product_key,
  listing_key,
  snapshot_ts,
  currency_code,
  is_listed,
  is_available,
  has_discount,
  price_amount,
  list_price_amount,
  price_without_discount_amount,
  spot_price_amount,
  available_quantity,
  price_valid_until_text
) from stdin with (format csv, header true);
{candidate_csv.getvalue()}\\.

insert into public.mkt_stage_listing_snapshot_candidate (
  source_stage_catalog_item_key,
  run_key,
  date_key,
  chain_key,
  location_key,
  product_key,
  listing_key,
  snapshot_ts,
  currency_code,
  is_listed,
  is_available,
  has_discount,
  price_amount,
  list_price_amount,
  price_without_discount_amount,
  spot_price_amount,
  available_quantity,
  price_valid_until_text
)
select
  source_stage_catalog_item_key,
  stage_catalog_run_key,
  date_key,
  chain_key,
  location_key,
  product_key,
  listing_key,
  snapshot_ts,
  currency_code,
  is_listed,
  is_available,
  has_discount,
  price_amount,
  list_price_amount,
  price_without_discount_amount,
  spot_price_amount,
  available_quantity,
  price_valid_until_text
from tmp_stage_listing_snapshot_candidate_load;

create temp table tmp_stage_listing_snapshot_review_load (
  review_reason text,
  source_stage_catalog_item_key bigint,
  stage_catalog_run_key bigint,
  chain_key integer,
  source_product_id text,
  source_sku text,
  seller_id text,
  seller_name text,
  sample_listing_name text,
  source_gtin text,
  snapshot_ts timestamptz,
  review_payload jsonb
);

copy tmp_stage_listing_snapshot_review_load (
  review_reason,
  source_stage_catalog_item_key,
  stage_catalog_run_key,
  chain_key,
  source_product_id,
  source_sku,
  seller_id,
  seller_name,
  sample_listing_name,
  source_gtin,
  snapshot_ts,
  review_payload
) from stdin with (format csv, header true);
{review_csv.getvalue()}\\.

insert into public.mkt_stage_listing_snapshot_review (
  review_reason,
  source_stage_catalog_item_key,
  run_key,
  chain_key,
  source_product_id,
  source_sku,
  seller_id,
  seller_name,
  sample_listing_name,
  source_gtin,
  snapshot_ts,
  review_payload
)
select
  review_reason,
  source_stage_catalog_item_key,
  stage_catalog_run_key,
  chain_key,
  source_product_id,
  source_sku,
  seller_id,
  seller_name,
  sample_listing_name,
  source_gtin,
  snapshot_ts,
  review_payload
from tmp_stage_listing_snapshot_review_load;

select
  (select count(*) from public.mkt_stage_listing_snapshot_candidate),
  (select count(*) from public.mkt_stage_listing_snapshot_review);
commit;
"""

    output = run_psql(env, sql=sql, tuples_only=True)
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError(
            "No pude confirmar la escritura de mkt_stage_listing_snapshot_candidate/review."
        )
    candidate_count_text, review_count_text = lines[-1].split("\t", 1)
    return ListingSnapshotStageWriteSummary(
        candidate_count=int(candidate_count_text),
        review_count=int(review_count_text),
    )


def load_stage_listing_snapshot_candidates_into_fact(
    env: dict[str, str],
    *,
    truncate_first: bool = False,
) -> ListingSnapshotLoadSummary:
    sql_lines = ["begin;"]
    if truncate_first:
        sql_lines.append("truncate table public.mkt_fact_listing_snapshot;")

    sql_lines.append(
        """
create temp table tmp_fact_listing_snapshot_upsert_result as
with upserted as (
  insert into public.mkt_fact_listing_snapshot (
    date_key,
    run_key,
    chain_key,
    location_key,
    product_key,
    listing_key,
    source_stage_catalog_item_key,
    snapshot_ts,
    currency_code,
    is_listed,
    is_available,
    has_discount,
    price_amount,
    list_price_amount,
    price_without_discount_amount,
    spot_price_amount,
    available_quantity,
    price_valid_until_text
  )
  select
    date_key,
    run_key,
    chain_key,
    location_key,
    product_key,
    listing_key,
    source_stage_catalog_item_key,
    snapshot_ts,
    currency_code,
    is_listed,
    is_available,
    has_discount,
    price_amount,
    list_price_amount,
    price_without_discount_amount,
    spot_price_amount,
    available_quantity,
    price_valid_until_text
  from public.mkt_stage_listing_snapshot_candidate
  on conflict (date_key, run_key, listing_key)
  do update
  set
    chain_key = excluded.chain_key,
    location_key = excluded.location_key,
    product_key = excluded.product_key,
    source_stage_catalog_item_key = excluded.source_stage_catalog_item_key,
    snapshot_ts = excluded.snapshot_ts,
    currency_code = excluded.currency_code,
    is_listed = excluded.is_listed,
    is_available = excluded.is_available,
    has_discount = excluded.has_discount,
    price_amount = excluded.price_amount,
    list_price_amount = excluded.list_price_amount,
    price_without_discount_amount = excluded.price_without_discount_amount,
    spot_price_amount = excluded.spot_price_amount,
    available_quantity = excluded.available_quantity,
    price_valid_until_text = excluded.price_valid_until_text
  returning 1
)
select
  (select count(*) from upserted) as loaded_rows;
"""
    )
    sql_lines.append(
        """
select
  (select count(*) from public.mkt_stage_listing_snapshot_candidate),
  (select coalesce(sum(loaded_rows), 0) from tmp_fact_listing_snapshot_upsert_result),
  (select count(*) from public.mkt_fact_listing_snapshot);
"""
    )
    sql_lines.append("commit;")

    output = run_psql(env, sql="\n".join(sql_lines), tuples_only=True)
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("No pude confirmar la carga hacia mkt_fact_listing_snapshot.")
    candidate_count_text, loaded_rows_text, fact_total_text = lines[-1].split("\t", 2)
    return ListingSnapshotLoadSummary(
        candidate_count=int(candidate_count_text),
        loaded_rows=int(loaded_rows_text),
        fact_total=int(fact_total_text),
        truncated_first=truncate_first,
    )
