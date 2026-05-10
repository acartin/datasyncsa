#!/usr/bin/env python3
"""Helpers de consulta operativa sobre mkt_run."""

from __future__ import annotations

from etl.postgres_cli import run_psql


def _sql_text(value: str | None) -> str:
    if value is None:
        return "null"
    return "'" + str(value).replace("'", "''") + "'"


def _sql_int(value: int | None) -> str:
    if value is None:
        return "null"
    return str(int(value))


def find_existing_succeeded_run_key(
    env: dict[str, str],
    *,
    business_date_key: int,
    run_kind: str,
    chain_id: str,
    location_key: int | None = None,
    campaign_id: int | None = None,
) -> int | None:
    output = run_psql(
        env,
        sql=f"""
copy (
  select r.run_key
  from public.mkt_run r
  join public.mkt_dim_chain c
    on c.chain_key = r.chain_key
  where r.business_date_key = {int(business_date_key)}
    and r.run_kind = {_sql_text(run_kind)}
    and r.run_status = 'succeeded'
    and c.chain_id = {_sql_text(chain_id)}
    and coalesce(r.location_key, -1) = coalesce({_sql_int(location_key)}, -1)
    and coalesce(r.campaign_id, -1) = coalesce({_sql_int(campaign_id)}, -1)
  order by r.run_key desc
  limit 1
) to stdout;
""",
        tuples_only=True,
    )
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return None
    return int(lines[-1])
