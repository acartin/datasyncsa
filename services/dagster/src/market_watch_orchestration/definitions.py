from datetime import datetime
import os
import subprocess
from pathlib import Path
from zoneinfo import ZoneInfo

from dagster import (
    DefaultScheduleStatus,
    Definitions,
    DynamicOut,
    DynamicOutput,
    Field,
    MetadataValue,
    OpExecutionContext,
    RunRequest,
    job,
    op,
    schedule,
)

from market_watch_orchestration.resources import PriceScrapperResource


CR_TIMEZONE = ZoneInfo("America/Costa_Rica")
DEFAULT_CAMPAIGN_ID = 1
DEFAULT_SPREAD_UNTIL_CR = "20:00"
DEFAULT_ANALYTIC_START_CRON = "0 8 * * *"
DEFAULT_ANALYTIC_SPREAD_UNTIL_CR = "18:00"
WALMART_FAMILY_CHAIN_IDS = ["masxmenos_cr", "maxi_pali_cr", "walmart_cr"]
MEGASUPER_CHAIN_IDS = ["megasuper_cr"]


def _business_date_from_scheduled_time(scheduled_time: datetime | None) -> str:
    if scheduled_time:
        return scheduled_time.astimezone(CR_TIMEZONE).strftime("%Y-%m-%d")
    return datetime.now(CR_TIMEZONE).strftime("%Y-%m-%d")


def _campaign_run_config(*, chain_ids: list[str], business_date: str) -> dict[str, object]:
    return {
        "ops": {
            "run_campaign_analytic_batch": {
                "config": {
                    "campaign_id": DEFAULT_CAMPAIGN_ID,
                    "chain_ids": chain_ids,
                    "business_date": business_date,
                    "spread_until_cr": DEFAULT_SPREAD_UNTIL_CR,
                    "only_pending": True,
                }
            }
        }
    }


def _daily_active_campaigns_run_config(*, business_date: str) -> dict[str, object]:
    return {
        "ops": {
            "discover_active_campaign_extract_groups": {
                "config": {
                    "business_date": business_date,
                    "spread_until_cr": DEFAULT_ANALYTIC_SPREAD_UNTIL_CR,
                    "only_pending": True,
                }
            }
        }
    }


def _resolve_business_date(value: str | None) -> str:
    if value:
        return value
    return datetime.now(CR_TIMEZONE).strftime("%Y-%m-%d")


def _mapping_key(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value).strip("_").lower()


def _log_process_result(context: OpExecutionContext, step_name: str, result) -> None:
    if result.stdout:
        context.log.info(result.stdout)
    if result.stderr:
        context.log.warning(result.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"{step_name} failed with return code {result.returncode}")


@op(required_resource_keys={"price_scrapper"})
def reset_daily_transform_stage(context: OpExecutionContext) -> dict[str, object]:
    context.resources.price_scrapper.reset_transform_stage_tables()
    tables = [
        "mkt_stage_product_candidate",
        "mkt_stage_product_review",
        "mkt_stage_listing_candidate",
        "mkt_stage_listing_review",
        "mkt_stage_listing_snapshot_candidate",
        "mkt_stage_listing_snapshot_review",
    ]
    context.add_output_metadata({"tables": MetadataValue.json(tables)})
    return {"reset": True}


@op(
    required_resource_keys={"price_scrapper"},
    out=DynamicOut(dict),
    config_schema={
        "business_date": Field(
            str,
            default_value="",
            description="Fecha de negocio YYYY-MM-DD. Si se omite, usa hoy en Costa Rica.",
        ),
        "spread_until_cr": Field(str, default_value=DEFAULT_ANALYTIC_SPREAD_UNTIL_CR),
        "only_pending": Field(bool, default_value=True),
    },
)
def discover_active_campaign_extract_groups(
    context: OpExecutionContext,
    reset_marker: dict[str, object],
):
    del reset_marker
    config = context.op_config
    business_date = _resolve_business_date(config.get("business_date"))
    groups = context.resources.price_scrapper.discover_active_campaign_extract_groups()
    context.log.info(
        "Discovered %s active campaign extract groups | business_date=%s | "
        "spread_until_cr=%s | only_pending=%s | groups=%s",
        len(groups),
        business_date,
        config["spread_until_cr"],
        config["only_pending"],
        groups,
    )

    for group in groups:
        campaign_id = int(group["campaign_id"])
        engine = str(group["engine"])
        chain_ids = list(group["chain_ids"])
        value = {
            "campaign_id": campaign_id,
            "engine": engine,
            "chain_ids": chain_ids,
            "business_date": business_date,
            "spread_until_cr": config["spread_until_cr"],
            "only_pending": config["only_pending"],
        }
        yield DynamicOutput(
            value,
            mapping_key=_mapping_key(f"campaign_{campaign_id}_{engine}"),
            metadata={
                "campaign_id": campaign_id,
                "engine": engine,
                "chain_ids": MetadataValue.json(chain_ids),
                "business_date": business_date,
                "spread_until_cr": config["spread_until_cr"],
                "only_pending": config["only_pending"],
            },
        )


