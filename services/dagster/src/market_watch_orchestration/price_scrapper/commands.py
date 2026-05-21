import ast
import re
import subprocess

from market_watch_orchestration.price_scrapper.command_runner import CommandRunner


class PriceScrapperCommands:
    """Command API for price-scrapper ETL scripts."""

    def __init__(self, *, runner: CommandRunner) -> None:
        self.runner = runner

    def _parse_run_keys(self, stdout: str) -> list[int]:
        matches = re.findall(r"run_keys=(\[[^\]]*\])", stdout)
        if not matches:
            return []
        parsed = ast.literal_eval(matches[-1])
        return [int(run_key) for run_key in parsed]

    def run_extract_campaign_analytic_to_stage(
        self,
        *,
        campaign_id: int,
        chain_ids: list[str],
        business_date: str,
        spread_until_cr: str,
        only_pending: bool,
    ) -> tuple[subprocess.CompletedProcess[str], list[int]]:
        command = [
            "python3",
            "commands/extract_campaign_analytic_to_stage.py",
            "--campaign-id",
            str(campaign_id),
            "--business-date",
            business_date,
            "--spread-until-cr",
            spread_until_cr,
        ]
        for chain_id in chain_ids:
            command.extend(["--chain-id", chain_id])
        if only_pending:
            command.append("--only-pending")

        result = self.runner.run(command)
        return result, self._parse_run_keys(result.stdout)

    def run_transform_stage_products(
        self,
        *,
        run_keys: list[int],
    ) -> subprocess.CompletedProcess[str]:
        command = ["python3", "commands/transform_stage_products.py"]
        for run_key in run_keys:
            command.extend(["--run-key", str(run_key)])
        return self.runner.run(command)

    def run_load_dim_products(self) -> subprocess.CompletedProcess[str]:
        return self.runner.run(["python3", "commands/load_dim_products.py"])

    def run_transform_stage_listings(
        self,
        *,
        run_keys: list[int],
    ) -> subprocess.CompletedProcess[str]:
        command = ["python3", "commands/transform_stage_listings.py"]
        for run_key in run_keys:
            command.extend(["--run-key", str(run_key)])
        return self.runner.run(command)

    def run_load_dim_listings(self) -> subprocess.CompletedProcess[str]:
        return self.runner.run(["python3", "commands/load_dim_listings.py"])

    def run_transform_stage_listing_snapshots(
        self,
        *,
        run_keys: list[int],
    ) -> subprocess.CompletedProcess[str]:
        command = ["python3", "commands/transform_stage_listing_snapshots.py"]
        for run_key in run_keys:
            command.extend(["--run-key", str(run_key)])
        return self.runner.run(command)

    def run_load_fact_listing_snapshots(self) -> subprocess.CompletedProcess[str]:
        return self.runner.run(["python3", "commands/load_fact_listing_snapshots.py"])

    def run_campaign_analytic_batch(
        self,
        *,
        campaign_id: int,
        chain_ids: list[str],
        business_date: str,
        spread_until_cr: str,
        only_pending: bool,
    ) -> subprocess.CompletedProcess[str]:
        command = [
            "python3",
            "commands/run_campaign_analytic_batch.py",
            "--campaign-id",
            str(campaign_id),
            "--business-date",
            business_date,
            "--spread-until-cr",
            spread_until_cr,
        ]
        for chain_id in chain_ids:
            command.extend(["--chain-id", chain_id])
        if only_pending:
            command.append("--only-pending")

        return self.runner.run(command)

