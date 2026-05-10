#!/usr/bin/env python3
"""Transform y load de productos canónicos desde stage de catálogo."""

from __future__ import annotations

import csv
import io
import json
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from etl.normalize import normalize_ean
from etl.postgres_cli import run_psql


VALID_GTIN_LENGTHS = {8, 12, 13, 14}
UNIT_CANONICALIZATION = {
    "g": ("g", Decimal("1")),
    "gr": ("g", Decimal("1")),
    "kg": ("g", Decimal("1000")),
    "ml": ("ml", Decimal("1")),
    "l": ("ml", Decimal("1000")),
    "lt": ("ml", Decimal("1000")),
    "lts": ("ml", Decimal("1000")),
    "un": ("un", Decimal("1")),
    "u": ("un", Decimal("1")),
    "ud": ("un", Decimal("1")),
    "uds": ("un", Decimal("1")),
}
REVIEW_REASON_INVALID_GTIN = "invalid_gtin"
REVIEW_REASON_SAME_CHAIN_COLLISION = "same_chain_collision"


@dataclass(frozen=True)
class StageProductRow:
    stage_catalog_item_key: int
    stage_catalog_run_key: int
    chain_id: str
    gtin_raw: str | None
    gtin_norm: str | None
    gtin_type: str | None
    gtin_is_valid: bool
    source_sku: str | None
    source_product_id: str | None
    brand_name: str | None
    brand_norm: str
    product_name: str
    name_norm: str
    quantity: str | None
    unit: str | None
    measurement_unit: str | None


@dataclass(frozen=True)
class ProductCandidate:
    preferred_stage_catalog_item_key: int
    gtin_raw: str | None
    gtin_norm: str
    gtin_type: str
    gtin_is_valid: bool
    brand_name: str | None
    product_name: str
    normalized_name: str
    content_quantity: str | None
    content_unit: str | None
    source_row_count: int
    source_chain_count: int
    source_chain_ids: list[str]
    source_stage_catalog_run_keys: list[int]


@dataclass(frozen=True)
class ProductReview:
    review_reason: str
    gtin_raw: str | None
    gtin_norm: str | None
    gtin_type: str | None
    gtin_is_valid: bool
    source_row_count: int
    source_chain_count: int
    source_chain_ids: list[str]
    source_stage_catalog_run_keys: list[int]
    sample_brand_name: str | None
    sample_product_name: str
    review_payload: dict[str, Any]


@dataclass(frozen=True)
class ProductTransformResult:
    stage_run_keys: list[int]
    stage_rows_read: int
    candidate_rows: list[ProductCandidate]
    review_rows: list[ProductReview]


@dataclass(frozen=True)
class ProductStageWriteSummary:
    candidate_count: int
    review_count: int


@dataclass(frozen=True)
class ProductLoadSummary:
    candidate_count: int
    loaded_rows: int
    dim_product_total: int
    truncated_first: bool


def _sql_literal(value: str) -> str:
    return value.replace("'", "''")


def digits_only(value: object) -> str | None:
    normalized = normalize_ean(value)
    if normalized is None:
        return None
    digits = re.sub(r"\D", "", str(normalized).strip())
    return digits or None


def gtin_type(code: str | None) -> str | None:
    if not code:
        return None
    if len(code) == 8:
        return "GTIN8"
    if len(code) == 12:
        return "GTIN12"
    if len(code) == 13:
        return "GTIN13"
    if len(code) == 14:
        return "GTIN14"
    return "NON_STANDARD"


def is_valid_gtin(code: str | None) -> bool:
    if not code or len(code) not in VALID_GTIN_LENGTHS or not code.isdigit():
        return False
    body = code[:-1]
    check_digit = int(code[-1])
    total = 0
    for index, char in enumerate(reversed(body), start=1):
        total += int(char) * (3 if index % 2 == 1 else 1)
    expected = (10 - (total % 10)) % 10
    return check_digit == expected


