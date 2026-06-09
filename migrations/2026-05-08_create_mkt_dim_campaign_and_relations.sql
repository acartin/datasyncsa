begin;

create table if not exists public.mkt_dim_campaign (
  id bigint generated always as identity primary key,
  name text not null,
  slug text not null,
  description text null,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz null,
  constraint mkt_dim_campaign_name_chk
    check (length(btrim(name)) > 0),
  constraint mkt_dim_campaign_slug_chk
    check (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$')
);

create unique index if not exists mkt_dim_campaign_slug_uk
  on public.mkt_dim_campaign (slug);

create index if not exists mkt_dim_campaign_is_active_idx
  on public.mkt_dim_campaign (is_active);

create table if not exists public.mkt_campaign_product (
  campaign_id bigint not null references public.mkt_dim_campaign(id) on delete cascade,
  product_key bigint not null references public.mkt_dim_product(product_key),
  product_role text not null default 'tracked',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint mkt_campaign_product_role_chk
    check (product_role in ('owned', 'competitor', 'tracked', 'reference')),
  primary key (campaign_id, product_key)
);

create index if not exists mkt_campaign_product_product_key_idx
  on public.mkt_campaign_product (product_key);

create index if not exists mkt_campaign_product_role_idx
  on public.mkt_campaign_product (product_role);

create table if not exists public.mkt_campaign_location (
  campaign_id bigint not null references public.mkt_dim_campaign(id) on delete cascade,
  location_key bigint not null references public.mkt_dim_location(location_key),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (campaign_id, location_key)
);

create index if not exists mkt_campaign_location_location_key_idx
  on public.mkt_campaign_location (location_key);

alter table public.mkt_run
  add column if not exists campaign_id bigint null references public.mkt_dim_campaign(id);

create index if not exists mkt_run_campaign_id_idx
  on public.mkt_run (campaign_id);

comment on table public.mkt_dim_campaign is
  'Campañas de monitoreo comercial. Definen el universo objetivo para corridas analíticas; el acceso por cliente se administra en mkt_campaign_client_access.';

comment on table public.mkt_campaign_product is
  'Relación entre campaña y productos canónicos incluidos en el monitoreo.';

comment on table public.mkt_campaign_location is
  'Relación entre campaña y locations incluidas en el monitoreo analítico.';

commit;
