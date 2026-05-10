#!/usr/bin/env python3
"""Actualiza en BD las categorias raiz VTEX por cadena."""

from __future__ import annotations

import argparse
import sys
from typing import Any
from urllib.parse import urlparse

from pathlib import Path


SERVICE_DIR = Path(__file__).resolve().parents[1]
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

from etl.chain_runtime_db import (
    list_active_chain_ids_by_engine,
    load_chain_row,
    replace_vtex_root_categories,
)
from etl.http_client import create_browser_session, request_with_retry
from etl.postgres_cli import parse_env


REQUEST_TIMEOUT = 30


def normalize_category_url(base_url: str, raw_url: str | None, slug: str) -> str:
    if raw_url:
        parsed = urlparse(raw_url)
        path = parsed.path.strip("/")
        if path:
            return f"{base_url}/{path}"
    return f"{base_url}/{slug}"


def fetch_root_categories(base_url: str) -> list[dict[str, Any]]:
    session = create_browser_session(
        headers={
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "es-CR,es;q=0.9,en;q=0.8",
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
            ),
        }
    )
    response = request_with_retry(
        session,
        "GET",
        f"{base_url}/api/catalog_system/pub/category/tree/1",
        timeout=REQUEST_TIMEOUT,
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


def update_chain_root_categories(env: dict[str, str], chain_id: str) -> int | None:
    existing_payload = load_chain_row(env, chain_id)
    engine = str(existing_payload.get("engine") or "").strip()
    if engine != "vtex":
        print(f"Saltando {chain_id!r}: engine={engine!r} no usa el catalogo publico VTEX.")
        return None

    base_url = str(existing_payload.get("base_url") or "").strip()
    if not base_url:
        raise ValueError(f"La cadena {chain_id!r} no define base_url en BD.")

    categories = fetch_root_categories(base_url)
    return replace_vtex_root_categories(env, chain_id=chain_id, categories=categories)


def build_arg_parser() -> argparse.ArgumentParser:
    env = parse_env()
    parser = argparse.ArgumentParser(
        description="Actualiza en BD la lista de categorias raiz VTEX por cadena y preserva la bandera is_enabled."
    )
    parser.add_argument(
        "--chain-id",
        choices=list_active_chain_ids_by_engine(env, "vtex"),
        default=None,
        help="Cadena a actualizar. Si se omite, procesa todas.",
    )
    return parser


def main() -> None:
    env = parse_env()
    args = build_arg_parser().parse_args()
    chain_ids = [args.chain_id] if args.chain_id else list_active_chain_ids_by_engine(env, "vtex")

    for chain_id in chain_ids:
        total = update_chain_root_categories(env, chain_id)
        if total is not None:
            print(f"Categorias raiz actualizadas en BD para {chain_id}: total={total}")


if __name__ == "__main__":
    main()
