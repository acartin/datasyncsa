from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import date
from decimal import Decimal
import json
import re
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

import psycopg
from psycopg import errors


ConnectionFactory = Callable[[], AbstractContextManager[psycopg.Connection]]

_MEASURE_SUFFIX_RE = re.compile(
    r"\s*-\s*\d+(?:[.,]\d+)?\s*(g|gr|kg|ml|l|lt|lts|un|u|ud|uds)\b\s*$",
    re.IGNORECASE,
)


class MarketRepository:
    def __init__(self, connection_factory: ConnectionFactory) -> None:
        self._connection_factory = connection_factory

    @staticmethod
    def _report_signal_family(signal_type: object) -> tuple[str, str]:
        value = str(signal_type or "").lower()
        if value == "driver_sku_detected":
            return ("driver_sku", "Driver SKU")
        if value in {"brand_over_market", "brand_under_market"}:
            return ("market_position", "Market position")
        if "promo" in value:
            return ("promotion", "Promotion")
        if "stock" in value or "availability" in value or "oos" in value:
            return ("availability", "Availability")
        if "price" in value or "gap" in value or "market" in value:
            return ("price_gap", "Price gap")
        return ("other", "Other")

    @classmethod
    def _report_highlights(cls, signals: list[dict[str, object]], *, limit: int = 4) -> list[dict[str, object]]:
        severity_rank = {"critical": 5, "high": 4, "medium": 3, "low": 2}
        family_rank = {
            "price_gap": 6,
            "driver_sku": 5,
            "market_position": 4,
            "promotion": 3,
            "availability": 2,
            "other": 1,
        }

        selected: dict[str, dict[str, object]] = {}
        for signal in signals:
            family_id, family_label = cls._report_signal_family(signal.get("signal_type"))
            candidate = {
                **signal,
                "family_id": family_id,
                "family_label": family_label,
            }
            current = selected.get(family_id)

            def score(row: dict[str, object]) -> tuple[int, float, int]:
                severity = str(row.get("severity") or "").lower()
                impact = float(row.get("impact_score") or 0)
                repeat_count = int(row.get("repeat_count") or 0)
                return (severity_rank.get(severity, 1), impact, repeat_count)

            if current is None or score(candidate) > score(current):
                selected[family_id] = candidate

        return sorted(
            selected.values(),
            key=lambda row: (
                family_rank.get(str(row.get("family_id")), 0),
                severity_rank.get(str(row.get("severity") or "").lower(), 1),
                float(row.get("impact_score") or 0),
            ),
            reverse=True,
        )[:limit]

    @staticmethod
    def _format_report_metric(value: object, value_format: object = None) -> str:
        if value is None:
            return "-"
        if isinstance(value, Decimal):
            value = float(value)
        metric_format = str(value_format or "")
        if metric_format == "currency":
            return f"₡{float(value):,.0f}"
        if metric_format == "percent":
            return f"{float(value):.1f}%"
        if isinstance(value, float):
            if value.is_integer():
                return str(int(value))
            return f"{value:.2f}".rstrip("0").rstrip(".")
        return str(value)

    @classmethod
    def _radar_report_highlights(cls, events: list[dict[str, object]]) -> list[dict[str, object]]:
        highlights: list[dict[str, object]] = []
        for event in events:
            product = str(event.get("product") or "Product")
            chain = str(event.get("chain") or "chain")
            label = str(event.get("short_label") or event.get("display_label") or event.get("event_type") or "Radar event")
            previous_label = str(event.get("metric_previous_label") or "Previous")
            current_label = str(event.get("metric_current_label") or "Current")
            change_label = str(event.get("metric_change_label") or "Change")
            previous_value = cls._format_report_metric(event.get("previous_value"), event.get("value_format"))
            current_value = cls._format_report_metric(event.get("current_value"), event.get("value_format"))
            change_value = cls._format_report_metric(
                event.get("change_pct") if event.get("change_pct") is not None else event.get("change_amount"),
                "percent" if event.get("change_pct") is not None else event.get("change_format"),
            )
            highlights.append(
                {
                    **event,
                    "source": "radar",
                    "family_id": str(event.get("event_area") or "radar"),
                    "family_label": str(event.get("event_area") or "Radar").replace("_", " ").title(),
                    "headline": f"{label}: {product} in {chain}",
                    "summary": f"{previous_label}: {previous_value}. {current_label}: {current_value}. {change_label}: {change_value}.",
                }
            )
        return highlights

    def fetch_overview(self, *, client_id: str) -> dict[str, object]:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    with scoped_runs as (
                      select r.run_key, r.chain_key, r.campaign_id
                      from public.mkt_run r
                      join public.mkt_campaign_client_access cca
                        on cca.campaign_id = r.campaign_id
                       and cca.is_active
                       and cca.client_id::text = %(client_id)s
                       and (
                         cca.valid_from is null
                         or to_date(r.business_date_key::text, 'YYYYMMDD') >= cca.valid_from
                       )
                       and (
                         cca.valid_to is null
                         or to_date(r.business_date_key::text, 'YYYYMMDD') <= cca.valid_to
                       )
                      where r.run_status = 'succeeded'
                    )
                    select
                      count(distinct run_key)::int as run_count,
                      count(distinct chain_key)::int as chain_count,
                      count(distinct campaign_id)::int as campaign_count
                    from scoped_runs;
                    """,
                    {"client_id": client_id},
                )
                summary = dict(cursor.fetchone() or {})

                cursor.execute(
                    """
                    select
                      r.run_key,
                      r.run_kind,
                      r.started_at,
                      r.finished_at,
                      r.catalog_records,
                      ch.chain_id,
                      ch.chain_name,
                      c.name as campaign_name
                    from public.mkt_run r
                    left join public.mkt_dim_chain ch
                      on ch.chain_key = r.chain_key
                    left join public.mkt_dim_campaign c
                      on c.id = r.campaign_id
                    join public.mkt_campaign_client_access cca
                      on cca.campaign_id = r.campaign_id
                     and cca.is_active
                     and cca.client_id::text = %(client_id)s
                     and (
                       cca.valid_from is null
                       or to_date(r.business_date_key::text, 'YYYYMMDD') >= cca.valid_from
                     )
                     and (
                       cca.valid_to is null
                       or to_date(r.business_date_key::text, 'YYYYMMDD') <= cca.valid_to
                     )
                    where r.run_status = 'succeeded'
                    order by r.started_at desc, r.run_key desc
                    limit 10;
                    """,
                    {"client_id": client_id},
                )
                recent_runs = [self._json_ready(row) for row in cursor.fetchall()]

        return {
            "client_id": client_id,
            "summary": summary,
            "recent_runs": recent_runs,
        }

    def fetch_products(
        self,
        *,
        client_id: str,
        query: str | None,
        limit: int,
        offset: int,
    ) -> dict[str, object]:
        params: dict[str, Any] = {
            "client_id": client_id,
            "limit": limit,
            "offset": offset,
            "query": f"%{query.strip()}%" if query else None,
        }
        query_filter = """
          and (
            %(query)s::text is null
            or p.product_name ilike %(query)s
            or p.brand_name ilike %(query)s
            or p.gtin_norm ilike %(query)s
          )
        """

        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    with scoped_products as (
                      select distinct f.product_key
                      from public.mkt_fact_listing_snapshot f
                      join public.mkt_run r
                        on r.run_key = f.run_key
                      join public.mkt_campaign_client_access cca
                        on cca.campaign_id = r.campaign_id
                       and cca.is_active
                       and cca.client_id::text = %(client_id)s
                       and (
                         cca.valid_from is null
                         or to_date(r.business_date_key::text, 'YYYYMMDD') >= cca.valid_from
                       )
                       and (
                         cca.valid_to is null
                         or to_date(r.business_date_key::text, 'YYYYMMDD') <= cca.valid_to
                       )
                      where r.run_status = 'succeeded'
                    )
                    select
                      p.product_key,
                      p.gtin_norm,
                      p.brand_name,
                      p.product_name,
                      p.content_quantity,
                      p.content_unit
                    from scoped_products sp
                    join public.mkt_dim_product p
                      on p.product_key = sp.product_key
                    where p.is_active = true
                    {query_filter}
                    order by p.product_name, p.product_key
                    limit %(limit)s offset %(offset)s;
                    """,
                    params,
                )
                rows = [self._json_ready(row) for row in cursor.fetchall()]

        return {
            "client_id": client_id,
            "limit": limit,
            "offset": offset,
            "items": rows,
        }

    def fetch_price_matrix(
        self,
        *,
        client_id: str,
        campaign_id: int | None,
        limit: int,
    ) -> dict[str, object]:
        params: dict[str, Any] = {
            "client_id": client_id,
            "campaign_id": campaign_id,
            "limit": limit,
        }

        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    with scoped_runs as (
                      select r.run_key
                      from public.mkt_run r
                      join public.mkt_campaign_client_access cca
                        on cca.campaign_id = r.campaign_id
                       and cca.is_active
                       and cca.client_id::text = %(client_id)s
                       and (
                         cca.valid_from is null
                         or to_date(r.business_date_key::text, 'YYYYMMDD') >= cca.valid_from
                       )
                       and (
                         cca.valid_to is null
                         or to_date(r.business_date_key::text, 'YYYYMMDD') <= cca.valid_to
                       )
                      where r.run_status = 'succeeded'
                        and (%(campaign_id)s::int is null or r.campaign_id = %(campaign_id)s)
                    ),
                    latest as (
                      select distinct on (f.product_key, f.chain_key)
                        f.product_key,
                        f.chain_key,
                        f.price_amount,
                        f.list_price_amount,
                        f.has_discount,
                        r.run_key
                      from public.mkt_fact_listing_snapshot f
                      join scoped_runs r
                        on r.run_key = f.run_key
                      order by f.product_key, f.chain_key, r.run_key desc
                    )
                    select
                      p.product_key,
                      p.product_name,
                      p.brand_name,
                      ch.chain_id,
                      ch.chain_name,
                      l.price_amount,
                      l.list_price_amount,
                      l.has_discount,
                      l.run_key
                    from latest l
                    join public.mkt_dim_product p
                      on p.product_key = l.product_key
                    join public.mkt_dim_chain ch
                      on ch.chain_key = l.chain_key
                    order by p.product_name, ch.chain_id
                    limit %(limit)s;
                    """,
                    params,
                )
                rows = [self._json_ready(row) for row in cursor.fetchall()]

        return {
            "client_id": client_id,
            "campaign_id": campaign_id,
            "limit": limit,
            "items": rows,
        }

    def list_campaigns_for_client(self, *, client_id: str) -> list[dict[str, object]]:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select
                      c.id::text as id,
                      c.name,
                      c.slug,
                      case
                        when c.deleted_at is not null then 'deleted'
                        when c.is_active then 'active'
                        else 'inactive'
                      end as status,
                      c.description,
                      current_access.access_role,
                      current_access.is_default,
                      count(distinct cp.product_key)::int as products,
                      count(distinct cl.location_key)::int as locations,
                      count(distinct all_access.client_id)::int as authorized_clients
                    from public.mkt_dim_campaign c
                    join public.mkt_campaign_client_access current_access
                      on current_access.campaign_id = c.id
                     and current_access.client_id::text = %(client_id)s
                     and current_access.is_active
                     and (current_access.valid_from is null or current_date >= current_access.valid_from)
                     and (current_access.valid_to is null or current_date <= current_access.valid_to)
                    left join public.mkt_campaign_product cp
                      on cp.campaign_id = c.id
                    left join public.mkt_campaign_location cl
                      on cl.campaign_id = c.id
                    left join public.mkt_campaign_client_access all_access
                      on all_access.campaign_id = c.id
                     and all_access.is_active
                    where c.deleted_at is null
                    group by
                      c.id,
                      c.name,
                      c.slug,
                      c.deleted_at,
                      c.is_active,
                      c.description,
                      current_access.access_role,
                      current_access.is_default
                    order by c.name;
                    """,
                    {"client_id": client_id},
                )
                return [self._json_ready(row) for row in cursor.fetchall()]

    def create_campaign(
        self,
        *,
        client_id: str,
        name: str,
        slug: str,
        description: str | None,
        is_active: bool,
        access_role: str,
        is_default: bool,
    ) -> dict[str, object]:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    insert into public.mkt_dim_campaign (
                      name,
                      slug,
                      description,
                      is_active
                    )
                    values (
                      %(name)s,
                      %(slug)s,
                      %(description)s,
                      %(is_active)s
                    )
                    returning id;
                    """,
                    {
                        "name": name,
                        "slug": slug,
                        "description": description,
                        "is_active": is_active,
                    },
                )
                campaign = cursor.fetchone()
                campaign_id = int(campaign["id"])

                cursor.execute(
                    """
                    insert into public.mkt_campaign_client_access (
                      campaign_id,
                      client_id,
                      access_role,
                      is_default,
                      is_active
                    )
                    values (
                      %(campaign_id)s,
                      %(client_id)s::bigint,
                      %(access_role)s,
                      %(is_default)s,
                      true
                    );
                    """,
                    {
                        "campaign_id": campaign_id,
                        "client_id": client_id,
                        "access_role": access_role,
                        "is_default": is_default,
                    },
                )

                row = self._fetch_campaign_for_client(cursor, campaign_id=campaign_id, client_id=client_id)
                connection.commit()
                return row or {"id": str(campaign_id), "name": name, "slug": slug, "status": "active" if is_active else "inactive"}

    def update_campaign(
        self,
        *,
        client_id: str,
        campaign_id: int,
        name: str | None,
        slug: str | None,
        description: str | None,
        is_active: bool | None,
        is_system_operator: bool,
    ) -> dict[str, object] | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    update public.mkt_dim_campaign c
                    set
                      name = coalesce(%(name)s, c.name),
                      slug = coalesce(%(slug)s, c.slug),
                      description = coalesce(%(description)s, c.description),
                      is_active = coalesce(%(is_active)s, c.is_active),
                      updated_at = now()
                    where c.id = %(campaign_id)s
                      and c.deleted_at is null
                      and exists (
                        select 1
                        from public.mkt_campaign_client_access cca
                        where cca.campaign_id = c.id
                          and cca.client_id::text = %(client_id)s
                          and cca.is_active
                          and (cca.valid_from is null or current_date >= cca.valid_from)
                          and (cca.valid_to is null or current_date <= cca.valid_to)
                          and (
                            %(is_system_operator)s
                            or cca.access_role in ('owner', 'admin')
                          )
                      )
                    returning c.id;
                    """,
                    {
                        "client_id": client_id,
                        "campaign_id": campaign_id,
                        "name": name,
                        "slug": slug,
                        "description": description,
                        "is_active": is_active,
                        "is_system_operator": is_system_operator,
                    },
                )
                row = cursor.fetchone()
                if not row:
                    connection.commit()
                    return None

                campaign = self._fetch_campaign_for_client(cursor, campaign_id=campaign_id, client_id=client_id)
                connection.commit()
                return campaign

    def _fetch_campaign_for_client(self, cursor: psycopg.Cursor, *, campaign_id: int, client_id: str) -> dict[str, object] | None:
        cursor.execute(
            """
            select
              c.id::text as id,
              c.name,
              c.slug,
              case
                when c.deleted_at is not null then 'deleted'
                when c.is_active then 'active'
                else 'inactive'
              end as status,
              c.description,
              current_access.access_role,
              current_access.is_default,
              count(distinct cp.product_key)::int as products,
              count(distinct cl.location_key)::int as locations,
              count(distinct all_access.client_id)::int as authorized_clients
            from public.mkt_dim_campaign c
            join public.mkt_campaign_client_access current_access
              on current_access.campaign_id = c.id
             and current_access.client_id::text = %(client_id)s
             and current_access.is_active
             and (current_access.valid_from is null or current_date >= current_access.valid_from)
             and (current_access.valid_to is null or current_date <= current_access.valid_to)
            left join public.mkt_campaign_product cp
              on cp.campaign_id = c.id
            left join public.mkt_campaign_location cl
              on cl.campaign_id = c.id
            left join public.mkt_campaign_client_access all_access
              on all_access.campaign_id = c.id
             and all_access.is_active
            where c.id = %(campaign_id)s
              and c.deleted_at is null
            group by
              c.id,
              c.name,
              c.slug,
              c.deleted_at,
              c.is_active,
              c.description,
              current_access.access_role,
              current_access.is_default
            limit 1;
            """,
            {"client_id": client_id, "campaign_id": campaign_id},
        )
        row = cursor.fetchone()
        return self._json_ready(row) if row else None

    def list_campaign_access_client_options(self) -> list[dict[str, object]]:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select
                      id::text as id,
                      name,
                      client_key,
                      market,
                      mode,
                      status
                    from public.auth_clients
                    where status = 'active'
                    order by name;
                    """
                )
                return [self._json_ready(row) for row in cursor.fetchall()]

    def _fetch_campaign_access(
        self,
        cursor: psycopg.Cursor,
        *,
        campaign_id: int,
        client_id: int,
    ) -> dict[str, object] | None:
        cursor.execute(
            """
            select
              ac.id::text as client_id,
              ac.name as client,
              ac.market,
              ac.status as client_status,
              cca.access_role,
              cca.is_default,
              cca.is_active,
              cca.valid_from,
              cca.valid_to
            from public.mkt_campaign_client_access cca
            join public.auth_clients ac
              on ac.id = cca.client_id
            where cca.campaign_id = %(campaign_id)s
              and cca.client_id = %(client_id)s
            limit 1;
            """,
            {"campaign_id": campaign_id, "client_id": client_id},
        )
        row = cursor.fetchone()
        return self._json_ready(row) if row else None

    def upsert_campaign_client_access(
        self,
        *,
        campaign_id: int,
        client_id: int,
        access_role: str,
        is_default: bool,
        is_active: bool,
        valid_from: date | None,
        valid_to: date | None,
    ) -> dict[str, object] | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select exists (
                      select 1
                      from public.mkt_dim_campaign
                      where id = %(campaign_id)s
                        and deleted_at is null
                    ) as campaign_exists,
                    exists (
                      select 1
                      from public.auth_clients
                      where id = %(client_id)s
                    ) as client_exists;
                    """,
                    {"campaign_id": campaign_id, "client_id": client_id},
                )
                exists_row = cursor.fetchone()
                if not exists_row or not exists_row["campaign_exists"] or not exists_row["client_exists"]:
                    connection.commit()
                    return None

                if is_default:
                    cursor.execute(
                        """
                        update public.mkt_campaign_client_access
                        set is_default = false,
                            updated_at = now()
                        where client_id = %(client_id)s
                          and campaign_id <> %(campaign_id)s;
                        """,
                        {"campaign_id": campaign_id, "client_id": client_id},
                    )

                cursor.execute(
                    """
                    insert into public.mkt_campaign_client_access (
                      campaign_id,
                      client_id,
                      access_role,
                      is_default,
                      is_active,
                      valid_from,
                      valid_to
                    )
                    values (
                      %(campaign_id)s,
                      %(client_id)s,
                      %(access_role)s,
                      %(is_default)s,
                      %(is_active)s,
                      %(valid_from)s,
                      %(valid_to)s
                    )
                    on conflict (campaign_id, client_id) do update
                    set access_role = excluded.access_role,
                        is_default = excluded.is_default,
                        is_active = excluded.is_active,
                        valid_from = excluded.valid_from,
                        valid_to = excluded.valid_to,
                        updated_at = now();
                    """,
                    {
                        "campaign_id": campaign_id,
                        "client_id": client_id,
                        "access_role": access_role,
                        "is_default": is_default,
                        "is_active": is_active,
                        "valid_from": valid_from,
                        "valid_to": valid_to,
                    },
                )
                access = self._fetch_campaign_access(cursor, campaign_id=campaign_id, client_id=client_id)
                connection.commit()
                return access

    def update_campaign_client_access(
        self,
        *,
        campaign_id: int,
        client_id: int,
        access_role: str | None,
        is_default: bool | None,
        is_active: bool | None,
        valid_from: date | None,
        valid_to: date | None,
    ) -> dict[str, object] | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                if is_default:
                    cursor.execute(
                        """
                        update public.mkt_campaign_client_access
                        set is_default = false,
                            updated_at = now()
                        where client_id = %(client_id)s
                          and campaign_id <> %(campaign_id)s;
                        """,
                        {"campaign_id": campaign_id, "client_id": client_id},
                    )

                cursor.execute(
                    """
                    update public.mkt_campaign_client_access cca
                    set
                      access_role = coalesce(%(access_role)s, cca.access_role),
                      is_default = coalesce(%(is_default)s, cca.is_default),
                      is_active = coalesce(%(is_active)s, cca.is_active),
                      valid_from = coalesce(%(valid_from)s, cca.valid_from),
                      valid_to = coalesce(%(valid_to)s, cca.valid_to),
                      updated_at = now()
                    where cca.campaign_id = %(campaign_id)s
                      and cca.client_id = %(client_id)s
                      and exists (
                        select 1
                        from public.mkt_dim_campaign c
                        where c.id = cca.campaign_id
                          and c.deleted_at is null
                      )
                    returning cca.campaign_id;
                    """,
                    {
                        "campaign_id": campaign_id,
                        "client_id": client_id,
                        "access_role": access_role,
                        "is_default": is_default,
                        "is_active": is_active,
                        "valid_from": valid_from,
                        "valid_to": valid_to,
                    },
                )
                row = cursor.fetchone()
                if not row:
                    connection.commit()
                    return None
                access = self._fetch_campaign_access(cursor, campaign_id=campaign_id, client_id=client_id)
                connection.commit()
                return access

    def list_campaign_chain_options(self) -> list[dict[str, object]]:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select
                      ch.chain_key::text as id,
                      ch.chain_id,
                      ch.chain_name,
                      ch.engine,
                      ch.pricing_scope,
                      ch.country_code,
                      ch.is_active,
                      count(l.location_key)::int as stores,
                      count(l.location_key) filter (where l.is_active)::int as active_stores
                    from public.mkt_dim_chain ch
                    left join public.mkt_dim_location l
                      on l.chain_key = ch.chain_key
                    group by
                      ch.chain_key,
                      ch.chain_id,
                      ch.chain_name,
                      ch.engine,
                      ch.pricing_scope,
                      ch.country_code,
                      ch.is_active
                    order by ch.chain_name;
                    """
                )
                return [self._json_ready(row) for row in cursor.fetchall()]

    def assign_campaign_chain(self, *, campaign_id: int, chain_key: int) -> dict[str, object] | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select exists (
                      select 1
                      from public.mkt_dim_campaign
                      where id = %(campaign_id)s
                        and deleted_at is null
                    ) as campaign_exists,
                    exists (
                      select 1
                      from public.mkt_dim_chain
                      where chain_key = %(chain_key)s
                    ) as chain_exists;
                    """,
                    {"campaign_id": campaign_id, "chain_key": chain_key},
                )
                exists_row = cursor.fetchone()
                if not exists_row or not exists_row["campaign_exists"] or not exists_row["chain_exists"]:
                    connection.commit()
                    return None

                cursor.execute(
                    """
                    insert into public.mkt_campaign_location (
                      campaign_id,
                      location_key
                    )
                    select
                      %(campaign_id)s,
                      l.location_key
                    from public.mkt_dim_location l
                    where l.chain_key = %(chain_key)s
                      and l.is_active
                    on conflict (campaign_id, location_key) do update
                    set updated_at = now();
                    """,
                    {"campaign_id": campaign_id, "chain_key": chain_key},
                )

                cursor.execute(
                    """
                    select
                      ch.chain_key::text as id,
                      ch.chain_id,
                      ch.chain_name,
                      ch.engine,
                      ch.pricing_scope,
                      ch.country_code,
                      count(cl.location_key)::int as assigned_locations
                    from public.mkt_dim_chain ch
                    left join public.mkt_dim_location l
                      on l.chain_key = ch.chain_key
                     and l.is_active
                    left join public.mkt_campaign_location cl
                      on cl.location_key = l.location_key
                     and cl.campaign_id = %(campaign_id)s
                    where ch.chain_key = %(chain_key)s
                    group by
                      ch.chain_key,
                      ch.chain_id,
                      ch.chain_name,
                      ch.engine,
                      ch.pricing_scope,
                      ch.country_code;
                    """,
                    {"campaign_id": campaign_id, "chain_key": chain_key},
                )
                row = cursor.fetchone()
                connection.commit()
                return self._json_ready(row) if row else None

    def remove_campaign_chain(self, *, campaign_id: int, chain_key: int) -> dict[str, object] | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select exists (
                      select 1
                      from public.mkt_dim_campaign
                      where id = %(campaign_id)s
                        and deleted_at is null
                    ) as campaign_exists,
                    exists (
                      select 1
                      from public.mkt_dim_chain
                      where chain_key = %(chain_key)s
                    ) as chain_exists;
                    """,
                    {"campaign_id": campaign_id, "chain_key": chain_key},
                )
                exists_row = cursor.fetchone()
                if not exists_row or not exists_row["campaign_exists"] or not exists_row["chain_exists"]:
                    connection.commit()
                    return None

                cursor.execute(
                    """
                    delete from public.mkt_campaign_location cl
                    using public.mkt_dim_location l
                    where cl.location_key = l.location_key
                      and cl.campaign_id = %(campaign_id)s
                      and l.chain_key = %(chain_key)s;
                    """,
                    {"campaign_id": campaign_id, "chain_key": chain_key},
                )
                removed_locations = cursor.rowcount
                connection.commit()
                return {
                    "campaign_id": str(campaign_id),
                    "chain_key": str(chain_key),
                    "removed_locations": removed_locations,
                }

    def list_campaign_store_options(self) -> list[dict[str, object]]:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select
                      l.location_key::text as id,
                      l.location_key::text as location_key,
                      ch.chain_key::text as chain_key,
                      ch.chain_id,
                      ch.chain_name,
                      l.location_name as store,
                      l.location_code,
                      l.sales_channel,
                      l.province,
                      l.canton,
                      l.district,
                      l.is_default,
                      l.is_active
                    from public.mkt_dim_location l
                    join public.mkt_dim_chain ch
                      on ch.chain_key = l.chain_key
                    where l.is_active
                      and ch.is_active
                    order by ch.chain_name, l.location_name;
                    """
                )
                return [self._json_ready(row) for row in cursor.fetchall()]

    def _fetch_campaign_store(
        self,
        cursor: psycopg.Cursor,
        *,
        campaign_id: int,
        location_key: int,
    ) -> dict[str, object] | None:
        cursor.execute(
            """
            select
              l.location_key::text as id,
              ch.chain_name,
              l.location_name as store,
              l.location_code,
              l.sales_channel,
              l.province,
              l.canton,
              l.district,
              l.is_default,
              l.is_active
            from public.mkt_campaign_location cl
            join public.mkt_dim_location l
              on l.location_key = cl.location_key
            join public.mkt_dim_chain ch
              on ch.chain_key = l.chain_key
            where cl.campaign_id = %(campaign_id)s
              and cl.location_key = %(location_key)s
            limit 1;
            """,
            {"campaign_id": campaign_id, "location_key": location_key},
        )
        row = cursor.fetchone()
        return self._json_ready(row) if row else None

    def assign_campaign_store(self, *, campaign_id: int, location_key: int) -> dict[str, object] | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select exists (
                      select 1
                      from public.mkt_dim_campaign
                      where id = %(campaign_id)s
                        and deleted_at is null
                    ) as campaign_exists,
                    exists (
                      select 1
                      from public.mkt_dim_location
                      where location_key = %(location_key)s
                        and is_active
                    ) as store_exists;
                    """,
                    {"campaign_id": campaign_id, "location_key": location_key},
                )
                exists_row = cursor.fetchone()
                if not exists_row or not exists_row["campaign_exists"] or not exists_row["store_exists"]:
                    connection.commit()
                    return None

                cursor.execute(
                    """
                    insert into public.mkt_campaign_location (
                      campaign_id,
                      location_key
                    )
                    values (
                      %(campaign_id)s,
                      %(location_key)s
                    )
                    on conflict (campaign_id, location_key) do update
                    set updated_at = now();
                    """,
                    {"campaign_id": campaign_id, "location_key": location_key},
                )
                store = self._fetch_campaign_store(cursor, campaign_id=campaign_id, location_key=location_key)
                connection.commit()
                return store

    def remove_campaign_store(self, *, campaign_id: int, location_key: int) -> dict[str, object] | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select exists (
                      select 1
                      from public.mkt_dim_campaign
                      where id = %(campaign_id)s
                        and deleted_at is null
                    ) as campaign_exists,
                    exists (
                      select 1
                      from public.mkt_dim_location
                      where location_key = %(location_key)s
                    ) as store_exists;
                    """,
                    {"campaign_id": campaign_id, "location_key": location_key},
                )
                exists_row = cursor.fetchone()
                if not exists_row or not exists_row["campaign_exists"] or not exists_row["store_exists"]:
                    connection.commit()
                    return None

                cursor.execute(
                    """
                    delete from public.mkt_campaign_location
                    where campaign_id = %(campaign_id)s
                      and location_key = %(location_key)s;
                    """,
                    {"campaign_id": campaign_id, "location_key": location_key},
                )
                removed_locations = cursor.rowcount
                connection.commit()
                return {
                    "campaign_id": str(campaign_id),
                    "location_key": str(location_key),
                    "removed_locations": removed_locations,
                }

    def list_campaign_product_options(self) -> list[dict[str, object]]:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    with product_media as (
                      select distinct on (l.product_key)
                        l.product_key,
                        l.product_url,
                        l.image_url
                      from public.mkt_dim_listing l
                      where l.product_key is not null
                        and (l.product_url is not null or l.image_url is not null)
                      order by
                        l.product_key,
                        case when l.image_url is not null then 0 else 1 end,
                        l.updated_at desc nulls last,
                        l.created_at desc nulls last
                    ),
                    chain_coverage as (
                      select
                        product_key,
                        jsonb_agg(
                          jsonb_build_object(
                            'chain_key', chain_key::text,
                            'chain_id', chain_id,
                            'chain_name', chain_name,
                            'active_listings', active_listings,
                            'listings_seen', listings_seen
                          )
                          order by chain_name
                        ) as chain_coverage
                      from public.mw_product_chain_coverage_detail
                      where active_listings > 0
                      group by product_key
                    )
                    select
                      p.product_key::text as id,
                      p.product_key::text as product_key,
                      p.brand_name as brand,
                      p.product_name as product,
                      p.gtin_norm,
                      p.content_quantity,
                      p.content_unit,
                      product_media.product_url,
                      product_media.image_url,
                      coalesce(chain_coverage.chain_coverage, '[]'::jsonb) as chain_coverage,
                      p.is_active
                    from public.mkt_dim_product p
                    left join product_media
                      on product_media.product_key = p.product_key
                    left join chain_coverage
                      on chain_coverage.product_key = p.product_key
                    where p.is_active
                    order by p.brand_name nulls last, p.product_name, p.product_key
                    limit 2000;
                    """
                )
                return [self._json_ready(row) for row in cursor.fetchall()]

    def list_monitored_products(self) -> dict[str, object]:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    with product_media as (
                      select distinct on (l.product_key)
                        l.product_key,
                        l.product_url,
                        l.image_url
                      from public.mkt_dim_listing l
                      where l.product_key is not null
                        and (l.product_url is not null or l.image_url is not null)
                      order by
                        l.product_key,
                        case when l.image_url is not null then 0 else 1 end,
                        l.updated_at desc nulls last,
                        l.created_at desc nulls last
                    ),
                    coverage as (
                      select
                        product_key,
                        count(distinct chain_key)::int as chains_seen,
                        count(distinct chain_key) filter (where active_listings > 0)::int as active_chains_seen,
                        sum(listings_seen)::int as listings_seen,
                        sum(active_listings)::int as active_listings,
                        string_agg(distinct chain_name, ', ' order by chain_name) as chains
                      from public.mw_product_chain_coverage_detail
                      group by product_key
                    ),
                    campaigns as (
                      select
                        cp.product_key,
                        count(distinct cp.campaign_id)::int as campaigns
                      from public.mkt_campaign_product cp
                      join public.mkt_dim_campaign c
                        on c.id = cp.campaign_id
                       and c.deleted_at is null
                      group by cp.product_key
                    ),
                    activity as (
                      select
                        product_key,
                        max(captured_at_cr) as latest_observation_at,
                        count(*)::int as observations
                      from public.mw_app_product_store_day
                      group by product_key
                    )
                    select
                      p.product_key::text as id,
                      p.product_key::text as product_key,
                      p.gtin_norm,
                      p.brand_name as brand,
                      p.product_name as product,
                      p.content_quantity,
                      p.content_unit,
                      case when p.is_active then 'active' else 'inactive' end as status,
                      coalesce(coverage.chains_seen, 0)::int as chains_seen,
                      coalesce(coverage.active_chains_seen, 0)::int as active_chains_seen,
                      coalesce(coverage.listings_seen, 0)::int as listings_seen,
                      coalesce(coverage.active_listings, 0)::int as active_listings,
                      coalesce(campaigns.campaigns, 0)::int as campaigns,
                      coalesce(activity.observations, 0)::int as observations,
                      activity.latest_observation_at,
                      coverage.chains,
                      product_media.product_url,
                      product_media.image_url
                    from public.mkt_dim_product p
                    left join product_media
                      on product_media.product_key = p.product_key
                    left join coverage
                      on coverage.product_key = p.product_key
                    left join campaigns
                      on campaigns.product_key = p.product_key
                    left join activity
                      on activity.product_key = p.product_key
                    order by p.is_active desc, activity.latest_observation_at desc nulls last, p.brand_name nulls last, p.product_name, p.product_key
                    limit 2000;
                    """
                )
                items = [self._json_ready(row) for row in cursor.fetchall()]

        chain_options = sorted(
            {
                chain.strip()
                for item in items
                for chain in str(item.get("chains") or "").split(",")
                if chain.strip()
            },
            key=str.casefold,
        )
        status_options = sorted({str(item.get("status")) for item in items if item.get("status")})
        return {
            "items": items,
            "filters": {
                "statuses": status_options,
                "chains": chain_options,
                "coverage": ["with_active_listings", "without_active_listings", "used_in_campaigns", "not_used_in_campaigns"],
            },
        }

    def fetch_monitored_product_workspace(self, *, product_key: int, client_id: str) -> dict[str, object] | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    with product_media as (
                      select distinct on (l.product_key)
                        l.product_key,
                        l.product_url,
                        l.image_url
                      from public.mkt_dim_listing l
                      where l.product_key = %(product_key)s
                        and (l.product_url is not null or l.image_url is not null)
                      order by
                        l.product_key,
                        case when l.image_url is not null then 0 else 1 end,
                        l.updated_at desc nulls last,
                        l.created_at desc nulls last
                    ),
                    coverage as (
                      select
                        product_key,
                        count(distinct chain_key)::int as chains_seen,
                        count(distinct chain_key) filter (where active_listings > 0)::int as active_chains_seen,
                        sum(listings_seen)::int as listings_seen,
                        sum(active_listings)::int as active_listings
                      from public.mw_product_chain_coverage_detail
                      where product_key = %(product_key)s
                      group by product_key
                    ),
                    campaigns as (
                      select
                        cp.product_key,
                        count(distinct cp.campaign_id)::int as campaigns
                      from public.mkt_campaign_product cp
                      join public.mkt_dim_campaign c
                        on c.id = cp.campaign_id
                       and c.deleted_at is null
                      where cp.product_key = %(product_key)s
                      group by cp.product_key
                    ),
                    activity as (
                      select
                        product_key,
                        max(captured_at_cr) as latest_observation_at,
                        count(*)::int as observations
                      from public.mw_app_product_store_day
                      where product_key = %(product_key)s
                      group by product_key
                    )
                    select
                      p.product_key::text as product_key,
                      p.gtin_norm,
                      p.brand_name as brand,
                      p.product_name as product,
                      p.content_quantity,
                      p.content_unit,
                      p.is_active,
                      case when p.is_active then 'active' else 'inactive' end as status,
                      coalesce(coverage.chains_seen, 0)::int as chains_seen,
                      coalesce(coverage.active_chains_seen, 0)::int as active_chains_seen,
                      coalesce(coverage.listings_seen, 0)::int as listings_seen,
                      coalesce(coverage.active_listings, 0)::int as active_listings,
                      coalesce(campaigns.campaigns, 0)::int as campaigns,
                      coalesce(activity.observations, 0)::int as observations,
                      activity.latest_observation_at,
                      product_media.product_url,
                      product_media.image_url
                    from public.mkt_dim_product p
                    left join product_media
                      on product_media.product_key = p.product_key
                    left join coverage
                      on coverage.product_key = p.product_key
                    left join campaigns
                      on campaigns.product_key = p.product_key
                    left join activity
                      on activity.product_key = p.product_key
                    where p.product_key = %(product_key)s
                    limit 1;
                    """,
                    {"product_key": product_key},
                )
                product = cursor.fetchone()
                if not product:
                    return None
                product_row = self._json_ready(product)

                cursor.execute(
                    """
                    select
                      chain_key::text as id,
                      chain_id,
                      chain_name as chain,
                      engine,
                      listings_seen,
                      active_listings,
                      root_category_slugs,
                      sample_product_url as product_url,
                      sample_image_url as image_url,
                      first_listing_created_at,
                      last_listing_updated_at
                    from public.mw_product_chain_coverage_detail
                    where product_key = %(product_key)s
                    order by active_listings desc, chain_name;
                    """,
                    {"product_key": product_key},
                )
                chain_coverage = [self._json_ready(row) for row in cursor.fetchall()]

                cursor.execute(
                    """
                    select
                      l.listing_key::text as id,
                      ch.chain_name as chain,
                      l.source_product_id,
                      l.source_sku,
                      l.listing_name,
                      l.root_category_name,
                      l.root_category_slug,
                      l.seller_name,
                      l.product_url,
                      l.image_url,
                      l.is_active,
                      l.updated_at
                    from public.mkt_dim_listing l
                    join public.mkt_dim_chain ch
                      on ch.chain_key = l.chain_key
                    where l.product_key = %(product_key)s
                    order by l.is_active desc, ch.chain_name, l.updated_at desc nulls last
                    limit 500;
                    """,
                    {"product_key": product_key},
                )
                listings = [self._json_ready(row) for row in cursor.fetchall()]

                cursor.execute(
                    """
                    select
                      c.id::text as id,
                      c.name,
                      c.slug,
                      case when c.is_active then 'active' else 'inactive' end as status,
                      cp.product_role,
                      count(distinct cl.location_key)::int as stores
                    from public.mkt_campaign_product cp
                    join public.mkt_dim_campaign c
                      on c.id = cp.campaign_id
                     and c.deleted_at is null
                    left join public.mkt_campaign_location cl
                      on cl.campaign_id = c.id
                    where cp.product_key = %(product_key)s
                    group by c.id, c.name, c.slug, c.is_active, cp.product_role
                    order by c.name;
                    """,
                    {"product_key": product_key},
                )
                campaigns = [self._json_ready(row) for row in cursor.fetchall()]

                cursor.execute(
                    """
                    select
                      date_key,
                      business_date,
                      campaign,
                      chain,
                      location_name as store,
                      province,
                      canton,
                      captured_at_cr,
                      is_listed,
                      is_available,
                      effective_price_amount,
                      reference_price_amount,
                      spot_price_amount,
                      promo_detected,
                      discount_pct_display as discount_pct,
                      product_url,
                      source_engine
                    from public.mw_app_product_store_day
                    where product_key = %(product_key)s
                    order by captured_at_cr desc nulls last, date_key desc
                    limit 200;
                    """,
                    {"product_key": product_key},
                )
                recent_activity = [self._json_ready(row) for row in cursor.fetchall()]

                cursor.execute(
                    """
                    select
                      e.event_id::text as id,
                      e.business_date::text as business_date,
                      e.date_key,
                      e.campaign_id,
                      e.campaign,
                      e.chain,
                      e.event_area,
                      e.event_type,
                      e.severity,
                      e.previous_value,
                      e.current_value,
                      e.change_amount,
                      e.change_pct,
                      e.visible_locations,
                      e.available_locations,
                      e.product_url,
                      et.short_label,
                      et.value_format,
                      et.change_format
                    from public.mw_bi_radar_event_feed e
                    join public.mkt_dim_market_event_type et
                      on et.event_type = e.event_type
                     and et.is_active
                    where e.client_id::text = %(client_id)s
                      and (
                        e.product_key = %(product_key_text)s
                        or (%(gtin_norm)s::text is not null and e.gtin = %(gtin_norm)s::text)
                      )
                    order by
                      e.date_key desc,
                      case lower(coalesce(e.severity, ''))
                        when 'high' then 1
                        when 'medium' then 2
                        when 'low' then 3
                        else 9
                      end,
                      e.chain,
                      e.event_type
                    limit 120;
                    """,
                    {
                        "client_id": client_id,
                        "product_key_text": str(product_key),
                        "gtin_norm": product_row.get("gtin_norm"),
                    },
                )
                related_event_rows = [self._json_ready(row) for row in cursor.fetchall()]

        def format_number(value: object) -> str:
            if value is None:
                return "-"
            if isinstance(value, Decimal):
                value = float(value)
            if isinstance(value, float):
                if value.is_integer():
                    return str(int(value))
                return f"{value:.2f}".rstrip("0").rstrip(".")
            if isinstance(value, int):
                return str(value)
            return str(value)

        def format_currency(value: object) -> str:
            if value is None:
                return "-"
            amount = float(value)
            return f"₡{amount:,.0f}"

        def format_percent(value: object) -> str:
            if value is None:
                return "-"
            return f"{float(value):.1f}%"

        def format_event_value(row: dict[str, object], field: str) -> str:
            value = row.get(field)
            if value is None:
                return "-"
            value_format = str(row.get("value_format") or "")
            event_area = str(row.get("event_area") or "")
            if value_format == "percent" or event_area == "promotion":
                return format_percent(value)
            if value_format == "currency" or event_area == "price":
                return format_currency(value)
            return format_number(value)

        def format_event_change(row: dict[str, object]) -> str:
            change_format = str(row.get("change_format") or "")
            event_area = str(row.get("event_area") or "")
            if change_format == "points" or event_area == "promotion":
                value = row.get("change_amount")
                return "-" if value is None else f"{float(value):.1f} pts"
            if change_format == "currency":
                return format_currency(row.get("change_amount"))
            if change_format == "percent":
                return format_percent(row.get("change_pct"))
            return format_number(row.get("change_amount"))

        related_events: list[dict[str, object]] = []
        for row in related_event_rows:
            date_key = row.get("date_key")
            chain = str(row.get("chain") or "")
            detail_url = (
                f"/pricing/products/{quote(str(product_key))}"
                f"?campaign_id={quote(str(row.get('campaign_id') or ''))}"
                f"&date_key={quote(str(date_key or ''))}"
                f"&chain={quote(chain)}"
                "&source=radar"
                if row.get("campaign_id") and date_key and chain
                else f"/pricing/products/{quote(str(product_key))}"
            )
            visible_locations = row.get("visible_locations")
            available_locations = row.get("available_locations")
            stores = "-"
            if visible_locations is not None and available_locations is not None:
                stores = f"{format_number(available_locations)}/{format_number(visible_locations)} available"

            related_events.append(
                {
                    "Date": row.get("business_date"),
                    "Event": row.get("short_label") or row.get("event_type"),
                    "Chain": row.get("chain"),
                    "Campaign": row.get("campaign"),
                    "Severity": row.get("severity"),
                    "Previous": format_event_value(row, "previous_value"),
                    "Current": format_event_value(row, "current_value"),
                    "Change": format_event_change(row),
                    "Stores": stores,
                    "detail_url": detail_url,
                    "product_url": row.get("product_url"),
                }
            )

        quality = [
            {
                "check": "Has GTIN",
                "status": "ok" if product_row.get("gtin_norm") else "warning",
                "detail": product_row.get("gtin_norm") or "Missing normalized GTIN",
            },
            {
                "check": "Has active listings",
                "status": "ok" if int(product_row.get("active_listings") or 0) > 0 else "warning",
                "detail": f"{int(product_row.get('active_listings') or 0)} active listings",
            },
            {
                "check": "Has chain coverage",
                "status": "ok" if int(product_row.get("active_chains_seen") or 0) > 0 else "warning",
                "detail": f"{int(product_row.get('active_chains_seen') or 0)} active chains",
            },
            {
                "check": "Has image",
                "status": "ok" if product_row.get("image_url") else "warning",
                "detail": "Image available" if product_row.get("image_url") else "No product image found",
            },
            {
                "check": "Observed in snapshots",
                "status": "ok" if int(product_row.get("observations") or 0) > 0 else "warning",
                "detail": f"{int(product_row.get('observations') or 0)} observations",
            },
        ]

        return {
            "product": product_row,
            "summary": {
                "chains": int(product_row.get("active_chains_seen") or 0),
                "listings": int(product_row.get("active_listings") or 0),
                "campaigns": int(product_row.get("campaigns") or 0),
                "observations": int(product_row.get("observations") or 0),
                "related_events": len(related_events),
            },
            "sections": [
                {
                    "id": "overview",
                    "label": "Overview",
                    "description": "Canonical product identity and operational monitoring status.",
                    "records": [
                        {"metric": "Status", "value": product_row.get("status")},
                        {"metric": "Active chains", "value": product_row.get("active_chains_seen")},
                        {"metric": "Active listings", "value": product_row.get("active_listings")},
                        {"metric": "Campaigns", "value": product_row.get("campaigns")},
                        {"metric": "Latest observation", "value": product_row.get("latest_observation_at")},
                    ],
                },
                {
                    "id": "chain-coverage",
                    "label": "Chain Coverage",
                    "description": "Chains where this canonical product has known source listings.",
                    "records": chain_coverage,
                },
                {
                    "id": "listings",
                    "label": "Listings",
                    "description": "Source listings mapped to this canonical product.",
                    "records": listings,
                },
                {
                    "id": "campaigns",
                    "label": "Campaigns",
                    "description": "Campaign baskets currently using this product.",
                    "records": campaigns,
                },
                {
                    "id": "related-events",
                    "label": "Related Events",
                    "description": "Radar-visible price, promotion and availability events associated with this product.",
                    "records": related_events,
                },
                {
                    "id": "recent-activity",
                    "label": "Recent Activity",
                    "description": "Recent store-level observations from loaded snapshots.",
                    "records": recent_activity,
                },
                {
                    "id": "quality",
                    "label": "Quality",
                    "description": "Operational checks for canonical product readiness.",
                    "records": quality,
                },
            ],
        }

    def list_catalog_sources(self) -> list[dict[str, object]]:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select
                      cat.category_key::text as id,
                      cat.chain_key::text as chain_key,
                      chain.chain_id,
                      chain.chain_name as chain,
                      chain.engine,
                      cat.category_name,
                      cat.category_slug,
                      cat.category_url,
                      cat.source_category_reference,
                      cat.is_enabled,
                      case when cat.is_enabled then 'enabled' else 'disabled' end as status,
                      count(distinct i.stage_catalog_item_key)::int as staged_items,
                      max(r.started_at) as latest_run_at
                    from public.mkt_dim_category cat
                    join public.mkt_dim_chain chain
                      on chain.chain_key = cat.chain_key
                    left join public.mkt_stage_catalog_item i
                      on i.chain_key = cat.chain_key
                     and i.root_category_slug = cat.category_slug
                    left join public.mkt_run r
                      on r.run_key = i.run_key
                    group by
                      cat.category_key,
                      cat.chain_key,
                      chain.chain_id,
                      chain.chain_name,
                      chain.engine,
                      cat.category_name,
                      cat.category_slug,
                      cat.category_url,
                      cat.source_category_reference,
                      cat.is_enabled
                    order by chain.chain_name, cat.category_name;
                    """
                )
                return [self._json_ready(row) for row in cursor.fetchall()]

    def update_catalog_source(
        self,
        *,
        category_key: int,
        is_enabled: bool | None,
    ) -> dict[str, object] | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    update public.mkt_dim_category cat
                    set
                      is_enabled = coalesce(%(is_enabled)s, cat.is_enabled),
                      updated_at = now()
                    where cat.category_key = %(category_key)s
                    returning cat.category_key;
                    """,
                    {
                        "category_key": category_key,
                        "is_enabled": is_enabled,
                    },
                )
                row = cursor.fetchone()
                if not row:
                    connection.commit()
                    return None
                category = self._fetch_catalog_source(cursor, category_key=category_key)
                connection.commit()
                return category

    def _fetch_catalog_source(self, cursor: psycopg.Cursor, *, category_key: int) -> dict[str, object] | None:
        cursor.execute(
            """
            select
              cat.category_key::text as id,
              cat.chain_key::text as chain_key,
              chain.chain_id,
              chain.chain_name as chain,
              chain.engine,
              cat.category_name,
              cat.category_slug,
              cat.category_url,
              cat.source_category_reference,
              cat.is_enabled,
              case when cat.is_enabled then 'enabled' else 'disabled' end as status
            from public.mkt_dim_category cat
            join public.mkt_dim_chain chain
              on chain.chain_key = cat.chain_key
            where cat.category_key = %(category_key)s
            limit 1;
            """,
            {"category_key": category_key},
        )
        row = cursor.fetchone()
        return self._json_ready(row) if row else None

    def _fetch_campaign_product(
        self,
        cursor: psycopg.Cursor,
        *,
        campaign_id: int,
        product_key: int,
    ) -> dict[str, object] | None:
        cursor.execute(
            """
            with product_media as (
              select distinct on (l.product_key)
                l.product_key,
                l.product_url,
                l.image_url
              from public.mkt_dim_listing l
              where l.product_key is not null
                and (l.product_url is not null or l.image_url is not null)
              order by
                l.product_key,
                case when l.image_url is not null then 0 else 1 end,
                l.updated_at desc nulls last,
                l.created_at desc nulls last
            ),
            chain_coverage as (
              select
                product_key,
                jsonb_agg(
                  jsonb_build_object(
                    'chain_key', chain_key::text,
                    'chain_id', chain_id,
                    'chain_name', chain_name,
                    'active_listings', active_listings,
                    'listings_seen', listings_seen
                  )
                  order by chain_name
                ) as chain_coverage
              from public.mw_product_chain_coverage_detail
              where active_listings > 0
              group by product_key
            ),
            campaign_observations as (
              select
                f.product_key,
                count(*)::int as campaign_observations,
                count(distinct f.run_key)::int as campaign_runs,
                max(r.finished_at) as latest_campaign_run_at
              from public.mkt_fact_listing_snapshot f
              join public.mkt_run r
                on r.run_key = f.run_key
              where r.campaign_id = %(campaign_id)s
                and f.product_key = %(product_key)s
              group by f.product_key
            )
            select
              p.product_key::text as id,
              cp.product_role,
              p.brand_name as brand,
              p.product_name as product,
              p.gtin_norm,
              p.content_quantity,
              p.content_unit,
              product_media.product_url,
              product_media.image_url,
              coalesce(chain_coverage.chain_coverage, '[]'::jsonb) as chain_coverage,
              coalesce(campaign_observations.campaign_observations, 0)::int as campaign_observations,
              coalesce(campaign_observations.campaign_runs, 0)::int as campaign_runs,
              campaign_observations.latest_campaign_run_at,
              p.is_active
            from public.mkt_campaign_product cp
            join public.mkt_dim_product p
              on p.product_key = cp.product_key
            left join product_media
              on product_media.product_key = p.product_key
            left join chain_coverage
              on chain_coverage.product_key = p.product_key
            left join campaign_observations
              on campaign_observations.product_key = p.product_key
            where cp.campaign_id = %(campaign_id)s
              and cp.product_key = %(product_key)s
            limit 1;
            """,
            {"campaign_id": campaign_id, "product_key": product_key},
        )
        row = cursor.fetchone()
        return self._json_ready(row) if row else None

    def assign_campaign_product(
        self,
        *,
        campaign_id: int,
        product_key: int,
        product_role: str,
    ) -> dict[str, object] | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select exists (
                      select 1
                      from public.mkt_dim_campaign
                      where id = %(campaign_id)s
                        and deleted_at is null
                    ) as campaign_exists,
                    exists (
                      select 1
                      from public.mkt_dim_product
                      where product_key = %(product_key)s
                        and is_active
                    ) as product_exists;
                    """,
                    {"campaign_id": campaign_id, "product_key": product_key},
                )
                exists_row = cursor.fetchone()
                if not exists_row or not exists_row["campaign_exists"] or not exists_row["product_exists"]:
                    connection.commit()
                    return None

                cursor.execute(
                    """
                    insert into public.mkt_campaign_product (
                      campaign_id,
                      product_key,
                      product_role
                    )
                    values (
                      %(campaign_id)s,
                      %(product_key)s,
                      %(product_role)s
                    )
                    on conflict (campaign_id, product_key) do update
                    set product_role = excluded.product_role,
                        updated_at = now();
                    """,
                    {
                        "campaign_id": campaign_id,
                        "product_key": product_key,
                        "product_role": product_role,
                    },
                )
                product = self._fetch_campaign_product(cursor, campaign_id=campaign_id, product_key=product_key)
                connection.commit()
                return product

    def update_campaign_product(
        self,
        *,
        campaign_id: int,
        product_key: int,
        product_role: str | None,
    ) -> dict[str, object] | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    update public.mkt_campaign_product cp
                    set
                      product_role = coalesce(%(product_role)s, cp.product_role),
                      updated_at = now()
                    where cp.campaign_id = %(campaign_id)s
                      and cp.product_key = %(product_key)s
                      and exists (
                        select 1
                        from public.mkt_dim_campaign c
                        where c.id = cp.campaign_id
                          and c.deleted_at is null
                      )
                    returning cp.campaign_id;
                    """,
                    {
                        "campaign_id": campaign_id,
                        "product_key": product_key,
                        "product_role": product_role,
                    },
                )
                row = cursor.fetchone()
                if not row:
                    connection.commit()
                    return None
                product = self._fetch_campaign_product(cursor, campaign_id=campaign_id, product_key=product_key)
                connection.commit()
                return product

    def remove_campaign_product(self, *, campaign_id: int, product_key: int) -> dict[str, object] | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select exists (
                      select 1
                      from public.mkt_dim_campaign
                      where id = %(campaign_id)s
                        and deleted_at is null
                    ) as campaign_exists,
                    exists (
                      select 1
                      from public.mkt_dim_product
                      where product_key = %(product_key)s
                    ) as product_exists;
                    """,
                    {"campaign_id": campaign_id, "product_key": product_key},
                )
                exists_row = cursor.fetchone()
                if not exists_row or not exists_row["campaign_exists"] or not exists_row["product_exists"]:
                    connection.commit()
                    return None

                cursor.execute(
                    """
                    delete from public.mkt_campaign_product
                    where campaign_id = %(campaign_id)s
                      and product_key = %(product_key)s;
                    """,
                    {"campaign_id": campaign_id, "product_key": product_key},
                )
                removed_products = cursor.rowcount
                connection.commit()
                return {
                    "campaign_id": str(campaign_id),
                    "product_key": str(product_key),
                    "removed_products": removed_products,
                }

    def list_campaign_report_recipient_user_options(self, *, client_id: str) -> list[dict[str, object]]:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select
                      u.id::text as id,
                      u.display_name,
                      u.email,
                      u.username,
                      u.status
                    from public.auth_user_clients uc
                    join public.auth_users u
                      on u.id = uc.user_id
                    where uc.client_id::text = %(client_id)s
                      and u.status = 'active'
                    order by u.display_name, u.email;
                    """,
                    {"client_id": client_id},
                )
                return [self._json_ready(row) for row in cursor.fetchall()]

    def _fetch_campaign_report_recipient(
        self,
        cursor: psycopg.Cursor,
        *,
        campaign_id: int,
        client_id: str,
        recipient_id: int,
    ) -> dict[str, object] | None:
        cursor.execute(
            """
            select
              r.id::text as id,
              r.campaign_id::text as campaign_id,
              r.client_id::text as client_id,
              r.user_id::text as user_id,
              r.email,
              r.display_name,
              r.recipient_type,
              r.report_kind,
              r.is_active,
              r.created_at,
              r.updated_at
            from public.mkt_campaign_report_recipient r
            where r.campaign_id = %(campaign_id)s
              and r.client_id::text = %(client_id)s
              and r.id = %(recipient_id)s;
            """,
            {
                "campaign_id": campaign_id,
                "client_id": client_id,
                "recipient_id": recipient_id,
            },
        )
        row = cursor.fetchone()
        return self._json_ready(row) if row else None

    def create_campaign_report_recipient(
        self,
        *,
        campaign_id: int,
        client_id: str,
        user_id: int | None,
        email: str | None,
        display_name: str | None,
        recipient_type: str,
        report_kind: str,
        is_active: bool,
    ) -> dict[str, object] | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                campaign = self._fetch_campaign_for_client(cursor, campaign_id=campaign_id, client_id=client_id)
                if not campaign:
                    return None

                resolved_email = email.strip().lower() if email else None
                resolved_display_name = display_name.strip() if display_name else None
                if user_id is not None:
                    cursor.execute(
                        """
                        select u.email, u.display_name
                        from public.auth_user_clients uc
                        join public.auth_users u
                          on u.id = uc.user_id
                        where uc.client_id::text = %(client_id)s
                          and uc.user_id = %(user_id)s
                          and u.status = 'active';
                        """,
                        {"client_id": client_id, "user_id": user_id},
                    )
                    user = cursor.fetchone()
                    if not user:
                        return None
                    resolved_email = str(user["email"]).strip().lower()
                    resolved_display_name = resolved_display_name or str(user["display_name"]).strip()

                if not resolved_email:
                    return None

                cursor.execute(
                    """
                    insert into public.mkt_campaign_report_recipient (
                      campaign_id,
                      client_id,
                      user_id,
                      email,
                      display_name,
                      recipient_type,
                      report_kind,
                      is_active
                    )
                    values (
                      %(campaign_id)s,
                      %(client_id)s,
                      %(user_id)s,
                      %(email)s,
                      %(display_name)s,
                      %(recipient_type)s,
                      %(report_kind)s,
                      %(is_active)s
                    )
                    returning id;
                    """,
                    {
                        "campaign_id": campaign_id,
                        "client_id": int(client_id),
                        "user_id": user_id,
                        "email": resolved_email,
                        "display_name": resolved_display_name,
                        "recipient_type": recipient_type,
                        "report_kind": report_kind,
                        "is_active": is_active,
                    },
                )
                row = cursor.fetchone()
                connection.commit()
                return self._fetch_campaign_report_recipient(
                    cursor,
                    campaign_id=campaign_id,
                    client_id=client_id,
                    recipient_id=int(row["id"]),
                )

    def update_campaign_report_recipient(
        self,
        *,
        campaign_id: int,
        client_id: str,
        recipient_id: int,
        email: str | None,
        display_name: str | None,
        recipient_type: str | None,
        report_kind: str | None,
        is_active: bool | None,
    ) -> dict[str, object] | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    update public.mkt_campaign_report_recipient
                    set
                      email = coalesce(%(email)s, email),
                      display_name = coalesce(%(display_name)s, display_name),
                      recipient_type = coalesce(%(recipient_type)s, recipient_type),
                      report_kind = coalesce(%(report_kind)s, report_kind),
                      is_active = coalesce(%(is_active)s, is_active),
                      updated_at = now()
                    where campaign_id = %(campaign_id)s
                      and client_id::text = %(client_id)s
                      and id = %(recipient_id)s
                    returning id;
                    """,
                    {
                        "campaign_id": campaign_id,
                        "client_id": client_id,
                        "recipient_id": recipient_id,
                        "email": email.strip().lower() if email else None,
                        "display_name": display_name.strip() if display_name else None,
                        "recipient_type": recipient_type,
                        "report_kind": report_kind,
                        "is_active": is_active,
                    },
                )
                row = cursor.fetchone()
                if not row:
                    return None
                connection.commit()
                return self._fetch_campaign_report_recipient(
                    cursor,
                    campaign_id=campaign_id,
                    client_id=client_id,
                    recipient_id=recipient_id,
                )

    def list_active_campaign_report_recipients(
        self,
        *,
        campaign_id: int,
        client_id: str,
        report_kind: str = "daily_price_radar",
    ) -> list[dict[str, object]]:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select
                      r.id::text as id,
                      r.user_id::text as user_id,
                      coalesce(r.display_name, u.display_name, r.email) as display_name,
                      r.email,
                      r.recipient_type,
                      r.report_kind
                    from public.mkt_campaign_report_recipient r
                    left join public.auth_users u
                      on u.id = r.user_id
                    where r.campaign_id = %(campaign_id)s
                      and r.client_id::text = %(client_id)s
                      and r.report_kind = %(report_kind)s
                      and r.is_active
                    order by r.recipient_type, display_name, r.email;
                    """,
                    {
                        "campaign_id": campaign_id,
                        "client_id": client_id,
                        "report_kind": report_kind,
                    },
                )
                return [self._json_ready(row) for row in cursor.fetchall()]

    def create_campaign_report_delivery(
        self,
        *,
        campaign_id: int,
        client_id: str,
        business_date: date,
        report_kind: str,
        status: str,
        subject: str | None,
        recipients: list[dict[str, object]],
        requested_by_user_id: str,
        error_summary: str | None = None,
    ) -> dict[str, object]:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    insert into public.mkt_campaign_report_delivery (
                      campaign_id,
                      client_id,
                      report_kind,
                      business_date,
                      status,
                      subject,
                      recipients_json,
                      requested_by_user_id,
                      error_summary,
                      sent_at
                    )
                    values (
                      %(campaign_id)s,
                      %(client_id)s,
                      %(report_kind)s,
                      %(business_date)s,
                      %(status)s,
                      %(subject)s,
                      %(recipients_json)s::jsonb,
                      %(requested_by_user_id)s,
                      %(error_summary)s,
                      case when %(status)s = 'sent' then now() else null end
                    )
                    returning id::text as id, status, created_at, sent_at;
                    """,
                    {
                        "campaign_id": campaign_id,
                        "client_id": int(client_id),
                        "report_kind": report_kind,
                        "business_date": business_date,
                        "status": status,
                        "subject": subject,
                        "recipients_json": json.dumps(recipients),
                        "requested_by_user_id": int(requested_by_user_id),
                        "error_summary": error_summary,
                    },
                )
                row = self._json_ready(cursor.fetchone() or {})
                connection.commit()
                return row

    def _fetch_campaign_report_preview(
        self,
        cursor: psycopg.Cursor,
        *,
        client_id: str,
        campaign_id: int,
        business_date: date,
    ) -> dict[str, object]:
        try:
            cursor.execute(
                """
                select
                  business_date,
                  date_key,
                  campaign_id::text as campaign_id,
                  campaign,
                  brand,
                  chain,
                  signal_type,
                  signal_status,
                  severity,
                  impact_score,
                  headline,
                  summary,
                  business_reading,
                  recommended_action,
                  notification_status,
                  repeat_count,
                  nullif(evidence_json ->> 'product', '') as product,
                  nullif(evidence_json ->> 'product_url', '') as product_url
                from public.mw_bi_executive_signal_feed
                where client_id::text = %(client_id)s
                  and campaign_id = %(campaign_id)s
                  and business_date = %(business_date)s
                order by
                  impact_score desc nulls last,
                  case lower(coalesce(severity, ''))
                    when 'critical' then 1
                    when 'high' then 2
                    when 'medium' then 3
                    when 'low' then 4
                    else 9
                  end,
                  repeat_count desc nulls last,
                  chain,
                  headline
                limit 30;
                """,
                {
                    "client_id": client_id,
                    "campaign_id": campaign_id,
                    "business_date": business_date,
                },
            )
            signals = [self._json_ready(row) for row in cursor.fetchall()]

            cursor.execute(
                """
                select
                  count(*)::int as total_signals,
                  count(*) filter (where lower(coalesce(severity, '')) in ('critical', 'high'))::int as high_severity_signals,
                  count(*) filter (where signal_type ilike '%%promo%%')::int as promo_signals,
                  count(*) filter (where signal_type ilike '%%price%%' or signal_type ilike '%%gap%%')::int as price_signals,
                  count(*) filter (where signal_type ilike '%%stock%%' or signal_type ilike '%%availability%%')::int as availability_signals,
                  count(distinct chain)::int as chains_with_signals
                from public.mw_bi_executive_signal_feed
                where client_id::text = %(client_id)s
                  and campaign_id = %(campaign_id)s
                  and business_date = %(business_date)s;
                """,
                {
                    "client_id": client_id,
                    "campaign_id": campaign_id,
                    "business_date": business_date,
                },
            )
            kpis = self._json_ready(cursor.fetchone() or {})

            cursor.execute(
                """
                select
                  count(*)::int as run_count,
                  count(*) filter (where run_status = 'succeeded')::int as succeeded_runs,
                  max(finished_at) as latest_finished_at
                from public.mkt_run
                where campaign_id = %(campaign_id)s
                  and business_date_key = to_char(%(business_date)s::date, 'YYYYMMDD')::int;
                """,
                {
                    "campaign_id": campaign_id,
                    "business_date": business_date,
                },
            )
            diagnostics = self._json_ready(cursor.fetchone() or {})

            cursor.execute(
                """
                select
                  e.event_id,
                  e.event_area,
                  e.event_type,
                  e.severity,
                  e.business_date,
                  e.date_key,
                  e.campaign_id::text as campaign_id,
                  e.campaign,
                  e.chain,
                  e.brand,
                  e.product,
                  e.product_key,
                  e.previous_value,
                  e.current_value,
                  e.change_amount,
                  e.change_pct,
                  e.promo_share_pct,
                  e.discount_pct,
                  e.visible_locations,
                  e.available_locations,
                  e.product_url,
                  et.display_label,
                  et.short_label,
                  et.metric_previous_label,
                  et.metric_current_label,
                  et.metric_change_label,
                  et.value_format,
                  et.change_format
                from public.mw_bi_radar_event_feed e
                left join public.mkt_dim_market_event_type et
                  on et.event_type = e.event_type
                where e.client_id::text = %(client_id)s
                  and e.campaign_id = %(campaign_id)s
                  and e.business_date = %(business_date)s
                order by
                  case lower(coalesce(e.severity, ''))
                    when 'high' then 1
                    when 'medium' then 2
                    when 'low' then 3
                    else 9
                  end,
                  abs(coalesce(e.change_pct, e.change_amount, 0)) desc,
                  e.chain,
                  e.product
                limit 4;
                """,
                {
                    "client_id": client_id,
                    "campaign_id": campaign_id,
                    "business_date": business_date,
                },
            )
            radar_highlights = [self._json_ready(row) for row in cursor.fetchall()]
        except errors.UndefinedTable:
            signals = []
            kpis = {}
            diagnostics = {}
            radar_highlights = []

        return {
            "business_date": business_date.isoformat(),
            "kpis": {
                "total_signals": int(kpis.get("total_signals") or 0),
                "high_severity_signals": int(kpis.get("high_severity_signals") or 0),
                "promo_signals": int(kpis.get("promo_signals") or 0),
                "price_signals": int(kpis.get("price_signals") or 0),
                "availability_signals": int(kpis.get("availability_signals") or 0),
                "chains_with_signals": int(kpis.get("chains_with_signals") or 0),
            },
            "diagnostics": {
                "run_count": int(diagnostics.get("run_count") or 0),
                "succeeded_runs": int(diagnostics.get("succeeded_runs") or 0),
                "latest_finished_at": diagnostics.get("latest_finished_at"),
            },
            "highlights": self._radar_report_highlights(radar_highlights),
            "records": signals,
        }

    def fetch_campaign_workspace(
        self,
        *,
        client_id: str,
        campaign_id: int,
        report_business_date: date,
    ) -> dict[str, object] | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                campaign = self._fetch_campaign_for_client(cursor, campaign_id=campaign_id, client_id=client_id)
                if not campaign:
                    return None

                cursor.execute(
                    """
                    select
                      ac.id::text as client_id,
                      ac.name as client,
                      ac.market,
                      ac.status as client_status,
                      cca.access_role,
                      cca.is_default,
                      cca.is_active,
                      cca.valid_from,
                      cca.valid_to
                    from public.mkt_campaign_client_access cca
                    join public.auth_clients ac
                      on ac.id = cca.client_id
                    where cca.campaign_id = %(campaign_id)s
                    order by cca.is_default desc, ac.name;
                    """,
                    {"campaign_id": campaign_id},
                )
                access = [self._json_ready(row) for row in cursor.fetchall()]

                cursor.execute(
                    """
                    select
                      r.id::text as id,
                      r.user_id::text as user_id,
                      coalesce(r.display_name, u.display_name, r.email) as display_name,
                      r.email,
                      r.recipient_type,
                      r.report_kind,
                      r.is_active,
                      r.updated_at
                    from public.mkt_campaign_report_recipient r
                    left join public.auth_users u
                      on u.id = r.user_id
                    where r.campaign_id = %(campaign_id)s
                      and r.client_id::text = %(client_id)s
                    order by r.is_active desc, r.recipient_type, display_name, r.email;
                    """,
                    {"campaign_id": campaign_id, "client_id": client_id},
                )
                report_recipients = [self._json_ready(row) for row in cursor.fetchall()]

                cursor.execute(
                    """
                    select
                      ch.chain_key::text as id,
                      ch.chain_id,
                      ch.chain_name,
                      ch.engine,
                      ch.pricing_scope,
                      ch.country_code,
                      ch.is_active,
                      count(distinct l.location_key)::int as stores
                    from public.mkt_campaign_location cl
                    join public.mkt_dim_location l
                      on l.location_key = cl.location_key
                    join public.mkt_dim_chain ch
                      on ch.chain_key = l.chain_key
                    where cl.campaign_id = %(campaign_id)s
                    group by
                      ch.chain_key,
                      ch.chain_id,
                      ch.chain_name,
                      ch.engine,
                      ch.pricing_scope,
                      ch.country_code,
                      ch.is_active
                    order by ch.chain_name;
                    """,
                    {"campaign_id": campaign_id},
                )
                chains = [self._json_ready(row) for row in cursor.fetchall()]

                cursor.execute(
                    """
                    select
                      l.location_key::text as id,
                      ch.chain_name,
                      l.location_name as store,
                      l.location_code,
                      l.sales_channel,
                      l.province,
                      l.canton,
                      l.district,
                      l.is_default,
                      l.is_active
                    from public.mkt_campaign_location cl
                    join public.mkt_dim_location l
                      on l.location_key = cl.location_key
                    join public.mkt_dim_chain ch
                      on ch.chain_key = l.chain_key
                    where cl.campaign_id = %(campaign_id)s
                    order by ch.chain_name, l.location_name;
                    """,
                    {"campaign_id": campaign_id},
                )
                stores = [self._json_ready(row) for row in cursor.fetchall()]

                cursor.execute(
                    """
                    with product_media as (
                      select distinct on (l.product_key)
                        l.product_key,
                        l.product_url,
                        l.image_url
                      from public.mkt_dim_listing l
                      where l.product_key is not null
                        and (l.product_url is not null or l.image_url is not null)
                      order by
                        l.product_key,
                        case when l.image_url is not null then 0 else 1 end,
                        l.updated_at desc nulls last,
                        l.created_at desc nulls last
                    ),
                    chain_coverage as (
                      select
                        product_key,
                        jsonb_agg(
                          jsonb_build_object(
                            'chain_key', chain_key::text,
                            'chain_id', chain_id,
                            'chain_name', chain_name,
                            'active_listings', active_listings,
                            'listings_seen', listings_seen
                          )
                          order by chain_name
                        ) as chain_coverage
                      from public.mw_product_chain_coverage_detail
                      where active_listings > 0
                      group by product_key
                    ),
                    campaign_observations as (
                      select
                        f.product_key,
                        count(*)::int as campaign_observations,
                        count(distinct f.run_key)::int as campaign_runs,
                        max(r.finished_at) as latest_campaign_run_at
                      from public.mkt_fact_listing_snapshot f
                      join public.mkt_run r
                        on r.run_key = f.run_key
                      where r.campaign_id = %(campaign_id)s
                      group by f.product_key
                    )
                    select
                      p.product_key::text as id,
                      cp.product_role,
                      p.brand_name as brand,
                      p.product_name as product,
                      p.gtin_norm,
                      p.content_quantity,
                      p.content_unit,
                      product_media.product_url,
                      product_media.image_url,
                      coalesce(chain_coverage.chain_coverage, '[]'::jsonb) as chain_coverage,
                      coalesce(campaign_observations.campaign_observations, 0)::int as campaign_observations,
                      coalesce(campaign_observations.campaign_runs, 0)::int as campaign_runs,
                      campaign_observations.latest_campaign_run_at,
                      p.is_active
                    from public.mkt_campaign_product cp
                    join public.mkt_dim_product p
                      on p.product_key = cp.product_key
                    left join product_media
                      on product_media.product_key = p.product_key
                    left join chain_coverage
                      on chain_coverage.product_key = p.product_key
                    left join campaign_observations
                      on campaign_observations.product_key = p.product_key
                    where cp.campaign_id = %(campaign_id)s
                    order by cp.product_role, p.brand_name, p.product_name;
                    """,
                    {"campaign_id": campaign_id},
                )
                products = [self._json_ready(row) for row in cursor.fetchall()]

                cursor.execute(
                    """
                    select
                      ch.chain_name,
                      count(distinct f.product_key)::int as observed_products,
                      count(distinct f.listing_key)::int as observed_listings,
                      max(r.finished_at) as latest_finished_at
                    from public.mkt_run r
                    join public.mkt_dim_chain ch
                      on ch.chain_key = r.chain_key
                    left join public.mkt_fact_listing_snapshot f
                      on f.run_key = r.run_key
                    where r.campaign_id = %(campaign_id)s
                      and r.run_status = 'succeeded'
                    group by ch.chain_name
                    order by ch.chain_name;
                    """,
                    {"campaign_id": campaign_id},
                )
                product_coverage = [self._json_ready(row) for row in cursor.fetchall()]
                report_preview = self._fetch_campaign_report_preview(
                    cursor,
                    client_id=client_id,
                    campaign_id=campaign_id,
                    business_date=report_business_date,
                )

        return {
            "campaign": campaign,
            "report_preview": report_preview,
            "summary": {
                "clients": len(access),
                "chains": len(chains),
                "stores": len(stores),
                "products": len(products),
                "recipients": len([recipient for recipient in report_recipients if recipient.get("is_active")]),
            },
            "sections": [
                {
                    "id": "overview",
                    "label": "Overview",
                    "description": "Basket identity and current configuration scope.",
                    "records": [
                        {"metric": "Authorized clients", "value": len(access)},
                        {"metric": "Chains", "value": len(chains)},
                        {"metric": "Stores", "value": len(stores)},
                        {"metric": "Products", "value": len(products)},
                    ],
                },
                {
                    "id": "access",
                    "label": "Access",
                    "description": "Clients and tenants authorized for this campaign.",
                    "records": access,
                },
                {
                    "id": "report-recipients",
                    "label": "Report Recipients",
                    "description": "People who receive campaign report emails and PDF attachments for the active tenant.",
                    "records": report_recipients,
                },
                {
                    "id": "report-preview",
                    "label": "Report Preview",
                    "description": f"Daily report preview for {report_preview['business_date']}.",
                    "records": report_preview["records"],
                },
                {
                    "id": "chains",
                    "label": "Chains",
                    "description": "Chains included through campaign store assignments.",
                    "records": chains,
                },
                {
                    "id": "stores",
                    "label": "Stores",
                    "description": "Stores monitored by chain for this campaign.",
                    "records": stores,
                },
                {
                    "id": "products",
                    "label": "Products",
                    "description": "Canonical products assigned to the campaign.",
                    "records": products,
                },
                {
                    "id": "products-by-chain",
                    "label": "Chain Coverage",
                    "description": "Observed product and listing coverage by chain from succeeded runs.",
                    "records": product_coverage,
                },
            ],
        }

    def fetch_executive_signals(
        self,
        *,
        client_id: str,
        campaign_id: str | None,
        date_from: str | None,
        date_to: str | None,
        brand: str | None,
        chain: str | None,
        signal_type: str | None,
        severity: str | None,
        signal_status: str | None,
        query: str | None,
        limit: int,
        offset: int,
    ) -> dict[str, object]:
        params: dict[str, Any] = {
            "client_id": client_id,
            "campaign_id": campaign_id,
            "date_from": date_from or None,
            "date_to": date_to or None,
            "brand": brand or None,
            "chain": chain or None,
            "signal_type": signal_type or None,
            "severity": severity or None,
            "signal_status": signal_status or None,
            "query": f"%{query.strip()}%" if query and query.strip() else None,
            "limit": limit,
            "offset": offset,
        }

        try:
            with self._connection_factory() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        with enriched as (
                          select
                            business_date,
                            date_key,
                            client_id::text as client_id,
                            campaign_id,
                            campaign,
                            brand,
                            chain,
                            signal_type,
                            signal_status,
                            effect,
                            severity,
                            impact_score,
                            confidence_score,
                            headline,
                            summary,
                            business_reading,
                            recommended_action,
                            notification_status,
                            repeat_count,
                            metrics_json,
                            evidence_json,
                            delta_metrics_json,
                            navigation_json,
                            narrative_json,
                            nullif(evidence_json ->> 'product', '') as evidence_product,
                            coalesce(
                              nullif(evidence_json ->> 'product_key', ''),
                              nullif(navigation_json ->> 'product_key', '')
                            ) as product_key
                          from public.mw_bi_executive_signal_feed
                          where client_id::text = %(client_id)s
                            and (%(campaign_id)s::text is null or campaign_id::text = any(string_to_array(%(campaign_id)s::text, ',')))
                            and (%(date_from)s::date is null or business_date >= %(date_from)s::date)
                            and (%(date_to)s::date is null or business_date <= %(date_to)s::date)
                            and (
                              %(date_from)s::date is not null
                              or %(date_to)s::date is not null
                              or business_date = (
                                select max(latest.business_date)
                                from public.mw_bi_executive_signal_feed latest
                                where latest.client_id::text = %(client_id)s
                                  and (%(campaign_id)s::text is null or latest.campaign_id::text = any(string_to_array(%(campaign_id)s::text, ',')))
                                  and (%(brand)s::text is null or latest.brand = any(string_to_array(%(brand)s::text, ',')))
                                  and (%(chain)s::text is null or latest.chain = any(string_to_array(%(chain)s::text, ',')))
                                  and (%(signal_type)s::text is null or latest.signal_type = any(string_to_array(%(signal_type)s::text, ',')))
                                  and (%(severity)s::text is null or latest.severity = any(string_to_array(%(severity)s::text, ',')))
                                  and (%(signal_status)s::text is null or latest.signal_status = any(string_to_array(%(signal_status)s::text, ',')))
                              )
                            )
                            and (%(brand)s::text is null or brand = any(string_to_array(%(brand)s::text, ',')))
                            and (%(chain)s::text is null or chain = any(string_to_array(%(chain)s::text, ',')))
                            and (%(signal_type)s::text is null or signal_type = any(string_to_array(%(signal_type)s::text, ',')))
                            and (%(severity)s::text is null or severity = any(string_to_array(%(severity)s::text, ',')))
                            and (%(signal_status)s::text is null or signal_status = any(string_to_array(%(signal_status)s::text, ',')))
                        ),
                        display_rows as (
                          select
                            *,
                            case
                              when evidence_product is not null then evidence_product
                              when signal_type = 'driver_sku_detected' then 'Multiple driver SKUs'
                              else 'Category / brand level'
                            end as product_display,
                            md5(concat_ws('|',
                              client_id,
                              campaign_id::text,
                              date_key::text,
                              coalesce(brand, ''),
                              coalesce(chain, ''),
                              coalesce(signal_type, ''),
                              coalesce(headline, ''),
                              coalesce(product_key, '')
                            )) as signal_id
                          from enriched
                        ),
                        filtered as (
                          select *
                          from display_rows
                          where %(query)s::text is null
                             or headline ilike %(query)s
                             or product_display ilike %(query)s
                             or brand ilike %(query)s
                             or chain ilike %(query)s
                        )
                        select *
                        from filtered
                        order by
                          business_date desc,
                          impact_score desc nulls last,
                          case lower(coalesce(severity, ''))
                            when 'critical' then 1
                            when 'high' then 2
                            when 'medium' then 3
                            when 'low' then 4
                            else 9
                          end,
                          repeat_count desc nulls last
                        limit %(limit)s offset %(offset)s;
                        """,
                        params,
                    )
                    rows = [self._json_ready(row) for row in cursor.fetchall()]

                    cursor.execute(
                        """
                        with enriched as (
                          select
                            business_date,
                            campaign_id,
                            campaign,
                            brand,
                            chain,
                            signal_type,
                            signal_status,
                            severity,
                            notification_status,
                            repeat_count,
                            nullif(evidence_json ->> 'product', '') as evidence_product
                          from public.mw_bi_executive_signal_feed
                          where client_id::text = %(client_id)s
                            and (%(campaign_id)s::text is null or campaign_id::text = any(string_to_array(%(campaign_id)s::text, ',')))
                            and (%(date_from)s::date is null or business_date >= %(date_from)s::date)
                            and (%(date_to)s::date is null or business_date <= %(date_to)s::date)
                            and (
                              %(date_from)s::date is not null
                              or %(date_to)s::date is not null
                              or business_date = (
                                select max(latest.business_date)
                                from public.mw_bi_executive_signal_feed latest
                                where latest.client_id::text = %(client_id)s
                                  and (%(campaign_id)s::text is null or latest.campaign_id::text = any(string_to_array(%(campaign_id)s::text, ',')))
                                  and (%(brand)s::text is null or latest.brand = any(string_to_array(%(brand)s::text, ',')))
                                  and (%(chain)s::text is null or latest.chain = any(string_to_array(%(chain)s::text, ',')))
                                  and (%(signal_type)s::text is null or latest.signal_type = any(string_to_array(%(signal_type)s::text, ',')))
                                  and (%(severity)s::text is null or latest.severity = any(string_to_array(%(severity)s::text, ',')))
                                  and (%(signal_status)s::text is null or latest.signal_status = any(string_to_array(%(signal_status)s::text, ',')))
                              )
                            )
                            and (%(brand)s::text is null or brand = any(string_to_array(%(brand)s::text, ',')))
                            and (%(chain)s::text is null or chain = any(string_to_array(%(chain)s::text, ',')))
                            and (%(signal_type)s::text is null or signal_type = any(string_to_array(%(signal_type)s::text, ',')))
                            and (%(severity)s::text is null or severity = any(string_to_array(%(severity)s::text, ',')))
                            and (%(signal_status)s::text is null or signal_status = any(string_to_array(%(signal_status)s::text, ',')))
                        )
                        select
                          count(*)::int as total_signals,
                          count(*) filter (where lower(coalesce(severity, '')) in ('critical', 'high'))::int as high_severity_signals,
                          count(*) filter (where lower(coalesce(signal_status, notification_status, '')) in ('new', 'nuevo'))::int as new_signals,
                          count(*) filter (where coalesce(repeat_count, 0) > 1 or lower(coalesce(signal_status, '')) in ('active', 'repeated'))::int as active_repeated_signals,
                          count(*) filter (where signal_type ilike '%%promo%%')::int as promo_signals,
                          count(*) filter (where signal_type ilike '%%gap%%' or signal_type ilike '%%price%%')::int as price_gap_signals,
                          max(business_date) as latest_business_date
                        from enriched;
                        """,
                        params,
                    )
                    kpis = self._json_ready(cursor.fetchone() or {})

        except errors.UndefinedTable:
            return self._empty_executive_signals(client_id=client_id, limit=limit, offset=offset)

        return {
            "client_id": client_id,
            "limit": limit,
            "offset": offset,
            "kpis": kpis,
            "filters": self._filter_options(rows),
            "items": rows,
        }

    def fetch_intraday_radar(
        self,
        *,
        client_id: str,
        campaign_id: int | None,
        date_key: int | None,
        date_key_from: int | None,
        date_key_to: int | None,
        brand: str | None,
        chain: str | None,
        product_key: str | None,
        event_area: str | None,
        severity: str | None,
        query: str | None,
        limit: int,
        offset: int,
    ) -> dict[str, object]:
        params: dict[str, Any] = {
            "client_id": client_id,
            "campaign_id": campaign_id,
            "date_key": date_key,
            "date_key_from": date_key_from,
            "date_key_to": date_key_to,
            "brands": [value for value in (brand or "").split(",") if value],
            "chains": [value for value in (chain or "").split(",") if value],
            "product_keys": [value for value in (product_key or "").split(",") if value],
            "event_areas": [value for value in (event_area or "").split(",") if value],
            "severities": [value for value in (severity or "").split(",") if value],
            "query": f"%{query.strip()}%" if query and query.strip() else None,
            "limit": limit,
            "offset": offset,
        }

        try:
            with self._connection_factory() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        with selected_date as (
                          select coalesce(
                            %(date_key)s::int,
                            (
                              select max(e.date_key)
                              from public.mkt_market_event e
                              join public.mkt_dim_market_event_type et
                                on et.event_type = e.event_type
                               and et.is_active
                               and et.appears_in_intraday_radar
                              join public.mkt_campaign_client_access cca
                                on cca.campaign_id = e.campaign_id
                               and cca.is_active
                               and (cca.valid_from is null or e.business_date >= cca.valid_from)
                               and (cca.valid_to is null or e.business_date <= cca.valid_to)
                              join public.auth_clients ac
                                on ac.id = cca.client_id
                               and ac.status = 'active'
                              where cca.client_id::text = %(client_id)s
                                and (e.client_id is null or e.client_id = cca.client_id)
                                and e.date_key < to_char((now() at time zone 'America/Costa_Rica')::date, 'YYYYMMDD')::int
                                and (%(campaign_id)s::int is null or e.campaign_id = %(campaign_id)s)
                            )
                          ) as selected_date_key
                        ),
                        enriched as (
                          select
                            e.event_key as event_id,
                            et.event_area,
                            e.event_type,
                            e.severity,
                            jsonb_build_object(
                              'display_label', et.display_label,
                              'short_label', et.short_label,
                              'description', et.description,
                              'metric_labels', jsonb_build_object(
                                'previous', et.metric_previous_label,
                                'current', et.metric_current_label,
                                'change', et.metric_change_label
                              ),
                              'value_format', et.value_format,
                              'change_format', et.change_format,
                              'direction_semantics', et.direction_semantics,
                              'header_variant', et.header_variant,
                              'icon_name', et.icon_name,
                              'accent_token', et.accent_token,
                              'chart_annotation_label', et.chart_annotation_label,
                              'config', et.presentation_config
                            ) as presentation,
                            e.business_date::text as business_date,
                            e.date_key,
                            nullif(e.metrics_json ->> 'previous_date_key', '')::int as previous_date_key,
                            e.campaign_id,
                            coalesce(e.campaign_name, '') as campaign,
                            e.chain,
                            e.evidence_json ->> 'brand' as brand,
                            e.evidence_json ->> 'product' as product,
                            null::numeric as content_quantity,
                            null::text as content_unit,
                            e.evidence_json ->> 'gtin' as gtin,
                            e.evidence_json ->> 'product_key' as product_key,
                            e.business_date::text as captured_at_cr,
                            null::text as previous_captured_at_cr,
                            nullif(e.metrics_json ->> 'previous_value', '')::numeric(12,2) as previous_value,
                            nullif(e.metrics_json ->> 'current_value', '')::numeric(12,2) as current_value,
                            nullif(e.metrics_json ->> 'change_abs', '')::numeric(12,2) as change_amount,
                            nullif(e.metrics_json ->> 'change_pct', '')::numeric(12,2) as change_pct,
                            case
                              when et.event_area = 'promotion' then nullif(e.metrics_json ->> 'promo_share_current', '')::numeric(5,2)
                              else null::numeric
                            end as promo_share_pct,
                            null::numeric(5,2) as discount_pct,
                            nullif(e.metrics_json ->> 'observed_locations', '')::int as observed_locations,
                            nullif(e.metrics_json ->> 'visible_locations', '')::int as visible_locations,
                            nullif(e.metrics_json ->> 'available_locations', '')::int as available_locations,
                            e.evidence_json ->> 'product_url' as product_url
                          from public.mkt_market_event e
                          cross join selected_date sd
                          join public.mkt_dim_market_event_type et
                            on et.event_type = e.event_type
                           and et.is_active
                           and et.appears_in_intraday_radar
                          join public.mkt_campaign_client_access cca
                            on cca.campaign_id = e.campaign_id
                           and cca.is_active
                           and (cca.valid_from is null or e.business_date >= cca.valid_from)
                           and (cca.valid_to is null or e.business_date <= cca.valid_to)
                          join public.auth_clients ac
                            on ac.id = cca.client_id
                           and ac.status = 'active'
                          where cca.client_id::text = %(client_id)s
                            and (e.client_id is null or e.client_id = cca.client_id)
                            and (
                              (%(date_key)s::int is not null and e.date_key = sd.selected_date_key)
                              or (
                                %(date_key)s::int is null
                                and %(date_key_from)s::int is null
                                and %(date_key_to)s::int is null
                                and e.date_key = sd.selected_date_key
                              )
                              or (
                                %(date_key)s::int is null
                                and (%(date_key_from)s::int is not null or %(date_key_to)s::int is not null)
                                and (%(date_key_from)s::int is null or e.date_key >= %(date_key_from)s::int)
                                and (%(date_key_to)s::int is null or e.date_key <= %(date_key_to)s::int)
                              )
                            )
                            and (%(campaign_id)s::int is null or e.campaign_id = %(campaign_id)s)
                            and (%(brands)s::text[] = '{}'::text[] or e.evidence_json ->> 'brand' = any(%(brands)s::text[]))
                            and (%(chains)s::text[] = '{}'::text[] or e.chain = any(%(chains)s::text[]))
                            and (%(product_keys)s::text[] = '{}'::text[] or e.evidence_json ->> 'product_key' = any(%(product_keys)s::text[]))
                            and (%(event_areas)s::text[] = '{}'::text[] or et.event_area = any(%(event_areas)s::text[]))
                            and (%(severities)s::text[] = '{}'::text[] or e.severity = any(%(severities)s::text[]))
                            and (
                              %(query)s::text is null
                              or e.evidence_json ->> 'product' ilike %(query)s
                              or e.evidence_json ->> 'brand' ilike %(query)s
                              or e.chain ilike %(query)s
                              or e.event_type ilike %(query)s
                              or et.display_label ilike %(query)s
                              or et.short_label ilike %(query)s
                            )
                        )
                        select
                          *,
                          count(*) over()::int as total_count,
                          count(*) filter (where event_area = 'price') over()::int as total_price_events,
                          count(*) filter (where event_area = 'promotion') over()::int as total_promo_events,
                          count(*) filter (where lower(coalesce(severity, '')) = 'high') over()::int as total_high_severity_events
                        from enriched
                        order by
                          date_key desc,
                          case lower(coalesce(severity, ''))
                            when 'high' then 1
                            when 'medium' then 2
                            when 'low' then 3
                            else 9
                          end,
                          abs(coalesce(change_pct, change_amount, 0)) desc,
                          captured_at_cr desc
                        limit %(limit)s offset %(offset)s;
                        """,
                        params,
                    )
                    rows = [self._normalize_product_display(self._json_ready(row)) for row in cursor.fetchall()]

                    cursor.execute(
                        """
                        select
                          coalesce(
                            %(date_key)s::int,
                            %(date_key_to)s::int,
                            max(e.date_key)
                          ) as selected_date_key,
                          max(nullif(e.metrics_json ->> 'previous_date_key', '')::int)
                            filter (where e.date_key = coalesce(%(date_key)s::int, %(date_key_to)s::int, e.date_key)) as prior_closed_date_key,
                          to_char((now() at time zone 'America/Costa_Rica')::date, 'YYYYMMDD')::int as current_cr_date_key
                        from public.mkt_market_event e
                        join public.mkt_dim_market_event_type et
                          on et.event_type = e.event_type
                         and et.is_active
                         and et.appears_in_intraday_radar
                        join public.mkt_campaign_client_access cca
                          on cca.campaign_id = e.campaign_id
                         and cca.is_active
                         and (cca.valid_from is null or e.business_date >= cca.valid_from)
                         and (cca.valid_to is null or e.business_date <= cca.valid_to)
                        join public.auth_clients ac
                          on ac.id = cca.client_id
                         and ac.status = 'active'
                        where cca.client_id::text = %(client_id)s
                          and (e.client_id is null or e.client_id = cca.client_id)
                          and e.date_key < to_char((now() at time zone 'America/Costa_Rica')::date, 'YYYYMMDD')::int
                          and (%(date_key_from)s::int is null or e.date_key >= %(date_key_from)s::int)
                          and (%(date_key_to)s::int is null or e.date_key <= %(date_key_to)s::int)
                          and (%(campaign_id)s::int is null or e.campaign_id = %(campaign_id)s);
                        """,
                        params,
                    )
                    date_meta = self._json_ready(cursor.fetchone() or {})

                    stats = rows[0] if rows else {}
                    selected_date_key = date_meta.get("selected_date_key") or max((row.get("date_key") for row in rows if row.get("date_key") is not None), default=date_key)
                    latest_capture = max((row.get("captured_at_cr") for row in rows if row.get("captured_at_cr")), default=None)
                    kpis = {
                        "total_events": stats.get("total_count", len(rows)),
                        "price_events": stats.get("total_price_events", sum(1 for row in rows if row.get("event_area") == "price")),
                        "promo_events": stats.get("total_promo_events", sum(1 for row in rows if row.get("event_area") == "promotion")),
                        "high_severity_events": stats.get(
                            "total_high_severity_events",
                            sum(1 for row in rows if str(row.get("severity") or "").lower() == "high"),
                        ),
                        "latest_date_key": selected_date_key,
                        "latest_capture": latest_capture,
                        "selected_date_key": selected_date_key,
                        "prior_closed_date_key": date_meta.get("prior_closed_date_key"),
                        "current_cr_date_key": date_meta.get("current_cr_date_key"),
                    }

        except errors.UndefinedTable:
            return self._empty_intraday_radar(client_id=client_id, limit=limit, offset=offset)

        return {
            "client_id": client_id,
            "limit": limit,
            "offset": offset,
            "kpis": kpis,
            "filters": self._intraday_filter_options(rows),
            "items": rows,
        }

    def fetch_signal_detail(self, *, client_id: str, signal_id: str) -> dict[str, object]:
        try:
            with self._connection_factory() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        with enriched as (
                          select
                            business_date,
                            date_key,
                            client_id::text as client_id,
                            campaign_id,
                            campaign,
                            brand,
                            chain,
                            signal_type,
                            signal_status,
                            effect,
                            severity,
                            impact_score,
                            confidence_score,
                            headline,
                            summary,
                            business_reading,
                            recommended_action,
                            notification_status,
                            repeat_count,
                            metrics_json,
                            evidence_json,
                            delta_metrics_json,
                            navigation_json,
                            narrative_json,
                            nullif(evidence_json ->> 'product', '') as evidence_product,
                            coalesce(
                              nullif(evidence_json ->> 'product_key', ''),
                              nullif(navigation_json ->> 'product_key', '')
                            ) as product_key
                          from public.mw_bi_executive_signal_feed
                          where client_id::text = %(client_id)s
                        ),
                        display_rows as (
                          select
                            *,
                            case
                              when evidence_product is not null then evidence_product
                              when signal_type = 'driver_sku_detected' then 'Multiple driver SKUs'
                              else 'Category / brand level'
                            end as product_display,
                            md5(concat_ws('|',
                              client_id,
                              campaign_id::text,
                              date_key::text,
                              coalesce(brand, ''),
                              coalesce(chain, ''),
                              coalesce(signal_type, ''),
                              coalesce(headline, ''),
                              coalesce(product_key, '')
                            )) as signal_id
                          from enriched
                        )
                        select *
                        from display_rows
                        where signal_id = %(signal_id)s
                        limit 1;
                        """,
                        {"client_id": client_id, "signal_id": signal_id},
                    )
                    signal = cursor.fetchone()
                    if not signal:
                        return {"client_id": client_id, "signal": None, "drivers": [], "evidence": []}

                    signal_row = self._json_ready(signal)
                    detail_params = {
                        "client_id": client_id,
                        "campaign_id": signal_row.get("campaign_id"),
                        "date_key": signal_row.get("date_key"),
                        "product_key": signal_row.get("product_key"),
                        "brand": signal_row.get("brand"),
                        "product": signal_row.get("evidence_product"),
                    }

                    cursor.execute(
                        """
                        select
                          business_date,
                          date_key,
                          client_id::text as client_id,
                          campaign_id,
                          campaign,
                          brand,
                          product,
                          gtin,
                          product_key::text as product_key,
                          chain,
                          chain_order,
                          average_price,
                          best_chain_average_price,
                          market_best_price,
                          gap_amount,
                          gap_pct,
                          price_index,
                          price_rank,
                          monitored_stores,
                          visible_stores,
                          visibility_pct,
                          price_reading,
                          suggested_action,
                          product_url,
                          image_url,
                          best_chain,
                          best_chain_url,
                          best_price_image_url
                        from public.mw_bi_sku_price_drivers
                        where client_id::text = %(client_id)s
                          and campaign_id = %(campaign_id)s
                          and date_key = %(date_key)s
                          and (
                            (%(product_key)s::text is not null and product_key::text = %(product_key)s)
                            or (%(product_key)s::text is null and brand = %(brand)s)
                          )
                        order by chain_order nulls last, gap_pct desc nulls last, chain
                        limit 100;
                        """,
                        detail_params,
                    )
                    drivers = [self._json_ready(row) for row in cursor.fetchall()]

                    cursor.execute(
                        """
                        select
                          business_date,
                          date_key,
                          client_id::text as client_id,
                          campaign_id,
                          campaign,
                          brand,
                          product,
                          gtin,
                          product_key::text as product_key,
                          chain,
                          chain_order,
                          store,
                          store_code,
                          province,
                          canton,
                          district,
                          observed_price,
                          reference_price,
