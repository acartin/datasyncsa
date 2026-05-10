#!/usr/bin/env python3
"""Extrae el catalogo chain-level para la cadena solicitada."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


SERVICE_DIR = Path(__file__).resolve().parents[1]
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

from engines import instaleap_catalog_engine, vtex_catalog_engine
from etl.chain_runtime_db import list_active_chain_ids, load_catalog_runtime_payload
from etl.postgres_cli import parse_env


ENGINES = {
    "vtex": vtex_catalog_engine,
    "instaleap": instaleap_catalog_engine,
}


def build_dispatcher_parser(*, required: bool) -> argparse.ArgumentParser:
    env = parse_env()
    parser = argparse.ArgumentParser(
        add_help=False,
        description=(
            "Despacha la extraccion del catalogo de una cadena hacia el engine configurado. "
            "Usa `--chain-id <id> --help` para ver flags especificos del engine."
        ),
    )
    parser.add_argument(
        "--chain-id",
        choices=list_active_chain_ids(env),
        required=required,
        help="Identificador de la cadena.",
    )
    return parser


def peek_chain_id(argv: list[str]) -> str:
    args, _ = build_dispatcher_parser(required=True).parse_known_args(argv)
    return args.chain_id


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    env = parse_env()

    if any(argument in {"-h", "--help"} for argument in argv) and "--chain-id" not in argv:
        help_parser = argparse.ArgumentParser(parents=[build_dispatcher_parser(required=False)])
        help_parser.print_help()
        return

    chain_id = peek_chain_id(argv)
    payload = load_catalog_runtime_payload(env, chain_id)
    engine = str(payload.get("engine") or "").strip()
    display_name = str(payload.get("display_name") or chain_id).strip()
    engine_module = ENGINES.get(engine)
    if engine_module is None:
        raise SystemExit(f"Engine desconocido para {chain_id!r}: {engine!r}")

    parser = engine_module.build_arg_parser(
        description=(
            f"Extrae el catalogo {engine} para {display_name} "
            "usando la definicion local de la cadena y sus categorias raiz habilitadas."
        ),
        default_output_dir=None,
    )
    parser.add_argument(
        "--chain-id",
        choices=list_active_chain_ids(env),
        required=True,
        help="Identificador de la cadena.",
    )
    args = parser.parse_args(argv)
    scraper = engine_module.build_chain_scraper_from_payload(payload, args)
    catalog_path, metadata_path = scraper.run()
    print(f"Catalogo guardado en: {catalog_path}")
    print(f"Metadata guardada en: {metadata_path}")


if __name__ == "__main__":
    main()
