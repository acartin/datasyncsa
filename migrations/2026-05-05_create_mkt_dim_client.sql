begin;

create table if not exists public.mkt_dim_client (
  id bigint generated always as identity primary key,
  name text not null,
  country_id integer,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz,
  slug text not null,

  constraint mkt_dim_client_name_chk
    check (length(btrim(name)) > 0),

  constraint mkt_dim_client_slug_chk
    check (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'),

  constraint mkt_dim_client_slug_uk
    unique (slug)
);

create index if not exists mkt_dim_client_country_idx
  on public.mkt_dim_client (country_id);

create index if not exists mkt_dim_client_deleted_idx
  on public.mkt_dim_client (deleted_at);

comment on table public.mkt_dim_client is
  'Dimension de clientes para asociar corridas y campañas de market intelligence.';

comment on column public.mkt_dim_client.country_id is
  'Identificador entero del país del cliente. Por ahora se mantiene sin foreign key porque no existe un catálogo de países en esta BD.';

comment on column public.mkt_dim_client.deleted_at is
  'Soft delete timestamp. Si es null, el cliente sigue activo.';

comment on column public.mkt_dim_client.slug is
  'Slug estable y único del cliente para referencias operativas y APIs internas.';

commit;
