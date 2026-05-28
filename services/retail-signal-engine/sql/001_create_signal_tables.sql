create table if not exists public.mkt_market_event (
  market_event_id bigserial primary key,
  event_key text not null unique,
  event_fingerprint_key text not null,
  event_type text not null,
  event_level text not null default 'raw_signal',
  business_date date not null,
  date_key integer not null,
  client_id bigint,
  campaign_id bigint,
  campaign_name text,
  category text,
  chain text,
  affected_brands jsonb not null default '[]'::jsonb,
  beneficiary_brands jsonb not null default '[]'::jsonb,
  disadvantaged_brands jsonb not null default '[]'::jsonb,
  neutral_entities jsonb not null default '[]'::jsonb,
  severity text not null,
  impact_score numeric(8,2) not null default 0,
  confidence_score numeric(8,2) not null default 0,
  metrics_json jsonb not null default '{}'::jsonb,
  evidence_json jsonb not null default '{}'::jsonb,
  source_view text,
  engine_version text not null,
  generated_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.mkt_market_event
  add column if not exists event_fingerprint_key text;

update public.mkt_market_event
set event_fingerprint_key = event_key
where event_fingerprint_key is null;

alter table public.mkt_market_event
  alter column event_fingerprint_key set not null;

create index if not exists idx_mkt_market_event_date
  on public.mkt_market_event (date_key, campaign_id, event_type);

create index if not exists idx_mkt_market_event_fingerprint_date
  on public.mkt_market_event (event_fingerprint_key, date_key desc);

create index if not exists idx_mkt_market_event_metrics
  on public.mkt_market_event using gin (metrics_json);

create table if not exists public.mkt_client_signal (
  client_signal_id bigserial primary key,
  signal_key text not null unique,
  fingerprint_key text not null,
  market_event_id bigint not null references public.mkt_market_event(market_event_id),
  previous_client_signal_id bigint,
  event_key text not null,
  signal_type text not null,
  signal_level text not null default 'client_signal',
  lifecycle_status text not null default 'new',
  business_date date not null,
  date_key integer not null,
  perspective_client_id bigint,
  campaign_id bigint,
  campaign_name text,
  category text,
  perspective_brand text,
  counterparty_brand text,
  chain text,
  effect text not null,
  audience text not null default 'brand_manager',
  severity text not null,
  impact_score numeric(8,2) not null default 0,
  confidence_score numeric(8,2) not null default 0,
  headline text,
  summary text,
  business_reading text,
  recommended_action text,
  tone text,
  metrics_json jsonb not null default '{}'::jsonb,
  evidence_json jsonb not null default '{}'::jsonb,
  narrative_json jsonb not null default '{}'::jsonb,
  delta_metrics_json jsonb not null default '{}'::jsonb,
  navigation_json jsonb not null default '{}'::jsonb,
  llm_provider text,
  llm_model text,
  llm_prompt_version text,
  first_detected_at timestamptz not null default now(),
  previous_detected_at timestamptz,
  last_detected_at timestamptz not null default now(),
  repeat_count integer not null default 1,
  notification_status text not null default 'not_scheduled',
  notification_reason text,
  last_notified_at timestamptz,
  last_notification_channel text,
  last_delivery_id text,
  engine_version text not null,
  generated_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint fk_mkt_client_signal_previous
    foreign key (previous_client_signal_id)
    references public.mkt_client_signal(client_signal_id)
    on delete set null
);

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
      references public.mkt_client_signal(client_signal_id);
  end if;
end $$;

create index if not exists idx_mkt_client_signal_date
  on public.mkt_client_signal (date_key, campaign_id, perspective_brand, signal_type);

create index if not exists idx_mkt_client_signal_fingerprint_date
  on public.mkt_client_signal (fingerprint_key, date_key desc);

create index if not exists idx_mkt_client_signal_event
  on public.mkt_client_signal (market_event_id);

create index if not exists idx_mkt_client_signal_notification
  on public.mkt_client_signal (notification_status, date_key, campaign_id);

create index if not exists idx_mkt_client_signal_evidence
  on public.mkt_client_signal using gin (evidence_json);

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