@op(required_resource_keys={"price_scrapper"})
def extract_campaign_analytic_group(
    context: OpExecutionContext,
    group: dict[str, object],
) -> dict[str, object]:
    result, run_keys = context.resources.price_scrapper.run_extract_campaign_analytic_to_stage(
        campaign_id=int(group["campaign_id"]),
        chain_ids=list(group["chain_ids"]),
        business_date=str(group["business_date"]),
        spread_until_cr=str(group["spread_until_cr"]),
        only_pending=bool(group["only_pending"]),
    )
    _log_process_result(context, "extract_campaign_analytic_to_stage", result)

    output = {
        **group,
        "run_keys": run_keys,
        "returncode": result.returncode,
    }
    context.add_output_metadata(
        {
            "campaign_id": int(group["campaign_id"]),
            "engine": str(group["engine"]),
            "chain_ids": MetadataValue.json(list(group["chain_ids"])),
            "business_date": str(group["business_date"]),
            "run_keys": MetadataValue.json(run_keys),
            "run_count": len(run_keys),
        }
    )
    return output


@op(required_resource_keys={"price_scrapper"})
def collect_daily_analytic_run_keys(
    context: OpExecutionContext,
    extract_results: list[dict[str, object]],
) -> dict[str, object]:
    if not extract_results:
        context.log.warning("No active campaign extract groups were discovered.")
        return {"run_keys": [], "campaign_ids": [], "business_date": None, "skipped": True}

    business_date = str(extract_results[0]["business_date"])
    campaign_ids = sorted({int(result["campaign_id"]) for result in extract_results})
    run_keys = context.resources.price_scrapper.collect_successful_analytic_run_keys(
        campaign_ids=campaign_ids,
        business_date=business_date,
    )
    context.add_output_metadata(
        {
            "business_date": business_date,
            "campaign_ids": MetadataValue.json(campaign_ids),
            "run_keys": MetadataValue.json(run_keys),
            "run_count": len(run_keys),
        }
    )
    return {
        "run_keys": run_keys,
        "campaign_ids": campaign_ids,
        "business_date": business_date,
        "skipped": not bool(run_keys),
    }


@op(required_resource_keys={"price_scrapper"})
def transform_stage_products(
    context: OpExecutionContext,
    plan: dict[str, object],
) -> dict[str, object]:
    run_keys = list(plan["run_keys"])
    if not run_keys:
        context.log.warning("No run_keys available; skipping product transform.")
        return {**plan, "products_transformed": False}
    result = context.resources.price_scrapper.run_transform_stage_products(run_keys=run_keys)
    _log_process_result(context, "transform_stage_products", result)
    return {**plan, "products_transformed": True}


@op(required_resource_keys={"price_scrapper"})
def load_dim_products(
    context: OpExecutionContext,
    plan: dict[str, object],
) -> dict[str, object]:
    if not plan.get("products_transformed"):
        context.log.warning("Products were not transformed; skipping dim product load.")
        return {**plan, "products_loaded": False}
    result = context.resources.price_scrapper.run_load_dim_products()
    _log_process_result(context, "load_dim_products", result)
    return {**plan, "products_loaded": True}


@op(required_resource_keys={"price_scrapper"})
def transform_stage_listings(
    context: OpExecutionContext,
    plan: dict[str, object],
) -> dict[str, object]:
    run_keys = list(plan["run_keys"])
    if not run_keys:
        context.log.warning("No run_keys available; skipping listing transform.")
        return {**plan, "listings_transformed": False}
    result = context.resources.price_scrapper.run_transform_stage_listings(run_keys=run_keys)
    _log_process_result(context, "transform_stage_listings", result)
    return {**plan, "listings_transformed": True}


