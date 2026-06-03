from collections.abc import Callable
from contextlib import AbstractContextManager
from decimal import Decimal
from typing import Any

import psycopg
from psycopg import errors


ConnectionFactory = Callable[[], AbstractContextManager[psycopg.Connection]]


class MarketRepository:
    def __init__(self, connection_factory: ConnectionFactory) -> None:
        self._connection_factory = connection_factory

    def fetch_overview(self, *, client_id: str) -> dict[str, object]:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    with scoped_runs as (
                      select r.run_key, r.chain_key, r.campaign_id
                      from public.mkt_run r
                      left join public.mkt_dim_campaign c
                        on c.id = r.campaign_id
                      where r.run_status = 'succeeded'
                        and (r.client_id::text = %(client_id)s or c.client_id::text = %(client_id)s)
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
                    where r.run_status = 'succeeded'
                      and (r.client_id::text = %(client_id)s or c.client_id::text = %(client_id)s)
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
                      left join public.mkt_dim_campaign c
                        on c.id = r.campaign_id
                      where r.run_status = 'succeeded'
                        and (r.client_id::text = %(client_id)s or c.client_id::text = %(client_id)s)
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
                      left join public.mkt_dim_campaign c
                        on c.id = r.campaign_id
                      where r.run_status = 'succeeded'
                        and (r.client_id::text = %(client_id)s or c.client_id::text = %(client_id)s)
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

    def fetch_executive_signals(
        self,
        *,
        client_id: str,
        campaign_id: int | None,
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
                            and (%(campaign_id)s::int is null or campaign_id = %(campaign_id)s)
                            and (%(date_from)s::date is null or business_date >= %(date_from)s::date)
                            and (%(date_to)s::date is null or business_date <= %(date_to)s::date)
                            and (
                              %(date_from)s::date is not null
                              or %(date_to)s::date is not null
                              or business_date = (
                                select max(latest.business_date)
                                from public.mw_bi_executive_signal_feed latest
                                where latest.client_id::text = %(client_id)s
                                  and (%(campaign_id)s::int is null or latest.campaign_id = %(campaign_id)s)
                                  and (%(brand)s::text is null or latest.brand = %(brand)s)
                                  and (%(chain)s::text is null or latest.chain = %(chain)s)
                                  and (%(signal_type)s::text is null or latest.signal_type = %(signal_type)s)
                                  and (%(severity)s::text is null or latest.severity = %(severity)s)
                                  and (%(signal_status)s::text is null or latest.signal_status = %(signal_status)s)
                              )
                            )
                            and (%(brand)s::text is null or brand = %(brand)s)
                            and (%(chain)s::text is null or chain = %(chain)s)
                            and (%(signal_type)s::text is null or signal_type = %(signal_type)s)
                            and (%(severity)s::text is null or severity = %(severity)s)
                            and (%(signal_status)s::text is null or signal_status = %(signal_status)s)
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
                            and (%(campaign_id)s::int is null or campaign_id = %(campaign_id)s)
                            and (%(date_from)s::date is null or business_date >= %(date_from)s::date)
                            and (%(date_to)s::date is null or business_date <= %(date_to)s::date)
                            and (
                              %(date_from)s::date is not null
                              or %(date_to)s::date is not null
                              or business_date = (
                                select max(latest.business_date)
                                from public.mw_bi_executive_signal_feed latest
                                where latest.client_id::text = %(client_id)s
                                  and (%(campaign_id)s::int is null or latest.campaign_id = %(campaign_id)s)
                                  and (%(brand)s::text is null or latest.brand = %(brand)s)
                                  and (%(chain)s::text is null or latest.chain = %(chain)s)
                                  and (%(signal_type)s::text is null or latest.signal_type = %(signal_type)s)
                                  and (%(severity)s::text is null or latest.severity = %(severity)s)
                                  and (%(signal_status)s::text is null or latest.signal_status = %(signal_status)s)
                              )
                            )
                            and (%(brand)s::text is null or brand = %(brand)s)
                            and (%(chain)s::text is null or chain = %(chain)s)
                            and (%(signal_type)s::text is null or signal_type = %(signal_type)s)
                            and (%(severity)s::text is null or severity = %(severity)s)
                            and (%(signal_status)s::text is null or signal_status = %(signal_status)s)
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
                              from public.mw_bi_radar_event_feed e
                              where e.client_id::text = %(client_id)s
                                and e.date_key < to_char((now() at time zone 'America/Costa_Rica')::date, 'YYYYMMDD')::int
                                and (%(campaign_id)s::int is null or e.campaign_id = %(campaign_id)s)
                            )
                          ) as selected_date_key
                        ),
                        enriched as (
                          select
                            e.event_id,
                            e.event_area,
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
                            e.previous_date_key,
                            e.campaign_id,
                            coalesce(e.campaign, '') as campaign,
                            e.chain,
                            e.brand,
                            e.product,
                            e.gtin,
                            e.product_key,
                            e.captured_at_cr,
                            e.previous_captured_at_cr,
                            e.previous_value,
                            e.current_value,
                            e.change_amount,
                            e.change_pct,
                            e.promo_share_pct,
                            e.discount_pct,
                            e.observed_locations,
                            e.visible_locations,
                            e.available_locations,
                            e.product_url
                          from public.mw_bi_radar_event_feed e
                          cross join selected_date sd
                          join public.mkt_dim_market_event_type et
                            on et.event_type = e.event_type
                           and et.is_active
                          where e.client_id::text = %(client_id)s
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
                            and (%(brands)s::text[] = '{}'::text[] or e.brand = any(%(brands)s::text[]))
                            and (%(chains)s::text[] = '{}'::text[] or e.chain = any(%(chains)s::text[]))
                            and (%(product_keys)s::text[] = '{}'::text[] or e.product_key = any(%(product_keys)s::text[]))
                            and (%(event_areas)s::text[] = '{}'::text[] or e.event_area = any(%(event_areas)s::text[]))
                            and (%(severities)s::text[] = '{}'::text[] or e.severity = any(%(severities)s::text[]))
                            and (
                              %(query)s::text is null
                              or e.product ilike %(query)s
                              or e.brand ilike %(query)s
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
                    rows = [self._json_ready(row) for row in cursor.fetchall()]

                    cursor.execute(
                        """
                        select
                          coalesce(
                            %(date_key)s::int,
                            %(date_key_to)s::int,
                            max(e.date_key)
                          ) as selected_date_key,
                          max(e.previous_date_key) filter (where e.date_key = coalesce(%(date_key)s::int, %(date_key_to)s::int, e.date_key)) as prior_closed_date_key,
                          to_char((now() at time zone 'America/Costa_Rica')::date, 'YYYYMMDD')::int as current_cr_date_key
                        from public.mw_bi_radar_event_feed e
                        where e.client_id::text = %(client_id)s
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

        try:
            with self._connection_factory() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        with selected_scope as (
                          select coalesce(
                            %(date_key)s::int,
                            (
                              select max(o.date_key)
                              from public.mw_core_sku_store_observation o
                              join public.mkt_campaign_client_access cca
                                on cca.campaign_id = o.campaign_id
                               and cca.is_active
                               and (cca.valid_from is null or o.business_date >= cca.valid_from)
                               and (cca.valid_to is null or o.business_date <= cca.valid_to)
                              where cca.client_id::text = %(client_id)s
                                and (o.client_id is null or o.client_id = cca.client_id)
                                and o.product_key::text = %(product_key)s
                                and (%(campaign_id)s::int is null or o.campaign_id = %(campaign_id)s)
                                and (%(chain)s::text is null or o.chain_label = %(chain)s)
                                and o.date_key < to_char((now() at time zone 'America/Costa_Rica')::date, 'YYYYMMDD')::int
                            )
                          ) as selected_date_key
                        ),
                        scoped as (
                          select
                            o.*,
                            cca.client_id as authorized_client_id
                          from public.mw_core_sku_store_observation o
                          join public.mkt_campaign_client_access cca
                            on cca.campaign_id = o.campaign_id
                           and cca.is_active
                           and (cca.valid_from is null or o.business_date >= cca.valid_from)
                           and (cca.valid_to is null or o.business_date <= cca.valid_to)
                          cross join selected_scope selected
                          where cca.client_id::text = %(client_id)s
                            and (o.client_id is null or o.client_id = cca.client_id)
                            and o.product_key::text = %(product_key)s
                            and o.date_key = selected.selected_date_key
                            and (%(campaign_id)s::int is null or o.campaign_id = %(campaign_id)s)
                            and (%(chain)s::text is null or o.chain_label = %(chain)s)
                        )
                        select
                          product_key::text as product_key,
                          max(gtin_norm) as gtin,
                          max(brand_name) as brand,
                          max(product_name) as product,
                          max(content_quantity) as content_quantity,
                          max(content_unit) as content_unit,
                          max(campaign_id) as campaign_id,
                          max(campaign_name) as campaign,
                          max(chain_label) as chain,
                          max(date_key) as date_key,
                          max(captured_at_cr) as latest_capture,
                          min(coalesce(spot_price_amount, effective_price_amount)) filter (where is_available) as min_price,
                          max(coalesce(spot_price_amount, effective_price_amount)) filter (where is_available) as max_price,
                          round(avg(coalesce(spot_price_amount, effective_price_amount)) filter (where is_available and coalesce(spot_price_amount, effective_price_amount) is not null), 2) as avg_price,
                          case
                            when (avg(reference_price_amount) filter (where is_available)) > 0
                              and (avg(spot_price_amount) filter (where is_available and spot_price_amount is not null)) is not null
                            then round((((avg(reference_price_amount) filter (where is_available)) - (avg(spot_price_amount) filter (where is_available and spot_price_amount is not null))) / (avg(reference_price_amount) filter (where is_available))) * 100, 2)
                          end as max_discount_pct,
                          bool_or(is_available and spot_price_amount is not null) as promo_seen,
                          max(image_url) filter (where image_url is not null) as image_url,
                          max(product_url) filter (where product_url is not null) as product_url
                        from scoped
                        group by product_key;
                        """,
                        params,
                    )
                    product = cursor.fetchone()
                    if not product:
                        return {"client_id": client_id, "product": None, "chain_snapshot": [], "daily_history": [], "history": [], "price_history": [], "events": []}
                    product_row = self._json_ready(product)

                    detail_params = {
                        **params,
                        "date_key": product_row.get("date_key"),
                    }
                    all_chain_params = {**detail_params, "chain": None}

                    cursor.execute(
                        """
                        select
                          o.chain_label as chain,
                          max(o.captured_at_cr) as captured_at_cr,
                          round(avg(coalesce(o.spot_price_amount, o.effective_price_amount)) filter (where o.is_available), 2) as average_price,
                          null::numeric as average_unit_price,
                          min(coalesce(o.spot_price_amount, o.effective_price_amount)) filter (where o.is_available) as min_price,
                          max(coalesce(o.spot_price_amount, o.effective_price_amount)) filter (where o.is_available) as max_price,
                          bool_or(o.is_available and o.spot_price_amount is not null) as promo_detected,
                          round((count(distinct o.location_key) filter (where o.is_available and o.spot_price_amount is not null)::numeric / nullif(count(distinct o.location_key), 0)) * 100, 2) as promo_share_pct,
                          case
                            when (avg(o.reference_price_amount) filter (where o.is_available)) > 0
                              and (avg(o.spot_price_amount) filter (where o.is_available and o.spot_price_amount is not null)) is not null
                            then round((((avg(o.reference_price_amount) filter (where o.is_available)) - (avg(o.spot_price_amount) filter (where o.is_available and o.spot_price_amount is not null))) / (avg(o.reference_price_amount) filter (where o.is_available))) * 100, 2)
                          end as max_discount_pct,
                          count(distinct o.location_key) filter (where o.is_listed) as visible_locations,
                          count(distinct o.location_key) filter (where o.is_available) as available_locations,
                          max(o.product_url) filter (where o.product_url is not null) as product_url,
                          max(o.image_url) filter (where o.image_url is not null) as image_url
                        from public.mw_core_sku_store_observation o
                        join public.mkt_campaign_client_access cca
                          on cca.campaign_id = o.campaign_id
                         and cca.is_active
                         and (cca.valid_from is null or o.business_date >= cca.valid_from)
                         and (cca.valid_to is null or o.business_date <= cca.valid_to)
                        where cca.client_id::text = %(client_id)s
                          and (o.client_id is null or o.client_id = cca.client_id)
                          and o.product_key::text = %(product_key)s
                          and o.date_key = %(date_key)s
                          and (%(campaign_id)s::int is null or o.campaign_id = %(campaign_id)s)
                          and (%(chain)s::text is null or o.chain_label = %(chain)s)
                        group by o.chain_label
                        order by average_price nulls last, chain;
                        """,
                        all_chain_params,
                    )
                    chain_snapshot = [self._json_ready(row) for row in cursor.fetchall()]

                    cursor.execute(
                        """
                        select
                          date_key,
                          business_date,
                          chain,
                          average_price,
                          null::numeric as average_unit_price,
                          gap_pct,
                          price_index,
                          price_reading,
                          suggested_action
                        from public.mw_bi_sku_price_drivers
                        where client_id::text = %(client_id)s
                          and product_key::text = %(product_key)s
                          and (%(campaign_id)s::int is null or campaign_id = %(campaign_id)s)
                          and (%(chain)s::text is null or chain = %(chain)s)
                          and date_key <= %(date_key)s
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
                        from public.mw_exp_intraday_sku_chain_capture
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
                            o.chain_label as chain,
                            max(o.captured_at_cr) as captured_at_cr,
                            round(avg(coalesce(o.spot_price_amount, o.effective_price_amount)) filter (
                              where o.is_available
                                and coalesce(o.spot_price_amount, o.effective_price_amount) is not null
                            ), 2) as effective_price_amount,
                            round(avg(o.reference_price_amount) filter (
                              where o.is_available
                                and o.reference_price_amount is not null
                            ), 2) as reference_price_amount,
                            round(avg(o.spot_price_amount) filter (
                              where o.is_available
                                and o.spot_price_amount is not null
                            ), 2) as promo_price_amount,
                            bool_or(o.is_available and o.spot_price_amount is not null) as promo_detected,
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
                              * 100, 2)
                            end as discount_pct
                          from public.mw_core_sku_store_observation as o
                          join public.mkt_campaign_client_access as cca
                            on cca.campaign_id = o.campaign_id
                           and cca.is_active
                           and (cca.valid_from is null or o.business_date >= cca.valid_from)
                           and (cca.valid_to is null or o.business_date <= cca.valid_to)
                          join public.auth_clients as ac
                            on ac.id = cca.client_id
                           and ac.status = 'active'
                          where cca.client_id::text = %(client_id)s
                            and (o.client_id is null or o.client_id = cca.client_id)
                            and o.product_key::text = %(product_key)s
                            and o.date_key <= %(date_key)s
                            and o.is_available
                            and (%(campaign_id)s::int is null or o.campaign_id = %(campaign_id)s)
                            and (%(chain)s::text is null or o.chain_label = %(chain)s)
                          group by
                            o.date_key,
                            o.business_date,
                            o.chain_label
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
                          from public.mw_core_sku_store_observation as o
                          join public.mkt_campaign_client_access as cca
                            on cca.campaign_id = o.campaign_id
                           and cca.is_active
                           and (cca.valid_from is null or o.business_date >= cca.valid_from)
                           and (cca.valid_to is null or o.business_date <= cca.valid_to)
                          where cca.client_id::text = %(client_id)s
                            and (o.client_id is null or o.client_id = cca.client_id)
                            and o.product_key::text = %(product_key)s
                            and o.date_key <= %(date_key)s
                            and o.is_available
                            and (%(campaign_id)s::int is null or o.campaign_id = %(campaign_id)s)
                          order by o.date_key desc
                          limit %(history_days)s
                        )
                        select
                            e.event_id,
                            e.event_type,
                            e.severity,
                            e.event_area,
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
                            e.previous_date_key,
                            e.campaign_id,
                            coalesce(e.campaign, '') as campaign,
                            e.chain,
                            e.brand,
                            e.product,
                            e.gtin,
                            e.product_key,
                            e.previous_value,
                            e.current_value,
                            e.change_amount,
                            e.change_pct,
                            e.promo_share_pct,
                            e.discount_pct,
                            e.product_url
                        from public.mw_bi_radar_event_feed e
                        join public.mkt_dim_market_event_type et
                            on et.event_type = e.event_type
                           and et.is_active
                        where e.client_id::text = %(client_id)s
                            and (%(campaign_id)s::int is null or e.campaign_id = %(campaign_id)s)
                            and (%(date_key)s::int is null or e.date_key <= %(date_key)s)
                            and e.product_key::text = %(product_key)s
                            and (
                              e.date_key in (select date_key from visible_dates)
                              or e.previous_date_key in (select date_key from visible_dates)
                            )
                        order by e.date_key desc
                        """,
                        all_chain_params,
                    )
                    events = [self._json_ready(row) for row in cursor.fetchall()]
                    for event in events:
                        event["event_id"] = event.get("event_id") or f"dod:{event.get('date_key')}:{event.get('product_key')}:{event.get('chain')}:{event.get('event_type')}"
                        event["captured_at_cr"] = event.get("business_date")
                        event["previous_captured_at_cr"] = None
                        event["observed_locations"] = None
                        event["visible_locations"] = None
                        event["available_locations"] = None

        except errors.UndefinedTable:
            return {"client_id": client_id, "product": None, "chain_snapshot": [], "daily_history": [], "history": [], "price_history": [], "events": []}

        return {
            "client_id": client_id,
            "product": product_row,
            "chain_snapshot": chain_snapshot,
            "daily_history": daily_history,
            "history": history,
            "price_history": price_history,
            "events": events,
        }

    @staticmethod
    def _json_ready(row: dict[str, Any]) -> dict[str, Any]:
        return {
            key: float(value) if isinstance(value, Decimal) else value.isoformat() if hasattr(value, "isoformat") else value
            for key, value in dict(row).items()
        }

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
