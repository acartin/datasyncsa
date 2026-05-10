begin;

alter table public.mkt_run
add column if not exists business_date_key integer;

update public.mkt_run
set business_date_key = cast(to_char(started_at at time zone 'America/Costa_Rica', 'YYYYMMDD') as integer)
where business_date_key is null;

alter table public.mkt_run
alter column business_date_key set not null;

alter table public.mkt_run
add constraint mkt_run_business_date_key_fkey
foreign key (business_date_key)
references public.mkt_dim_date(date_key);

comment on column public.mkt_run.business_date_key is
'Fecha de negocio diaria en America/Costa_Rica usada para segmentacion e idempotencia operativa.';

create index if not exists mkt_run_business_date_kind_idx
on public.mkt_run (business_date_key, run_kind, chain_key, location_key);

create unique index if not exists mkt_run_daily_success_unique_idx
on public.mkt_run (
  business_date_key,
  run_kind,
  chain_key,
  coalesce(location_key, -1),
  coalesce(campaign_id, -1)
)
where run_status = 'succeeded';

commit;
