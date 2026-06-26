#!/usr/bin/env python3
"""Prueba de rate limiter + proxy + http_client integrados.

Corre dos workers concurrentes contra el endpoint de prueba de BrightData.
Ambos comparten el bucket del dominio real de la URL, igual que el runtime.
"""

from __future__ import annotations

import os
import sys
import time
import threading
from urllib.parse import urlparse

_PRICE_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "price-scrapper"))
if _PRICE_DIR not in sys.path:
    sys.path.insert(0, _PRICE_DIR)

GEO_URL = "https://geo.brdtest.com/mygeo.json"


def worker(
    name: str,
    requests: int,
) -> None:
    from etl.http_client import create_browser_session, request_with_retry

    session = create_browser_session()

    print(f"  [{name}] Inicia ({requests} requests)")
    for i in range(1, requests + 1):
        start = time.monotonic()
        resp = request_with_retry(session, "GET", GEO_URL, timeout=30, verify=False)
        resp.raise_for_status()
        data = resp.json()
        elapsed = time.monotonic() - start
        city = data.get("geo", {}).get("city", "?")
        asn = data.get("asn", {}).get("org_name", "?")[:30]
        print(f"  [{name}:{i}] {city:<20} {asn:<30} {elapsed:.2f}s")
    print(f"  [{name}] Terminado")


def main() -> int:
    from etl.http_client import set_rate_limiter

    missing = [k for k in ("BRIGHTDATA_CUSTOMER_ID", "BRIGHTDATA_ZONE", "BRIGHTDATA_ZONE_PASSWORD") if k not in os.environ]
    if missing:
        print(f"Faltan variables de entorno: {', '.join(missing)}", file=sys.stderr)
        return 1

    print("=" * 60)
    print("RATE LIMITER + PROXY: PRUEBA DE CONCURRENCIA")
    print("=" * 60)
    print()

    rate = 5.0
    domain = urlparse(GEO_URL).netloc
    set_rate_limiter(domain, rate)
    print(f"Dominio real: {domain}")
    print(f"Rate limiter compartido: {rate} req/s")
    print()

    worker_a = {"name": "worker-a", "requests": 5}
    worker_b = {"name": "worker-b", "requests": 5}

    threads = [
        threading.Thread(target=worker, kwargs=worker_a),
        threading.Thread(target=worker, kwargs=worker_b),
    ]

    total_start = time.monotonic()

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    total_elapsed = time.monotonic() - total_start
    total_req = worker_a["requests"] + worker_b["requests"]

    print()
    print(f"  Total: {total_req} requests en {total_elapsed:.1f}s")
    print(f"  Throughput: {total_req / total_elapsed:.1f} req/s")
    print()
    print("=" * 60)
    print("PRUEBA COMPLETADA")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
