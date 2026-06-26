#!/usr/bin/env python3
"""Extrae locations por cadena y hace upsert idempotente en mkt_dim_location."""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


SERVICE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_DIR.parents[1]
ENV_PATH = REPO_ROOT / ".env"

if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

from engines import instaleap_location_engine, vtex_location_engine


ENGINES = {
    "vtex": vtex_location_engine,
    "instaleap": instaleap_location_engine,
}


def flatten_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.replace("\r", " ").replace("\n", " ")
    text = " ".join(text.split()).strip()
    return text or None


def parse_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def run_psql(
    env: dict[str, str],
    *,
    sql: str,
    tuples_only: bool = False,
) -> str:
    command = [
        "docker",
        "compose",
        "--env-file",
        str(ENV_PATH),
        "exec",
        "-T",
        "postgres",
        "psql",
        "-U",
        env["DB_USER"],
        "-d",
        env["DB_NAME"],
        "-v",
        "ON_ERROR_STOP=1",
    ]
    if tuples_only:
        command.extend(["-At", "-F", "\t"])

    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        input=sql,
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def fetch_chain_rows(env: dict[str, str], chain_id: str | None) -> list[tuple[str, str]]:
    sql = """
select chain_id, engine
from public.mkt_dim_chain
where is_active = true
"""
    if chain_id:
        sql += f"  and chain_id = '{chain_id}'\n"
    sql += "order by chain_id;"
    output = run_psql(env, sql=sql, tuples_only=True)
    rows: list[tuple[str, str]] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        current_chain_id, engine = line.split("\t", 1)
        rows.append((current_chain_id.strip(), engine.strip()))
    return rows


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Extrae locations por cadena usando el engine configurado y hace upsert idempotente "
            "en public.mkt_dim_location."
        )
    )
    parser.add_argument(
        "--chain-id",
        default=None,
        help="Cadena a procesar. Si se omite, recorre todas las cadenas activas en mkt_dim_chain.",
    )
    parser.add_argument(
        "--sleep-min",
        type=float,
        default=0.0,
        help="Parametro legacy ignorado; el pacing HTTP vive en etl/http_client.py.",
    )
    parser.add_argument(
        "--sleep-max",
        type=float,
        default=0.0,
        help="Parametro legacy ignorado; el pacing HTTP vive en etl/http_client.py.",
    )
    parser.add_argument(
        "--postal-code-limit",
        type=int,
        default=None,
        help="Limite de codigos postales a recorrer en VTEX. Util para smoke tests.",
    )
    parser.add_argument(
        "--deactivate-missing",
        action="store_true",
        help="Marca inactivas las locations de la cadena que no aparezcan en esta corrida.",
    )
    return parser


