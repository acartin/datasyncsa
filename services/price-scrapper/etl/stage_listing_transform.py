#!/usr/bin/env python3
"""Transform y load de listings desde stage de catálogo."""

from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

from etl.postgres_cli import run_psql
from etl.stage_product_transform import digits_only, resolve_stage_run_keys


@dataclass(frozen=True)
class StageListingRow:
    stage_catalog_item_key: int
    stage_catalog_run_key: int
    chain_key: int
    chain_id: str
    source_product_id: str
    source_sku: str
    seller_id: str
    seller_name: str | None
    listing_name: str
    product_url: str | None
    image_url: str | None
    root_category_slug: str | None
    root_category_name: str | None
    source_gtin: str | None
    gtin_norm: str | None


@dataclass(frozen=True)
class ListingCandidate:
    preferred_stage_catalog_item_key: int
    chain_key: int
    product_key: int
    source_product_id: str
    source_sku: str
    seller_id: str
    seller_name: str | None
    listing_name: str
    product_url: str | None
    image_url: str | None
    root_category_slug: str | None
    root_category_name: str | None
    source_row_count: int
    source_stage_catalog_run_keys: list[int]


@dataclass(frozen=True)
class ListingReview:
    review_reason: str
    chain_key: int
    source_product_id: str
    source_sku: str
    seller_id: str
    seller_name: str | None
    sample_listing_name: str
    source_row_count: int
    source_stage_catalog_run_keys: list[int]
    review_payload: dict[str, Any]


@dataclass(frozen=True)
class ListingTransformResult:
    stage_run_keys: list[int]
    stage_rows_read: int
    candidate_rows: list[ListingCandidate]
    review_rows: list[ListingReview]


@dataclass(frozen=True)
class ListingStageWriteSummary:
    candidate_count: int
    review_count: int


@dataclass(frozen=True)
class ListingLoadSummary:
    candidate_count: int
    loaded_rows: int
    dim_listing_total: int
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


def preferred_row(rows: list[StageListingRow]) -> StageListingRow:
    return sorted(
        rows,
        key=lambda row: (
            -row.stage_catalog_run_key,
            -row.stage_catalog_item_key,
            -(len(row.product_url or "")),
            -(len(row.image_url or "")),
        ),
    )[0]


def serialize_review_entries(rows: list[StageListingRow]) -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []
    for row in rows:
        serialized.append(
            {
                "stage_catalog_item_key": row.stage_catalog_item_key,
                "stage_catalog_run_key": row.stage_catalog_run_key,
                "chain_id": row.chain_id,
                "source_product_id": row.source_product_id,
                "source_sku": row.source_sku,
                "seller_id": row.seller_id,
                "seller_name": row.seller_name,
                "listing_name": row.listing_name,
                "source_gtin": row.source_gtin,
                "gtin_norm": row.gtin_norm,
                "product_url": row.product_url,
                "image_url": row.image_url,
                "root_category_slug": row.root_category_slug,
                "root_category_name": row.root_category_name,
            }
        )
    return serialized


