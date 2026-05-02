#!/usr/bin/env python3
"""Actualiza las categorias raiz configurables por tienda VTEX."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from store_catalog_config import (
    get_store_definition,
    iter_store_definitions,
    load_store_config,
    save_store_config,
    seed_store_config_payload,
)


REQUEST_TIMEOUT = 30


def normalize_category_url(base_url: str, raw_url: str | None, slug: str) -> str:
    if raw_url:
        parsed = urlparse(raw_url)
        path = parsed.path.strip("/")
        if path:
            return f"{base_url}/{path}"
    return f"{base_url}/{slug}"


def fetch_root_categories(base_url: str) -> list[dict[str, Any]]:
    response = requests.get(
        f"{base_url}/api/catalog_system/pub/category/tree/1",
        timeout=REQUEST_TIMEOUT,
        headers={
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "es-CR,es;q=0.9,en;q=0.8",
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
            ),
        },
    )
    response.raise_for_status()
    tree = response.json()
    categories: list[dict[str, Any]] = []

    for node in tree:
        raw_url = node.get("url")
        parsed = urlparse(raw_url or "")
        slug = parsed.path.strip("/").split("/")[0] if parsed.path.strip("/") else ""
        if not slug:
            continue

        categories.append(
            {
                "name": node.get("name") or slug,
                "slug": slug,
                "url": normalize_category_url(base_url, raw_url, slug),
            }
        )

    categories.sort(key=lambda item: str(item["name"]).casefold())
    return categories


def refresh_store(store_id: str) -> Path | None:
    definition = get_store_definition(store_id)
    if definition.engine != "vtex":
        print(
            f"Saltando {store_id!r}: engine={definition.engine!r} no usa el catalogo publico VTEX."
        )
        return None

    existing_payload: dict[str, Any] | None
    try:
        existing_payload = load_store_config(store_id)
    except FileNotFoundError:
        existing_payload = None

    categories = fetch_root_categories(definition.base_url)
    payload = seed_store_config_payload(
        definition,
        categories=categories,
        existing_payload=existing_payload,
    )
    return save_store_config(store_id, payload)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Refresca la lista de categorias raiz por tienda y preserva la bandera enabled cuando existe."
    )
    parser.add_argument(
        "--store-id",
        choices=sorted(definition.store_id for definition in iter_store_definitions()),
        default=None,
        help="Tienda a refrescar. Si se omite, procesa todas.",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    store_ids = [args.store_id] if args.store_id else [definition.store_id for definition in iter_store_definitions()]

    for store_id in store_ids:
        path = refresh_store(store_id)
        if path is not None:
            print(f"Config de categorias actualizada: {path}")


if __name__ == "__main__":
    main()
