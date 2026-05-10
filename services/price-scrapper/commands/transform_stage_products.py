#!/usr/bin/env python3
"""Transforma stage de catálogo en candidatos y revisiones para productos."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


SERVICE_DIR = Path(__file__).resolve().parents[1]
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

from etl.postgres_cli import parse_env
from etl.stage_product_transform import (
    build_product_transform_result,
    fetch_stage_product_rows,
    replace_stage_product_transform_tables,
    resolve_stage_run_keys,
)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Transforma mkt_stage_catalog_item en mkt_stage_product_candidate y "
            "mkt_stage_product_review."
        )
    )
    parser.add_argument(
        "--run-key",
        "--stage-run-key",
        dest="run_key",
        action="append",
        type=int,
        default=None,
        help=(
            "Run exitosa a considerar. Si se omite, usa automaticamente "
            "la ultima corrida succeeded por cadena activa."
        ),
    )
    parser.add_argument(
        "--run-kind",
        choices=["comparative", "analytic"],
        default="comparative",
        help=(
            "Tipo de corrida a usar cuando no se especifican --run-key. "
            "Por defecto usa comparative."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    env = parse_env()

    stage_run_keys = resolve_stage_run_keys(
        env,
        explicit_run_keys=args.run_key,
        run_kind=args.run_kind,
    )
    rows = fetch_stage_product_rows(env, stage_run_keys=stage_run_keys)
    result = build_product_transform_result(rows, stage_run_keys=stage_run_keys)
    write_summary = replace_stage_product_transform_tables(env, result)

    print(
        "Transform stage products completado | "
        f"run_keys={result.stage_run_keys} | "
        f"run_kind={args.run_kind} | "
        f"stage_rows={result.stage_rows_read} | "
        f"candidates={write_summary.candidate_count} | "
        f"review={write_summary.review_count}",
        flush=True,
    )


if __name__ == "__main__":
    main()
