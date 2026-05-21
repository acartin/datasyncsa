from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

import psycopg


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

    @staticmethod
    def _json_ready(row: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value.isoformat() if hasattr(value, "isoformat") else value
            for key, value in dict(row).items()
        }
