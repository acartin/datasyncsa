begin;

create table if not exists public.mkt_campaign_client_access (
  campaign_id bigint not null references public.mkt_dim_campaign(id),
  client_id bigint not null references public.auth_clients(id),
  access_role text not null default 'viewer',
  is_default boolean not null default false,
  is_active boolean not null default true,
  valid_from date null,
  valid_to date null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (campaign_id, client_id),
  constraint mkt_campaign_client_access_role_check
    check (access_role in ('viewer', 'owner', 'admin')),
  constraint mkt_campaign_client_access_valid_range_check
    check (valid_to is null or valid_from is null or valid_to >= valid_from)
);

create index if not exists idx_mkt_campaign_client_access_client
  on public.mkt_campaign_client_access (client_id, is_active, campaign_id);

create index if not exists idx_mkt_campaign_client_access_campaign
  on public.mkt_campaign_client_access (campaign_id, is_active, client_id);

insert into public.mkt_campaign_client_access (
  campaign_id,
  client_id,
  access_role,
  is_default,
  is_active
)
values (1, 1, 'owner', true, true)
on conflict (campaign_id, client_id) do update
set access_role = excluded.access_role,
    is_default = excluded.is_default,
    is_active = excluded.is_active,
    updated_at = now();

create or replace view public.mw_bi_brand_chain_price_index as
select
  b.business_date,
  b.week_start_date as week_start,
  b.month_start_date as month_start,
  b.date_key,
  cca.client_id,
  b.campaign_id,
  ac.name as client,
  b.campaign_name as campaign,
  b.brand_name as brand,
  b.chain_label as chain,
  b.chain_key as chain_order,
  b.tracked_product_count as monitored_products,
  round(b.avg_price_position_index, 2) as price_index,
  round((b.avg_price_position_index - 100), 2) as gap_vs_market_pct,
  b.brand_chain_price_rank as price_rank,
  round(b.avg_visibility_rate * 100, 2) as visibility_pct,
  round(b.avg_availability_rate * 100, 2) as availability_pct,
  round(b.avg_promo_share * 100, 2) as promo_pct,
  b.lowest_price_product_count as best_price_products,
  b.competitive_product_count as competitive_products,
  b.over_market_product_count as over_market_products,
  round(b.avg_price_amount, 2) as average_price_crc,
  round(b.avg_price_per_unit_amount, 4) as average_unit_price,
  b.price_reading,
  b.visibility_reading as visibility_reading
from public.mw_signal_brand_chain_daily as b
join public.mkt_campaign_client_access as cca
  on cca.campaign_id = b.campaign_id
 and cca.is_active
 and (cca.valid_from is null or b.business_date >= cca.valid_from)
 and (cca.valid_to is null or b.business_date <= cca.valid_to)
join public.auth_clients as ac
  on ac.id = cca.client_id
 and ac.status = 'active'
where b.client_id is null
   or b.client_id = cca.client_id;

create or replace view public.mw_bi_sku_price_drivers as
select
  s.business_date,
  s.week_start_date as week_start,
  s.month_start_date as month_start,
  s.date_key,
  cca.client_id,
  s.campaign_id,
  ac.name as client,
  s.campaign_name as campaign,
  s.brand_name as brand,
  s.product_name as product,
  s.gtin_norm as gtin,
  s.product_key,
  s.chain_label as chain,
  s.chain_key as chain_order,
  s.content_quantity as content_quantity,
  s.content_unit,
  round(s.avg_price_amount, 2) as average_price,
  round(s.market_best_price_amount, 2) as market_best_price,
  round(s.market_best_price_amount, 2) as best_chain_average_price,
  round(s.gap_vs_market_best_amount, 2) as gap_amount,
  round(s.gap_vs_market_best_pct * 100, 2) as gap_pct,
  round(s.price_position_index, 2) as price_index,
  s.chain_price_rank as price_rank,
  s.monitored_locations_count as monitored_stores,
  s.visible_locations_count as visible_stores,
  round(s.visibility_rate * 100, 2) as visibility_pct,
  s.price_reading,
  s.suggested_action as suggested_action,
  s.product_url,
  s.image_url,
  s.best_price_chain_label as best_price_chain,
  s.best_price_chain_label as best_chain,
  s.best_price_product_url as best_price_url,
  s.best_price_product_url as best_chain_url,
  s.best_price_image_url as best_price_image_url
from public.mw_signal_sku_chain_daily as s
join public.mkt_campaign_client_access as cca
  on cca.campaign_id = s.campaign_id
 and cca.is_active
 and (cca.valid_from is null or s.business_date >= cca.valid_from)
 and (cca.valid_to is null or s.business_date <= cca.valid_to)
join public.auth_clients as ac
  on ac.id = cca.client_id
 and ac.status = 'active'
where s.client_id is null
   or s.client_id = cca.client_id;

