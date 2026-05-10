begin;

create table if not exists public.mkt_dim_listing (
  listing_key bigint generated always as identity primary key,
  chain_key integer not null references public.mkt_dim_chain(chain_key),
  product_key bigint not null references public.mkt_dim_product(product_key),
  source_product_id text not null,
  source_sku text not null,
  seller_id text not null default '',
  seller_name text,
  listing_name text not null,
  product_url text,
  image_url text,
  root_category_slug text,
  root_category_name text,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint mkt_dim_listing_listing_name_chk
    check (length(btrim(listing_name)) > 0),

  constraint mkt_dim_listing_natural_uk
    unique (chain_key, source_product_id, source_sku, seller_id)
);

create index if not exists mkt_dim_listing_product_idx
  on public.mkt_dim_listing (product_key);

create index if not exists mkt_dim_listing_chain_idx
  on public.mkt_dim_listing (chain_key);

create index if not exists mkt_dim_listing_root_category_idx
  on public.mkt_dim_listing (root_category_slug);

comment on table public.mkt_dim_listing is
  'Publicación específica de un producto canónico dentro de una cadena.';

comment on column public.mkt_dim_listing.seller_id is
  'Identificador técnico de seller/publicación. Usa cadena vacía si la fuente no lo provee.';


create table if not exists public.mkt_stage_listing_candidate (
  stage_listing_candidate_key bigint generated always as identity primary key,
  preferred_stage_catalog_item_key bigint not null
    references public.mkt_stage_catalog_item(stage_catalog_item_key),
  chain_key integer not null references public.mkt_dim_chain(chain_key),
  product_key bigint not null references public.mkt_dim_product(product_key),
  source_product_id text not null,
  source_sku text not null,
  seller_id text not null default '',
  seller_name text,
  listing_name text not null,
  product_url text,
  image_url text,
  root_category_slug text,
  root_category_name text,
  source_row_count integer not null,
  source_stage_catalog_run_keys jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint mkt_stage_listing_candidate_listing_name_chk
    check (length(btrim(listing_name)) > 0),

  constraint mkt_stage_listing_candidate_counts_chk
    check (source_row_count > 0),

  constraint mkt_stage_listing_candidate_source_run_keys_array_chk
    check (jsonb_typeof(source_stage_catalog_run_keys) = 'array'),

  constraint mkt_stage_listing_candidate_natural_uk
    unique (chain_key, source_product_id, source_sku, seller_id)
);

create index if not exists mkt_stage_listing_candidate_product_idx
  on public.mkt_stage_listing_candidate (product_key);

create index if not exists mkt_stage_listing_candidate_preferred_item_idx
  on public.mkt_stage_listing_candidate (preferred_stage_catalog_item_key);

comment on table public.mkt_stage_listing_candidate is
  'Salida transformada desde mkt_stage_catalog_item hacia listings auto-cargables.';


create table if not exists public.mkt_stage_listing_review (
  stage_listing_review_key bigint generated always as identity primary key,
  review_reason text not null,
  chain_key integer not null references public.mkt_dim_chain(chain_key),
  source_product_id text not null,
  source_sku text not null,
  seller_id text not null default '',
  seller_name text,
  sample_listing_name text not null,
  source_row_count integer not null,
  source_stage_catalog_run_keys jsonb not null default '[]'::jsonb,
  review_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint mkt_stage_listing_review_reason_chk
    check (review_reason in ('missing_product_match')),

  constraint mkt_stage_listing_review_listing_name_chk
    check (length(btrim(sample_listing_name)) > 0),

  constraint mkt_stage_listing_review_counts_chk
    check (source_row_count > 0),

  constraint mkt_stage_listing_review_source_run_keys_array_chk
    check (jsonb_typeof(source_stage_catalog_run_keys) = 'array'),

  constraint mkt_stage_listing_review_payload_obj_chk
    check (jsonb_typeof(review_payload) = 'object')
);

create index if not exists mkt_stage_listing_review_reason_idx
  on public.mkt_stage_listing_review (review_reason);

create index if not exists mkt_stage_listing_review_chain_idx
  on public.mkt_stage_listing_review (chain_key);

comment on table public.mkt_stage_listing_review is
  'Casos de revisión manual detectados al transformar stage hacia listings.';

commit;
