#!/usr/bin/env python3
"""Carga candidatos de snapshot transformados hacia mkt_fact_listing_snapshot."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


SERVICE_DIR = Path(__file__).resolve().parents[1]
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

from etl.postgres_cli import parse_env
from etl.stage_listing_snapshot_transform import (
    load_stage_listing_snapshot_candidates_into_fact,
)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Carga mkt_stage_listing_snapshot_candidate hacia "
            "public.mkt_fact_listing_snapshot."
        )
    )
    parser.add_argument(
        "--truncate-first",
        action="store_true",
        help=(
            "Vacía mkt_fact_listing_snapshot antes de cargar. "
            "Úsalo solo para bootstrap inicial o reconstrucciones controladas."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    env = parse_env()

    summary = load_stage_listing_snapshot_candidates_into_fact(
        env,
        truncate_first=args.truncate_first,
    )
    print(
        "Load fact listing snapshots completado | "
        f"truncate_first={summary.truncated_first} | "
        f"candidate_rows={summary.candidate_count} | "
        f"loaded_rows={summary.loaded_rows} | "
        f"fact_total={summary.fact_total}",
        flush=True,
    )


if __name__ == "__main__":
    main()