@op(required_resource_keys={"price_scrapper"})
def load_dim_listings(
    context: OpExecutionContext,
    plan: dict[str, object],
) -> dict[str, object]:
    if not plan.get("listings_transformed"):
        context.log.warning("Listings were not transformed; skipping dim listing load.")
        return {**plan, "listings_loaded": False}
    result = context.resources.price_scrapper.run_load_dim_listings()
    _log_process_result(context, "load_dim_listings", result)
    return {**plan, "listings_loaded": True}


@op(required_resource_keys={"price_scrapper"})
def transform_stage_listing_snapshots(
    context: OpExecutionContext,
    plan: dict[str, object],
) -> dict[str, object]:
    run_keys = list(plan["run_keys"])
    if not run_keys:
        context.log.warning("No run_keys available; skipping listing snapshot transform.")
        return {**plan, "snapshots_transformed": False}
    result = context.resources.price_scrapper.run_transform_stage_listing_snapshots(run_keys=run_keys)
    _log_process_result(context, "transform_stage_listing_snapshots", result)
    return {**plan, "snapshots_transformed": True}


@op(required_resource_keys={"price_scrapper"})
def load_fact_listing_snapshots(
    context: OpExecutionContext,
    plan: dict[str, object],
) -> dict[str, object]:
    if not plan.get("snapshots_transformed"):
        context.log.warning("Snapshots were not transformed; skipping fact load.")
        return {**plan, "facts_loaded": False}
    result = context.resources.price_scrapper.run_load_fact_listing_snapshots()
    _log_process_result(context, "load_fact_listing_snapshots", result)
    return {**plan, "facts_loaded": True}


@op(required_resource_keys={"price_scrapper"})
def validate_daily_analytic_counts(
    context: OpExecutionContext,
    plan: dict[str, object],
) -> dict[str, object]:
    run_keys = list(plan["run_keys"])
    summary = context.resources.price_scrapper.validate_analytic_run_keys(run_keys=run_keys)
    context.add_output_metadata(
        {
            "business_date": str(plan.get("business_date")),
            "run_keys": MetadataValue.json(run_keys),
            "validation": MetadataValue.json(summary),
        }
    )

    if summary["stage_minus_fact"] != 0 or summary["duplicate_facts"] != 0 or summary["suspect_runs"] != 0:
        raise RuntimeError(f"Daily analytic validation failed: {summary!r}")

    return {**plan, "validation": summary}


@op(
    required_resource_keys={"price_scrapper"},
    config_schema={
        "campaign_id": Field(int, default_value=DEFAULT_CAMPAIGN_ID),
        "chain_ids": Field([str]),
        "business_date": Field(str, description="Fecha de negocio YYYY-MM-DD."),
        "spread_until_cr": Field(str, default_value=DEFAULT_SPREAD_UNTIL_CR),
        "only_pending": Field(bool, default_value=True),
    },
)
def run_campaign_analytic_batch(context: OpExecutionContext) -> dict[str, object]:
    config = context.op_config
    result = context.resources.price_scrapper.run_campaign_analytic_batch(
        campaign_id=config["campaign_id"],
        chain_ids=config["chain_ids"],
        business_date=config["business_date"],
        spread_until_cr=config["spread_until_cr"],
        only_pending=config["only_pending"],
    )

    context.add_output_metadata(
        {
            "campaign_id": config["campaign_id"],
            "chain_ids": MetadataValue.json(config["chain_ids"]),
            "business_date": config["business_date"],
            "spread_until_cr": config["spread_until_cr"],
            "only_pending": config["only_pending"],
            "returncode": result.returncode,
        }
    )

    _log_process_result(context, "run_campaign_analytic_batch", result)

    return {
        "campaign_id": config["campaign_id"],
        "chain_ids": config["chain_ids"],
        "business_date": config["business_date"],
        "returncode": result.returncode,
    }


@job
def daily_active_campaigns_analytic_job() -> None:
    reset_marker = reset_daily_transform_stage()
    groups = discover_active_campaign_extract_groups(reset_marker)
    extract_results = groups.map(extract_campaign_analytic_group)
    daily_run_keys = collect_daily_analytic_run_keys(extract_results.collect())
    product_transform = transform_stage_products(daily_run_keys)
    product_load = load_dim_products(product_transform)
    listing_transform = transform_stage_listings(product_load)
    listing_load = load_dim_listings(listing_transform)
    snapshot_transform = transform_stage_listing_snapshots(listing_load)
    fact_load = load_fact_listing_snapshots(snapshot_transform)
    validate_daily_analytic_counts(fact_load)


