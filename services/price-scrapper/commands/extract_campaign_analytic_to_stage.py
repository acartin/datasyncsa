#!/usr/bin/env python3
"""Extrae una campaña analítica a stage usando consultas puntuales por producto."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import sleep
from zoneinfo import ZoneInfo


SERVICE_DIR = Path(__file__).resolve().parents[1]
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

from engines.vtex_analytic_engine import (
    VtexAnalyticChainConfig,
    VtexAnalyticLocation,
    VtexAnalyticScraper,
    VtexAnalyticTarget,
)
from engines.instaleap_analytic_engine import (
    InstaleapAnalyticChainConfig,
    InstaleapAnalyticLocation,
    InstaleapAnalyticScraper,
    InstaleapAnalyticTarget,
)
from etl.business_date import parse_business_date_key
from etl.campaign_runtime_db import (
    fetch_campaign_listing_targets,
    fetch_campaign_locations,
    load_campaign_row,
)
from etl.catalog_stage_loader import (
    load_failed_catalog_stage_run,
    load_successful_catalog_stage_run,
)
from etl.chain_runtime_db import load_chain_row
from etl.postgres_cli import parse_env
from etl.run_runtime_db import find_existing_succeeded_run_key

CR_TIMEZONE = ZoneInfo("America/Costa_Rica")


@dataclass(frozen=True)
class AnalyticWorkUnit:
    chain_id: str
    engine: str
    location_key: int
    location_name: str
    scraper: VtexAnalyticScraper | InstaleapAnalyticScraper
    targets: list[VtexAnalyticTarget] | list[InstaleapAnalyticTarget]
    pricing_scope: str


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Extrae una campaña analítica a mkt_run/mkt_stage_catalog_item usando "
            "consultas puntuales por producto y location."
        )
    )
    parser.add_argument("--campaign-id", type=int, required=True, help="Campaña analítica a ejecutar.")
    parser.add_argument("--chain-id", action="append", default=None, help="Filtra a una o varias cadenas.")
    parser.add_argument("--max-locations-per-chain", type=int, default=None, help="Limita locations por cadena.")
    parser.add_argument("--max-products-per-chain", type=int, default=None, help="Limita productos por cadena.")
    parser.add_argument("--sleep-min", type=float, default=1.25, help="Sleep mínimo entre requests.")
    parser.add_argument("--sleep-max", type=float, default=3.00, help="Sleep máximo entre requests.")
    parser.add_argument("--client-id", type=int, default=None, help="Sobrescribe client_id de la campaña.")
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


def build_vtex_chain_config(env: dict[str, str], chain_id: str) -> VtexAnalyticChainConfig:
    payload = load_chain_row(env, chain_id)
    return VtexAnalyticChainConfig(
        chain_id=chain_id,
        display_name=str(payload["display_name"]),
        catalog_id=str(payload["catalog_id"]),
        base_url=str(payload["base_url"]),
    )


def build_instaleap_chain_config(env: dict[str, str], chain_id: str) -> InstaleapAnalyticChainConfig:
    payload = load_chain_row(env, chain_id)
    extras = dict(payload.get("engine_extras") or {})
    client_id = str(extras.get("client_id") or "").strip()
    if not client_id:
        raise RuntimeError(f"Instaleap analytic requiere client_id para chain_id={chain_id!r}.")
    graphql_endpoint = str(
        extras.get("graphql_endpoint") or "https://nextgentheadless.instaleap.io/api/v3"
    ).strip()
    return InstaleapAnalyticChainConfig(
        chain_id=chain_id,
        display_name=str(payload["display_name"]),
        catalog_id=str(payload["catalog_id"]),
        base_url=str(payload["base_url"]),
        client_id=client_id,
        graphql_endpoint=graphql_endpoint,
    )


def parse_spread_until_cr(value: str | None) -> datetime | None:
    if not value:
        return None
    hour_text, minute_text = value.strip().split(":", 1)
    now_cr = datetime.now(CR_TIMEZONE)
    return now_cr.replace(
        hour=int(hour_text),
        minute=int(minute_text),
        second=0,
        microsecond=0,
    )


def maybe_sleep_to_spread(deadline_cr: datetime | None, *, remaining_units: int) -> None:
    if deadline_cr is None or remaining_units <= 0:
        return
    now_cr = datetime.now(CR_TIMEZONE)
    remaining_seconds = (deadline_cr - now_cr).total_seconds()
    if remaining_seconds <= 0:
        return
    sleep_seconds = remaining_seconds / remaining_units
    if sleep_seconds <= 0:
        return
    print(
        f"[analytic] spread sleep {round(sleep_seconds, 1)}s | "
        f"remaining_locations={remaining_units} | "
        f"deadline_cr={deadline_cr.strftime('%Y-%m-%d %H:%M')}",
        flush=True,
    )
    sleep(sleep_seconds)


def extract_campaign_analytic_to_stage(
    *,
    campaign_id: int,
    chain_ids: list[str] | None,
    max_locations_per_chain: int | None,
    max_products_per_chain: int | None,
    sleep_min: float,
    sleep_max: float,
    client_id_override: int | None,
    business_date_key: int,
    spread_until_cr: datetime | None = None,
    only_pending: bool = False,
) -> list[int]:
    env = parse_env()
    campaign = load_campaign_row(env, campaign_id)
    locations = fetch_campaign_locations(
        env,
        campaign_id,
        chain_ids=chain_ids,
        business_date_key=business_date_key,
        only_pending=only_pending,
    )
    targets = fetch_campaign_listing_targets(env, campaign_id, chain_ids=chain_ids)
    effective_client_id = client_id_override if client_id_override is not None else campaign.client_id

    locations_by_chain: dict[str, list] = defaultdict(list)
    for row in locations:
        locations_by_chain[row.chain_id].append(row)
    targets_by_chain: dict[str, list] = defaultdict(list)
    for row in targets:
        targets_by_chain[row.chain_id].append(row)

    inserted_run_keys: list[int] = []
    planned_units: list[AnalyticWorkUnit] = []

    for chain_id in sorted(locations_by_chain):
        chain_locations = locations_by_chain[chain_id]
        chain_targets = targets_by_chain.get(chain_id, [])
        if max_locations_per_chain is not None:
            chain_locations = chain_locations[: max_locations_per_chain]
        if max_products_per_chain is not None:
            chain_targets = chain_targets[: max_products_per_chain]
        if not chain_targets:
            print(f"[{chain_id}] sin productos objetivo para campaña {campaign_id}; se omite.", flush=True)
            continue

        engine = chain_locations[0].engine
        if engine == "vtex":
            chain_config = build_vtex_chain_config(env, chain_id)
            analytic_targets = [
                VtexAnalyticTarget(
                    product_key=row.product_key,
                    product_role=row.product_role,
                    gtin_raw=row.gtin_raw,
                    brand_name=row.brand_name,
                    product_name=row.product_name,
                    content_quantity=row.content_quantity,
                    content_unit=row.content_unit,
                    listing_key=row.listing_key,
                    source_product_id=row.source_product_id,
                    source_sku=row.source_sku,
                    seller_id=row.seller_id,
                    seller_name=row.seller_name,
                    listing_name=row.listing_name,
                    product_url=row.product_url or "",
                    image_url=row.image_url,
                    root_category_slug=row.root_category_slug,
                    root_category_name=row.root_category_name,
                )
                for row in chain_targets
                if row.product_url
            ]
        elif engine == "instaleap":
            chain_config = build_instaleap_chain_config(env, chain_id)
            analytic_targets = [
                InstaleapAnalyticTarget(
                    product_key=row.product_key,
                    product_role=row.product_role,
                    gtin_raw=row.gtin_raw,
                    brand_name=row.brand_name,
                    product_name=row.product_name,
                    content_quantity=row.content_quantity,
                    content_unit=row.content_unit,
                    listing_key=row.listing_key,
                    source_product_id=row.source_product_id,
                    source_sku=row.source_sku,
                    seller_id=row.seller_id,
                    seller_name=row.seller_name,
                    listing_name=row.listing_name,
                    product_url=row.product_url or "",
                    image_url=row.image_url,
                    root_category_slug=row.root_category_slug,
                    root_category_name=row.root_category_name,
                )
                for row in chain_targets
                if row.source_sku
            ]
        else:
            print(
                f"[{chain_id}] engine={engine} aún no soportado para analítico por tienda; se omite.",
                flush=True,
            )
            continue

        if not analytic_targets:
            print(
                f"[{chain_id}] sin targets analíticos utilizables para campaña {campaign_id}; se omite.",
                flush=True,
            )
            continue

        for location in chain_locations:
            existing_run_key = find_existing_succeeded_run_key(
                env,
                business_date_key=business_date_key,
                run_kind="analytic",
                chain_id=chain_id,
                location_key=location.location_key,
                campaign_id=campaign_id,
            )
            if existing_run_key is not None:
                print(
                    f"[{chain_id}] location={location.location_name} ya registrada para "
                    f"business_date_key={business_date_key} | run_key={existing_run_key}; se omite.",
                    flush=True,
                )
                continue
            if engine == "vtex":
                if not location.sales_channel or not location.region_id:
                    print(
                        f"[{chain_id}] location_key={location.location_key} sin sales_channel/region_id; se omite.",
                        flush=True,
                    )
                    continue
                scraper = VtexAnalyticScraper(
                    chain=chain_config,
                    location=VtexAnalyticLocation(
                        location_key=location.location_key,
                        location_name=location.location_name,
                        sales_channel=location.sales_channel,
                        region_id=location.region_id,
                        postal_code=location.postal_code,
                    ),
                    sleep_min=sleep_min,
                    sleep_max=sleep_max,
                )
                current_pricing_scope = "physical_store_online"
            else:
                if not location.source_location_ref:
                    print(
                        f"[{chain_id}] location_key={location.location_key} sin storeReference; se omite.",
                        flush=True,
                    )
                    continue
                scraper = InstaleapAnalyticScraper(
                    chain=chain_config,
                    location=InstaleapAnalyticLocation(
                        location_key=location.location_key,
                        location_name=location.location_name,
                        store_reference=location.source_location_ref,
                        store_id=location.source_internal_id,
                    ),
                    sleep_min=sleep_min,
                    sleep_max=sleep_max,
                )
                current_pricing_scope = "physical_store_online"

            planned_units.append(
                AnalyticWorkUnit(
                    chain_id=chain_id,
                    engine=engine,
                    location_key=location.location_key,
                    location_name=location.location_name,
                    scraper=scraper,
                    targets=analytic_targets,
                    pricing_scope=current_pricing_scope,
                )
            )

    total_units = len(planned_units)
    if total_units:
        print(
            f"[analytic] locations planificadas={total_units}"
            + (
                f" | spread_until_cr={spread_until_cr.strftime('%Y-%m-%d %H:%M')}"
                if spread_until_cr is not None
                else ""
            ),
            flush=True,
        )

    for index, unit in enumerate(planned_units, start=1):
        print(
            f"[analytic] ejecutando {index}/{total_units} | "
            f"chain={unit.chain_id} | location={unit.location_name}",
            flush=True,
        )
        scraper = unit.scraper
        analytic_targets = unit.targets
        chain_id = unit.chain_id
        current_pricing_scope = unit.pricing_scope

        try:
            records, metadata = scraper.collect_records(analytic_targets)
            if not records:
                raise RuntimeError("No se obtuvieron registros exitosos para esta location.")
            run_key, inserted_items = load_successful_catalog_stage_run(
                chain_id=chain_id,
                metadata=metadata,
                records=records,
                run_kind="analytic",
                client_id=effective_client_id,
                business_date_key=business_date_key,
                location_key=unit.location_key,
                campaign_id=campaign_id,
            )
            inserted_run_keys.append(run_key)
            print(
                f"[{chain_id}] analytic stage load completado | "
                f"campaign_id={campaign_id} | location={unit.location_name} | "
                f"run_key={run_key} | items={inserted_items}",
                flush=True,
            )
        except Exception as exc:
            run_key = load_failed_catalog_stage_run(
                chain_id=chain_id,
                engine=unit.engine,
                pricing_scope=current_pricing_scope,
                started_at=scraper.started_at,
                error_message=str(exc),
                run_kind="analytic",
                client_id=effective_client_id,
                business_date_key=business_date_key,
                location_key=unit.location_key,
                campaign_id=campaign_id,
                raw_metadata={
                    "campaign_id": campaign_id,
                    "location_key": unit.location_key,
                    "location_name": unit.location_name,
                    "requested_targets": len(analytic_targets),
                },
            )
            print(
                f"[{chain_id}] corrida analítica fallida registrada | "
                f"location={unit.location_name} | run_key={run_key}",
                flush=True,
            )
        remaining_units = total_units - index
        maybe_sleep_to_spread(spread_until_cr, remaining_units=remaining_units)

    return inserted_run_keys


def main(argv: list[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    business_date_key = parse_business_date_key(args.business_date)
    spread_until_cr = parse_spread_until_cr(args.spread_until_cr)
    run_keys = extract_campaign_analytic_to_stage(
        campaign_id=args.campaign_id,
        chain_ids=args.chain_id,
        max_locations_per_chain=args.max_locations_per_chain,
        max_products_per_chain=args.max_products_per_chain,
        sleep_min=args.sleep_min,
        sleep_max=args.sleep_max,
        client_id_override=args.client_id,
        business_date_key=business_date_key,
        spread_until_cr=spread_until_cr,
        only_pending=args.only_pending,
    )
    print(
        "Extract campaign analytic to stage completado | "
        f"campaign_id={args.campaign_id} | business_date_key={business_date_key} | "
        f"spread_until_cr={args.spread_until_cr} | run_keys={run_keys}",
        flush=True,
    )


if __name__ == "__main__":
    main()
