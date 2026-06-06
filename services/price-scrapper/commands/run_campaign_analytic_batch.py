#!/usr/bin/env python3
"""Orquesta una corrida analítica completa de campaña."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


SERVICE_DIR = Path(__file__).resolve().parents[1]
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

from commands.extract_campaign_analytic_to_stage import (
    extract_campaign_analytic_to_stage,
    parse_spread_until_cr,
)
from etl.business_date import parse_business_date_key
from etl.postgres_cli import parse_env
from etl.stage_product_transform import (
    build_product_transform_result,
    fetch_stage_product_rows,
    load_stage_product_candidates_into_dim_product,
    replace_stage_product_transform_tables,
)
from etl.stage_listing_transform import (
    build_listing_transform_result,
    fetch_product_key_map,
    fetch_stage_listing_rows,
    load_stage_listing_candidates_into_dim_listing,
    replace_stage_listing_transform_tables,
)
from etl.stage_listing_snapshot_transform import (
    build_listing_snapshot_transform_result,
    fetch_stage_snapshot_source_rows,
    load_stage_listing_snapshot_candidates_into_fact,
    replace_stage_listing_snapshot_transform_tables,
)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Corre extract + transform + load para una campaña analítica."
    )
    parser.add_argument("--campaign-id", type=int, required=True, help="Campaña analítica a ejecutar.")
    parser.add_argument("--chain-id", action="append", default=None, help="Filtra a una o varias cadenas.")
    parser.add_argument("--max-locations-per-chain", type=int, default=None, help="Limita locations por cadena.")
    parser.add_argument("--max-products-per-chain", type=int, default=None, help="Limita productos por cadena.")
    parser.add_argument("--sleep-min", type=float, default=1.25, help="Sleep mínimo entre requests.")
    parser.add_argument("--sleep-max", type=float, default=3.00, help="Sleep máximo entre requests.")
    parser.add_argument(
        "--business-date",
        default=None,
        help="Fecha de negocio en formato YYYY-MM-DD. Por defecto usa hoy en Costa Rica.",
    )
    parser.add_argument(
        "--spread-until-cr",
        default=None,
        help="Hora limite HH:MM en Costa Rica para repartir la corrida analitica entre locations.",
    )
    parser.add_argument(
        "--only-pending",
        action="store_true",
        help="Corre solo locations que aún no tengan runs analíticos exitosos para la campaña.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    env = parse_env()
    business_date_key = parse_business_date_key(args.business_date)

    run_keys = extract_campaign_analytic_to_stage(
        campaign_id=args.campaign_id,
        chain_ids=args.chain_id,
        max_locations_per_chain=args.max_locations_per_chain,
        max_products_per_chain=args.max_products_per_chain,
        sleep_min=args.sleep_min,
        sleep_max=args.sleep_max,
        business_date_key=business_date_key,
        spread_until_cr=parse_spread_until_cr(args.spread_until_cr),
        only_pending=args.only_pending,
    )
    if not run_keys:
        print(
            "Run campaign analytic batch sin trabajo nuevo | "
            f"campaign_id={args.campaign_id} | business_date_key={business_date_key}",
            flush=True,
        )
        return

    product_rows = fetch_stage_product_rows(env, stage_run_keys=run_keys)
    product_result = build_product_transform_result(product_rows, stage_run_keys=run_keys)
    product_stage_summary = replace_stage_product_transform_tables(env, product_result)
    product_load_summary = load_stage_product_candidates_into_dim_product(env, truncate_first=False)

    listing_rows = fetch_stage_listing_rows(env, stage_run_keys=run_keys)
    gtin_norms = [row.gtin_norm for row in listing_rows if row.gtin_norm]
    product_key_by_gtin = fetch_product_key_map(env, gtin_norms=gtin_norms)
    listing_result = build_listing_transform_result(
        listing_rows,
        stage_run_keys=run_keys,
        product_key_by_gtin=product_key_by_gtin,
    )
    listing_stage_summary = replace_stage_listing_transform_tables(env, listing_result)
    listing_load_summary = load_stage_listing_candidates_into_dim_listing(env, truncate_first=False)

    snapshot_rows = fetch_stage_snapshot_source_rows(env, stage_run_keys=run_keys)
    snapshot_result = build_listing_snapshot_transform_result(snapshot_rows, stage_run_keys=run_keys)
    snapshot_stage_summary = replace_stage_listing_snapshot_transform_tables(env, snapshot_result)
    snapshot_load_summary = load_stage_listing_snapshot_candidates_into_fact(env, truncate_first=False)

    print(
        "Run campaign analytic batch completado | "
        f"campaign_id={args.campaign_id} | "
        f"business_date_key={business_date_key} | "
        f"run_keys={run_keys} | "
        f"product_candidates={product_stage_summary.candidate_count} | "
        f"product_loaded={product_load_summary.loaded_rows} | "
        f"listing_candidates={listing_stage_summary.candidate_count} | "
        f"listing_loaded={listing_load_summary.loaded_rows} | "
        f"snapshot_candidates={snapshot_stage_summary.candidate_count} | "
        f"snapshot_loaded={snapshot_load_summary.loaded_rows}",
        flush=True,
    )


if __name__ == "__main__":
    main()
