#!/usr/bin/env python3
"""Limpia el stage temporal de catálogo sin tocar runs persistentes ni facts."""

from __future__ import annotations

import sys
from pathlib import Path


SERVICE_DIR = Path(__file__).resolve().parents[1]
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

from etl.catalog_stage_reset import reset_catalog_stage
from etl.postgres_cli import parse_env


def main() -> None:
    env = parse_env()
    summary = reset_catalog_stage(env)
    print(
        "Reset catalog stage completado | "
        f"stage_catalog_items_before={summary.stage_catalog_items_before} | "
        f"stage_catalog_items_after={summary.stage_catalog_items_after}",
        flush=True,
    )


if __name__ == "__main__":
    main()
