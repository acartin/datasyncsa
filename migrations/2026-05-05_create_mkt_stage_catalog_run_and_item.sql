begin;

create table if not exists public.mkt_stage_catalog_run (
  stage_catalog_run_key bigint generated always as identity primary key,
  chain_key integer not null references public.mkt_dim_chain(chain_key),
  location_key bigint references public.mkt_dim_location(location_key),
  source_engine text not null,
  pricing_scope text not null,
  catalog_id text,
  run_status text not null,
  started_at timestamptz not null,
  finished_at timestamptz,
  elapsed_seconds numeric(12,3),
  catalog_records integer not null default 0,
  unique_products integer,
  duplicates_skipped integer not null default 0,
  debug_output_dir text,
  error_message text,
  raw_metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint mkt_stage_catalog_run_source_engine_chk
    check (source_engine in ('vtex', 'instaleap')),

  constraint mkt_stage_catalog_run_pricing_scope_chk
    check (
      pricing_scope in (
        'chain_public_online',
        'default_store_online',
        'physical_store_online'
      )
    ),

  constraint mkt_stage_catalog_run_status_chk
    check (run_status in ('running', 'succeeded', 'failed')),

  constraint mkt_stage_catalog_run_catalog_records_chk
    check (catalog_records >= 0),

  constraint mkt_stage_catalog_run_duplicates_chk
    check (duplicates_skipped >= 0),

  constraint mkt_stage_catalog_run_raw_metadata_obj_chk
    check (jsonb_typeof(raw_metadata) = 'object')
);

create index if not exists mkt_stage_catalog_run_chain_started_idx
  on public.mkt_stage_catalog_run (chain_key, started_at desc);

create index if not exists mkt_stage_catalog_run_status_idx
  on public.mkt_stage_catalog_run (run_status, started_at desc);

create index if not exists mkt_stage_catalog_run_location_idx
  on public.mkt_stage_catalog_run (location_key);

comment on table public.mkt_stage_catalog_run is
  'Stage append-only de corridas de extraccion de catalogo. Fuente operativa para ETL antes de poblar dimensiones/facts.';

comment on column public.mkt_stage_catalog_run.location_key is
  'Location opcional asociada a la extraccion cuando aplique. Para catalogos chain-level puede quedar null.';

comment on column public.mkt_stage_catalog_run.debug_output_dir is
  'Directorio opcional donde se escribieron artifacts JSON de debug si la corrida lo solicito.';

create table if not exists public.mkt_stage_catalog_item (
  stage_catalog_item_key bigint generated always as identity primary key,
  stage_catalog_run_key bigint not null references public.mkt_stage_catalog_run(stage_catalog_run_key) on delete cascade,
  chain_key integer not null references public.mkt_dim_chain(chain_key),
  catalog_row_number integer not null,
  catalog_id text,
  pricing_scope text,
  source_product_id text not null,
  source_sku text not null,
  source_gtin text,
  product_reference text,
  reference_id text,
  brand_name text,
  brand_id text,
  seller_id text,
  seller_name text,
  root_category_slug text,
  root_category_name text,
  category_id text,
  category_path text,
  raw_categories jsonb not null default '[]'::jsonb,
  product_name text not null,
  product_description text,
  product_url text,
  image_url text,
  quantity numeric(14,4),
  unit text,
  measurement_unit text,
  unit_multiplier numeric(14,4),
  currency_code char(3),
  price_amount numeric(12,2),
  list_price_amount numeric(12,2),
  price_without_discount_amount numeric(12,2),
  spot_price_amount numeric(12,2),
  has_discount boolean not null default false,
  price_valid_until_text text,
  available_quantity numeric(14,3),
  raw_payload jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint mkt_stage_catalog_item_run_row_uk
    unique (stage_catalog_run_key, catalog_row_number),

  constraint mkt_stage_catalog_item_source_identity_uk
    unique (stage_catalog_run_key, source_product_id, source_sku),

  constraint mkt_stage_catalog_item_product_name_chk
    check (length(btrim(product_name)) > 0),

  constraint mkt_stage_catalog_item_raw_categories_array_chk
    check (jsonb_typeof(raw_categories) = 'array'),

  constraint mkt_stage_catalog_item_raw_payload_obj_chk
    check (jsonb_typeof(raw_payload) = 'object')
);

create index if not exists mkt_stage_catalog_item_run_idx
  on public.mkt_stage_catalog_item (stage_catalog_run_key);

create index if not exists mkt_stage_catalog_item_chain_gtin_idx
  on public.mkt_stage_catalog_item (chain_key, source_gtin);

create index if not exists mkt_stage_catalog_item_chain_brand_idx
  on public.mkt_stage_catalog_item (chain_key, brand_name);

create index if not exists mkt_stage_catalog_item_chain_category_idx
  on public.mkt_stage_catalog_item (chain_key, root_category_slug);

comment on table public.mkt_stage_catalog_item is
  'Stage append-only de items extraidos en una corrida de catalogo. Mantiene payload crudo canonico antes de cargas dimensionales.';

comment on column public.mkt_stage_catalog_item.source_gtin is
  'GTIN/EAN normalizado por el scraper. No implica automaticamente unicidad canónica global.';

comment on column public.mkt_stage_catalog_item.price_valid_until_text is
  'Valor textual de vigencia de precio tal como quedo normalizado por el scraper. Se parsea despues en transform.';

commit;