def discover_chain_locations(
    *,
    chain_id: str,
    engine: str,
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    if engine == "vtex":
        return vtex_location_engine.discover_locations(
            chain_id,
            sleep_min=args.sleep_min,
            sleep_max=args.sleep_max,
            postal_code_limit=args.postal_code_limit,
        )
    if engine == "instaleap":
        return instaleap_location_engine.discover_locations(chain_id)
    raise RuntimeError(f"Engine no soportado para locations: {engine!r}")


def upsert_locations(
    env: dict[str, str],
    *,
    chain_id: str,
    rows: list[dict[str, Any]],
    deactivate_missing: bool,
) -> None:
    csv_buffer = io.StringIO()
    writer = csv.DictWriter(
        csv_buffer,
        fieldnames=[
            "chain_id",
            "location_code",
            "source_engine",
            "source_location_ref",
            "source_internal_id",
            "location_name",
            "location_type",
            "sales_channel",
            "region_id",
            "address_text",
            "province",
            "canton",
            "district",
            "postal_code",
            "latitude",
            "longitude",
            "phone",
            "is_default",
            "source_origin",
            "source_payload",
        ],
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "chain_id": chain_id,
                "location_code": flatten_text(str(row["location_code"])),
                "source_engine": row["source_engine"],
                "source_location_ref": flatten_text(row.get("source_location_ref")),
                "source_internal_id": flatten_text(row.get("source_internal_id")),
                "location_name": flatten_text(row["location_name"]),
                "location_type": row["location_type"],
                "sales_channel": flatten_text(row.get("sales_channel")),
                "region_id": flatten_text(row.get("region_id")),
                "address_text": flatten_text(row.get("address_text")),
                "province": flatten_text(row.get("province")),
                "canton": flatten_text(row.get("canton")),
                "district": flatten_text(row.get("district")),
                "postal_code": flatten_text(row.get("postal_code")),
                "latitude": row.get("latitude"),
                "longitude": row.get("longitude"),
                "phone": flatten_text(row.get("phone")),
                "is_default": bool(row.get("is_default")),
                "source_origin": row["source_origin"],
                "source_payload": json.dumps(row.get("source_payload") or {}, ensure_ascii=False),
            }
        )

    deactivate_sql = ""
    if deactivate_missing:
        deactivate_sql = """
update public.mkt_dim_location as l
set
  is_active = false,
  updated_at = now()
where l.chain_key = (
  select chain_key from public.mkt_dim_chain where chain_id = '%s'
)
and not exists (
  select 1
  from tmp_mkt_dim_location_load as t
  where t.location_code = l.location_code
);
""" % chain_id

    sql = f"""
begin;
create temp table tmp_mkt_dim_location_load (
  chain_id text,
  location_code text,
  source_engine text,
  source_location_ref text,
  source_internal_id text,
  location_name text,
  location_type text,
  sales_channel text,
  region_id text,
  address_text text,
  province text,
  canton text,
  district text,
  postal_code text,
  latitude numeric(9,6),
  longitude numeric(9,6),
  phone text,
  is_default boolean,
  source_origin text,
  source_payload jsonb
);
copy tmp_mkt_dim_location_load (
  chain_id,
  location_code,
  source_engine,
  source_location_ref,
  source_internal_id,
  location_name,
  location_type,
  sales_channel,
  region_id,
  address_text,
  province,
  canton,
  district,
  postal_code,
  latitude,
  longitude,
  phone,
  is_default,
  source_origin,
  source_payload
) from stdin with (format csv, header true);
{csv_buffer.getvalue()}\\.
insert into public.mkt_dim_location (
  chain_key,
  location_code,
  source_engine,
  source_location_ref,
  source_internal_id,
  location_name,
  location_type,
  sales_channel,
  region_id,
  address_text,
  province,
  canton,
  district,
  postal_code,
  latitude,
  longitude,
  phone,
  is_default,
  is_active,
  source_origin,
  source_payload,
  last_seen_at
)
select
  c.chain_key,
  t.location_code,
  t.source_engine,
  t.source_location_ref,
  t.source_internal_id,
  t.location_name,
  t.location_type,
  t.sales_channel,
  t.region_id,
  t.address_text,
  t.province,
  t.canton,
  t.district,
  t.postal_code,
  t.latitude,
  t.longitude,
  t.phone,
  t.is_default,
  true,
  t.source_origin,
  t.source_payload,
  now()
from tmp_mkt_dim_location_load as t
join public.mkt_dim_chain as c
  on c.chain_id = t.chain_id
on conflict (chain_key, location_code) do update
set
  source_engine = excluded.source_engine,
  source_location_ref = coalesce(excluded.source_location_ref, public.mkt_dim_location.source_location_ref),
  source_internal_id = coalesce(excluded.source_internal_id, public.mkt_dim_location.source_internal_id),
  location_name = excluded.location_name,
  location_type = excluded.location_type,
  sales_channel = coalesce(excluded.sales_channel, public.mkt_dim_location.sales_channel),
  region_id = coalesce(excluded.region_id, public.mkt_dim_location.region_id),
  address_text = coalesce(excluded.address_text, public.mkt_dim_location.address_text),
  province = coalesce(excluded.province, public.mkt_dim_location.province),
  canton = coalesce(excluded.canton, public.mkt_dim_location.canton),
  district = coalesce(excluded.district, public.mkt_dim_location.district),
  postal_code = coalesce(excluded.postal_code, public.mkt_dim_location.postal_code),
  latitude = coalesce(excluded.latitude, public.mkt_dim_location.latitude),
  longitude = coalesce(excluded.longitude, public.mkt_dim_location.longitude),
  phone = coalesce(excluded.phone, public.mkt_dim_location.phone),
  is_default = public.mkt_dim_location.is_default or excluded.is_default,
  is_active = true,
  source_origin = excluded.source_origin,
  source_payload = case
    when public.mkt_dim_location.source_payload = '{{}}'::jsonb then excluded.source_payload
    when excluded.source_payload = '{{}}'::jsonb then public.mkt_dim_location.source_payload
    else public.mkt_dim_location.source_payload || excluded.source_payload
  end,
  last_seen_at = now(),
  updated_at = now();
{deactivate_sql}
commit;
"""
    run_psql(env, sql=sql, tuples_only=False)


def fetch_chain_location_count(env: dict[str, str], chain_id: str) -> int:
    sql = f"""
select count(*)
from public.mkt_dim_location as l
join public.mkt_dim_chain as c
  on c.chain_key = l.chain_key
where c.chain_id = '{chain_id}';
"""
    output = run_psql(env, sql=sql, tuples_only=True)
    return int(output.strip() or "0")


def main() -> None:
    args = build_arg_parser().parse_args()
    env = parse_env(ENV_PATH)
    chain_rows = fetch_chain_rows(env, args.chain_id)

    if not chain_rows:
        raise SystemExit(
            f"No se encontraron cadenas activas en mkt_dim_chain para chain_id={args.chain_id!r}."
        )

    for chain_id, engine in chain_rows:
        print(f"Procesando chain_id={chain_id} engine={engine}", flush=True)
        rows = discover_chain_locations(chain_id=chain_id, engine=engine, args=args)
        if not rows:
            print(f"[{chain_id}] no se descubrieron locations.", flush=True)
            continue
        upsert_locations(
            env,
            chain_id=chain_id,
            rows=rows,
            deactivate_missing=args.deactivate_missing,
        )
        total = fetch_chain_location_count(env, chain_id)
        print(
            f"[{chain_id}] upsert completado | rows_descubiertas={len(rows)} | total_en_bd={total}",
            flush=True,
        )


if __name__ == "__main__":
    main()