null::numeric(5,2) as discount_pct,
                          is_available,
                          promo_detected,
                          available_quantity,
                          captured_at_cr,
                          product_url,
                          image_url
                        from public.mw_bi_sku_store_price_evidence
                        where client_id::text = %(client_id)s
                          and campaign_id = %(campaign_id)s
                          and date_key = %(date_key)s
                          and (
                            (%(product_key)s::text is not null and product_key::text = %(product_key)s)
                            or (%(product_key)s::text is null and brand = %(brand)s and (%(product)s::text is null or product = %(product)s))
                          )
                        order by chain_order nulls last, chain, observed_price nulls last, store
                        limit 300;
                        """,
                        detail_params,
                    )
                    evidence = [self._json_ready(row) for row in cursor.fetchall()]

        except errors.UndefinedTable:
            return {"client_id": client_id, "signal": None, "drivers": [], "evidence": []}

        return {
            "client_id": client_id,
            "signal": signal_row,
            "drivers": drivers,
            "evidence": evidence,
        }

    def fetch_intraday_product_detail(
        self,
        *,
        client_id: str,
        product_key: str,
        campaign_id: int | None,
        date_key: int | None,
        chain: str | None,
        history_days: int = 30,
    ) -> dict[str, object]:
        params: dict[str, Any] = {
            "client_id": client_id,
            "product_key": product_key,
            "campaign_id": campaign_id,
            "date_key": date_key,
            "chain": chain or None,
            "history_days": max(7, min(history_days, 365)),
        }
        empty_payload = {
            "client_id": client_id,
            "product": None,
            "chain_snapshot": [],
            "store_evidence": [],
            "daily_history": [],
            "history": [],
            "price_history": [],
            "events": [],
        }

        try:
            with self._connection_factory() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        select
                          coalesce(
                            %(date_key)s::int,
                            max(o.date_key)
                          ) as selected_date_key,
                          max(o.date_key) as latest_history_date_key
                        from public.mw_app_product_chain_day o
                        where o.client_id::text = %(client_id)s
                          and o.product_key::text = %(product_key)s
                          and (%(campaign_id)s::int is null or o.campaign_id = %(campaign_id)s)
                          and (%(chain)s::text is null or o.chain = %(chain)s)
                          and o.date_key < to_char((now() at time zone 'America/Costa_Rica')::date, 'YYYYMMDD')::int;
                        """,
                        params,
                    )
                    scope_row = self._json_ready(cursor.fetchone() or {})
                    selected_date_key = scope_row.get("selected_date_key")
                    history_date_key = scope_row.get("latest_history_date_key") or selected_date_key
                    if selected_date_key is None:
                        return empty_payload

                    detail_params = {
                        **params,
                        "date_key": selected_date_key,
                        "history_date_key": history_date_key,
                    }

                    cursor.execute(
                        """
                        select
                          o.product_key::text as product_key,
                          max(o.gtin) as gtin,
                          max(o.brand) as brand,
                          max(o.product) as product,
                          max(o.content_quantity) as content_quantity,
                          max(o.content_unit) as content_unit,
                          max(o.campaign_id) as campaign_id,
                          max(o.campaign) as campaign,
                          max(o.chain) as chain,
                          max(o.date_key) as date_key,
                          max(o.captured_at_cr) as latest_capture,
                          min(o.min_price) as min_price,
                          max(o.max_price) as max_price,
                          round(avg(o.average_price) filter (where o.average_price is not null), 2) as avg_price,
                          max(o.max_discount_pct) as max_discount_pct,
                          bool_or(o.promo_detected) as promo_seen,
                          max(o.image_url) filter (where o.image_url is not null) as image_url,
                          max(o.product_url) filter (where o.product_url is not null) as product_url
                        from public.mw_app_product_chain_day o
                        where o.client_id::text = %(client_id)s
                          and o.product_key::text = %(product_key)s
                          and o.date_key = %(date_key)s
                          and (%(campaign_id)s::int is null or o.campaign_id = %(campaign_id)s)
                          and (%(chain)s::text is null or o.chain = %(chain)s)
                        group by o.product_key;
                        """,
                        detail_params,
                    )
                    product = cursor.fetchone()
                    if not product:
                        return empty_payload
                    product_row = self._json_ready(product)
                    product_row = self._normalize_product_display(product_row)
                    all_chain_params = {**detail_params, "chain": None}

                    cursor.execute(
                        """
                        select
                          o.chain,
                          max(o.captured_at_cr) as captured_at_cr,
                          round(avg(o.average_price) filter (where o.average_price is not null), 2) as average_price,
                          round(avg(o.average_unit_price) filter (where o.average_unit_price is not null), 4) as average_unit_price,
                          min(o.min_price) as min_price,
                          max(o.max_price) as max_price,
                          bool_or(o.promo_detected) as promo_detected,
                          round(avg(o.promo_share_pct) filter (where o.promo_share_pct is not null), 2) as promo_share_pct,
                          max(o.max_discount_pct) as max_discount_pct,
                          max(o.visible_locations) as visible_locations,
                          max(o.available_locations) as available_locations,
                          max(o.product_url) filter (where o.product_url is not null) as product_url,
                          max(o.image_url) filter (where o.image_url is not null) as image_url
                        from public.mw_app_product_chain_day o
                        where o.client_id::text = %(client_id)s
                          and o.product_key::text = %(product_key)s
                          and o.date_key = %(date_key)s
                          and (%(campaign_id)s::int is null or o.campaign_id = %(campaign_id)s)
                          and (%(chain)s::text is null or o.chain = %(chain)s)
                        group by o.chain
                        order by average_price nulls last, chain;
                        """,
                        all_chain_params,
                    )
                    chain_snapshot = [self._json_ready(row) for row in cursor.fetchall()]

                    cursor.execute(
                        """
                        select
                          o.date_key,
                          o.chain,
                          o.location_key,
                          o.location_code,
                          o.location_name,
                          o.province,
                          o.canton,
                          o.district,
                          o.sales_channel,
                          o.region_id,
                          o.captured_at_cr,
                          o.is_listed,
                          o.is_available,
                          o.reference_price_amount,
                          o.spot_price_amount,
                          coalesce(o.spot_price_amount, o.effective_price_amount) as effective_price_amount,
                          o.promo_detected,
                          o.discount_pct_display as discount_pct,
                          o.available_quantity,
                          o.product_url,
                          o.source_engine
                        from public.mw_app_product_store_day o
                        where o.client_id::text = %(client_id)s
                          and o.product_key::text = %(product_key)s
                          and o.date_key = %(date_key)s
                          and (%(campaign_id)s::int is null or o.campaign_id = %(campaign_id)s)
                          and (%(chain)s::text is null or o.chain = %(chain)s)
                        order by
                          o.chain,
                          o.is_available desc nulls last,
                          coalesce(o.spot_price_amount, o.effective_price_amount) nulls last,
                          o.location_name nulls last,
                          o.captured_at_cr desc
                        limit 500;
                        """,
                        detail_params,
                    )
                    store_evidence = [self._json_ready(row) for row in cursor.fetchall()]
                    store_evidence = [self._with_store_context_url(row) for row in store_evidence]

                    cursor.execute(
                        """
                        select
                          date_key,
                          business_date,
                          chain,
                          average_price,
                          average_unit_price,
                          gap_pct,
                          price_index,
                          price_reading,
                          suggested_action
                        from public.mw_app_product_chain_day
                        where client_id::text = %(client_id)s
                          and product_key::text = %(product_key)s
                          and (%(campaign_id)s::int is null or campaign_id = %(campaign_id)s)
                          and (%(chain)s::text is null or chain = %(chain)s)
                          and date_key <= %(history_date_key)s
                        order by date_key, chain;
                        """,
                        all_chain_params,
                    )
                    daily_history = [self._json_ready(row) for row in cursor.fetchall()]

                    cursor.execute(
                        """
                        select
                          date_key,
                          chain,
                          captured_at_cr,
                          average_price,
                          average_unit_price,
                          promo_detected,
                          promo_share_pct,
                          max_discount_pct,
                          visible_locations,
                          available_locations
                        from public.mw_app_product_chain_day
                        where client_id::text = %(client_id)s
                          and product_key::text = %(product_key)s
                          and date_key = %(date_key)s
                          and (%(campaign_id)s::int is null or campaign_id = %(campaign_id)s)
                          and (%(chain)s::text is null or chain = %(chain)s)
                        order by chain, captured_at_cr;
                        """,
                        all_chain_params,
                    )
                    history = [self._json_ready(row) for row in cursor.fetchall()]

                    cursor.execute(
                        """
                        with daily as (
                          select
                            o.date_key,
                            o.business_date,
                            o.chain,
                            max(o.captured_at_cr) as captured_at_cr,
                            round(avg(o.average_price) filter (where o.average_price is not null), 2) as effective_price_amount,
                            round(avg(o.reference_price_amount) filter (where o.reference_price_amount is not null), 2) as reference_price_amount,
                            round(avg(o.promo_price_amount) filter (where o.promo_price_amount is not null), 2) as promo_price_amount,
                            bool_or(o.promo_detected) as promo_detected,
                            max(o.max_discount_pct) as discount_pct,
                            max(o.visible_locations) as visible_locations,
                            max(o.available_locations) as available_locations,
                            case
                              when max(o.available_locations) > 0 then 'available'
                              when max(o.visible_locations) > 0 then 'listed_unavailable'
                              else 'unobserved'
                            end as availability_state
                          from public.mw_app_product_chain_day as o
                          where o.client_id::text = %(client_id)s
                            and o.product_key::text = %(product_key)s
                            and o.date_key <= %(history_date_key)s
                            and (%(campaign_id)s::int is null or o.campaign_id = %(campaign_id)s)
                            and (%(chain)s::text is null or o.chain = %(chain)s)
                          group by
                            o.date_key,
                            o.business_date,
                            o.chain
                        ),
                        limited_dates as (
                          select distinct date_key
                          from daily
                          order by date_key desc
                          limit %(history_days)s
                        ),
                        sequenced as (
                          select
                            d.*,
                            lag(d.date_key) over (
                              partition by d.chain
                              order by d.date_key
                            ) as previous_date_key
                          from daily as d
                          where d.date_key in (select date_key from limited_dates)
                        )
                        select
                          date_key,
                          business_date,
                          chain,
                          captured_at_cr,
                          effective_price_amount,
                          reference_price_amount,
                          promo_price_amount,
                          promo_detected,
                          discount_pct,
                          visible_locations,
                          available_locations,
                          availability_state,
                          previous_date_key
                        from sequenced
                        order by date_key, chain;
                        """,
                        all_chain_params,
                    )
                    price_history = [self._json_ready(row) for row in cursor.fetchall()]
                    events = []

                    cursor.execute(
                        """
                        with visible_dates as (
                          select distinct o.date_key
                          from public.mw_app_product_chain_day as o
                          where o.client_id::text = %(client_id)s
                            and o.product_key::text = %(product_key)s
                            and o.date_key <= %(history_date_key)s
                            and (%(campaign_id)s::int is null or o.campaign_id = %(campaign_id)s)
                          order by o.date_key desc
                          limit %(history_days)s
                        )
	                        select
	                            me.event_key as event_id,
	                            me.event_type,
	                            me.severity,
	                            et.event_area,
	                            jsonb_build_object(
	                              'display_label', et.display_label,
	                              'short_label', et.short_label,
                              'description', et.description,
                              'metric_labels', jsonb_build_object(
                                'previous', et.metric_previous_label,
                                'current', et.metric_current_label,
                                'change', et.metric_change_label
                              ),
                              'value_format', et.value_format,
                              'change_format', et.change_format,
                              'direction_semantics', et.direction_semantics,
                              'header_variant', et.header_variant,
                              'icon_name', et.icon_name,
                              'accent_token', et.accent_token,
                              'chart_annotation_label', et.chart_annotation_label,
	                              'config', et.presentation_config
	                            ) as presentation,
	                            me.business_date::text as business_date,
	                            me.date_key,
	                            nullif(me.metrics_json ->> 'previous_date_key', '')::int as previous_date_key,
	                            me.campaign_id,
	                            coalesce(me.campaign_name, '') as campaign,
	                            coalesce(me.chain, me.evidence_json ->> 'chain') as chain,
	                            me.evidence_json ->> 'brand' as brand,
	                            me.evidence_json ->> 'product' as product,
	                            dp.content_quantity,
	                            dp.content_unit,
	                            me.evidence_json ->> 'gtin' as gtin,
	                            me.evidence_json ->> 'product_key' as product_key,
	                            coalesce(
	                              nullif(me.metrics_json ->> 'previous_value', '')::numeric(12,2),
	                              nullif(me.metrics_json ->> 'market_best_price', '')::numeric(12,2)
	                            ) as previous_value,
	                            coalesce(
	                              nullif(me.metrics_json ->> 'current_value', '')::numeric(12,2),
	                              nullif(me.metrics_json ->> 'avg_price', '')::numeric(12,2)
	                            ) as current_value,
	                            coalesce(
	                              nullif(me.metrics_json ->> 'change_abs', '')::numeric(12,2),
	                              nullif(me.metrics_json ->> 'gap_amount', '')::numeric(12,2)
	                            ) as change_amount,
	                            coalesce(
	                              nullif(me.metrics_json ->> 'change_pct', '')::numeric(12,2),
	                              nullif(me.metrics_json ->> 'gap_pct', '')::numeric(12,2)
	                            ) as change_pct,
	                            case
	                              when et.event_area = 'promotion' then nullif(me.metrics_json ->> 'promo_share_current', '')::numeric(5,2)
	                              else null::numeric
	                            end as promo_share_pct,
	                            null::numeric(5,2) as discount_pct,
	                            nullif(me.metrics_json ->> 'observed_locations', '')::int as observed_locations,
	                            nullif(me.metrics_json ->> 'visible_locations', '')::int as visible_locations,
	                            nullif(me.metrics_json ->> 'available_locations', '')::int as available_locations,
	                            me.evidence_json ->> 'product_url' as product_url,
	                            me.metrics_json as metrics,
	                            me.evidence_json as evidence,
	                            cs.signal_json as signal
	                        from public.mkt_market_event me
	                        join public.mkt_dim_market_event_type et
	                            on et.event_type = me.event_type
	                           and et.is_active
	                        join public.mkt_campaign_client_access cca
	                            on cca.campaign_id = me.campaign_id
	                           and cca.is_active
	                           and cca.client_id::text = %(client_id)s
	                           and (cca.valid_from is null or me.business_date >= cca.valid_from)
	                           and (cca.valid_to is null or me.business_date <= cca.valid_to)
	                        left join lateral (
	                            select jsonb_build_object(
	                              'signal_key', s.signal_key,
	                              'signal_type', s.signal_type,
	                              'signal_status', s.lifecycle_status,
	                              'headline', s.headline,
	                              'summary', s.summary,
	                              'business_reading', s.business_reading,
	                              'recommended_action', s.recommended_action,
	                              'narrative', s.narrative_json,
	                              'llm_provider', s.llm_provider,
	                              'llm_model', s.llm_model,
	                              'llm_prompt_version', s.llm_prompt_version
	                            ) as signal_json
	                            from public.mkt_client_signal s
	                            where s.event_key = me.event_key
	                              and s.perspective_client_id::text = %(client_id)s
	                              and s.campaign_id = me.campaign_id
	                            order by s.updated_at desc nulls last, s.signal_key desc
	                            limit 1
	                        ) cs on true
	                        left join public.mkt_dim_product dp
	                            on dp.product_key::text = me.evidence_json ->> 'product_key'
	                            or ((me.evidence_json ->> 'product_key') is null and dp.gtin_norm = me.evidence_json ->> 'gtin')
	                        where (%(campaign_id)s::int is null or me.campaign_id = %(campaign_id)s)
	                            and (%(history_date_key)s::int is null or me.date_key <= %(history_date_key)s)
	                            and (me.client_id is null or me.client_id::text = %(client_id)s)
	                            and me.evidence_json ->> 'product_key' = %(product_key)s
	                            and (
	                              (%(date_key)s::int is not null and me.date_key = %(date_key)s)
	                              or me.date_key in (select date_key from visible_dates)
	                              or nullif(me.metrics_json ->> 'previous_date_key', '')::int in (select date_key from visible_dates)
	                            )
	                        order by me.date_key desc
                        """,
                        all_chain_params,
                    )
                    events = [self._normalize_product_display(self._json_ready(row), fallback=product_row) for row in cursor.fetchall()]
                    for event in events:
                        event["event_id"] = event.get("event_id") or f"dod:{event.get('date_key')}:{event.get('product_key')}:{event.get('chain')}:{event.get('event_type')}"
                        event["captured_at_cr"] = event.get("business_date")
                        event["previous_captured_at_cr"] = None

        except errors.UndefinedTable:
            return {
                "client_id": client_id,
                "product": None,
                "chain_snapshot": [],
                "store_evidence": [],
                "daily_history": [],
                "history": [],
                "price_history": [],
                "events": [],
            }

        return {
            "client_id": client_id,
            "product": product_row,
            "chain_snapshot": chain_snapshot,
            "store_evidence": store_evidence,
            "daily_history": daily_history,
            "history": history,
            "price_history": price_history,
            "events": events,
        }

    def fetch_intraday_product_store_detail(
        self,
        *,
        client_id: str,
        product_key: str,
        location_key: int,
        campaign_id: int | None,
        date_key: int | None,
        chain: str | None,
        history_days: int = 30,
    ) -> dict[str, object]:
        params: dict[str, Any] = {
            "client_id": client_id,
            "product_key": product_key,
            "location_key": location_key,
            "campaign_id": campaign_id,
            "date_key": date_key,
            "chain": chain,
            "history_days": max(7, min(history_days, 365)),
        }

        empty_payload: dict[str, object] = {
            "client_id": client_id,
            "product": None,
            "selected_store": None,
            "store_options": [],
            "price_history": [],
            "captures": [],
        }

        try:
            with self._connection_factory() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        with selected_scope as (
                          select
                            coalesce(%(date_key)s::int, max(o.date_key)) as selected_date_key,
                            max(o.date_key) as latest_history_date_key
                          from public.mw_app_product_store_day o
                          where o.client_id::text = %(client_id)s
                            and o.product_key::text = %(product_key)s
                            and o.location_key = %(location_key)s
                            and (%(campaign_id)s::int is null or o.campaign_id = %(campaign_id)s)
                            and (%(chain)s::text is null or o.chain = %(chain)s)
                            and o.date_key < to_char((now() at time zone 'America/Costa_Rica')::date, 'YYYYMMDD')::int
                        ),
                        latest_capture as (
                          select distinct on (o.product_key, o.location_key)
                            o.product_key,
                            o.location_key,
                            o.chain,
                            o.location_name,
                            o.location_code,
                            o.province,
                            o.canton,
                            o.district,
                            o.sales_channel,
                            o.region_id,
                            o.campaign_id,
                            o.campaign,
                            o.date_key,
                            o.business_date,
                            o.captured_at_cr,
                            o.reference_price_amount,
                            o.spot_price_amount,
                            coalesce(o.spot_price_amount, o.effective_price_amount) as effective_price_amount,
                            o.promo_detected,
                            o.discount_pct_display as discount_pct,
                            o.is_listed,
                            o.is_available,
                            o.product_url,
                            o.image_url,
                            o.source_engine
                          from public.mw_app_product_store_day o
                          join selected_scope ss
                            on o.date_key = ss.selected_date_key
                          where o.client_id::text = %(client_id)s
                            and o.product_key::text = %(product_key)s
                            and o.location_key = %(location_key)s
                            and (%(campaign_id)s::int is null or o.campaign_id = %(campaign_id)s)
                            and (%(chain)s::text is null or o.chain = %(chain)s)
                          order by o.product_key, o.location_key, o.captured_at_cr desc
                        )
                        select
                          lc.product_key::text as product_key,
                          p.gtin_norm as gtin,
                          p.brand_name as brand,
                          p.product_name as product,
                          p.content_quantity,
                          p.content_unit,
                          lc.campaign_id,
                          lc.campaign,
                          lc.chain,
                          lc.date_key,
                          lc.captured_at_cr as latest_capture,
                          lc.reference_price_amount as current_regular_price,
                          lc.spot_price_amount as current_promo_price,
                          lc.effective_price_amount as current_effective_price,
                          lc.promo_detected,
                          lc.discount_pct,
                          lc.product_url,
                          lc.image_url
                        from latest_capture lc
                        join public.mkt_dim_product p
                          on p.product_key = lc.product_key;
                        """,
                        params,
                    )
                    product = cursor.fetchone()
                    if not product:
                        return empty_payload
                    product_row = self._normalize_product_display(self._json_ready(product))

                    cursor.execute(
                        """
                        select
                          coalesce(%(date_key)s::int, max(o.date_key)) as selected_date_key,
                          max(o.date_key) as latest_history_date_key
                        from public.mw_app_product_store_day o
                        where o.client_id::text = %(client_id)s
                          and o.product_key::text = %(product_key)s
                          and o.location_key = %(location_key)s
                          and (%(campaign_id)s::int is null or o.campaign_id = %(campaign_id)s)
                          and (%(chain)s::text is null or o.chain = %(chain)s)
                          and o.date_key < to_char((now() at time zone 'America/Costa_Rica')::date, 'YYYYMMDD')::int;
                        """,
                        params,
                    )
                    scope_row = self._json_ready(cursor.fetchone() or {})
                    detail_params = {
                        **params,
                        "history_date_key": scope_row.get("latest_history_date_key") or product_row.get("date_key"),
                    }

                    cursor.execute(
                        """
                        select distinct on (o.location_key)
                          o.location_key,
                          o.chain,
                          o.location_name,
                          o.location_code,
                          o.province,
                          o.canton,
                          o.district,
                          o.sales_channel,
                          o.region_id
                        from public.mw_app_product_store_day o
                        where o.client_id::text = %(client_id)s
                          and o.product_key::text = %(product_key)s
                          and (%(campaign_id)s::int is null or o.campaign_id = %(campaign_id)s)
                          and (%(chain)s::text is null or o.chain = %(chain)s)
                        order by o.location_key, o.date_key desc, o.captured_at_cr desc;
                        """,
                        params,
                    )
                    store_options = [self._json_ready(row) for row in cursor.fetchall()]
                    selected_store = next(
                        (row for row in store_options if int(row.get("location_key") or -1) == location_key),
                        None,
                    )

                    cursor.execute(
                        """
                        with daily as (
                          select distinct on (o.date_key)
                            o.date_key,
                            o.business_date,
                            o.chain,
                            o.location_name as store,
                            o.location_key,
                            o.captured_at_cr,
                            o.reference_price_amount,
                            o.spot_price_amount as promo_price_amount,
                            coalesce(o.spot_price_amount, o.effective_price_amount) as effective_price_amount,
                            o.promo_detected,
                            o.discount_pct_display as discount_pct,
                            o.is_listed,
                            o.is_available,
                            o.available_quantity,
                            case
                              when o.is_available then 'available'
                              when o.is_listed then 'listed_unavailable'
                              else 'unobserved'
                            end as availability_state,
                            o.product_url,
                            o.source_engine
                          from public.mw_app_product_store_day o
                          where o.client_id::text = %(client_id)s
                            and o.product_key::text = %(product_key)s
                            and o.location_key = %(location_key)s
                            and o.date_key <= %(history_date_key)s
                            and (%(campaign_id)s::int is null or o.campaign_id = %(campaign_id)s)
                            and (%(chain)s::text is null or o.chain = %(chain)s)
                          order by o.date_key, o.captured_at_cr desc
                        ),
                        limited as (
                          select *
                          from daily
                          order by date_key desc
                          limit %(history_days)s
                        ),
                        sequenced as (
                          select
                            l.*,
                            lag(l.date_key) over (order by l.date_key) as previous_date_key
                          from limited l
                        )
                        select
                          date_key,
                          previous_date_key,
                          business_date,
                          chain,
                          store,
                          location_key,
                          captured_at_cr,
                          effective_price_amount,
                          reference_price_amount,
                          promo_price_amount,
                          promo_detected,
                          discount_pct,
                          is_listed,
                          is_available,
                          available_quantity,
                          availability_state,
                          product_url,
                          source_engine
                        from sequenced
                        order by date_key;
                        """,
                        detail_params,
                    )
                    captures = [self._with_store_context_url(self._json_ready(row)) for row in cursor.fetchall()]
                    price_history = [
                        {
                            "date_key": row.get("date_key"),
                            "previous_date_key": row.get("previous_date_key"),
                            "business_date": row.get("business_date"),
                            "chain": row.get("chain"),
                            "store": row.get("store"),
                            "captured_at_cr": row.get("captured_at_cr"),
                            "effective_price_amount": row.get("effective_price_amount") if row.get("is_available") else None,
                            "reference_price_amount": row.get("reference_price_amount") if row.get("is_available") else None,
                            "promo_price_amount": row.get("promo_price_amount") if row.get("is_available") else None,
                            "promo_detected": row.get("promo_detected"),
                            "discount_pct": row.get("discount_pct"),
                            "is_listed": row.get("is_listed"),
                            "is_available": row.get("is_available"),
                            "availability_state": row.get("availability_state"),
                        }
                        for row in captures
                    ]

        except errors.UndefinedTable:
            return empty_payload

        return {
            "client_id": client_id,
            "product": product_row,
            "selected_store": selected_store,
            "store_options": store_options,
            "price_history": price_history,
            "captures": captures,
        }

    @staticmethod
    def _json_ready(row: dict[str, Any]) -> dict[str, Any]:
        return {
            key: float(value) if isinstance(value, Decimal) else value.isoformat() if hasattr(value, "isoformat") else value
            for key, value in dict(row).items()
        }

    @staticmethod
    def _format_content_quantity(value: object) -> str | None:
        if value in (None, ""):
            return None
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        text = str(value).strip()
        if not text:
            return None
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text

    @classmethod
    def _normalize_product_display(cls, row: dict[str, Any], *, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
        product = row.get("product")
        if not isinstance(product, str) or not product.strip():
            return row

        quantity = cls._format_content_quantity(row.get("content_quantity") or (fallback or {}).get("content_quantity"))
        unit = row.get("content_unit") or (fallback or {}).get("content_unit")
        if not quantity or not unit:
            return row

        suffix = f" - {quantity} {unit}"
        if not _MEASURE_SUFFIX_RE.search(product):
            return row

        row["product"] = _MEASURE_SUFFIX_RE.sub(suffix, product).strip()
        return row

    @staticmethod
    def _with_store_context_url(row: dict[str, Any]) -> dict[str, Any]:
        product_url = row.get("product_url")
        if not isinstance(product_url, str) or not product_url:
            row["store_context_url"] = None
            return row

        if row.get("source_engine") != "vtex":
            row["store_context_url"] = product_url
            return row

        query = dict(parse_qsl(urlsplit(product_url).query, keep_blank_values=True))
        sales_channel = row.get("sales_channel")
        region_id = row.get("region_id")
        if sales_channel:
            query["sc"] = str(sales_channel)
        if region_id:
            query["region-id"] = str(region_id)

        split_url = urlsplit(product_url)
        row["store_context_url"] = urlunsplit(
            (
                split_url.scheme,
                split_url.netloc,
                split_url.path,
                urlencode(query),
                split_url.fragment,
            )
        )
        return row

    @staticmethod
    def _empty_executive_signals(*, client_id: str, limit: int, offset: int = 0) -> dict[str, object]:
        return {
            "client_id": client_id,
            "limit": limit,
            "offset": offset,
            "kpis": {
                "total_signals": 0,
                "high_severity_signals": 0,
                "new_signals": 0,
                "active_repeated_signals": 0,
                "promo_signals": 0,
                "price_gap_signals": 0,
                "latest_business_date": None,
            },
            "filters": {
                "campaigns": [],
                "brands": [],
                "chains": [],
                "signal_types": [],
                "severities": [],
                "statuses": [],
            },
            "items": [],
        }

    @staticmethod
    def _empty_intraday_radar(*, client_id: str, limit: int, offset: int = 0) -> dict[str, object]:
        return {
            "client_id": client_id,
            "limit": limit,
            "offset": offset,
            "kpis": {
                "total_events": 0,
                "price_events": 0,
                "promo_events": 0,
                "high_severity_events": 0,
                "latest_date_key": None,
                "latest_capture": None,
                "selected_date_key": None,
                "prior_closed_date_key": None,
                "current_cr_date_key": None,
            },
            "filters": {
                "campaigns": [],
                "brands": [],
                "chains": [],
                "products": [],
                "event_areas": [],
                "severities": [],
            },
            "items": [],
        }

    @staticmethod
    def _intraday_filter_options(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, object]]]:
        campaigns: dict[str, dict[str, object]] = {}
        brands: set[str] = set()
        chains: set[str] = set()
        products: dict[str, dict[str, object]] = {}
        event_areas: set[str] = set()
        severities: set[str] = set()

        for row in rows:
            if row.get("campaign_id") is not None:
                campaign_id = str(row["campaign_id"])
                campaigns[campaign_id] = {
                    "id": campaign_id,
                    "label": str(row.get("campaign") or campaign_id),
                }
            if row.get("brand"):
                brands.add(str(row["brand"]))
            if row.get("chain"):
                chains.add(str(row["chain"]))
            if row.get("product_key"):
                product_key = str(row["product_key"])
                products[product_key] = {
                    "id": product_key,
                    "label": str(row.get("product") or product_key),
                }
            if row.get("event_area"):
                event_areas.add(str(row["event_area"]))
            if row.get("severity"):
                severities.add(str(row["severity"]))

        return {
            "campaigns": sorted(campaigns.values(), key=lambda item: str(item["label"])),
            "brands": [{"id": value, "label": value} for value in sorted(brands)],
            "chains": [{"id": value, "label": value} for value in sorted(chains)],
            "products": sorted(products.values(), key=lambda item: str(item["label"])),
            "event_areas": [{"id": value, "label": value} for value in sorted(event_areas)],
            "severities": [{"id": value, "label": value} for value in sorted(severities)],
        }

    @staticmethod
    def _filter_options(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, object]]]:
        campaigns: dict[str, dict[str, object]] = {}
        brands: set[str] = set()
        chains: set[str] = set()
        signal_types: set[str] = set()
        severities: set[str] = set()
        statuses: set[str] = set()

        for row in rows:
            if row.get("campaign_id") is not None:
                campaign_id = str(row["campaign_id"])
                campaigns[campaign_id] = {
                    "id": campaign_id,
                    "label": str(row.get("campaign") or campaign_id),
                }
            if row.get("brand"):
                brands.add(str(row["brand"]))
            if row.get("chain"):
                chains.add(str(row["chain"]))
            if row.get("signal_type"):
                signal_types.add(str(row["signal_type"]))
            if row.get("severity"):
                severities.add(str(row["severity"]))
            if row.get("signal_status"):
                statuses.add(str(row["signal_status"]))

        return {
            "campaigns": sorted(campaigns.values(), key=lambda item: str(item["label"])),
            "brands": [{"id": value, "label": value} for value in sorted(brands)],
            "chains": [{"id": value, "label": value} for value in sorted(chains)],
            "signal_types": [{"id": value, "label": value} for value in sorted(signal_types)],
            "severities": [{"id": value, "label": value} for value in sorted(severities)],
            "statuses": [{"id": value, "label": value} for value in sorted(statuses)],
        }
