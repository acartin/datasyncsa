create table if not exists public.mkt_user_table_view (
  table_view_id bigserial primary key,
  client_id bigint not null,
  user_id bigint not null,
  view_key text not null,
  label text not null,
  icon text,
  color text,
  scope text not null default 'private',
  is_favorite boolean not null default true,
  view_order int not null default 0,
  state jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint mkt_user_table_view_scope_check
    check (scope in ('private', 'shared', 'global'))
);

create index if not exists idx_mkt_user_table_view_user
  on public.mkt_user_table_view (client_id, user_id, view_key, is_favorite, view_order);

create index if not exists idx_mkt_user_table_view_state
  on public.mkt_user_table_view using gin (state);
