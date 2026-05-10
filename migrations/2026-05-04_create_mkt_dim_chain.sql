begin;

create table if not exists public.mkt_dim_chain (
  chain_key integer generated always as identity primary key,
  chain_id text not null unique,
  chain_name text not null,
  short_label text,
  catalog_id text,
  base_url text not null,
  engine text not null,
  pricing_scope text not null,
  country_code char(2) not null default 'CR',
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint mkt_dim_chain_chain_id_chk
    check (chain_id ~ '^[a-z0-9_]+$'),

  constraint mkt_dim_chain_engine_chk
    check (engine in ('vtex', 'instaleap')),

  constraint mkt_dim_chain_pricing_scope_chk
    check (
      pricing_scope in (
        'chain_public_online',
        'default_store_online',
        'physical_store_online'
      )
    ),

  constraint mkt_dim_chain_chain_name_chk
    check (length(btrim(chain_name)) > 0),

  constraint mkt_dim_chain_base_url_chk
    check (base_url ~ '^https?://')
);

comment on table public.mkt_dim_chain is
  'Dimension de cadenas comerciales para analitica de market/pricing.';

comment on column public.mkt_dim_chain.chain_id is
  'Identificador canonico de cadena usado por el price-scrapper y su runtime ETL.';

comment on column public.mkt_dim_chain.engine is
  'Motor tecnico de origen actual de la cadena, por ejemplo vtex o instaleap.';

insert into public.mkt_dim_chain (
  chain_id,
  chain_name,
  short_label,
  catalog_id,
  base_url,
  engine,
  pricing_scope,
  country_code,
  is_active
)
values
  (
    'masxmenos_cr',
    'Más x Menos Costa Rica',
    'Más x Menos',
    'masxmenos_cr_catalog',
    'https://www.masxmenos.cr',
    'vtex',
    'chain_public_online',
    'CR',
    true
  ),
  (
    'maxi_pali_cr',
    'Maxi Palí Costa Rica',
    'Maxi Palí',
    'maxi_pali_cr_catalog',
    'https://www.maxipali.co.cr',
    'vtex',
    'chain_public_online',
    'CR',
    true
  ),
  (
    'megasuper_cr',
    'Megasuper Costa Rica',
    'Megasuper',
    'megasuper_cr_catalog',
    'https://www.megasuper.com',
    'instaleap',
    'default_store_online',
    'CR',
    true
  ),
  (
    'walmart_cr',
    'Walmart Costa Rica',
    'Walmart',
    'walmart_cr_catalog',
    'https://www.walmart.co.cr',
    'vtex',
    'chain_public_online',
    'CR',
    true
  )
on conflict (chain_id) do update
set
  chain_name = excluded.chain_name,
  short_label = excluded.short_label,
  catalog_id = excluded.catalog_id,
  base_url = excluded.base_url,
  engine = excluded.engine,
  pricing_scope = excluded.pricing_scope,
  country_code = excluded.country_code,
  is_active = excluded.is_active,
  updated_at = now();

commit;
