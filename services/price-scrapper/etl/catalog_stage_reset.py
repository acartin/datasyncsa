#!/usr/bin/env python3
"""Reset controlado del stage temporal de catálogo."""

from __future__ import annotations

from dataclasses import dataclass

from etl.postgres_cli import parse_env, run_psql


STAGE_TABLES = [
    "public.mkt_stage_listing_snapshot_candidate",
    "public.mkt_stage_listing_snapshot_review",
    "public.mkt_stage_listing_candidate",
    "public.mkt_stage_listing_review",
    "public.mkt_stage_product_candidate",
    "public.mkt_stage_product_review",
    "public.mkt_stage_catalog_item",
]


@dataclass(frozen=True)
class CatalogStageResetSummary:
    stage_catalog_items_before: int
    stage_catalog_items_after: int


def reset_catalog_stage(env: dict[str, str] | None = None) -> CatalogStageResetSummary:
    resolved_env = env or parse_env()
    truncate_targets = ",\n  ".join(STAGE_TABLES)
    output = run_psql(
        resolved_env,
        sql=f"""
begin;
select count(*) as before_count from public.mkt_stage_catalog_item;
truncate table
  {truncate_targets}
restart identity;
select count(*) as after_count from public.mkt_stage_catalog_item;
commit;
""",
        tuples_only=True,
    )
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if len(lines) < 2:
        raise RuntimeError("No pude confirmar el reset de mkt_stage_catalog_item.")
    before_count = int(lines[-2])
    after_count = int(lines[-1])
    return CatalogStageResetSummary(
        stage_catalog_items_before=before_count,
        stage_catalog_items_after=after_count,
    )
