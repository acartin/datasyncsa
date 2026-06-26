create table if not exists public.mkt_campaign_report_recipient (
  id bigint generated always as identity primary key,
  campaign_id bigint not null references public.mkt_dim_campaign(id),
  client_id bigint not null references public.auth_clients(id),
  user_id bigint references public.auth_users(id),
  email text not null,
  display_name text,
  recipient_type text not null default 'to',
  report_kind text not null default 'daily_price_radar',
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint mkt_campaign_report_recipient_type_ck
    check (recipient_type in ('to', 'cc', 'bcc')),
  constraint mkt_campaign_report_recipient_kind_ck
    check (report_kind in ('daily_price_radar'))
);

create index if not exists idx_mkt_campaign_report_recipient_campaign_client
  on public.mkt_campaign_report_recipient (campaign_id, client_id, report_kind, is_active);

create unique index if not exists mkt_campaign_report_recipient_email_uk
  on public.mkt_campaign_report_recipient (
    campaign_id,
    client_id,
    report_kind,
    recipient_type,
    lower(email)
  );

create table if not exists public.mkt_campaign_report_delivery (
  id bigint generated always as identity primary key,
  campaign_id bigint not null references public.mkt_dim_campaign(id),
  client_id bigint not null references public.auth_clients(id),
  report_kind text not null default 'daily_price_radar',
  business_date date not null,
  status text not null default 'pending',
  subject text,
  recipients_json jsonb not null default '[]'::jsonb,
  provider_message_id text,
  error_summary text,
  requested_by_user_id bigint references public.auth_users(id),
  created_at timestamptz not null default now(),
  sent_at timestamptz,
  constraint mkt_campaign_report_delivery_kind_ck
    check (report_kind in ('daily_price_radar')),
  constraint mkt_campaign_report_delivery_status_ck
    check (status in ('pending', 'sent', 'failed', 'skipped'))
);

create index if not exists idx_mkt_campaign_report_delivery_campaign_client
  on public.mkt_campaign_report_delivery (campaign_id, client_id, report_kind, business_date desc);
