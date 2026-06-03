begin;

create table if not exists public.mkt_dim_market_event_type (
  event_type text primary key,
  event_area text not null,
  display_label text not null,
  short_label text not null,
  description text not null default '',
  metric_previous_label text not null default 'Previous',
  metric_current_label text not null default 'Current',
  metric_change_label text not null default 'Change',
  value_format text not null default 'number',
  change_format text not null default 'number',
  direction_semantics text not null default 'neutral',
  header_variant text not null default 'generic',
  icon_name text not null default 'activity',
  accent_token text not null default 'neutral',
  chart_annotation_label text not null default '',
  appears_in_intraday_radar boolean not null default false,
  creates_client_signal boolean not null default false,
  default_sort_order integer not null default 100,
  is_active boolean not null default true,
  presentation_config jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint mkt_dim_market_event_type_area_check
    check (event_area in ('price', 'promotion', 'availability', 'catalog', 'competitive', 'assortment', 'generic')),
  constraint mkt_dim_market_event_type_direction_check
    check (direction_semantics in ('positive_good', 'positive_bad', 'negative_good', 'negative_bad', 'neutral')),
  constraint mkt_dim_market_event_type_accent_check
    check (accent_token in ('success', 'danger', 'warning', 'info', 'neutral'))
);

alter table public.mkt_dim_market_event_type
  alter column metric_previous_label set default 'Previous',
  alter column metric_current_label set default 'Current',
  alter column metric_change_label set default 'Change';

comment on table public.mkt_dim_market_event_type is
  'Central semantic and presentation configuration for Market Watch event types.';
comment on column public.mkt_dim_market_event_type.accent_token is
  'Semantic UI token. Do not store CSS classes or raw colors here.';
comment on column public.mkt_dim_market_event_type.presentation_config is
  'Optional structured renderer hints for web/API clients. Keep it semantic and token-based.';

create index if not exists idx_mkt_dim_market_event_type_radar
  on public.mkt_dim_market_event_type (appears_in_intraday_radar, is_active, default_sort_order);

