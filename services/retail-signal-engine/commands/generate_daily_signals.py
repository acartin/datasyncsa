#!/usr/bin/env python3
"""Generate Market Watch retail signals for a date/scope."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


SERVICE_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = SERVICE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from retail_signal_engine.db import Database
from retail_signal_engine.engine import SignalRunConfig, run_signal_generation


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate deterministic retail signals and optional LLM synthesis."
    )
    parser.add_argument("--business-date", default=None, help="Business date YYYY-MM-DD. Defaults to latest available date.")
    parser.add_argument("--campaign-id", type=int, default=None, help="Limit generation to one campaign.")
    parser.add_argument("--client-id", type=int, default=None, help="Limit generation to one client_id.")
    parser.add_argument("--category", default=None, help="Optional category label for generated signals.")
    parser.add_argument("--max-signals", type=int, default=12, help="Maximum scored client signals to synthesize/save.")
    parser.add_argument("--brand-over-threshold", type=float, default=105.0)
    parser.add_argument("--brand-under-threshold", type=float, default=95.0)
    parser.add_argument("--sku-gap-threshold-pct", type=float, default=10.0)
    parser.add_argument("--driver-concentration-threshold-pct", type=float, default=60.0)
    parser.add_argument("--promo-break-discount-threshold-pct", type=float, default=15.0)
    parser.add_argument("--promo-break-market-gap-threshold-pct", type=float, default=20.0)
    parser.add_argument("--promo-break-min-visible-locations", type=int, default=3)
    parser.add_argument("--promo-break-min-promo-share-pct", type=float, default=50.0)
    parser.add_argument("--init-schema", action="store_true", help="Apply SQL schema before generating signals.")
    parser.add_argument("--dry-run", action="store_true", help="Build signals but do not persist them.")
    parser.add_argument("--skip-llm", action="store_true", help="Use deterministic narrative templates only.")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    db = Database.from_env()
    if args.init_schema:
        for sql_path in sorted((SERVICE_DIR / "sql").glob("*.sql")):
            db.apply_sql_file(sql_path)

    config = SignalRunConfig(
        business_date=args.business_date,
        campaign_id=args.campaign_id,
        client_id=args.client_id,
        category=args.category,
        max_signals=args.max_signals,
        brand_over_threshold=args.brand_over_threshold,
        brand_under_threshold=args.brand_under_threshold,
        sku_gap_threshold_pct=args.sku_gap_threshold_pct,
        driver_concentration_threshold_pct=args.driver_concentration_threshold_pct,
        promo_break_discount_threshold_pct=args.promo_break_discount_threshold_pct,
        promo_break_market_gap_threshold_pct=args.promo_break_market_gap_threshold_pct,
        promo_break_min_visible_locations=args.promo_break_min_visible_locations,
        promo_break_min_promo_share_pct=args.promo_break_min_promo_share_pct,
        dry_run=args.dry_run,
        skip_llm=args.skip_llm,
    )
    summary = run_signal_generation(db, config)
    print(
        "Retail signal generation completed | "
        f"date_key={summary['date_key']} | "
        f"business_date={summary['business_date']} | "
        f"market_events={summary['market_events']} | "
        f"client_signals={summary['client_signals']} | "
        f"saved={summary['saved']} | "
        f"llm_used={summary['llm_used']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