def fetch_stage_listing_rows(
    env: dict[str, str],
    *,
    stage_run_keys: Iterable[int],
) -> list[StageListingRow]:
    run_keys = sorted({int(run_key) for run_key in stage_run_keys})
    if not run_keys:
        raise RuntimeError("Debes indicar al menos una stage run para transformar listings.")

    run_keys_sql = ", ".join(str(run_key) for run_key in run_keys)
    output = run_psql(
        env,
        sql=f"""
copy (
  select
    i.stage_catalog_item_key,
    i.run_key as stage_catalog_run_key,
    i.chain_key,
    c.chain_id,
    i.source_product_id,
    i.source_sku,
    coalesce(i.seller_id, '') as seller_id,
    i.seller_name,
    i.product_name,
    i.product_url,
    i.image_url,
    i.root_category_slug,
    i.root_category_name,
    i.source_gtin
  from public.mkt_stage_catalog_item as i
  join public.mkt_dim_chain as c
    on c.chain_key = i.chain_key
  where i.run_key in ({run_keys_sql})
  order by i.chain_key, i.run_key, i.stage_catalog_item_key
) to stdout with (format csv, header true);
""",
    )

    rows: list[StageListingRow] = []
    for payload in _parse_copy_csv(output):
        source_gtin = flatten_text(payload["source_gtin"])
        rows.append(
            StageListingRow(
                stage_catalog_item_key=int(payload["stage_catalog_item_key"]),
                stage_catalog_run_key=int(payload["stage_catalog_run_key"]),
                chain_key=int(payload["chain_key"]),
                chain_id=payload["chain_id"].strip(),
                source_product_id=payload["source_product_id"].strip(),
                source_sku=payload["source_sku"].strip(),
                seller_id=(payload["seller_id"] or "").strip(),
                seller_name=flatten_text(payload["seller_name"]),
                listing_name=flatten_text(payload["product_name"]) or "SIN_NOMBRE",
                product_url=flatten_text(payload["product_url"]),
                image_url=flatten_text(payload["image_url"]),
                root_category_slug=flatten_text(payload["root_category_slug"]),
                root_category_name=flatten_text(payload["root_category_name"]),
                source_gtin=source_gtin,
                gtin_norm=digits_only(source_gtin),
            )
        )
    return rows


def fetch_product_key_map(
    env: dict[str, str],
    *,
    gtin_norms: Iterable[str],
) -> dict[str, int]:
    norms = sorted({norm for norm in gtin_norms if norm})
    if not norms:
        return {}
    norms_sql = ", ".join("'" + norm.replace("'", "''") + "'" for norm in norms)
    output = run_psql(
        env,
        sql=f"""
copy (
  select gtin_norm, product_key
  from public.mkt_dim_product
  where gtin_norm in ({norms_sql})
) to stdout with (format csv, header true);
""",
    )
    mapping: dict[str, int] = {}
    for payload in _parse_copy_csv(output):
        mapping[payload["gtin_norm"]] = int(payload["product_key"])
    return mapping


def build_listing_transform_result(
    rows: list[StageListingRow],
    *,
    stage_run_keys: Iterable[int],
    product_key_by_gtin: dict[str, int],
) -> ListingTransformResult:
    grouped_rows: dict[tuple[int, str, str, str], list[StageListingRow]] = defaultdict(list)
    for row in rows:
        group_key = (row.chain_key, row.source_product_id, row.source_sku, row.seller_id)
        grouped_rows[group_key].append(row)

    candidates: list[ListingCandidate] = []
    reviews: list[ListingReview] = []

    for (_chain_key, source_product_id, source_sku, seller_id), grouped in sorted(grouped_rows.items()):
        preferred = preferred_row(grouped)
        gtin_norm = preferred.gtin_norm
        product_key = product_key_by_gtin.get(gtin_norm or "")
        source_stage_catalog_run_keys = sorted({row.stage_catalog_run_key for row in grouped})

        if product_key is None:
            reviews.append(
                ListingReview(
                    review_reason="missing_product_match",
                    chain_key=preferred.chain_key,
                    source_product_id=source_product_id,
                    source_sku=source_sku,
                    seller_id=seller_id,
                    seller_name=preferred.seller_name,
                    sample_listing_name=preferred.listing_name,
                    source_row_count=len(grouped),
                    source_stage_catalog_run_keys=source_stage_catalog_run_keys,
                    review_payload={
                        "chain_id": preferred.chain_id,
                        "source_gtin": preferred.source_gtin,
                        "gtin_norm": gtin_norm,
                        "entries": serialize_review_entries(grouped),
                    },
                )
            )
            continue

        candidates.append(
            ListingCandidate(
                preferred_stage_catalog_item_key=preferred.stage_catalog_item_key,
                chain_key=preferred.chain_key,
                product_key=product_key,
                source_product_id=source_product_id,
                source_sku=source_sku,
                seller_id=seller_id,
                seller_name=preferred.seller_name,
                listing_name=preferred.listing_name,
                product_url=preferred.product_url,
                image_url=preferred.image_url,
                root_category_slug=preferred.root_category_slug,
                root_category_name=preferred.root_category_name,
                source_row_count=len(grouped),
                source_stage_catalog_run_keys=source_stage_catalog_run_keys,
            )
        )

    return ListingTransformResult(
        stage_run_keys=sorted({int(run_key) for run_key in stage_run_keys}),
        stage_rows_read=len(rows),
        candidate_rows=candidates,
        review_rows=reviews,
    )