insert into public.mkt_dim_market_event_type (
  event_type,
  event_area,
  display_label,
  short_label,
  description,
  metric_previous_label,
  metric_current_label,
  metric_change_label,
  value_format,
  change_format,
  direction_semantics,
  header_variant,
  icon_name,
  accent_token,
  chart_annotation_label,
  appears_in_intraday_radar,
  creates_client_signal,
  default_sort_order,
  presentation_config
)
values
  ('promo_started', 'promotion', 'PROMOTION STARTED', 'Promotion started', 'The promotion appears compared to the previous period.', 'No promo', 'With promo', 'Change', 'percent', 'points', 'positive_good', 'promotion', 'tag', 'success', 'Promotion started', true, false, 10, '{"header_metric_mode":"promotion_share","show_header_metrics":false,"value_display_mode":"promo_state","show_change_value":false}'::jsonb),
  ('promo_ended', 'promotion', 'PROMOTION ENDED', 'Promotion ended', 'The promotion disappears compared to the previous period.', 'With promo', 'No promo', 'Change', 'percent', 'points', 'negative_bad', 'promotion', 'tag', 'danger', 'Promotion ended', true, false, 20, '{"header_metric_mode":"promotion_share","show_header_metrics":false,"value_display_mode":"promo_state","show_change_value":false}'::jsonb),
  ('regular_price_increase', 'price', 'REGULAR PRICE INCREASE', 'Regular increase', 'The regular price increases compared to the previous period.', 'Previous', 'Current', 'Change', 'currency', 'percent', 'positive_bad', 'price', 'trending-up', 'danger', 'Regular increase', true, false, 30, '{"header_metric_mode":"price_change","change_visual":"market_direction"}'::jsonb),
  ('regular_price_decrease', 'price', 'REGULAR PRICE DECREASE', 'Regular decrease', 'The regular price decreases compared to the previous period.', 'Previous', 'Current', 'Change', 'currency', 'percent', 'negative_good', 'price', 'trending-down', 'success', 'Regular decrease', true, false, 40, '{"header_metric_mode":"price_change","change_visual":"market_direction"}'::jsonb),
  ('promo_price_increase', 'price', 'PROMOTIONAL PRICE INCREASE', 'Promo increase', 'The promotional price increases compared to the previous period.', 'Previous promo', 'Current promo', 'Change', 'currency', 'percent', 'positive_bad', 'price', 'trending-up', 'danger', 'Promo increase', true, false, 50, '{"header_metric_mode":"price_change","change_visual":"market_direction"}'::jsonb),
  ('promo_price_decrease', 'price', 'PROMOTIONAL PRICE DECREASE', 'Promo decrease', 'The promotional price decreases compared to the previous period.', 'Previous promo', 'Current promo', 'Change', 'currency', 'percent', 'negative_good', 'price', 'trending-down', 'success', 'Promo decrease', true, false, 60, '{"header_metric_mode":"price_change","change_visual":"market_direction"}'::jsonb),
  ('brand_over_market', 'competitive', 'BRAND ABOVE MARKET', 'Above market', 'The brand is above the market price index.', 'Market', 'Brand', 'Gap', 'price_index', 'percent', 'positive_bad', 'competitive', 'trending-up', 'danger', 'Above market', false, true, 110, '{}'::jsonb),
  ('brand_under_market', 'competitive', 'BRAND BELOW MARKET', 'Below market', 'The brand is below the market price index.', 'Market', 'Brand', 'Gap', 'price_index', 'percent', 'negative_good', 'competitive', 'trending-down', 'success', 'Below market', false, true, 120, '{}'::jsonb),
  ('sku_price_gap', 'competitive', 'SKU PRICE GAP', 'SKU gap', 'A SKU has a relevant gap against the best market price.', 'Best market', 'Current', 'Gap', 'currency', 'percent', 'positive_bad', 'competitive', 'git-compare', 'warning', 'SKU gap', false, true, 130, '{}'::jsonb),
  ('driver_sku_detected', 'competitive', 'GAP DRIVER DETECTED', 'Driver SKU', 'A group of SKUs explains a relevant part of the commercial gap.', 'Total', 'Drivers', 'Contribution', 'currency', 'percent', 'neutral', 'competitive', 'list-filter', 'warning', 'Driver SKU', false, true, 140, '{}'::jsonb),
  ('promo_price_break', 'promotion', 'PROMOTIONAL BREAK', 'Promo break', 'A promotion creates a relevant advantage against the market.', 'Market', 'Promo', 'Gap', 'currency', 'percent', 'positive_good', 'promotion', 'badge-percent', 'success', 'Promo break', false, true, 150, '{}'::jsonb),
  ('price_increase', 'price', 'PRICE INCREASE', 'Price increase', 'The price increases compared to the previous period.', 'Previous', 'Current', 'Change', 'currency', 'percent', 'positive_bad', 'price', 'trending-up', 'danger', 'Price increase', false, false, 210, '{"legacy":true}'::jsonb),
  ('price_decrease', 'price', 'PRICE DECREASE', 'Price decrease', 'The price decreases compared to the previous period.', 'Previous', 'Current', 'Change', 'currency', 'percent', 'negative_good', 'price', 'trending-down', 'success', 'Price decrease', false, false, 220, '{"legacy":true}'::jsonb),
  ('promo_detected', 'promotion', 'PROMOTION DETECTED', 'Promotion detected', 'An active promotion is detected in the period.', 'No promo', 'With promo', 'Change', 'percent', 'points', 'positive_good', 'promotion', 'tag', 'success', 'Promotion detected', false, false, 230, '{"legacy":true}'::jsonb),
  ('promo_intensity_spike', 'promotion', 'PROMOTIONAL INTENSITY INCREASE', 'Promo intensity increase', 'The promotional share or intensity increases significantly.', 'Previous', 'Current', 'Change', 'percent', 'points', 'positive_good', 'promotion', 'badge-percent', 'success', 'Promo intensity increase', false, false, 240, '{}'::jsonb),
  ('promo_intensity_drop', 'promotion', 'PROMOTIONAL INTENSITY DECREASE', 'Promo intensity decrease', 'The promotional share or intensity decreases significantly.', 'Previous', 'Current', 'Change', 'percent', 'points', 'negative_bad', 'promotion', 'badge-percent', 'warning', 'Promo intensity decrease', false, false, 250, '{}'::jsonb)
