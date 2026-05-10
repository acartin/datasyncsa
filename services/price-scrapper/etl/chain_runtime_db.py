#!/usr/bin/env python3
"""Runtime de cadenas respaldado por BD para scrapers y jobs ETL."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from etl.postgres_cli import run_psql


def _sql_literal(value: str) -> str:
    return value.replace("'", "''")


def list_active_chain_ids(env: dict[str, str]) -> list[str]:
    output = run_psql(
        env,
        sql="""
select chain_id
from public.mkt_dim_chain
where is_active = true
order by chain_id;
""",
        tuples_only=True,
    )
    return [line.strip() for line in output.splitlines() if line.strip()]


def list_active_chain_ids_by_engine(env: dict[str, str], engine: str) -> list[str]:
    quoted_engine = _sql_literal(engine)
    output = run_psql(
        env,
        sql=f"""
select chain_id
from public.mkt_dim_chain
where is_active = true
  and engine = '{quoted_engine}'
order by chain_id;
""",
        tuples_only=True,
    )
    return [line.strip() for line in output.splitlines() if line.strip()]


def load_chain_row(env: dict[str, str], chain_id: str) -> dict[str, Any]:
    quoted_chain_id = _sql_literal(chain_id)
    output = run_psql(
        env,
        sql=f"""
select
  chain_id,
  chain_name,
  short_label,
  catalog_id,
  base_url,
  engine,
  pricing_scope,
  pricing_context::text,
  engine_settings::text
from public.mkt_dim_chain
where is_active = true
  and chain_id = '{quoted_chain_id}';
""",
        tuples_only=True,
    )
    lines = [line for line in output.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError(f"No existe una cadena activa en BD para chain_id={chain_id!r}.")
    (
        payload_chain_id,
        chain_name,
        short_label,
        catalog_id,
        base_url,
        engine,
        pricing_scope,
        pricing_context_text,
        engine_settings_text,
    ) = lines[0].split("\t")

    return {
        "chain_id": payload_chain_id,
        "display_name": chain_name,
        "short_label": short_label or chain_name,
        "catalog_id": catalog_id or payload_chain_id,
        "base_url": base_url,
        "engine": engine,
        "pricing_scope": pricing_scope,
        "pricing_context": json.loads(pricing_context_text or "{}"),
        "engine_extras": json.loads(engine_settings_text or "{}"),
    }


def load_catalog_runtime_payload(env: dict[str, str], chain_id: str) -> dict[str, Any]:
    payload = load_chain_row(env, chain_id)
    quoted_chain_id = _sql_literal(chain_id)
    category_output = run_psql(
        env,
        sql=f"""
select
  category_name,
  category_slug,
  category_url,
  is_enabled,
  source_category_reference
from public.mkt_dim_category as cat
join public.mkt_dim_chain as chain
  on chain.chain_key = cat.chain_key
where chain.chain_id = '{quoted_chain_id}'
order by cat.category_name;
""",
        tuples_only=True,
    )

    categories: list[dict[str, Any]] = []
    for line in category_output.splitlines():
        if not line.strip():
            continue
        name, slug, url, is_enabled, category_reference = (line.split("\t") + ["", "", "", "", ""])[:5]
        category_payload = {
            "name": name,
            "slug": slug,
            "url": url or None,
            "enabled": is_enabled == "t",
        }
        if category_reference:
            category_payload["category_reference"] = category_reference
        categories.append(category_payload)

    payload["categories"] = categories
    return payload


def load_vtex_location_runtime_config(env: dict[str, str], chain_id: str) -> dict[str, Any]:
    payload = load_chain_row(env, chain_id)
    if payload["engine"] != "vtex":
        raise RuntimeError(f"Cadena {chain_id!r} no usa engine VTEX (engine={payload['engine']!r}).")
    extras = dict(payload.get("engine_extras") or {})
    return {
        "chain_id": payload["chain_id"],
        "base_url": payload["base_url"],
        "display_name": payload["display_name"],
        "sales_channel": extras.get("sales_channel"),
    }


def load_instaleap_location_runtime_config(env: dict[str, str], chain_id: str) -> dict[str, Any]:
    payload = load_chain_row(env, chain_id)
    if payload["engine"] != "instaleap":
        raise RuntimeError(
            f"Cadena {chain_id!r} no usa engine Instaleap (engine={payload['engine']!r})."
        )
    extras = dict(payload.get("engine_extras") or {})
    return {
        "chain_id": payload["chain_id"],
        "display_name": payload["display_name"],
        "client_id": extras.get("client_id"),
        "default_store_reference": extras.get("store_reference"),
        "default_store_internal_id": extras.get("store_internal_id"),
        "graphql_v2_endpoint": extras.get("graphql_v2_endpoint")
        or "https://nextgentheadless.instaleap.io/api/v2",
    }


def replace_vtex_root_categories(
    env: dict[str, str],
    *,
    chain_id: str,
    categories: list[dict[str, Any]],
) -> int:
    csv_buffer = io.StringIO()
    writer = csv.DictWriter(
        csv_buffer,
        fieldnames=["chain_id", "category_slug", "category_name", "category_url"],
        lineterminator="\n",
    )
    writer.writeheader()
    for category in categories:
        writer.writerow(
            {
                "chain_id": chain_id,
                "category_slug": str(category["slug"]).strip(),
                "category_name": str(category["name"]).strip(),
                "category_url": str(category["url"]).strip() if category.get("url") else None,
            }
        )

    quoted_chain_id = _sql_literal(chain_id)
    sql = f"""
begin;
create temp table tmp_mkt_dim_category_refresh (
  chain_id text,
  category_slug text,
  category_name text,
  category_url text
);
copy tmp_mkt_dim_category_refresh (
  chain_id,
  category_slug,
  category_name,
  category_url
) from stdin with (format csv, header true);
{csv_buffer.getvalue()}\\.

insert into public.mkt_dim_category (
  chain_key,
  category_slug,
  category_name,
  category_url,
  source_category_reference,
  is_enabled
)
select
  chain.chain_key,
  src.category_slug,
  src.category_name,
  src.category_url,
  null,
  coalesce(existing.is_enabled, false)
from tmp_mkt_dim_category_refresh as src
join public.mkt_dim_chain as chain
  on chain.chain_id = src.chain_id
left join public.mkt_dim_category as existing
  on existing.chain_key = chain.chain_key
 and existing.category_slug = src.category_slug
on conflict (chain_key, category_slug) do update
set
  category_name = excluded.category_name,
  category_url = excluded.category_url,
  updated_at = now();

delete from public.mkt_dim_category as cat
using public.mkt_dim_chain as chain
where chain.chain_key = cat.chain_key
  and chain.chain_id = '{quoted_chain_id}'
  and not exists (
    select 1
    from tmp_mkt_dim_category_refresh as src
    where src.category_slug = cat.category_slug
  );

select count(*)
from public.mkt_dim_category as cat
join public.mkt_dim_chain as chain
  on chain.chain_key = cat.chain_key
where chain.chain_id = '{quoted_chain_id}';
commit;
"""
    output = run_psql(env, sql=sql, tuples_only=True)
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return int(lines[-1])