create or replace view public.mw_bi_sku_store_price_evidence as
select
  o.business_date,
  o.week_start_date as week_start,
  o.month_start_date as month_start,
  o.date_key,
  cca.client_id,
  o.campaign_id,
  ac.name as client,
  o.campaign_name as campaign,
  o.brand_name as brand,
  o.product_name as product,
  o.gtin_norm as gtin,
  o.product_key,
  o.chain_label as chain,
  o.chain_key as chain_order,
  o.location_name as store,
  o.location_code as store_code,
  o.province,
  o.canton,
  o.district,
  round(o.effective_price_amount, 2) as observed_price,
  round(o.reference_price_amount, 2) as reference_price,
  round(o.discount_pct * 100, 2) as discount_pct,
  o.is_available as is_available,
  o.promo_detected as promo_detected,
  o.available_quantity as available_quantity,
  o.captured_at_cr,
  o.product_url,
  o.image_url
from public.mw_signal_sku_store_observation as o
join public.mkt_campaign_client_access as cca
  on cca.campaign_id = o.campaign_id
 and cca.is_active
 and (cca.valid_from is null or o.business_date >= cca.valid_from)
 and (cca.valid_to is null or o.business_date <= cca.valid_to)
join public.auth_clients as ac
  on ac.id = cca.client_id
 and ac.status = 'active'
where o.client_id is null
   or o.client_id = cca.client_id;

create or replace view public.mw_bi_price_events as
select
  e.business_date,
  e.week_start_date as week_start,
  e.month_start_date as month_start,
  e.date_key,
  cca.client_id,
  e.campaign_id,
  ac.name as client,
  e.campaign_name as campaign,
  e.brand_name as brand,
  e.product_name as product,
  e.gtin_norm as gtin,
  e.chain_label as chain,
  'price'::text as event_area,
  e.event_type as event_type,
  e.severity,
  round(e.previous_avg_price_amount, 2) as previous_value,
  round(e.current_avg_price_amount, 2) as current_value,
  round(e.price_change_amount, 2) as change_amount,
  round(e.price_change_pct * 100, 2) as change_pct
from public.mw_signal_price_change_daily as e
join public.mkt_campaign_client_access as cca
  on cca.campaign_id = e.campaign_id
 and cca.is_active
 and (cca.valid_from is null or e.business_date >= cca.valid_from)
 and (cca.valid_to is null or e.business_date <= cca.valid_to)
join public.auth_clients as ac
  on ac.id = cca.client_id
 and ac.status = 'active'
where e.client_id is null
   or e.client_id = cca.client_id
union all
select
  p.business_date,
  p.week_start_date as week_start,
  p.month_start_date as month_start,
  p.date_key,
  cca.client_id,
  p.campaign_id,
  ac.name as client,
  p.campaign_name as campaign,
  p.brand_name as brand,
  p.product_name as product,
  p.gtin_norm as gtin,
  p.chain_label as chain,
  'promotion'::text as event_area,
  p.event_type,
  p.severity,
  round(p.previous_promo_share * 100, 2) as previous_value,
  round(p.promo_share * 100, 2) as current_value,
  null::numeric as change_amount,
  round((p.promo_share - coalesce(p.previous_promo_share, 0)) * 100, 2) as change_pct
from public.mw_signal_promo_daily as p
join public.mkt_campaign_client_access as cca
  on cca.campaign_id = p.campaign_id
 and cca.is_active
 and (cca.valid_from is null or p.business_date >= cca.valid_from)
 and (cca.valid_to is null or p.business_date <= cca.valid_to)
join public.auth_clients as ac
  on ac.id = cca.client_id
 and ac.status = 'active'
where p.client_id is null
   or p.client_id = cca.client_id;

create or replace view public.mw_bi_executive_signal_feed as
select
  s.business_date,
  date_trunc('week', s.business_date)::date as week_start,
  date_trunc('month', s.business_date)::date as month_start,
  s.date_key,
  cca.client_id,
  s.campaign_id,
  s.campaign_name as campaign,
  s.perspective_brand as brand,
  s.chain,
  s.signal_type,
  s.lifecycle_status as signal_status,
  s.effect,
  s.severity,
  s.impact_score,
  s.confidence_score,
  s.headline,
  s.summary,
  s.business_reading,
  s.recommended_action,
  s.notification_status,
  s.notification_reason,
  s.repeat_count,
  s.metrics_json,
  s.evidence_json,
  s.delta_metrics_json,
  s.navigation_json,
  s.narrative_json
from public.mkt_client_signal as s
join public.mkt_campaign_client_access as cca
  on cca.campaign_id = s.campaign_id
 and cca.is_active
 and (cca.valid_from is null or s.business_date >= cca.valid_from)
 and (cca.valid_to is null or s.business_date <= cca.valid_to)
join public.auth_clients as ac
  on ac.id = cca.client_id
 and ac.status = 'active'
where s.perspective_client_id is null
   or s.perspective_client_id = cca.client_id;

commit;