on conflict (event_type) do update
set event_area = excluded.event_area,
    display_label = excluded.display_label,
    short_label = excluded.short_label,
    description = excluded.description,
    metric_previous_label = excluded.metric_previous_label,
    metric_current_label = excluded.metric_current_label,
    metric_change_label = excluded.metric_change_label,
    value_format = excluded.value_format,
    change_format = excluded.change_format,
    direction_semantics = excluded.direction_semantics,
    header_variant = excluded.header_variant,
    icon_name = excluded.icon_name,
    accent_token = excluded.accent_token,
    chart_annotation_label = excluded.chart_annotation_label,
    appears_in_intraday_radar = excluded.appears_in_intraday_radar,
    creates_client_signal = excluded.creates_client_signal,
    default_sort_order = excluded.default_sort_order,
    is_active = excluded.is_active,
    presentation_config = excluded.presentation_config,
    updated_at = now();

create or replace view public.mw_bi_radar_event_feed as
select
  e.event_key as event_id,
  et.event_area,
  e.event_type,
  e.severity,
  e.business_date,
  date_trunc('week', e.business_date)::date as week_start,
  date_trunc('month', e.business_date)::date as month_start,
  e.date_key,
  (e.metrics_json->>'previous_date_key')::int as previous_date_key,
  cca.client_id,
  e.campaign_id,
  ac.name as client,
  e.campaign_name as campaign,
  e.chain,
  e.evidence_json->>'brand' as brand,
  e.evidence_json->>'product' as product,
  e.evidence_json->>'gtin' as gtin,
  e.evidence_json->>'product_key' as product_key,
  null::numeric as content_quantity,
  null::text as content_unit,
  e.business_date::text as captured_at_cr,
  null::text as previous_captured_at_cr,
  (e.metrics_json->>'previous_value')::numeric(12,2) as previous_value,
  (e.metrics_json->>'current_value')::numeric(12,2) as current_value,
  (e.metrics_json->>'change_abs')::numeric(12,2) as change_amount,
  (e.metrics_json->>'change_pct')::numeric(12,2) as change_pct,
  case when et.event_area = 'promotion'
    then (e.metrics_json->>'promo_share_current')::numeric(5,2)
    else null::numeric
  end as promo_share_pct,
  null::numeric(5,2) as discount_pct,
  null::int as observed_locations,
  null::int as visible_locations,
  null::int as available_locations,
  e.evidence_json->>'product_url' as product_url,
  null::text as image_url
from public.mkt_market_event as e
join public.mkt_dim_market_event_type as et
  on et.event_type = e.event_type
 and et.is_active
 and et.appears_in_intraday_radar
join public.mkt_campaign_client_access as cca
  on cca.campaign_id = e.campaign_id
 and cca.is_active
 and (cca.valid_from is null or e.business_date >= cca.valid_from)
 and (cca.valid_to is null or e.business_date <= cca.valid_to)
join public.auth_clients as ac
  on ac.id = cca.client_id
 and ac.status = 'active'
where e.client_id is null
   or e.client_id = cca.client_id;

comment on view public.mw_bi_radar_event_feed is
  'Market Watch radar event feed. Grain: one client-visible market event per product, chain, campaign and date.';

commit;
