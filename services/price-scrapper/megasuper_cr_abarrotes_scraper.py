#!/usr/bin/env python3
"""Wrapper del scraper Instaleap configurable para Megasuper Costa Rica."""

from __future__ import annotations

from instaleap_catalog_scraper import (
    build_arg_parser,
    default_output_dir_for_store,
    run_store_scraper,
)


STORE_ID = "megasuper_cr"
DEFAULT_OUTPUT_DIR = default_output_dir_for_store(STORE_ID)


def parse_args():
    return build_arg_parser(
        description="Extrae el catalogo de Abarrotes de Megasuper Costa Rica usando GraphQL Instaleap.",
        default_output_dir=DEFAULT_OUTPUT_DIR,
    ).parse_args()


def main() -> None:
    args = parse_args()
    catalog_path, metadata_path = run_store_scraper(STORE_ID, args)
    print(f"Catalogo guardado en: {catalog_path}")
    print(f"Metadata guardada en: {metadata_path}")


if __name__ == "__main__":
    main()