@job
def campaign_analytic_walmart_family_job() -> None:
    run_campaign_analytic_batch()


@job
def campaign_analytic_megasuper_job() -> None:
    run_campaign_analytic_batch()


@op(
    required_resource_keys={"price_scrapper"},
    config_schema={
        "campaign_id": Field(int, default_value=DEFAULT_CAMPAIGN_ID),
        "business_date": Field(str, default_value="", description="YYYY-MM-DD. Defaults to today Costa Rica."),
        "skip_llm": Field(bool, default_value=True, description="Skip LLM synthesis, use deterministic narratives."),
    },
)
def generate_retail_signals(context: OpExecutionContext) -> dict[str, object]:
    config = context.op_config
    campaign_id = config["campaign_id"]
    business_date = config["business_date"] or datetime.now(CR_TIMEZONE).strftime("%Y-%m-%d")
    skip_llm = config["skip_llm"]

    signal_root = Path(os.environ.get("RETAIL_SIGNAL_ENGINE_ROOT", "/workspace/services/retail-signal-engine"))
    command = [
        "python3",
        "commands/generate_daily_signals.py",
        f"--campaign-id={campaign_id}",
        f"--business-date={business_date}",
        "--skip-llm" if skip_llm else "",
    ]
    command = [part for part in command if part]

    result = subprocess.run(
        command,
        cwd=str(signal_root),
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )
    if result.stdout:
        context.log.info(result.stdout.strip())
    if result.stderr:
        context.log.warning(result.stderr.strip())
    if result.returncode != 0:
        raise RuntimeError(f"generate_retail_signals failed: {result.stderr}")

    return {
        "campaign_id": campaign_id,
        "business_date": business_date,
        "skip_llm": skip_llm,
        "returncode": result.returncode,
    }


@job
def daily_signal_generation_job() -> None:
    generate_retail_signals()


@schedule(
    cron_schedule=DEFAULT_ANALYTIC_START_CRON,
    job=daily_active_campaigns_analytic_job,
    execution_timezone="America/Costa_Rica",
    default_status=DefaultScheduleStatus.STOPPED,
)
def daily_active_campaigns_analytic_schedule(context) -> RunRequest:
    business_date = _business_date_from_scheduled_time(context.scheduled_execution_time)
    return RunRequest(
        run_key=f"active-campaigns-analytic-{business_date}",
        run_config=_daily_active_campaigns_run_config(business_date=business_date),
    )


@schedule(
    cron_schedule="0 5 * * *",
    job=campaign_analytic_walmart_family_job,
    execution_timezone="America/Costa_Rica",
    default_status=DefaultScheduleStatus.STOPPED,
)
def daily_campaign_analytic_walmart_family_schedule(context) -> RunRequest:
    business_date = _business_date_from_scheduled_time(context.scheduled_execution_time)
    return RunRequest(
        run_key=f"campaign-1-walmart-family-{business_date}",
        run_config=_campaign_run_config(
            chain_ids=WALMART_FAMILY_CHAIN_IDS,
            business_date=business_date,
        ),
    )


@schedule(
    cron_schedule="15 5 * * *",
    job=campaign_analytic_megasuper_job,
    execution_timezone="America/Costa_Rica",
    default_status=DefaultScheduleStatus.STOPPED,
)
def daily_campaign_analytic_megasuper_schedule(context) -> RunRequest:
    business_date = _business_date_from_scheduled_time(context.scheduled_execution_time)
    return RunRequest(
        run_key=f"campaign-1-megasuper-{business_date}",
        run_config=_campaign_run_config(
            chain_ids=MEGASUPER_CHAIN_IDS,
            business_date=business_date,
        ),
    )


defs = Definitions(
    jobs=[
        daily_active_campaigns_analytic_job,
        campaign_analytic_walmart_family_job,
        campaign_analytic_megasuper_job,
        daily_signal_generation_job,
    ],
    schedules=[
        daily_active_campaigns_analytic_schedule,
        daily_campaign_analytic_walmart_family_schedule,
        daily_campaign_analytic_megasuper_schedule,
    ],
    resources={"price_scrapper": PriceScrapperResource.from_env()},
)
