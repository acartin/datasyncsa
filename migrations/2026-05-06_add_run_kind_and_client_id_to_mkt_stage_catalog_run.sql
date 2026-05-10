begin;

alter table public.mkt_stage_catalog_run
  add column if not exists run_kind text;

update public.mkt_stage_catalog_run
set run_kind = 'comparative'
where run_kind is null;

alter table public.mkt_stage_catalog_run
  alter column run_kind set default 'comparative';

alter table public.mkt_stage_catalog_run
  alter column run_kind set not null;

alter table public.mkt_stage_catalog_run
  drop constraint if exists mkt_stage_catalog_run_kind_chk;

alter table public.mkt_stage_catalog_run
  add constraint mkt_stage_catalog_run_kind_chk
  check (run_kind in ('comparative', 'analytic'));

alter table public.mkt_stage_catalog_run
  add column if not exists client_id bigint;

alter table public.mkt_stage_catalog_run
  drop constraint if exists mkt_stage_catalog_run_client_id_fkey;

alter table public.mkt_stage_catalog_run
  add constraint mkt_stage_catalog_run_client_id_fkey
  foreign key (client_id) references public.mkt_dim_client(id);

create index if not exists mkt_stage_catalog_run_kind_started_idx
  on public.mkt_stage_catalog_run (run_kind, started_at desc);

create index if not exists mkt_stage_catalog_run_client_idx
  on public.mkt_stage_catalog_run (client_id);

comment on column public.mkt_stage_catalog_run.run_kind is
  'Tipo operativo de corrida: comparative para comparadores full-catalog, analytic para subsets orientados a BI.';

comment on column public.mkt_stage_catalog_run.client_id is
  'Cliente opcional que solicitó la corrida.';

commit;
