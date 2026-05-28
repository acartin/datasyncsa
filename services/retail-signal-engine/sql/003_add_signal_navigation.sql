alter table public.mkt_client_signal
  add column if not exists navigation_json jsonb not null default '{}'::jsonb;
