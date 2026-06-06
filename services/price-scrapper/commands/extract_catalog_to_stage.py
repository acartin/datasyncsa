#!/usr/bin/env python3
"""Extrae un catalogo con el engine configurado y lo carga en tablas stage del ETL."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SERVICE_DIR = Path(__file__).resolve().parents[1]
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

from engines import instaleap_catalog_engine, vtex_catalog_engine
from etl.business_date import parse_business_date_key
from etl.chain_runtime_db import list_active_chain_ids, load_catalog_runtime_payload
from etl.catalog_stage_loader import (
    load_failed_catalog_stage_run,
    load_successful_catalog_stage_run,
)
from etl.postgres_cli import parse_env
from etl.run_runtime_db import find_existing_succeeded_run_key


ENGINES = {
    "vtex": vtex_catalog_engine,
    "instaleap": instaleap_catalog_engine,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_dispatcher_parser(*, required: bool) -> argparse.ArgumentParser:
    env = parse_env()
    parser = argparse.ArgumentParser(
        add_help=False,
        description=(
            "Despacha una extraccion ETL de catalogo hacia el engine configurado y "
            "carga el resultado en mkt_run/mkt_stage_catalog_item."
        ),
    )
    parser.add_argument(
        "--chain-id",
        choices=list_active_chain_ids(env),
        required=required,
        help="Identificador de la cadena.",
    )
    parser.add_argument(
        "--run-kind",
        choices=["comparative", "analytic"],
        default="comparative",
        help="Tipo de corrida ETL a registrar en mkt_run.",
    )
    parser.add_argument(
        "--business-date",
        default=None,
        help="Fecha de negocio en formato YYYY-MM-DD. Por defecto usa hoy en Costa Rica.",
    )
    return parser


def peek_chain_id(argv: list[str]) -> str:
    args, _ = build_dispatcher_parser(required=True).parse_known_args(argv)
    return args.chain_id


def build_parser_for_chain(chain_id: str, payload: dict[str, Any], env: dict[str, str]) -> argparse.ArgumentParser:
    engine = str(payload.get("engine") or "").strip()
    display_name = str(payload.get("display_name") or chain_id).strip()
    engine_module = ENGINES.get(engine)
    if engine_module is None:
        raise SystemExit(f"Engine desconocido para {chain_id!r}: {engine!r}")

    parser = engine_module.build_arg_parser(
        description=(
            f"Extrae el catalogo de {display_name} usando el engine {engine}, "
            "carga el resultado en tablas stage y opcionalmente escribe JSON de debug."
        ),
        default_output_dir=None,
    )
    parser.add_argument(
        "--chain-id",
        choices=list_active_chain_ids(env),
        required=True,
        help="Identificador de la cadena.",
    )
    parser.add_argument(
        "--write-debug-files",
        action="store_true",
        help="Si se usa, tambien escribe catalog.json y metadata.json en output/chains/<chain_id>/.",
    )
    parser.add_argument(
        "--run-kind",
        choices=["comparative", "analytic"],
        default="comparative",
        help="Tipo de corrida ETL a registrar en mkt_run.",
    )
    parser.add_argument(
        "--business-date",
        default=None,
        help="Fecha de negocio en formato YYYY-MM-DD. Por defecto usa hoy en Costa Rica.",
    )
    return parser


def record_failed_run(
    *,
    chain_id: str,
    engine: str,
    pricing_scope: str,
    started_at: str,
    debug_output_dir: Path | None,
    run_kind: str,
    business_date_key: int,
    exc: Exception,
    extra_metadata: dict[str, Any] | None = None,
) -> int | None:
    raw_metadata = {
        "chain_id": chain_id,
        "engine": engine,
        "pricing_scope": pricing_scope,
        "failed_at": utc_now_iso(),
        "exception_type": type(exc).__name__,
        "exception_message": str(exc),
    }
    if extra_metadata:
        raw_metadata.update(extra_metadata)

    try:
        return load_failed_catalog_stage_run(
            chain_id=chain_id,
            engine=engine,
            pricing_scope=pricing_scope,
            started_at=started_at,
            error_message=str(exc),
            run_kind=run_kind,
            business_date_key=business_date_key,
            raw_metadata=raw_metadata,
            debug_output_dir=debug_output_dir,
        )
    except Exception as stage_exc:  # pragma: no cover - best effort logging path
        print(
            f"[{chain_id}] no se pudo registrar la corrida fallida en mkt_run: {stage_exc}",
            file=sys.stderr,
            flush=True,
        )
        return None


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)

    if any(argument in {"-h", "--help"} for argument in argv) and "--chain-id" not in argv:
        help_parser = argparse.ArgumentParser(parents=[build_dispatcher_parser(required=False)])
        help_parser.print_help()
        return

    env = parse_env()
    chain_id = peek_chain_id(argv)
    payload = load_catalog_runtime_payload(env, chain_id)
    engine = str(payload.get("engine") or "").strip()
    pricing_scope = str(payload.get("pricing_scope") or "chain_public_online").strip()
    engine_module = ENGINES.get(engine)
    if engine_module is None:
        raise SystemExit(f"Engine desconocido para {chain_id!r}: {engine!r}")

    parser = build_parser_for_chain(chain_id, payload, env)
    args = parser.parse_args(argv)
    business_date_key = parse_business_date_key(args.business_date)
    existing_run_key = find_existing_succeeded_run_key(
        env,
        business_date_key=business_date_key,
        run_kind=args.run_kind,
        chain_id=chain_id,
    )
    if existing_run_key is not None:
        print(
            f"[{chain_id}] corrida ya registrada para business_date_key={business_date_key} "
            f"| run_kind={args.run_kind} | run_key={existing_run_key}; se omite.",
            flush=True,
        )
        return
    scraper = engine_module.build_chain_scraper_from_payload(payload, args)
    debug_output_dir = scraper.output_dir if args.write_debug_files else None

    try:
        records, metadata = scraper.collect_catalog()
    except Exception as exc:
        run_key = record_failed_run(
            chain_id=chain_id,
            engine=engine,
            pricing_scope=pricing_scope,
            started_at=scraper.started_at,
            debug_output_dir=debug_output_dir,
            run_kind=args.run_kind,
            business_date_key=business_date_key,
            exc=exc,
            extra_metadata={"write_debug_files": args.write_debug_files},
        )
        if run_key is not None:
            print(
                f"[{chain_id}] corrida fallida registrada en run_key={run_key}",
                flush=True,
            )
        raise

    catalog_path = None
    metadata_path = None
    if args.write_debug_files:
        catalog_path, metadata_path = scraper.write_outputs(records, metadata)

    try:
        run_key, inserted_items = load_successful_catalog_stage_run(
            chain_id=chain_id,
            metadata=metadata,
            records=records,
            run_kind=args.run_kind,
            business_date_key=business_date_key,
            debug_output_dir=debug_output_dir,
        )
    except Exception as exc:
        record_failed_run(
            chain_id=chain_id,
            engine=engine,
            pricing_scope=pricing_scope,
            started_at=scraper.started_at,
            debug_output_dir=debug_output_dir,
            run_kind=args.run_kind,
            business_date_key=business_date_key,
            exc=exc,
            extra_metadata={
                "write_debug_files": args.write_debug_files,
                "catalog_records": len(records),
            },
        )
        raise

    print(
        f"[{chain_id}] stage load completado | run_key={run_key} | "
        f"items={inserted_items}",
        flush=True,
    )
    if catalog_path and metadata_path:
        print(f"Catalogo debug guardado en: {catalog_path}", flush=True)
        print(f"Metadata debug guardada en: {metadata_path}", flush=True)


if __name__ == "__main__":
    main()