def replace_stage_listing_transform_tables(
    env: dict[str, str],
    result: ListingTransformResult,
) -> ListingStageWriteSummary:
    candidate_csv = io.StringIO()
    candidate_writer = csv.DictWriter(
        candidate_csv,
        fieldnames=[
            "preferred_stage_catalog_item_key",
            "chain_key",
            "product_key",
            "source_product_id",
            "source_sku",
            "seller_id",
            "seller_name",
            "listing_name",
            "product_url",
            "image_url",
            "root_category_slug",
            "root_category_name",
            "source_row_count",
            "source_stage_catalog_run_keys",
        ],
        lineterminator="\n",
    )
    candidate_writer.writeheader()
    for row in result.candidate_rows:
        candidate_writer.writerow(
            {
                "preferred_stage_catalog_item_key": row.preferred_stage_catalog_item_key,
                "chain_key": row.chain_key,
                "product_key": row.product_key,
                "source_product_id": row.source_product_id,
                "source_sku": row.source_sku,
                "seller_id": row.seller_id,
                "seller_name": row.seller_name,
                "listing_name": row.listing_name,
                "product_url": row.product_url,
                "image_url": row.image_url,
                "root_category_slug": row.root_category_slug,
                "root_category_name": row.root_category_name,
                "source_row_count": row.source_row_count,
                "source_stage_catalog_run_keys": json.dumps(
                    row.source_stage_catalog_run_keys,
                    ensure_ascii=False,
                ),
            }
        )

    review_csv = io.StringIO()
    review_writer = csv.DictWriter(
        review_csv,
        fieldnames=[
            "review_reason",
            "chain_key",
            "source_product_id",
            "source_sku",
            "seller_id",
            "seller_name",
            "sample_listing_name",
            "source_row_count",
            "source_stage_catalog_run_keys",
            "review_payload",
        ],
        lineterminator="\n",
    )
    review_writer.writeheader()
    for row in result.review_rows:
        review_writer.writerow(
            {
                "review_reason": row.review_reason,
                "chain_key": row.chain_key,
                "source_product_id": row.source_product_id,
                "source_sku": row.source_sku,
                "seller_id": row.seller_id,
                "seller_name": row.seller_name,
                "sample_listing_name": row.sample_listing_name,
                "source_row_count": row.source_row_count,
                "source_stage_catalog_run_keys": json.dumps(
                    row.source_stage_catalog_run_keys,
                    ensure_ascii=False,
                ),
                "review_payload": json.dumps(row.review_payload, ensure_ascii=False),
            }
        )

    sql = f"""
begin;
truncate table public.mkt_stage_listing_candidate restart identity;
truncate table public.mkt_stage_listing_review restart identity;

create temp table tmp_stage_listing_candidate_load (
  preferred_stage_catalog_item_key bigint,
  chain_key integer,
  product_key bigint,
  source_product_id text,
  source_sku text,
  seller_id text,
  seller_name text,
  listing_name text,
  product_url text,
  image_url text,
  root_category_slug text,
  root_category_name text,
  source_row_count integer,
  source_stage_catalog_run_keys jsonb
);

copy tmp_stage_listing_candidate_load (
  preferred_stage_catalog_item_key,
  chain_key,
  product_key,
  source_product_id,
  source_sku,
  seller_id,
  seller_name,
  listing_name,
  product_url,
  image_url,
  root_category_slug,
  root_category_name,
  source_row_count,
  source_stage_catalog_run_keys
) from stdin with (format csv, header true);
{candidate_csv.getvalue()}\\.

insert into public.mkt_stage_listing_candidate (
  preferred_stage_catalog_item_key,
  chain_key,
  product_key,
  source_product_id,
  source_sku,
  seller_id,
  seller_name,
  listing_name,
  product_url,
  image_url,
  root_category_slug,
  root_category_name,
  source_row_count,
  source_stage_catalog_run_keys
)
select
  preferred_stage_catalog_item_key,
  chain_key,
  product_key,
  source_product_id,
  source_sku,
  seller_id,
  seller_name,
  listing_name,
  product_url,
  image_url,
  root_category_slug,
  root_category_name,
  source_row_count,
  source_stage_catalog_run_keys
from tmp_stage_listing_candidate_load;

create temp table tmp_stage_listing_review_load (
  review_reason text,
  chain_key integer,
  source_product_id text,
  source_sku text,
  seller_id text,
  seller_name text,
  sample_listing_name text,
  source_row_count integer,
  source_stage_catalog_run_keys jsonb,
  review_payload jsonb
);

copy tmp_stage_listing_review_load (
  review_reason,
  chain_key,
  source_product_id,
  source_sku,
  seller_id,
  seller_name,
  sample_listing_name,
  source_row_count,
  source_stage_catalog_run_keys,
  review_payload
) from stdin with (format csv, header true);
{review_csv.getvalue()}\\.

insert into public.mkt_stage_listing_review (
  review_reason,
  chain_key,
  source_product_id,
  source_sku,
  seller_id,
  seller_name,
  sample_listing_name,
  source_row_count,
  source_stage_catalog_run_keys,
  review_payload
)
select
  review_reason,
  chain_key,
  source_product_id,
  source_sku,
  seller_id,
  seller_name,
  sample_listing_name,
  source_row_count,
  source_stage_catalog_run_keys,
  review_payload
from tmp_stage_listing_review_load;

select
  (select count(*) from public.mkt_stage_listing_candidate),
  (select count(*) from public.mkt_stage_listing_review);
commit;
"""

    output = run_psql(env, sql=sql, tuples_only=True)
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("No pude confirmar la escritura de mkt_stage_listing_candidate/review.")
    candidate_count_text, review_count_text = lines[-1].split("\t", 1)
    return ListingStageWriteSummary(
        candidate_count=int(candidate_count_text),
        review_count=int(review_count_text),
    )


