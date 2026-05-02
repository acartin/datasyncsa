#!/usr/bin/env python3
"""Entry point generico para ejecutar el scraper de la tienda solicitada.

El runner inspecciona el `engine` configurado en `STORE_DEFINITIONS` y delega
en el motor correspondiente (`vtex_abarrotes_scraper` o `instaleap_catalog_scraper`).
"""

from __future__ import annotations

import argparse
import sys

from store_catalog_config import get_store_definition, iter_store_definitions

import instaleap_catalog_scraper
import vtex_abarrotes_scraper


ENGINES = {
    "vtex": vtex_abarrotes_scraper,
    "instaleap": instaleap_catalog_scraper,
}


def _peek_store_id(argv: list[str]) -> str:
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument(
        "--store-id",
        choices=sorted(definition.store_id for definition in iter_store_definitions()),
        required=True,
    )
    args, _ = pre_parser.parse_known_args(argv)
    return args.store_id


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    store_id = _peek_store_id(argv)
    definition = get_store_definition(store_id)
    engine_module = ENGINES.get(definition.engine)
    if engine_module is None:
        raise SystemExit(f"Engine desconocido para {store_id!r}: {definition.engine!r}")

    parser = engine_module.build_arg_parser(
        description=(
            f"Ejecuta el scraper {definition.engine} para {definition.display_name} "
            "usando la definicion local de la tienda y sus categorias raiz habilitadas."
        ),
        default_output_dir=None,
    )
    parser.add_argument(
        "--store-id",
        choices=sorted(definition.store_id for definition in iter_store_definitions()),
        required=True,
        help="Identificador de la tienda.",
    )
    args = parser.parse_args(argv)
    catalog_path, metadata_path = engine_module.run_store_scraper(store_id, args)
    print(f"Catalogo guardado en: {catalog_path}")
    print(f"Metadata guardada en: {metadata_path}")


if __name__ == "__main__":
    main()
