begin;

create temp table tmp_mkt_dim_category_root_seed on commit drop as
select
  chain_key,
  category_slug,
  category_name,
  category_url,
  source_category_reference,
  is_enabled
from public.mkt_dim_category
where is_root_category = true;

drop table if exists public.mkt_dim_category;

create table public.mkt_dim_category (
  category_key bigint generated always as identity primary key,
  chain_key integer not null references public.mkt_dim_chain(chain_key),
  category_slug text not null,
  category_name text not null,
  category_url text,
  source_category_reference text,
  is_enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint mkt_dim_category_chain_slug_uk
    unique (chain_key, category_slug),

  constraint mkt_dim_category_category_name_chk
    check (length(btrim(category_name)) > 0),

  constraint mkt_dim_category_category_url_chk
    check (category_url is null or category_url ~ '^https?://')
);

create index mkt_dim_category_chain_idx
  on public.mkt_dim_category (chain_key);

create index mkt_dim_category_chain_enabled_idx
  on public.mkt_dim_category (chain_key, is_enabled);

comment on table public.mkt_dim_category is
  'Dimensión simple de categorías raíz por cadena. También funciona como configuración operativa de extracción.';

comment on column public.mkt_dim_category.category_slug is
  'Slug estable de la categoría raíz dentro de la cadena.';

comment on column public.mkt_dim_category.source_category_reference is
  'Referencia de categoría raíz del engine cuando aplica, por ejemplo categoryReference de Instaleap.';

comment on column public.mkt_dim_category.is_enabled is
  'Switch operativo simple: si está true la categoría raíz entra al scrape por defecto.';

insert into public.mkt_dim_category (
  chain_key,
  category_slug,
  category_name,
  category_url,
  source_category_reference,
  is_enabled
)
select
  chain_key,
  category_slug,
  category_name,
  category_url,
  source_category_reference,
  is_enabled
from tmp_mkt_dim_category_root_seed
order by chain_key, category_name;

commit;
