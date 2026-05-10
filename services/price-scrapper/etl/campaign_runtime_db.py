#!/usr/bin/env python3
"""Helpers de campañas para corridas analíticas."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Iterable

from etl.postgres_cli import run_psql


@dataclass(frozen=True)
class CampaignRow:
    id: int
    client_id: int | None
    name: str
    slug: str
    frequency_type: str
    frequency_note: str | None
    is_active: bool


@dataclass(frozen=True)
class CampaignLocationRow:
    campaign_id: int
    chain_key: int
    chain_id: str
    engine: str
    location_key: int
    location_name: str
    location_code: str
    sales_channel: str | None
    region_id: str | None
    source_location_ref: str | None
    source_internal_id: str | None


@dataclass(frozen=True)
class CampaignListingTargetRow:
    campaign_id: int
    chain_key: int
    chain_id: str
    engine: str
    product_key: int
    product_role: str
    gtin_raw: str | None
    gtin_norm: str | None
    brand_name: str | None
    product_name: str
    content_quantity: str | None
    content_unit: str | None
    listing_key: int
    source_product_id: str
    source_sku: str
    seller_id: str
    seller_name: str | None
    listing_name: str
    product_url: str | None
    image_url: str | None
    root_category_slug: str | None
    root_category_name: str | None


def _chain_filter_sql(chain_ids: Iterable[str] | None) -> str:
    if not chain_ids:
        return ""
    values = ", ".join("'" + str(chain_id).replace("'", "''") + "'" for chain_id in sorted(set(chain_ids)))
    return f" and c.chain_id in ({values})"


def _parse_copy_csv(output: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(output))
    return [dict(row) for row in reader]


def _flatten_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = " ".join(value.replace("\r", " ").replace("\n", " ").split()).strip()
    return text or None


def load_campaign_row(env: dict[str, str], campaign_id: int) -> CampaignRow:
    output = run_psql(
        env,
        sql=f"""
copy (
  select
    id,
    client_id::text,
    name,
    slug,
    frequency_type,
    frequency_note,
    is_active::text
  from public.mkt_dim_campaign
  where id = {int(campaign_id)}
) to stdout with (format csv, header true);
""",
    )
    rows = _parse_copy_csv(output)
    if not rows:
        raise RuntimeError(f"No existe la campaña campaign_id={campaign_id}.")
    row = rows[0]
    return CampaignRow(
        id=int(row["id"]),
        client_id=int(row["client_id"]) if row["client_id"] else None,
        name=row["name"].strip(),
        slug=row["slug"].strip(),
        frequency_type=row["frequency_type"].strip(),
        frequency_note=_flatten_text(row["frequency_note"]),
        is_active=row["is_active"] == "t",
    )


def fetch_campaign_locations(
    env: dict[str, str],
    campaign_id: int,
    *,
    chain_ids: Iterable[str] | None = None,
    business_date_key: int | None = None,
    only_pending: bool = False,
) -> list[CampaignLocationRow]:
    chain_filter = _chain_filter_sql(chain_ids)
    pending_filter = ""
    if only_pending:
        if business_date_key is None:
            raise RuntimeError("only_pending requiere business_date_key para campañas analíticas.")
        pending_filter = f"""
    and not exists (
      select 1
      from public.mkt_run r
      where r.campaign_id = {int(campaign_id)}
        and r.business_date_key = {int(business_date_key)}
        and r.run_kind = 'analytic'
        and r.run_status = 'succeeded'
        and r.location_key = l.location_key
    )
"""

    output = run_psql(
        env,
        sql=f"""
copy (
  select
    cl.campaign_id,
    c.chain_key,
    c.chain_id,
    c.engine,
    l.location_key,
    l.location_name,
    l.location_code,
    l.sales_channel,
    l.region_id,
    l.source_location_ref,
    l.source_internal_id
  from public.mkt_campaign_location cl
  join public.mkt_dim_location l
    on l.location_key = cl.location_key
  join public.mkt_dim_chain c
    on c.chain_key = l.chain_key
  where cl.campaign_id = {int(campaign_id)}
{chain_filter}
    and l.is_active = true
{pending_filter}
  order by c.chain_id, l.location_name
) to stdout with (format csv, header true);
""",
    )
    rows: list[CampaignLocationRow] = []
    for payload in _parse_copy_csv(output):
        rows.append(
            CampaignLocationRow(
                campaign_id=int(payload["campaign_id"]),
                chain_key=int(payload["chain_key"]),
                chain_id=payload["chain_id"].strip(),
                engine=payload["engine"].strip(),
                location_key=int(payload["location_key"]),
                location_name=payload["location_name"].strip(),
                location_code=payload["location_code"].strip(),
                sales_channel=_flatten_text(payload["sales_channel"]),
                region_id=_flatten_text(payload["region_id"]),
                source_location_ref=_flatten_text(payload["source_location_ref"]),
                source_internal_id=_flatten_text(payload["source_internal_id"]),
            )
        )
    return rows


def fetch_campaign_listing_targets(
    env: dict[str, str],
    campaign_id: int,
    *,
    chain_ids: Iterable[str] | None = None,
) -> list[CampaignListingTargetRow]:
    chain_filter = _chain_filter_sql(chain_ids)

    output = run_psql(
        env,
        sql=f"""
copy (
  select
    cp.campaign_id,
    c.chain_key,
    c.chain_id,
    c.engine,
    p.product_key,
    cp.product_role,
    p.gtin_raw,
    p.gtin_norm,
    p.brand_name,
    p.product_name,
    p.content_quantity::text,
    p.content_unit,
    l.listing_key,
    l.source_product_id,
    l.source_sku,
    l.seller_id,
    l.seller_name,
    l.listing_name,
    l.product_url,
    l.image_url,
    l.root_category_slug,
    l.root_category_name
  from public.mkt_campaign_product cp
  join public.mkt_dim_product p
    on p.product_key = cp.product_key
  join public.mkt_dim_listing l
    on l.product_key = p.product_key
  join public.mkt_dim_chain c
    on c.chain_key = l.chain_key
  where cp.campaign_id = {int(campaign_id)}
{chain_filter}
    and l.is_active = true
  order by c.chain_id, cp.product_role desc, p.brand_name, p.product_name
) to stdout with (format csv, header true);
""",
    )
    rows: list[CampaignListingTargetRow] = []
    for payload in _parse_copy_csv(output):
        rows.append(
            CampaignListingTargetRow(
                campaign_id=int(payload["campaign_id"]),
                chain_key=int(payload["chain_key"]),
                chain_id=payload["chain_id"].strip(),
                engine=payload["engine"].strip(),
                product_key=int(payload["product_key"]),
                product_role=payload["product_role"].strip(),
                gtin_raw=_flatten_text(payload["gtin_raw"]),
                gtin_norm=_flatten_text(payload["gtin_norm"]),
                brand_name=_flatten_text(payload["brand_name"]),
                product_name=payload["product_name"].strip(),
                content_quantity=_flatten_text(payload["content_quantity"]),
                content_unit=_flatten_text(payload["content_unit"]),
                listing_key=int(payload["listing_key"]),
                source_product_id=payload["source_product_id"].strip(),
                source_sku=payload["source_sku"].strip(),
                seller_id=payload["seller_id"].strip(),
                seller_name=_flatten_text(payload["seller_name"]),
                listing_name=payload["listing_name"].strip(),
                product_url=_flatten_text(payload["product_url"]),
                image_url=_flatten_text(payload["image_url"]),
                root_category_slug=_flatten_text(payload["root_category_slug"]),
                root_category_name=_flatten_text(payload["root_category_name"]),
            )
        )
    return rows
