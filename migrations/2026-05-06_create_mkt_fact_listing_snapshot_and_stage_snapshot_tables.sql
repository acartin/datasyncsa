begin;

create table if not exists public.mkt_stage_listing_snapshot_candidate (
  stage_listing_snapshot_candidate_key bigint generated always as identity primary key,
  source_stage_catalog_item_key bigint not null
    references public.mkt_stage_catalog_item(stage_catalog_item_key),
  stage_catalog_run_key bigint not null
    references public.mkt_stage_catalog_run(stage_catalog_run_key) on delete cascade,
  date_key integer not null
    references public.mkt_dim_date(date_key),
  chain_key integer not null
    references public.mkt_dim_chain(chain_key),
  location_key bigint
    references public.mkt_dim_location(location_key),
  product_key bigint not null
    references public.mkt_dim_product(product_key),
  listing_key bigint not null
    references public.mkt_dim_listing(listing_key),
  snapshot_ts timestamptz not null,
  currency_code char(3),
  is_listed boolean not null default true,
  is_available boolean,
  has_discount boolean not null default false,
  price_amount numeric(12,2),
  list_price_amount numeric(12,2),
  price_without_discount_amount numeric(12,2),
  spot_price_amount numeric(12,2),
  available_quantity numeric(14,3),
  price_valid_until_text text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint mkt_stage_listing_snapshot_candidate_run_listing_uk
    unique (stage_catalog_run_key, listing_key)
);

create index if not exists mkt_stage_listing_snapshot_candidate_date_idx
  on public.mkt_stage_listing_snapshot_candidate (date_key);

create index if not exists mkt_stage_listing_snapshot_candidate_listing_idx
  on public.mkt_stage_listing_snapshot_candidate (listing_key);

create index if not exists mkt_stage_listing_snapshot_candidate_product_idx
  on public.mkt_stage_listing_snapshot_candidate (product_key);

comment on table public.mkt_stage_listing_snapshot_candidate is
  'Salida transformada desde mkt_stage_catalog_item hacia snapshots auto-cargables en la fact.';


create table if not exists public.mkt_stage_listing_snapshot_review (
  stage_listing_snapshot_review_key bigint generated always as identity primary key,
  review_reason text not null,
  source_stage_catalog_item_key bigint not null
    references public.mkt_stage_catalog_item(stage_catalog_item_key),
  stage_catalog_run_key bigint not null
    references public.mkt_stage_catalog_run(stage_catalog_run_key) on delete cascade,
  chain_key integer not null
    references public.mkt_dim_chain(chain_key),
  source_product_id text not null,
  source_sku text not null,
  seller_id text not null default '',
  seller_name text,
  sample_listing_name text not null,
  source_gtin text,
  snapshot_ts timestamptz not null,
  review_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint mkt_stage_listing_snapshot_review_reason_chk
    check (review_reason in ('missing_listing_match')),

  constraint mkt_stage_listing_snapshot_review_payload_obj_chk
    check (jsonb_typeof(review_payload) = 'object')
);

create index if not exists mkt_stage_listing_snapshot_review_reason_idx
  on public.mkt_stage_listing_snapshot_review (review_reason);

create index if not exists mkt_stage_listing_snapshot_review_run_idx
  on public.mkt_stage_listing_snapshot_review (stage_catalog_run_key);

comment on table public.mkt_stage_listing_snapshot_review is
  'Casos de revisión manual detectados al transformar stage hacia snapshots factibles.';


create table if not exists public.mkt_fact_listing_snapshot (
  date_key integer not null
    references public.mkt_dim_date(date_key),
  stage_catalog_run_key bigint not null
    references public.mkt_stage_catalog_run(stage_catalog_run_key) on delete cascade,
  chain_key integer not null
    references public.mkt_dim_chain(chain_key),
  location_key bigint
    references public.mkt_dim_location(location_key),
  product_key bigint not null
    references public.mkt_dim_product(product_key),
  listing_key bigint not null
    references public.mkt_dim_listing(listing_key),
  source_stage_catalog_item_key bigint not null
    references public.mkt_stage_catalog_item(stage_catalog_item_key),
  snapshot_ts timestamptz not null,
  currency_code char(3),
  is_listed boolean not null default true,
  is_available boolean,
  has_discount boolean not null default false,
  price_amount numeric(12,2),
  list_price_amount numeric(12,2),
  price_without_discount_amount numeric(12,2),
  spot_price_amount numeric(12,2),
  available_quantity numeric(14,3),
  price_valid_until_text text,
  created_at timestamptz not null default now(),

  constraint mkt_fact_listing_snapshot_pkey
    primary key (date_key, stage_catalog_run_key, listing_key)
) partition by range (date_key);

create table if not exists public.mkt_fact_listing_snapshot_202605
  partition of public.mkt_fact_listing_snapshot
  for values from (20260501) to (20260601);

create table if not exists public.mkt_fact_listing_snapshot_default
  partition of public.mkt_fact_listing_snapshot
  default;

create index if not exists mkt_fact_listing_snapshot_chain_date_idx
  on public.mkt_fact_listing_snapshot (chain_key, date_key);

create index if not exists mkt_fact_listing_snapshot_product_date_idx
  on public.mkt_fact_listing_snapshot (product_key, date_key);

create index if not exists mkt_fact_listing_snapshot_listing_date_idx
  on public.mkt_fact_listing_snapshot (listing_key, date_key);

comment on table public.mkt_fact_listing_snapshot is
  'Snapshot de precio y existencia por listing observado en una corrida.';

comment on column public.mkt_fact_listing_snapshot.date_key is
  'Fecha de negocio derivada en America/Costa_Rica a partir de snapshot_ts.';

commit;
