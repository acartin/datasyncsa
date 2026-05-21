from market_watch_orchestration.price_scrapper.postgres_runner import PostgresRunner


class MarketWatchRepository:
    """SQL queries used by Market Watch orchestration."""

    def __init__(self, *, postgres: PostgresRunner) -> None:
        self.postgres = postgres

    def discover_active_campaign_extract_groups(self) -> list[dict[str, object]]:
        output = self.postgres.run(
            """
select
  camp.id,
  c.engine,
  string_agg(distinct c.chain_id, ',' order by c.chain_id) as chain_ids
from public.mkt_dim_campaign camp
join public.mkt_campaign_location cl
  on cl.campaign_id = camp.id
join public.mkt_dim_location l
  on l.location_key = cl.location_key
join public.mkt_dim_chain c
  on c.chain_key = l.chain_key
where camp.is_active = true
  and l.is_active = true
group by camp.id, c.engine
order by camp.id, c.engine;
"""
        )
        groups: list[dict[str, object]] = []
        for line in output.splitlines():
            if not line.strip():
                continue
            campaign_id_text, engine, chain_ids_text = line.split("\t", 2)
            chain_ids = [chain_id for chain_id in chain_ids_text.split(",") if chain_id]
            groups.append(
                {
                    "campaign_id": int(campaign_id_text),
                    "engine": engine,
                    "chain_ids": chain_ids,
                }
            )
        return groups

    def reset_transform_stage_tables(self) -> None:
        self.postgres.run(
            """
begin;
truncate table public.mkt_stage_product_candidate restart identity;
truncate table public.mkt_stage_product_review restart identity;
truncate table public.mkt_stage_listing_candidate restart identity;
truncate table public.mkt_stage_listing_review restart identity;
truncate table public.mkt_stage_listing_snapshot_candidate restart identity;
truncate table public.mkt_stage_listing_snapshot_review restart identity;
commit;
"""
        )

    def collect_successful_analytic_run_keys(
        self,
        *,
        campaign_ids: list[int],
        business_date: str,
    ) -> list[int]:
        if not campaign_ids:
            return []
        campaign_ids_sql = ", ".join(str(int(campaign_id)) for campaign_id in sorted(set(campaign_ids)))
        output = self.postgres.run(
            f"""
select r.run_key
from public.mkt_run r
where r.run_kind = 'analytic'
  and r.run_status = 'succeeded'
  and r.business_date_key = to_char(date '{business_date}', 'YYYYMMDD')::int
  and r.campaign_id in ({campaign_ids_sql})
order by r.run_key;
"""
        )
        return [int(line.strip()) for line in output.splitlines() if line.strip()]

    def validate_analytic_run_keys(self, *, run_keys: list[int]) -> dict[str, int]:
        if not run_keys:
            return {
                "run_count": 0,
                "stage_items": 0,
                "fact_rows": 0,
                "stage_minus_fact": 0,
                "duplicate_facts": 0,
                "suspect_runs": 0,
            }

        run_keys_sql = ", ".join(str(int(run_key)) for run_key in sorted(set(run_keys)))
        output = self.postgres.run(
            f"""
with selected_runs as (
  select r.run_key
  from public.mkt_run r
  where r.run_key in ({run_keys_sql})
), stage as (
  select run_key, count(*) as stage_items
  from public.mkt_stage_catalog_item
  where run_key in (select run_key from selected_runs)
  group by run_key
), facts as (
  select run_key, count(*) as fact_rows
  from public.mkt_fact_listing_snapshot
  where run_key in (select run_key from selected_runs)
  group by run_key
), duplicate_facts as (
  select count(*) as duplicate_groups
  from (
    select date_key, run_key, listing_key
    from public.mkt_fact_listing_snapshot
    where run_key in (select run_key from selected_runs)
    group by date_key, run_key, listing_key
    having count(*) > 1
  ) d
), rollup as (
  select
    count(*) as run_count,
    coalesce(sum(stage.stage_items), 0) as stage_items,
    coalesce(sum(facts.fact_rows), 0) as fact_rows,
    coalesce(sum(stage.stage_items), 0) - coalesce(sum(facts.fact_rows), 0) as stage_minus_fact,
    count(*) filter (
      where coalesce(stage.stage_items, 0) > 0
        and coalesce(facts.fact_rows, 0) = 0
    ) as suspect_runs
  from selected_runs
  left join stage on stage.run_key = selected_runs.run_key
  left join facts on facts.run_key = selected_runs.run_key
)
select
  rollup.run_count,
  rollup.stage_items,
  rollup.fact_rows,
  rollup.stage_minus_fact,
  duplicate_facts.duplicate_groups,
  rollup.suspect_runs
from rollup
cross join duplicate_facts;
"""
        )
        if not output:
            raise RuntimeError("No se pudo validar run_keys analiticos.")
        fields = output.splitlines()[-1].split("\t")
        return {
            "run_count": int(fields[0]),
            "stage_items": int(fields[1]),
            "fact_rows": int(fields[2]),
            "stage_minus_fact": int(fields[3]),
            "duplicate_facts": int(fields[4]),
            "suspect_runs": int(fields[5]),
        }

