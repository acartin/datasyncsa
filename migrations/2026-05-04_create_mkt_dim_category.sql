begin;

create table if not exists public.mkt_dim_category (
  category_key bigint generated always as identity primary key,
  chain_key integer not null references public.mkt_dim_chain(chain_key),
  category_slug text not null,
  category_name text not null,
  category_path text,
  root_category_slug text,
  root_category_name text,
  source_category_id text,
  source_category_reference text,
  category_level smallint,
  is_root_category boolean not null default false,
  is_enabled boolean not null default true,
  source_origin text not null,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint mkt_dim_category_chain_slug_uk
    unique (chain_key, category_slug),

  constraint mkt_dim_category_category_name_chk
    check (length(btrim(category_name)) > 0),

  constraint mkt_dim_category_source_origin_chk
    check (source_origin in ('config_root', 'catalog_observed')),

  constraint mkt_dim_category_level_chk
    check (category_level is null or category_level >= 1)
);

create index if not exists mkt_dim_category_chain_idx
  on public.mkt_dim_category (chain_key);

create index if not exists mkt_dim_category_root_slug_idx
  on public.mkt_dim_category (root_category_slug);

create index if not exists mkt_dim_category_root_flag_idx
  on public.mkt_dim_category (is_root_category);

comment on table public.mkt_dim_category is
  'Categorias del retailer por cadena. Mezcla categorias configuradas raiz y categorias observadas en catalogos scrapeados.';

comment on column public.mkt_dim_category.category_slug is
  'Slug canonico por cadena. Para categorias observadas se deriva del category_path.';

comment on column public.mkt_dim_category.source_origin is
  'Origen del registro: config_root o catalog_observed.';

commit;
