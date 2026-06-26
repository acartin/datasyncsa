#!/usr/bin/env python3
"""Construye las tablas app-facing de historial de producto para Market Watch."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path


SERVICE_DIR = Path(__file__).resolve().parents[1]
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

from etl.postgres_cli import parse_env, run_psql


@dataclass(frozen=True)
class BuildScope:
    date_keys: tuple[int, ...] = ()
    date_from: int | None = None
    date_to: int | None = None
    truncate_first: bool = False

    @property
    def is_all_history(self) -> bool:
        return not self.date_keys and self.date_from is None and self.date_to is None


def _int_list(values: list[int]) -> str:
    return ", ".join(str(value) for value in values)


def _table_date_filter(scope: BuildScope, *, alias: str = "") -> str:
    prefix = f"{alias}." if alias else ""
    if scope.date_keys:
        return f"{prefix}date_key in ({_int_list(list(scope.date_keys))})"
    clauses: list[str] = []
    if scope.date_from is not None:
        clauses.append(f"{prefix}date_key >= {scope.date_from}")
    if scope.date_to is not None:
        clauses.append(f"{prefix}date_key <= {scope.date_to}")
    return " and ".join(clauses) if clauses else "true"


def _resolve_run_date_keys(env: dict[str, str], run_keys: list[int]) -> tuple[int, ...]:
    if not run_keys:
        return ()
    output = run_psql(
        env,
        sql=f"""
        select distinct date_key::text
        from public.mkt_fact_listing_snapshot
        where run_key in ({_int_list(run_keys)})
        order by date_key;
        """,
        tuples_only=True,
    )
    if not output:
        return ()
    return tuple(int(value) for value in output.splitlines() if value.strip())


def _build_sql(scope: BuildScope) -> str:
    source_filter = _table_date_filter(scope, alias="o")
    chain_delete = "truncate table public.mw_app_product_chain_day;" if scope.truncate_first else f"delete from public.mw_app_product_chain_day where {_table_date_filter(scope)};"
    store_delete = "truncate table public.mw_app_product_store_day;" if scope.truncate_first else f"delete from public.mw_app_product_store_day where {_table_date_filter(scope)};"

    return f"""
    begin;

    {store_delete}
    {chain_delete}

    insert into public.mw_app_product_chain_day (
      date_key,
      business_date,
      week_start,
      month_start,
      client_id,
      client,
      campaign_id,
      campaign,
      chain_key,
      chain_id,
      chain_name,
      chain,
      product_key,
      gtin,
      brand,
      product,
      content_quantity,
      content_unit,
      capture_started_at_cr,
      captured_at_cr,
      runs_seen,
      observed_locations,
      visible_locations,
      available_locations,
      promo_locations,
      average_price,
      average_unit_price,
      min_price,
      max_price,
      reference_price_amount,
      promo_price_amount,
      promo_detected,
      promo_share_pct,
      max_discount_pct,
      discount_pct,
      gap_pct,
      price_index,
      price_reading,
      suggested_action,
      availability_state,
      product_url,
      image_url
    )
    select
      o.date_key,
      o.business_date,
      o.week_start_date as week_start,
      o.month_start_date as month_start,
      o.client_id,
      o.client_name as client,
      o.campaign_id,
      o.campaign_name as campaign,
      o.chain_key,
      o.chain_id,
      o.chain_name,
      o.chain_label as chain,
      o.product_key,
      o.gtin_norm as gtin,
      o.brand_name as brand,
      o.product_name as product,
      o.content_quantity,
      o.content_unit,
      min(o.captured_at_cr) as capture_started_at_cr,
      max(o.captured_at_cr) as captured_at_cr,
      count(distinct o.run_key)::int as runs_seen,
      count(distinct o.location_key)::int as observed_locations,
      count(distinct o.location_key) filter (where o.is_listed)::int as visible_locations,
      count(distinct o.location_key) filter (where o.is_available)::int as available_locations,
      count(distinct o.location_key) filter (
        where o.is_available
          and o.spot_price_amount is not null
      )::int as promo_locations,
      round(avg(coalesce(o.spot_price_amount, o.effective_price_amount)) filter (
        where o.is_available
          and coalesce(o.spot_price_amount, o.effective_price_amount) is not null
      ), 2) as average_price,
      round(avg(o.effective_price_per_unit_amount) filter (
        where o.is_available
          and o.effective_price_per_unit_amount is not null
      ), 4) as average_unit_price,
      round(min(coalesce(o.spot_price_amount, o.effective_price_amount)) filter (where o.is_available), 2) as min_price,
      round(max(coalesce(o.spot_price_amount, o.effective_price_amount)) filter (where o.is_available), 2) as max_price,
      round(avg(o.reference_price_amount) filter (
        where o.is_available
          and o.reference_price_amount is not null
      ), 2) as reference_price_amount,
      round(avg(o.spot_price_amount) filter (
        where o.is_available
          and o.spot_price_amount is not null
      ), 2) as promo_price_amount,
      bool_or(o.is_available and o.spot_price_amount is not null) as promo_detected,
      round(
        count(distinct o.location_key) filter (
          where o.is_available
            and o.spot_price_amount is not null
        )::numeric
        / nullif(count(distinct o.location_key), 0)::numeric
        * 100,
        2
      ) as promo_share_pct,
      case
        when (avg(o.reference_price_amount) filter (where o.is_available)) > 0
          and (avg(o.spot_price_amount) filter (where o.is_available and o.spot_price_amount is not null)) is not null
        then round(
          (
            (
              avg(o.reference_price_amount) filter (where o.is_available)
            ) - (
              avg(o.spot_price_amount) filter (where o.is_available and o.spot_price_amount is not null)
            )
          ) / (avg(o.reference_price_amount) filter (where o.is_available))
          * 100,
          2
        )
      end as max_discount_pct,
      round(max(o.discount_pct) * 100, 2) as discount_pct,
      round(s.gap_vs_market_best_pct * 100, 2) as gap_pct,
      round(s.price_position_index, 2) as price_index,
      s.price_reading,
      s.suggested_action,
      case
        when count(distinct o.location_key) filter (where o.is_available) > 0 then 'available'
        when count(distinct o.location_key) filter (where o.is_listed) > 0 then 'listed_unavailable'
        else 'unobserved'
      end as availability_state,
      max(o.product_url) filter (where o.product_url is not null) as product_url,
      max(o.image_url) filter (where o.image_url is not null) as image_url
    from public.mw_core_sku_store_observation as o
    left join public.mw_signal_sku_chain_daily as s
      on s.date_key = o.date_key
     and s.client_id = o.client_id
     and s.campaign_id = o.campaign_id
     and s.product_key = o.product_key
     and s.chain_key = o.chain_key
    where (o.is_listed or o.effective_price_amount is not null)
      and {source_filter}
    group by
      o.date_key,
      o.business_date,
      o.week_start_date,
      o.month_start_date,
      o.client_id,
      o.client_name,
      o.campaign_id,
      o.campaign_name,
      o.chain_key,
      o.chain_id,
      o.chain_name,
      o.chain_label,
      o.product_key,
      o.gtin_norm,
      o.brand_name,
      o.product_name,
      o.content_quantity,
      o.content_unit,
      s.gap_vs_market_best_pct,
      s.price_position_index,
      s.price_reading,
      s.suggested_action;

    insert into public.mw_app_product_store_day (
      date_key,
      business_date,
      week_start,
      month_start,
      client_id,
      client,
      campaign_id,
      campaign,
      chain_key,
      chain_id,
      chain_name,
      chain,
      product_key,
      gtin,
      brand,
      product,
      content_quantity,
      content_unit,
      location_key,
      location_code,
      location_name,
      location_type,
      province,
      canton,
      district,
      sales_channel,
      region_id,
      captured_at_cr,
      currency_code,
      is_listed,
      is_available,
      has_discount,
      price_amount,
      list_price_amount,
      price_without_discount_amount,
      spot_price_amount,
      effective_price_amount,
      reference_price_amount,
      effective_price_per_unit_amount,
      discount_pct,
      discount_pct_display,
      promo_detected,
      available_quantity,
      availability_state,
      product_url,
      image_url,
      source_engine
    )
    with ranked as (
      select
        o.*,
        row_number() over (
          partition by
            o.date_key,
            o.client_id,
            o.campaign_id,
            o.chain_key,
            o.product_key,
            o.location_key
          order by
            o.captured_at_cr desc nulls last,
            o.is_available desc nulls last,
            o.is_listed desc nulls last,
            coalesce(o.spot_price_amount, o.effective_price_amount, o.price_amount) nulls last,
            o.listing_key desc
        ) as row_rank
      from public.mw_core_sku_store_observation as o
      where (o.is_listed or o.effective_price_amount is not null)
        and o.location_key is not null
        and {source_filter}
    )
    select
      r.date_key,
      r.business_date,
      r.week_start_date as week_start,
      r.month_start_date as month_start,
      r.client_id,
      r.client_name as client,
      r.campaign_id,
      r.campaign_name as campaign,
      r.chain_key,
      r.chain_id,
      r.chain_name,
      r.chain_label as chain,
      r.product_key,
      r.gtin_norm as gtin,
      r.brand_name as brand,
      r.product_name as product,
      r.content_quantity,
      r.content_unit,
      r.location_key,
      coalesce(loc.location_code, r.location_code) as location_code,
      coalesce(loc.location_name, r.location_name) as location_name,
      coalesce(loc.location_type, r.location_type) as location_type,
      coalesce(loc.province, r.province) as province,
      coalesce(loc.canton, r.canton) as canton,
      coalesce(loc.district, r.district) as district,
      coalesce(loc.sales_channel, r.sales_channel) as sales_channel,
      coalesce(loc.region_id, r.region_id) as region_id,
      r.captured_at_cr,
      r.currency_code,
      r.is_listed,
      r.is_available,
      r.has_discount,
      r.price_amount,
      r.list_price_amount,
      r.price_without_discount_amount,
      r.spot_price_amount,
      r.effective_price_amount,
      r.reference_price_amount,
      r.effective_price_per_unit_amount,
      r.discount_pct,
      round(r.discount_pct * 100, 2) as discount_pct_display,
      r.promo_detected,
      r.available_quantity,
      case
        when r.is_available then 'available'
        when r.is_listed then 'listed_unavailable'
        else 'unobserved'
      end as availability_state,
      r.product_url,
      r.image_url,
      r.source_engine
    from ranked as r
    left join public.mkt_dim_location as loc
      on loc.location_key = r.location_key
    where r.row_rank = 1;

    commit;
    """


def _summary_sql(scope: BuildScope) -> str:
    chain_filter = _table_date_filter(scope, alias="chain_day")
    store_filter = _table_date_filter(scope, alias="store_day")
    return f"""
    with chain_day as (
      select
        max(date_key) as latest_date_key,
        count(*)::int as total_rows
      from public.mw_app_product_chain_day as chain_day
      where {chain_filter}
    ),
    store_day as (
      select
        max(date_key) as latest_date_key,
        count(*)::int as total_rows
      from public.mw_app_product_store_day as store_day
      where {store_filter}
    )
    select
      coalesce(chain_day.latest_date_key::text, '') as chain_latest_date_key,
      chain_day.total_rows::text as chain_total_rows,
      coalesce(store_day.latest_date_key::text, '') as store_latest_date_key,
      store_day.total_rows::text as store_total_rows
    from chain_day
    cross join store_day;
    """


def build_app_product_history(env: dict[str, str], scope: BuildScope) -> dict[str, int | None]:
    run_psql(env, sql=_build_sql(scope), tuples_only=False)
    output = run_psql(env, sql=_summary_sql(scope), tuples_only=True)
    latest_chain, chain_rows, latest_store, store_rows = output.split("\t")
    return {
        "chain_latest_date_key": int(latest_chain) if latest_chain else None,
        "chain_total_rows": int(chain_rows),
        "store_latest_date_key": int(latest_store) if latest_store else None,
        "store_total_rows": int(store_rows),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Construye mw_app_product_chain_day y mw_app_product_store_day."
    )
    parser.add_argument("--run-key", action="append", type=int, default=[], help="run_key afectado por el ETL. Se puede repetir.")
    parser.add_argument("--date-key", action="append", type=int, default=[], help="date_key YYYYMMDD a reconstruir. Se puede repetir.")
    parser.add_argument("--date-from", type=int, help="date_key inicial YYYYMMDD para reconstruccion por rango.")
    parser.add_argument("--date-to", type=int, help="date_key final YYYYMMDD para reconstruccion por rango.")
    parser.add_argument("--truncate-first", action="store_true", help="Vacía ambas tablas antes de reconstruir el alcance.")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.date_from and args.date_to and args.date_from > args.date_to:
        parser.error("--date-from no puede ser mayor que --date-to")

    env = parse_env()
    date_keys = tuple(sorted(set(args.date_key)))
    if args.run_key and not date_keys:
        date_keys = _resolve_run_date_keys(env, sorted(set(args.run_key)))
        if not date_keys:
            print(
                "Build app product history omitido | "
                f"run_keys={sorted(set(args.run_key))} | affected_date_keys=[]",
                flush=True,
            )
            return

    scope = BuildScope(
        date_keys=date_keys,
        date_from=args.date_from,
        date_to=args.date_to,
        truncate_first=args.truncate_first,
    )
    summary = build_app_product_history(env, scope)
    print(
        "Build app product history completado | "
        f"truncate_first={scope.truncate_first} | "
        f"date_keys={list(scope.date_keys)} | "
        f"date_from={scope.date_from} | "
        f"date_to={scope.date_to} | "
        f"chain_latest_date_key={summary['chain_latest_date_key']} | "
        f"chain_total_rows={summary['chain_total_rows']} | "
        f"store_latest_date_key={summary['store_latest_date_key']} | "
        f"store_total_rows={summary['store_total_rows']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