def load_stage_listing_candidates_into_dim_listing(
    env: dict[str, str],
    *,
    truncate_first: bool = False,
) -> ListingLoadSummary:
    sql_lines = ["begin;"]
    if truncate_first:
        sql_lines.append("truncate table public.mkt_dim_listing restart identity;")

    sql_lines.append(
        """
create temp table tmp_dim_listing_upsert_result as
with upserted as (
  insert into public.mkt_dim_listing (
    chain_key,
    product_key,
    source_product_id,
    source_sku,
    seller_id,
    seller_name,
    listing_name,
    product_url,
    image_url,
    root_category_slug,
    root_category_name,
    is_active
  )
  select
    chain_key,
    product_key,
    source_product_id,
    source_sku,
    seller_id,
    seller_name,
    listing_name,
    product_url,
    image_url,
    root_category_slug,
    root_category_name,
    true
  from public.mkt_stage_listing_candidate
  on conflict (chain_key, source_product_id, source_sku, seller_id)
  do update
  set
    product_key = excluded.product_key,
    seller_name = excluded.seller_name,
    listing_name = excluded.listing_name,
    product_url = excluded.product_url,
    image_url = excluded.image_url,
    root_category_slug = excluded.root_category_slug,
    root_category_name = excluded.root_category_name,
    is_active = true,
    updated_at = now()
  returning 1
)
select
  (select count(*) from upserted) as loaded_rows;
"""
    )
    sql_lines.append(
        """
select
  (select count(*) from public.mkt_stage_listing_candidate),
  (select coalesce(sum(loaded_rows), 0) from tmp_dim_listing_upsert_result),
  (select count(*) from public.mkt_dim_listing);
"""
    )
    sql_lines.append("commit;")

    output = run_psql(env, sql="\n".join(sql_lines), tuples_only=True)
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("No pude confirmar la carga hacia mkt_dim_listing.")
    candidate_count_text, loaded_rows_text, dim_total_text = lines[-1].split("\t", 2)
    return ListingLoadSummary(
        candidate_count=int(candidate_count_text),
        loaded_rows=int(loaded_rows_text),
        dim_listing_total=int(dim_total_text),
        truncated_first=truncate_first,
    )