def normalize_text(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.upper()
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def flatten_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def safe_decimal(value: object) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None


def normalize_measure(quantity: object, unit: str | None) -> tuple[Decimal, str] | None:
    quantity_decimal = safe_decimal(quantity)
    if quantity_decimal is None or not unit:
        return None
    unit_key = unit.strip().lower()
    if unit_key not in UNIT_CANONICALIZATION:
        return None
    canonical_unit, multiplier = UNIT_CANONICALIZATION[unit_key]
    return (quantity_decimal * multiplier, canonical_unit)


def preferred_row(rows: list[StageProductRow]) -> StageProductRow:
    name_frequency = Counter(row.name_norm for row in rows)
    brand_frequency = Counter(row.brand_norm for row in rows)

    def sort_key(row: StageProductRow) -> tuple[int, int, int, int]:
        has_mixed_case = 1 if row.product_name != row.product_name.upper() else 0
        return (
            -name_frequency[row.name_norm],
            -brand_frequency[row.brand_norm],
            -has_mixed_case,
            -len(row.product_name),
        )

    return sorted(rows, key=sort_key)[0]


def consensus_measure(rows: list[StageProductRow]) -> tuple[str | None, str | None]:
    normalized = [normalize_measure(row.quantity, row.unit) for row in rows]
    non_null = [entry for entry in normalized if entry is not None]
    if not non_null:
        return (None, None)
    unique = set(non_null)
    if len(unique) != 1:
        return (None, None)
    quantity, unit = next(iter(unique))
    quantity_text = format(quantity, "f")
    if "." in quantity_text:
        quantity_text = quantity_text.rstrip("0").rstrip(".")
    return (quantity_text, unit)


def same_chain_collision(rows: list[StageProductRow]) -> bool:
    identities_by_chain: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for row in rows:
        identities_by_chain[row.chain_id].add((row.source_sku or "", row.source_product_id or ""))
    return any(len(identities) > 1 for identities in identities_by_chain.values())


def serialize_review_entries(rows: list[StageProductRow]) -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []
    for row in rows:
        serialized.append(
            {
                "stage_catalog_item_key": row.stage_catalog_item_key,
                "stage_catalog_run_key": row.stage_catalog_run_key,
                "chain_id": row.chain_id,
                "gtin_raw": row.gtin_raw,
                "gtin_norm": row.gtin_norm,
                "gtin_type": row.gtin_type,
                "source_sku": row.source_sku,
                "source_product_id": row.source_product_id,
                "brand_name": row.brand_name,
                "product_name": row.product_name,
                "quantity": row.quantity,
                "unit": row.unit,
                "measurement_unit": row.measurement_unit,
            }
        )
    return serialized


def _parse_copy_csv(output: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(output))
    return [dict(row) for row in reader]


def resolve_stage_run_keys(
    env: dict[str, str],
    *,
    explicit_run_keys: Iterable[int] | None = None,
    run_kind: str = "comparative",
) -> list[int]:
    explicit = sorted({int(run_key) for run_key in explicit_run_keys or []})
    if explicit:
        run_keys_sql = ", ".join(str(run_key) for run_key in explicit)
        output = run_psql(
            env,
            sql=f"""
select run_key
from public.mkt_run
where run_status = 'succeeded'
  and run_key in ({run_keys_sql})
order by run_key;
""",
            tuples_only=True,
        )
        found = [int(line.strip()) for line in output.splitlines() if line.strip()]
        if found != explicit:
            raise RuntimeError(
                "No todas las stage runs solicitadas existen con estado succeeded. "
                f"Esperadas={explicit!r} Encontradas={found!r}"
            )
        return found

    output = run_psql(
        env,
        sql=f"""
select distinct on (r.chain_key) r.run_key
from public.mkt_run as r
join public.mkt_dim_chain as c
  on c.chain_key = r.chain_key
where r.run_status = 'succeeded'
  and r.run_kind = '{_sql_literal(run_kind)}'
  and c.is_active = true
order by r.chain_key, r.started_at desc, r.run_key desc;
""",
        tuples_only=True,
    )
    run_keys = [int(line.strip()) for line in output.splitlines() if line.strip()]
    if not run_keys:
        raise RuntimeError(
            "No encontré stage runs exitosas para transformar productos. "
            f"run_kind={run_kind!r}"
        )
    return run_keys


def fetch_stage_product_rows(
    env: dict[str, str],
    *,
    stage_run_keys: Iterable[int],
) -> list[StageProductRow]:
    run_keys = sorted({int(run_key) for run_key in stage_run_keys})
    if not run_keys:
        raise RuntimeError("Debes indicar al menos una stage run para transformar productos.")

    run_keys_sql = ", ".join(str(run_key) for run_key in run_keys)
    output = run_psql(
        env,
        sql=f"""
copy (
  select
    i.stage_catalog_item_key,
    i.run_key as stage_catalog_run_key,
    c.chain_id,
    i.source_gtin,
    i.source_sku,
    i.source_product_id,
    i.brand_name,
    i.product_name,
    i.quantity::text,
    i.unit,
    i.measurement_unit
  from public.mkt_stage_catalog_item as i
  join public.mkt_dim_chain as c
    on c.chain_key = i.chain_key
  where i.run_key in ({run_keys_sql})
  order by i.run_key, i.stage_catalog_item_key
) to stdout with (format csv, header true);
""",
    )

    rows: list[StageProductRow] = []
    for payload in _parse_copy_csv(output):
        gtin_raw = flatten_text(payload["source_gtin"])
        gtin_norm = digits_only(gtin_raw)
        product_name = flatten_text(payload["product_name"]) or "SIN_NOMBRE"
        rows.append(
            StageProductRow(
                stage_catalog_item_key=int(payload["stage_catalog_item_key"]),
                stage_catalog_run_key=int(payload["stage_catalog_run_key"]),
                chain_id=payload["chain_id"].strip(),
                gtin_raw=gtin_raw,
                gtin_norm=gtin_norm,
                gtin_type=gtin_type(gtin_norm),
                gtin_is_valid=is_valid_gtin(gtin_norm),
                source_sku=flatten_text(payload["source_sku"]),
                source_product_id=flatten_text(payload["source_product_id"]),
                brand_name=flatten_text(payload["brand_name"]),
                brand_norm=normalize_text(payload["brand_name"]),
                product_name=product_name,
                name_norm=normalize_text(product_name),
                quantity=flatten_text(payload["quantity"]),
                unit=flatten_text(payload["unit"]),
                measurement_unit=flatten_text(payload["measurement_unit"]),
            )
        )
    return rows


def build_product_transform_result(
    rows: list[StageProductRow],
    *,
    stage_run_keys: Iterable[int],
) -> ProductTransformResult:
    grouped_rows: dict[str, list[StageProductRow]] = defaultdict(list)
    for row in rows:
        group_key = row.gtin_norm or row.gtin_raw or f"__NO_GTIN__:{row.stage_catalog_item_key}"
        grouped_rows[group_key].append(row)

    candidates: list[ProductCandidate] = []
    reviews: list[ProductReview] = []

    for group_key, grouped in sorted(grouped_rows.items(), key=lambda item: item[0]):
        sample_row = grouped[0]
        source_chain_ids = sorted({row.chain_id for row in grouped})
        source_stage_catalog_run_keys = sorted({row.stage_catalog_run_key for row in grouped})

        if not sample_row.gtin_is_valid or sample_row.gtin_type == "NON_STANDARD":
            reviews.append(
                ProductReview(
                    review_reason=REVIEW_REASON_INVALID_GTIN,
                    gtin_raw=sample_row.gtin_raw,
                    gtin_norm=sample_row.gtin_norm,
                    gtin_type=sample_row.gtin_type,
                    gtin_is_valid=sample_row.gtin_is_valid,
                    source_row_count=len(grouped),
                    source_chain_count=len(source_chain_ids),
                    source_chain_ids=source_chain_ids,
                    source_stage_catalog_run_keys=source_stage_catalog_run_keys,
                    sample_brand_name=sample_row.brand_name,
                    sample_product_name=sample_row.product_name,
                    review_payload={
                        "group_key": group_key,
                        "entries": serialize_review_entries(grouped),
                    },
                )
            )
            continue

        if same_chain_collision(grouped):
            reviews.append(
                ProductReview(
                    review_reason=REVIEW_REASON_SAME_CHAIN_COLLISION,
                    gtin_raw=sample_row.gtin_raw,
                    gtin_norm=sample_row.gtin_norm,
                    gtin_type=sample_row.gtin_type,
                    gtin_is_valid=sample_row.gtin_is_valid,
                    source_row_count=len(grouped),
                    source_chain_count=len(source_chain_ids),
                    source_chain_ids=source_chain_ids,
                    source_stage_catalog_run_keys=source_stage_catalog_run_keys,
                    sample_brand_name=sample_row.brand_name,
                    sample_product_name=sample_row.product_name,
                    review_payload={
                        "group_key": group_key,
                        "entries": serialize_review_entries(grouped),
                    },
                )
            )
            continue

        preferred = preferred_row(grouped)
        content_quantity, content_unit = consensus_measure(grouped)
        candidates.append(
            ProductCandidate(
                preferred_stage_catalog_item_key=preferred.stage_catalog_item_key,
                gtin_raw=preferred.gtin_raw,
                gtin_norm=preferred.gtin_norm or "",
                gtin_type=preferred.gtin_type or "NON_STANDARD",
                gtin_is_valid=True,
                brand_name=preferred.brand_name,
                product_name=preferred.product_name,
                normalized_name=preferred.name_norm,
                content_quantity=content_quantity,
                content_unit=content_unit,
                source_row_count=len(grouped),
                source_chain_count=len(source_chain_ids),
                source_chain_ids=source_chain_ids,
                source_stage_catalog_run_keys=source_stage_catalog_run_keys,
            )
        )

    return ProductTransformResult(
        stage_run_keys=sorted({int(run_key) for run_key in stage_run_keys}),
        stage_rows_read=len(rows),
        candidate_rows=candidates,
        review_rows=reviews,
    )


def replace_stage_product_transform_tables(
    env: dict[str, str],
    result: ProductTransformResult,
) -> ProductStageWriteSummary:
    candidate_csv = io.StringIO()
    candidate_writer = csv.DictWriter(
        candidate_csv,
        fieldnames=[
            "preferred_stage_catalog_item_key",
            "gtin_raw",
            "gtin_norm",
            "gtin_type",
            "gtin_is_valid",
            "brand_name",
            "product_name",
            "normalized_name",
            "content_quantity",
            "content_unit",
            "source_row_count",
            "source_chain_count",
            "source_chain_ids",
            "source_stage_catalog_run_keys",
        ],
        lineterminator="\n",
    )
    candidate_writer.writeheader()
    for row in result.candidate_rows:
        candidate_writer.writerow(
            {
                "preferred_stage_catalog_item_key": row.preferred_stage_catalog_item_key,
                "gtin_raw": row.gtin_raw,
                "gtin_norm": row.gtin_norm,
                "gtin_type": row.gtin_type,
                "gtin_is_valid": row.gtin_is_valid,
                "brand_name": row.brand_name,
                "product_name": row.product_name,
                "normalized_name": row.normalized_name,
                "content_quantity": row.content_quantity,
                "content_unit": row.content_unit,
                "source_row_count": row.source_row_count,
                "source_chain_count": row.source_chain_count,
                "source_chain_ids": json.dumps(row.source_chain_ids, ensure_ascii=False),
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
            "gtin_raw",
            "gtin_norm",
            "gtin_type",
            "gtin_is_valid",
            "source_row_count",
            "source_chain_count",
            "source_chain_ids",
            "source_stage_catalog_run_keys",
            "sample_brand_name",
            "sample_product_name",
            "review_payload",
        ],
        lineterminator="\n",
    )
    review_writer.writeheader()
    for row in result.review_rows:
        review_writer.writerow(
            {
                "review_reason": row.review_reason,
                "gtin_raw": row.gtin_raw,
                "gtin_norm": row.gtin_norm,
                "gtin_type": row.gtin_type,
                "gtin_is_valid": row.gtin_is_valid,
                "source_row_count": row.source_row_count,
                "source_chain_count": row.source_chain_count,
                "source_chain_ids": json.dumps(row.source_chain_ids, ensure_ascii=False),
                "source_stage_catalog_run_keys": json.dumps(
                    row.source_stage_catalog_run_keys,
                    ensure_ascii=False,
                ),
                "sample_brand_name": row.sample_brand_name,
                "sample_product_name": row.sample_product_name,
                "review_payload": json.dumps(row.review_payload, ensure_ascii=False),
            }
        )

    sql = f"""
begin;
truncate table public.mkt_stage_product_candidate restart identity;
truncate table public.mkt_stage_product_review restart identity;

create temp table tmp_stage_product_candidate_load (
  preferred_stage_catalog_item_key bigint,
  gtin_raw text,
  gtin_norm text,
  gtin_type text,
  gtin_is_valid boolean,
  brand_name text,
  product_name text,
  normalized_name text,
  content_quantity numeric(14,4),
  content_unit varchar(30),
  source_row_count integer,
  source_chain_count integer,
  source_chain_ids jsonb,
  source_stage_catalog_run_keys jsonb
);

copy tmp_stage_product_candidate_load (
  preferred_stage_catalog_item_key,
  gtin_raw,
  gtin_norm,
  gtin_type,
  gtin_is_valid,
  brand_name,
  product_name,
  normalized_name,
  content_quantity,
  content_unit,
  source_row_count,
  source_chain_count,
  source_chain_ids,
  source_stage_catalog_run_keys
) from stdin with (format csv, header true);
{candidate_csv.getvalue()}\\.

insert into public.mkt_stage_product_candidate (
  preferred_stage_catalog_item_key,
  gtin_raw,
  gtin_norm,
  gtin_type,
  gtin_is_valid,
  brand_name,
  product_name,
  normalized_name,
  content_quantity,
  content_unit,
  source_row_count,
  source_chain_count,
  source_chain_ids,
  source_stage_catalog_run_keys
)
select
  preferred_stage_catalog_item_key,
  gtin_raw,
  gtin_norm,
  gtin_type,
  gtin_is_valid,
  brand_name,
  product_name,
  normalized_name,
  content_quantity,
  content_unit,
  source_row_count,
  source_chain_count,
  source_chain_ids,
  source_stage_catalog_run_keys
from tmp_stage_product_candidate_load;

create temp table tmp_stage_product_review_load (
  review_reason text,
  gtin_raw text,
  gtin_norm text,
  gtin_type text,
  gtin_is_valid boolean,
  source_row_count integer,
  source_chain_count integer,
  source_chain_ids jsonb,
  source_stage_catalog_run_keys jsonb,
  sample_brand_name text,
  sample_product_name text,
  review_payload jsonb
);

copy tmp_stage_product_review_load (
  review_reason,
  gtin_raw,
  gtin_norm,
  gtin_type,
  gtin_is_valid,
  source_row_count,
  source_chain_count,
  source_chain_ids,
  source_stage_catalog_run_keys,
  sample_brand_name,
  sample_product_name,
  review_payload
) from stdin with (format csv, header true);
{review_csv.getvalue()}\\.

insert into public.mkt_stage_product_review (
  review_reason,
  gtin_raw,
  gtin_norm,
  gtin_type,
  gtin_is_valid,
  source_row_count,
  source_chain_count,
  source_chain_ids,
  source_stage_catalog_run_keys,
  sample_brand_name,
  sample_product_name,
  review_payload
)
select
  review_reason,
  gtin_raw,
  gtin_norm,
  gtin_type,
  gtin_is_valid,
  source_row_count,
  source_chain_count,
  source_chain_ids,
  source_stage_catalog_run_keys,
  sample_brand_name,
  sample_product_name,
  review_payload
from tmp_stage_product_review_load;

select
  (select count(*) from public.mkt_stage_product_candidate),
  (select count(*) from public.mkt_stage_product_review);
commit;
"""

    output = run_psql(env, sql=sql, tuples_only=True)
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("No pude confirmar la escritura de mkt_stage_product_candidate/review.")
    candidate_count_text, review_count_text = lines[-1].split("\t", 1)
    return ProductStageWriteSummary(
        candidate_count=int(candidate_count_text),
        review_count=int(review_count_text),
    )


def load_stage_product_candidates_into_dim_product(
    env: dict[str, str],
    *,
    truncate_first: bool = False,
) -> ProductLoadSummary:
    sql_lines = ["begin;"]
    if truncate_first:
        sql_lines.append("truncate table public.mkt_dim_product restart identity;")

    sql_lines.append(
        """
create temp table tmp_dim_product_upsert_result as
with upserted as (
  insert into public.mkt_dim_product (
    gtin_raw,
    gtin_norm,
    gtin_type,
    gtin_is_valid,
    brand_name,
    product_name,
    normalized_name,
    content_quantity,
    content_unit,
    is_active
  )
  select
    gtin_raw,
    gtin_norm,
    gtin_type,
    gtin_is_valid,
    brand_name,
    product_name,
    normalized_name,
    content_quantity,
    content_unit,
    true
  from public.mkt_stage_product_candidate
  on conflict (gtin_norm)
    where (gtin_is_valid = true and gtin_norm is not null)
  do update
  set
    gtin_raw = excluded.gtin_raw,
    gtin_type = excluded.gtin_type,
    gtin_is_valid = excluded.gtin_is_valid,
    brand_name = excluded.brand_name,
    product_name = excluded.product_name,
    normalized_name = excluded.normalized_name,
    content_quantity = excluded.content_quantity,
    content_unit = excluded.content_unit,
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
  (select count(*) from public.mkt_stage_product_candidate),
  (select coalesce(sum(loaded_rows), 0) from tmp_dim_product_upsert_result),
  (select count(*) from public.mkt_dim_product);
"""
    )
    sql_lines.append("commit;")

    output = run_psql(env, sql="\n".join(sql_lines), tuples_only=True)
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("No pude confirmar la carga hacia mkt_dim_product.")
    candidate_count_text, loaded_rows_text, dim_total_text = lines[-1].split("\t", 2)
    return ProductLoadSummary(
        candidate_count=int(candidate_count_text),
        loaded_rows=int(loaded_rows_text),
        dim_product_total=int(dim_total_text),
        truncated_first=truncate_first,
    )
