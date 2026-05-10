begin;

do $$
begin
  if to_regclass('public.mkt_run') is null
     and to_regclass('public.mkt_stage_catalog_run') is not null then
    execute 'alter table public.mkt_stage_catalog_run rename to mkt_run';
  end if;
end $$;

do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'mkt_run'
      and column_name = 'stage_catalog_run_key'
  ) and not exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'mkt_run'
      and column_name = 'run_key'
  ) then
    execute 'alter table public.mkt_run rename column stage_catalog_run_key to run_key';
  end if;
end $$;

do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'mkt_stage_catalog_item'
      and column_name = 'stage_catalog_run_key'
  ) and not exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'mkt_stage_catalog_item'
      and column_name = 'run_key'
  ) then
    execute 'alter table public.mkt_stage_catalog_item rename column stage_catalog_run_key to run_key';
  end if;
end $$;

do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'mkt_stage_listing_snapshot_candidate'
      and column_name = 'stage_catalog_run_key'
  ) and not exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'mkt_stage_listing_snapshot_candidate'
      and column_name = 'run_key'
  ) then
    execute 'alter table public.mkt_stage_listing_snapshot_candidate rename column stage_catalog_run_key to run_key';
  end if;
end $$;

do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'mkt_stage_listing_snapshot_review'
      and column_name = 'stage_catalog_run_key'
  ) and not exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'mkt_stage_listing_snapshot_review'
      and column_name = 'run_key'
  ) then
    execute 'alter table public.mkt_stage_listing_snapshot_review rename column stage_catalog_run_key to run_key';
  end if;
end $$;

do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'mkt_fact_listing_snapshot'
      and column_name = 'stage_catalog_run_key'
  ) and not exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'mkt_fact_listing_snapshot'
      and column_name = 'run_key'
  ) then
    execute 'alter table public.mkt_fact_listing_snapshot rename column stage_catalog_run_key to run_key';
  end if;
end $$;

alter table public.mkt_fact_listing_snapshot
  drop constraint if exists mkt_fact_listing_snapshot_source_stage_catalog_item_key_fkey;

comment on table public.mkt_run is
  'Bitácora persistente de corridas ETL. No forma parte del stage temporal.';

comment on column public.mkt_fact_listing_snapshot.source_stage_catalog_item_key is
  'Referencia opcional al item de stage que originó el snapshot. Se conserva solo para trazabilidad y no debe bloquear truncados del stage.';

commit;
