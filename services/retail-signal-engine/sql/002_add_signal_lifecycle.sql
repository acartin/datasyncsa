alter table public.mkt_market_event
  add column if not exists event_fingerprint_key text;

update public.mkt_market_event
set event_fingerprint_key = event_key
where event_fingerprint_key is null;

alter table public.mkt_market_event
  alter column event_fingerprint_key set not null;

create index if not exists idx_mkt_market_event_fingerprint_date
  on public.mkt_market_event (event_fingerprint_key, date_key desc);

alter table public.mkt_client_signal
  add column if not exists fingerprint_key text,
  add column if not exists previous_client_signal_id bigint,
  add column if not exists lifecycle_status text not null default 'new',
  add column if not exists delta_metrics_json jsonb not null default '{}'::jsonb,
  add column if not exists navigation_json jsonb not null default '{}'::jsonb,
  add column if not exists first_detected_at timestamptz not null default now(),
  add column if not exists previous_detected_at timestamptz,
  add column if not exists last_detected_at timestamptz not null default now(),
  add column if not exists repeat_count integer not null default 1,
  add column if not exists notification_status text not null default 'not_scheduled',
  add column if not exists notification_reason text,
  add column if not exists last_notified_at timestamptz,
  add column if not exists last_notification_channel text,
  add column if not exists last_delivery_id text;

update public.mkt_client_signal
set
  fingerprint_key = coalesce(fingerprint_key, signal_key),
  first_detected_at = coalesce(first_detected_at, generated_at, now()),
  last_detected_at = coalesce(last_detected_at, generated_at, now())
where fingerprint_key is null
   or first_detected_at is null
   or last_detected_at is null;

alter table public.mkt_client_signal
  alter column fingerprint_key set not null,
  alter column first_detected_at set not null,
  alter column last_detected_at set not null;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'fk_mkt_client_signal_previous'
  ) then
    alter table public.mkt_client_signal
      add constraint fk_mkt_client_signal_previous
      foreign key (previous_client_signal_id)
      references public.mkt_client_signal(client_signal_id)
      on delete set null;
  end if;
end $$;

create index if not exists idx_mkt_client_signal_fingerprint_date
  on public.mkt_client_signal (fingerprint_key, date_key desc);

create index if not exists idx_mkt_client_signal_notification
  on public.mkt_client_signal (notification_status, date_key, campaign_id);

create table if not exists public.mkt_signal_delivery (
  signal_delivery_id bigserial primary key,
  client_signal_id bigint not null references public.mkt_client_signal(client_signal_id),
  signal_key text not null,
  delivery_channel text not null,
  delivery_format text,
  delivery_status text not null default 'pending',
  delivery_target text,
  delivery_ref text,
  scheduled_at timestamptz,
  sent_at timestamptz,
  error_message text,
  metadata_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_mkt_signal_delivery_signal
  on public.mkt_signal_delivery (client_signal_id, delivery_channel, delivery_status);

create index if not exists idx_mkt_signal_delivery_status
  on public.mkt_signal_delivery (delivery_status, scheduled_at);
