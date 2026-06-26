#!/usr/bin/env python3
"""Test de conectividad contra BrightData Residential Proxy.

Uso:
  Opcion A - .env:
       set -a; source ../../.env; set +a
       python3 test_brd.py

  Opcion B - export directo:
       export BRIGHTDATA_CUSTOMER_ID="..."
       export BRIGHTDATA_ZONE="..."
       export BRIGHTDATA_ZONE_PASSWORD="..."
       export BRIGHTDATA_COUNTRY="cr"   (opcional)
       python3 test_brd.py
"""

from __future__ import annotations

import os
import sys

from curl_cffi import requests

from brightdata import config_from_env

TEST_URL = "https://geo.brdtest.com/welcome.txt?product=resi&method=native"


def main() -> int:
    missing = [k for k in ("BRIGHTDATA_CUSTOMER_ID", "BRIGHTDATA_ZONE", "BRIGHTDATA_ZONE_PASSWORD") if k not in os.environ]
    if missing:
        print(f"Faltan variables de entorno: {', '.join(missing)}", file=sys.stderr)
        return 1

    cfg = config_from_env()
    print(f"Proxy:  {cfg.host}:{cfg.port}")
    print(f"Zone:   {cfg.zone}")
    print(f"Country: {cfg.country or 'random'}")
    print(f"Target: {TEST_URL}")
    print()

    session = requests.Session(impersonate="chrome136")
    try:
        resp = session.get(TEST_URL, proxies=cfg.as_proxies_dict(), timeout=30, verify=False)
        resp.raise_for_status()
        print(f"Status: {resp.status_code}")
        print(f"Body:\n{resp.text.strip()}")
        print()
        print("OK: Proxy residencial funcional.")
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
