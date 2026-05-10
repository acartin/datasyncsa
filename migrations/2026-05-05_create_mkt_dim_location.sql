begin;

create table if not exists public.mkt_dim_location (
  location_key bigint generated always as identity primary key,
  chain_key integer not null references public.mkt_dim_chain(chain_key),
  location_code text not null,
  source_engine text not null,
  source_location_ref text,
  source_internal_id text,
  location_name text not null,
  location_type text not null default 'physical_store',
  sales_channel text,
  region_id text,
  address_text text,
  province text,
  canton text,
  district text,
  postal_code text,
  latitude numeric(9,6),
  longitude numeric(9,6),
  phone text,
  is_default boolean not null default false,
  is_active boolean not null default true,
  source_origin text not null,
  source_payload jsonb not null default '{}'::jsonb,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint mkt_dim_location_chain_code_uk
    unique (chain_key, location_code),

  constraint mkt_dim_location_location_code_chk
    check (location_code ~ '^[a-z0-9_-]+$'),

  constraint mkt_dim_location_source_engine_chk
    check (source_engine in ('vtex', 'instaleap')),

  constraint mkt_dim_location_location_type_chk
    check (location_type in ('physical_store', 'distribution_store', 'online_store')),

  constraint mkt_dim_location_source_origin_chk
    check (source_origin in ('engine_api', 'chain_site_page')),

  constraint mkt_dim_location_location_name_chk
    check (length(btrim(location_name)) > 0),

  constraint mkt_dim_location_postal_code_chk
    check (postal_code is null or postal_code ~ '^[0-9A-Za-z -]+$'),

  constraint mkt_dim_location_source_payload_obj_chk
    check (jsonb_typeof(source_payload) = 'object')
);

create index if not exists mkt_dim_location_chain_idx
  on public.mkt_dim_location (chain_key);

create index if not exists mkt_dim_location_active_idx
  on public.mkt_dim_location (is_active);

create index if not exists mkt_dim_location_chain_active_idx
  on public.mkt_dim_location (chain_key, is_active);

create index if not exists mkt_dim_location_source_ref_idx
  on public.mkt_dim_location (source_location_ref);

comment on table public.mkt_dim_location is
  'Dimensión de locations por cadena. Distingue sucursales físicas, nodos de distribución y contextos online.';

comment on column public.mkt_dim_location.location_code is
  'Código canónico estable dentro de la cadena para hacer upsert idempotente.';

comment on column public.mkt_dim_location.source_location_ref is
  'Referencia original expuesta por la fuente cuando existe, por ejemplo sellerId VTEX o storeReference Instaleap.';

comment on column public.mkt_dim_location.source_internal_id is
  'Identificador interno secundario de la fuente cuando existe, por ejemplo storeId Instaleap.';

commit;
