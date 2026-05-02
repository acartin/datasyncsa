#!/usr/bin/env python3
"""Wrapper del scraper VTEX configurable para Maxi Palí Costa Rica."""

from __future__ import annotations

from vtex_abarrotes_scraper import build_arg_parser, default_output_dir_for_store, run_store_scraper


STORE_ID = "maxi_pali_cr"
DEFAULT_OUTPUT_DIR = default_output_dir_for_store(STORE_ID)


def parse_args():
    return build_arg_parser(
        description="Extrae el catalogo de Abarrotes de Maxi Palí Costa Rica usando GraphQL paginado.",
        default_output_dir=DEFAULT_OUTPUT_DIR,
    ).parse_args()


def main() -> None:
    args = parse_args()
    catalog_path, metadata_path = run_store_scraper(STORE_ID, args)
    print(f"Catalogo guardado en: {catalog_path}")
    print(f"Metadata guardada en: {metadata_path}")


if __name__ == "__main__":
    main()
