#!/usr/bin/env python3
"""Orquestador concurrente de scraping de catalogos.

Lanza un worker por cadena en paralelo, con rate limiter por dominio
(5 req/s default) y proxy BrightData auto-detectedo desde .env.

Uso:
    python3 commands/scrape_all_catalogs.py [--max-chains N] [--rate 5.0]
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SERVICE_DIR = Path(__file__).resolve().parents[1]
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

from etl.chain_runtime_db import list_active_chain_ids, load_catalog_runtime_payload
from etl.http_client import set_rate_limiter
from etl.postgres_cli import parse_env
from engines import algolia_catalog_engine, instaleap_catalog_engine, vtex_catalog_engine


ENGINES = {
    "vtex": vtex_catalog_engine,
    "instaleap": instaleap_catalog_engine,
    "algolia": algolia_catalog_engine,
}


def _extract_domain(payload: dict[str, Any]) -> str:
    engine = str(payload.get("engine", "")).strip()
    if engine == "instaleap":
        extras = payload.get("engine_extras") or {}
        endpoint = str(extras.get("graphql_endpoint", "")) or "https://nextgentheadless.instaleap.io/api/v3"
        from urllib.parse import urlparse
        return urlparse(endpoint).netloc
    if engine == "algolia":
        return "algolia.net"
    base_url = str(payload.get("base_url", ""))
    if base_url:
        from urllib.parse import urlparse
        return urlparse(base_url).netloc
    return "unknown"


def scrape_chain(
    chain_id: str,
    rate: float,
    args: argparse.Namespace,
) -> tuple[str, bool, str]:
    try:
        env = parse_env()
        payload = load_catalog_runtime_payload(env, chain_id)
        engine_name = str(payload.get("engine", "")).strip()
        engine_module = ENGINES.get(engine_name)

        if not engine_module:
            return chain_id, False, f"engine desconocido: {engine_name}"

        engine_args = engine_module.build_arg_parser(
            description=f"Catalogo para {chain_id}",
        ).parse_args([
            str(a) for a in [
                f"--sleep-min={args.sleep_min}",
                f"--sleep-max={args.sleep_max}",
                *([f"--max-categories={args.max_categories}"] if args.max_categories else []),
                *([f"--max-pages-per-category={args.max_pages_per_category}"] if args.max_pages_per_category else []),
            ]
        ])

        scraper = engine_module.build_chain_scraper(chain_id, engine_args)
        t0 = time.monotonic()
        scraper.run()
        elapsed = time.monotonic() - t0

        return chain_id, True, f"OK en {elapsed:.1f}s"
    except Exception as e:
        return chain_id, False, str(e)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrapeo concurrente de todos los catalogos activos.")
    parser.add_argument("--max-chains", type=int, default=None, help="Limita cuantas cadenas procesar.")
    parser.add_argument("--rate", type=float, default=5.0, help="Requests por segundo por dominio.")
    parser.add_argument("--sleep-min", type=float, default=0.0, help="Parametro legacy ignorado; el pacing HTTP vive en etl/http_client.py.")
    parser.add_argument("--sleep-max", type=float, default=0.0, help="Parametro legacy ignorado; el pacing HTTP vive en etl/http_client.py.")
    parser.add_argument("--max-categories", type=int, default=None, help="Limita categorias por cadena (smoke).")
    parser.add_argument("--max-pages-per-category", type=int, default=None, help="Limita paginas por categoria (smoke).")
    parser.add_argument("--dry-run", action="store_true", help="Solo muestra el plan sin scrapear.")
    args = parser.parse_args()

    env = parse_env()
    chain_ids = list_active_chain_ids(env)
    if args.max_chains:
        chain_ids = chain_ids[:args.max_chains]

    if not chain_ids:
        print("No hay cadenas activas configuradas.")
        return

    print(f"Cadenas activas: {len(chain_ids)}")
    print(f"Rate limiter: {args.rate} req/s por dominio")

    # Agrupar por dominio y configurar rate limiters
    domains: dict[str, list[str]] = {}
    for cid in chain_ids:
        payload = load_catalog_runtime_payload(env, cid)
        domain = _extract_domain(payload)
        domains.setdefault(domain, []).append(cid)
        engine = str(payload.get("engine", "?"))
        print(f"  {cid}: engine={engine}, domain={domain}")

    for domain, chains in domains.items():
        set_rate_limiter(domain, args.rate)
        print(f"  -> Dominio {domain}: {len(chains)} cadenas, rate limiter {args.rate} req/s")

    if args.dry_run:
        print("\nDry-run: no se ejecuto scraping.")
        return

    print(f"\nInicio: {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}")
    print("=" * 60)

    results: list[tuple[str, bool, str]] = []
    threads: list[threading.Thread] = []

    def worker(cid: str) -> None:
        results.append(scrape_chain(cid, args.rate, args))

    for cid in chain_ids:
        t = threading.Thread(target=worker, args=(cid,), name=cid)
        threads.append(t)
        t.start()
        print(f"  Lanzado: {cid}")

    for t in threads:
        t.join()

    print("=" * 60)
    ok = sum(1 for _, success, _ in results if success)
    fail = sum(1 for _, success, _ in results if not success)
    print(f"Resultados: {ok} OK, {fail} fallos")

    for cid, success, msg in results:
        status = "OK" if success else "FAIL"
        print(f"  [{status}] {cid}: {msg}")

    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
