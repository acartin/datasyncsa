#!/usr/bin/env python3
"""Simula requests estilo scraper a traves del proxy residencial BrightData.

Muestra rotacion de IP en cada request y opcionalmente sesion fija.
Usa curl_cffi con impersonacion Chrome igual que los engines reales.
"""

from __future__ import annotations

import os
import sys
import time
import uuid

from curl_cffi import requests

from brightdata import config_from_env

GEO_URL = "https://geo.brdtest.com/mygeo.json"
REQUESTS = 5

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-CR,es;q=0.9,en;q=0.8",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
    ),
}


def geo_info(session: requests.Session, proxies: dict) -> dict:
    resp = session.get(GEO_URL, proxies=proxies, timeout=30, verify=False)
    resp.raise_for_status()
    return resp.json()


def main() -> int:
    missing = [k for k in ("BRIGHTDATA_CUSTOMER_ID", "BRIGHTDATA_ZONE", "BRIGHTDATA_ZONE_PASSWORD") if k not in os.environ]
    if missing:
        print(f"Faltan variables de entorno: {', '.join(missing)}", file=sys.stderr)
        return 1

    print("=" * 60)
    print("SIMULACION DE SCRAPING CON PROXY RESIDENCIAL BRIGHTDATA")
    print("=" * 60)

    # --- Parte 1: IP rotando en cada request ---
    cfg_rotating = config_from_env()
    proxies = cfg_rotating.as_proxies_dict()
    print(f"\n[1] IP ROTACION ({REQUESTS} requests, sin session)")
    print(f"    Proxy: {cfg_rotating.host}:{cfg_rotating.port}")
    print(f"    Zone:  {cfg_rotating.zone}")
    print(f"    Country: {cfg_rotating.country or 'random'}")
    print("-" * 60)

    session = requests.Session(impersonate="chrome136")
    session.headers.update(HEADERS)

    fingerprints: list[str] = []
    for i in range(1, REQUESTS + 1):
        start = time.monotonic()
        info = geo_info(session, proxies)
        elapsed = time.monotonic() - start
        city = info.get("geo", {}).get("city", "?")
        asn_org = info.get("asn", {}).get("org_name", "?")
        asnum = info.get("asn", {}).get("asnum", "?")
        fp = f"{city}/{asnum}"
        fingerprints.append(fp)
        print(f"  [{i}] City: {city:<20} ASN: {asn_org} ({elapsed:.2f}s)")

    unique = len(set(fingerprints))
    print(f"\n  → {unique} peers distintos de {REQUESTS} requests")

    # --- Parte 2: Session fija (misma IP) ---
    session_id = f"test{uuid.uuid4().hex[:8]}"
    cfg_sticky = config_from_env(session=session_id)
    sticky_proxies = cfg_sticky.as_proxies_dict()
    print(f"\n[2] SESION FIJA (3 requests con session={session_id})")
    print("-" * 60)

    sticky_fp: list[str] = []
    for i in range(1, 4):
        start = time.monotonic()
        info = geo_info(session, sticky_proxies)
        elapsed = time.monotonic() - start
        city = info.get("geo", {}).get("city", "?")
        asnum = info.get("asn", {}).get("asnum", "?")
        fp = f"{city}/{asnum}"
        sticky_fp.append(fp)
        print(f"  [{i}] City: {city:<20} ASN: {asnum} ({elapsed:.2f}s)")

    all_same = len(set(sticky_fp)) == 1
    print(f"  → {'MISMO PEER (sesion funciona)' if all_same else 'PEER CAMBIO (sesion fallo)'}")

    # --- Parte 3: Request GET a target real (estilo VTEX) ---
    print(f"\n[3] GET TIPO SCRAPER (VTEX-style)")
    print("-" * 60)

    try:
        resp = session.get(
            "https://geo.brdtest.com/welcome.txt?product=resi&method=native",
            proxies=proxies,
            timeout=30,
            verify=False,
        )
        lines = resp.text.strip().split("\n")
        print(f"  GET a geo.brdtest.com")
        print(f"  Status: {resp.status_code}")
        print(f"  Salida: {lines[0]}")
        print(f"  Country/Region: {lines[1]} / {lines[2]}")
        print("  OK: GET funcionando via proxy residencial")
    except Exception as e:
        print(f"  ERROR: {e}")

    print()
    print("=" * 60)
    print("SIMULACION COMPLETADA")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
