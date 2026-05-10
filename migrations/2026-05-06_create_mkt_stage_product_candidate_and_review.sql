begin;

create table if not exists public.mkt_stage_product_candidate (
  stage_product_candidate_key bigint generated always as identity primary key,
  preferred_stage_catalog_item_key bigint not null
    references public.mkt_stage_catalog_item(stage_catalog_item_key),
  gtin_raw text,
  gtin_norm text not null,
  gtin_type text not null,
  gtin_is_valid boolean not null,
  brand_name text,
  product_name text not null,
  normalized_name text not null,
  content_quantity numeric(14,4),
  content_unit varchar(30),
  source_row_count integer not null,
  source_chain_count integer not null,
  source_chain_ids jsonb not null default '[]'::jsonb,
  source_stage_catalog_run_keys jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint mkt_stage_product_candidate_gtin_norm_digits_chk
    check (gtin_norm ~ '^[0-9]+$'),

  constraint mkt_stage_product_candidate_gtin_type_chk
    check (gtin_type in ('GTIN8', 'GTIN12', 'GTIN13', 'GTIN14')),

  constraint mkt_stage_product_candidate_gtin_valid_chk
    check (gtin_is_valid = true),

  constraint mkt_stage_product_candidate_product_name_chk
    check (length(btrim(product_name)) > 0),

  constraint mkt_stage_product_candidate_counts_chk
    check (source_row_count > 0 and source_chain_count > 0),

  constraint mkt_stage_product_candidate_source_chain_ids_array_chk
    check (jsonb_typeof(source_chain_ids) = 'array'),

  constraint mkt_stage_product_candidate_source_run_keys_array_chk
    check (jsonb_typeof(source_stage_catalog_run_keys) = 'array'),

  constraint mkt_stage_product_candidate_gtin_norm_uk
    unique (gtin_norm)
);

create index if not exists mkt_stage_product_candidate_preferred_item_idx
  on public.mkt_stage_product_candidate (preferred_stage_catalog_item_key);

create index if not exists mkt_stage_product_candidate_brand_name_idx
  on public.mkt_stage_product_candidate (brand_name);

comment on table public.mkt_stage_product_candidate is
  'Salida transformada desde mkt_stage_catalog_item hacia candidatos auto-cargables de mkt_dim_product.';

comment on column public.mkt_stage_product_candidate.preferred_stage_catalog_item_key is
  'Fila stage elegida como representante para poblar el producto canónico.';


create table if not exists public.mkt_stage_product_review (
  stage_product_review_key bigint generated always as identity primary key,
  review_reason text not null,
  gtin_raw text,
  gtin_norm text,
  gtin_type text,
  gtin_is_valid boolean not null,
  source_row_count integer not null,
  source_chain_count integer not null,
  source_chain_ids jsonb not null default '[]'::jsonb,
  source_stage_catalog_run_keys jsonb not null default '[]'::jsonb,
  sample_brand_name text,
  sample_product_name text,
  review_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint mkt_stage_product_review_reason_chk
    check (review_reason in ('invalid_gtin', 'same_chain_collision')),

  constraint mkt_stage_product_review_counts_chk
    check (source_row_count > 0 and source_chain_count > 0),

  constraint mkt_stage_product_review_source_chain_ids_array_chk
    check (jsonb_typeof(source_chain_ids) = 'array'),

  constraint mkt_stage_product_review_source_run_keys_array_chk
    check (jsonb_typeof(source_stage_catalog_run_keys) = 'array'),

  constraint mkt_stage_product_review_payload_obj_chk
    check (jsonb_typeof(review_payload) = 'object')
);

create index if not exists mkt_stage_product_review_reason_idx
  on public.mkt_stage_product_review (review_reason);

create index if not exists mkt_stage_product_review_gtin_norm_idx
  on public.mkt_stage_product_review (gtin_norm);

comment on table public.mkt_stage_product_review is
  'Casos de revisión manual detectados al transformar mkt_stage_catalog_item hacia productos canónicos.';

comment on column public.mkt_stage_product_review.review_payload is
  'Detalle de filas stage que impidieron auto-cargar el producto.';

commit;
