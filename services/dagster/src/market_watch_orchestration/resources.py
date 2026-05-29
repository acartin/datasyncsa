import os
import subprocess
from pathlib import Path

from dagster import ConfigurableResource

from market_watch_orchestration.price_scrapper.command_runner import CommandRunner
from market_watch_orchestration.price_scrapper.commands import PriceScrapperCommands
from market_watch_orchestration.price_scrapper.postgres_runner import PostgresRunner
from market_watch_orchestration.price_scrapper.repository import MarketWatchRepository


class PriceScrapperResource(ConfigurableResource):
    """Dagster resource for the price-scrapper bounded context.

    Keep this class as a small facade: Dagster depends on it, but the actual
    command and SQL details live in domain-specific adapter modules.
    """

    root: str

    @classmethod
    def from_env(cls) -> "PriceScrapperResource":
        return cls(root=os.getenv("PRICE_SCRAPPER_ROOT", "/workspace/services/price-scrapper"))

    @property
    def root_path(self) -> Path:
        return Path(self.root)

    @property
    def command_runner(self) -> CommandRunner:
        return CommandRunner(root_path=self.root_path)

    @property
    def commands(self) -> PriceScrapperCommands:
        return PriceScrapperCommands(runner=self.command_runner)

    @property
    def repository(self) -> MarketWatchRepository:
        return MarketWatchRepository(postgres=PostgresRunner())

    def discover_active_campaign_extract_groups(self) -> list[dict[str, object]]:
        return self.repository.discover_active_campaign_extract_groups()

    def reset_transform_stage_tables(self) -> None:
        self.repository.reset_transform_stage_tables()

    def collect_successful_analytic_run_keys(
        self,
        *,
        campaign_ids: list[int],
        business_date: str,
    ) -> list[int]:
        return self.repository.collect_successful_analytic_run_keys(
            campaign_ids=campaign_ids,
            business_date=business_date,
        )

    def validate_analytic_run_keys(self, *, run_keys: list[int]) -> dict[str, int]:
        return self.repository.validate_analytic_run_keys(run_keys=run_keys)

    def run_extract_campaign_analytic_to_stage(
        self,
        *,
        campaign_id: int,
        chain_ids: list[str],
        business_date: str,
        spread_until_cr: str,
        only_pending: bool,
    ) -> tuple[subprocess.CompletedProcess[str], list[int]]:
        return self.commands.run_extract_campaign_analytic_to_stage(
            campaign_id=campaign_id,
            chain_ids=chain_ids,
            business_date=business_date,
            spread_until_cr=spread_until_cr,
            only_pending=only_pending,
        )

    def run_transform_stage_products(
        self,
        *,
        run_keys: list[int],
    ) -> subprocess.CompletedProcess[str]:
        return self.commands.run_transform_stage_products(run_keys=run_keys)

    def run_load_dim_products(self) -> subprocess.CompletedProcess[str]:
        return self.commands.run_load_dim_products()

    def run_transform_stage_listings(
        self,
        *,
        run_keys: list[int],
    ) -> subprocess.CompletedProcess[str]:
        return self.commands.run_transform_stage_listings(run_keys=run_keys)

    def run_load_dim_listings(self) -> subprocess.CompletedProcess[str]:
        return self.commands.run_load_dim_listings()

    def run_transform_stage_listing_snapshots(
        self,
        *,
        run_keys: list[int],
    ) -> subprocess.CompletedProcess[str]:
        return self.commands.run_transform_stage_listing_snapshots(run_keys=run_keys)

    def run_load_fact_listing_snapshots(self) -> subprocess.CompletedProcess[str]:
        return self.commands.run_load_fact_listing_snapshots()

    def run_campaign_analytic_batch(
        self,
        *,
        campaign_id: int,
        chain_ids: list[str],
        business_date: str,
        spread_until_cr: str,
        only_pending: bool,
    ) -> subprocess.CompletedProcess[str]:
        return self.commands.run_campaign_analytic_batch(
            campaign_id=campaign_id,
            chain_ids=chain_ids,
            business_date=business_date,
            spread_until_cr=spread_until_cr,
            only_pending=only_pending,
        )
