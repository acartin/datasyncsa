begin;

drop view if exists public.mw_exp_intraday_radar_events;
drop view if exists public.mw_exp_intraday_promo_movement;
drop view if exists public.mw_exp_intraday_price_movement;
drop view if exists public.mw_exp_intraday_sku_chain_capture;

create or replace view public.mw_exp_intraday_sku_chain_capture as
with scoped as (
  select
    o.*,
    cca.client_id as authorized_client_id,
    ac.name as authorized_client_name
  from public.mw_core_sku_store_observation as o
  join public.mkt_campaign_client_access as cca
    on cca.campaign_id = o.campaign_id
   and cca.is_active
   and (cca.valid_from is null or o.business_date >= cca.valid_from)
   and (cca.valid_to is null or o.business_date <= cca.valid_to)
  join public.auth_clients as ac
    on ac.id = cca.client_id
   and ac.status = 'active'
  where o.client_id is null
     or o.client_id = cca.client_id
)
select
  s.date_key,
  s.business_date,
  s.week_start_date as week_start,
  s.month_start_date as month_start,
  s.authorized_client_id as client_id,
  s.authorized_client_name as client,
  s.campaign_id,
  s.campaign_name as campaign,
  s.chain_key,
  s.chain_label as chain,
  s.product_key,
  s.gtin_norm as gtin,
  s.brand_name as brand,
  s.product_name as product,
  s.content_quantity,
  s.content_unit,
  s.run_key,
  min(s.captured_at_cr) as capture_started_at_cr,
  max(s.captured_at_cr) as captured_at_cr,
  count(distinct s.location_key) as observed_locations,
  count(distinct s.location_key) filter (where s.is_listed) as visible_locations,
  count(distinct s.location_key) filter (where s.is_available) as available_locations,
  count(distinct s.location_key) filter (where s.promo_detected) as promo_locations,
  round(avg(s.effective_price_amount) filter (where s.effective_price_amount is not null), 2) as average_price,
  round(min(s.effective_price_amount), 2) as min_price,
  round(max(s.effective_price_amount), 2) as max_price,
  round(avg(s.effective_price_per_unit_amount) filter (where s.effective_price_per_unit_amount is not null), 4) as average_unit_price,
  bool_or(coalesce(s.promo_detected, false)) as promo_detected,
  round(
    (
      count(distinct s.location_key) filter (where s.promo_detected)::numeric
      / nullif(count(distinct s.location_key), 0)
    ) * 100,
    2
  ) as promo_share_pct,
  round(max(s.discount_pct) * 100, 2) as max_discount_pct,
  max(s.product_url) filter (where s.product_url is not null) as product_url,
  max(s.image_url) filter (where s.image_url is not null) as image_url
from scoped as s
where s.is_listed
   or s.effective_price_amount is not null
group by
  s.date_key,
  s.business_date,
  s.week_start_date,
  s.month_start_date,
  s.authorized_client_id,
  s.authorized_client_name,
  s.campaign_id,
  s.campaign_name,
  s.chain_key,
  s.chain_label,
  s.product_key,
  s.gtin_norm,
  s.brand_name,
  s.product_name,
  s.content_quantity,
  s.content_unit,
  s.run_key;

create or replace view public.mw_exp_intraday_price_movement as
with sequenced as (
  select
    c.*,
    lag(c.run_key) over w as previous_run_key,
    lag(c.captured_at_cr) over w as previous_captured_at_cr,
    lag(c.average_price) over w as previous_average_price,
    lag(c.average_unit_price) over w as previous_average_unit_price
  from public.mw_exp_intraday_sku_chain_capture as c
  where c.average_price is not null
  window w as (
    partition by c.client_id, c.campaign_id, c.chain_key, c.product_key
    order by c.captured_at_cr, c.run_key
  )
)
select
  md5(concat_ws(':', 'intraday_price', s.date_key, s.client_id, s.campaign_id, s.chain_key, s.product_key, s.run_key)) as event_id,
  s.date_key,
  s.business_date,
  s.client_id,
  s.client,
  s.campaign_id,
  s.campaign,
  s.chain_key,
  s.chain,
  s.product_key,
  s.gtin,
  s.brand,
  s.product,
  s.content_quantity,
  s.content_unit,
  s.run_key,
  s.previous_run_key,
  s.previous_captured_at_cr,
  s.captured_at_cr,
  s.previous_average_price,
  s.average_price as current_average_price,
  round(s.average_price - s.previous_average_price, 2) as price_change_amount,
  round(((s.average_price - s.previous_average_price) / nullif(s.previous_average_price, 0)) * 100, 2) as price_change_pct,
  s.previous_average_unit_price,
  s.average_unit_price as current_average_unit_price,
  round(s.average_unit_price - s.previous_average_unit_price, 4) as unit_price_change_amount,
  round(((s.average_unit_price - s.previous_average_unit_price) / nullif(s.previous_average_unit_price, 0)) * 100, 2) as unit_price_change_pct,
  case
    when s.average_price > s.previous_average_price then 'price_increase'
    when s.average_price < s.previous_average_price then 'price_decrease'
  end as event_type,
  case
    when abs((s.average_price - s.previous_average_price) / nullif(s.previous_average_price, 0)) >= 0.10
      or abs(s.average_price - s.previous_average_price) >= 500
    then 'high'
    when abs((s.average_price - s.previous_average_price) / nullif(s.previous_average_price, 0)) >= 0.05
      or abs(s.average_price - s.previous_average_price) >= 100
    then 'medium'
    else 'low'
  end as severity,
  s.observed_locations,
  s.visible_locations,
  s.available_locations,
  s.promo_detected,
  s.promo_share_pct,
  s.max_discount_pct,
  s.product_url,
  s.image_url
from sequenced as s
where s.previous_average_price is not null
  and s.average_price <> s.previous_average_price
  and (
    abs((s.average_price - s.previous_average_price) / nullif(s.previous_average_price, 0)) >= 0.03
    or abs(s.average_price - s.previous_average_price) >= 50
  );

create or replace view public.mw_exp_intraday_promo_movement as
with sequenced as (
  select
    c.*,
    lag(c.run_key) over w as previous_run_key,
    lag(c.captured_at_cr) over w as previous_captured_at_cr,
    lag(c.promo_detected) over w as previous_promo_detected,
    lag(c.promo_share_pct) over w as previous_promo_share_pct,
    lag(c.max_discount_pct) over w as previous_max_discount_pct
  from public.mw_exp_intraday_sku_chain_capture as c
  window w as (
    partition by c.client_id, c.campaign_id, c.chain_key, c.product_key
    order by c.captured_at_cr, c.run_key
  )
)
select
  md5(concat_ws(':', 'intraday_promo', s.date_key, s.client_id, s.campaign_id, s.chain_key, s.product_key, s.run_key)) as event_id,
  s.date_key,
  s.business_date,
  s.client_id,
  s.client,
  s.campaign_id,
  s.campaign,
  s.chain_key,
  s.chain,
  s.product_key,
  s.gtin,
  s.brand,
  s.product,
  s.content_quantity,
  s.content_unit,
  s.run_key,
  s.previous_run_key,
  s.previous_captured_at_cr,
  s.captured_at_cr,
  s.previous_promo_detected,
  s.promo_detected as current_promo_detected,
  s.previous_promo_share_pct,
  s.promo_share_pct as current_promo_share_pct,
  round(s.promo_share_pct - coalesce(s.previous_promo_share_pct, 0), 2) as promo_share_change_points,
  s.previous_max_discount_pct,
  s.max_discount_pct as current_max_discount_pct,
  case
    when s.promo_detected and coalesce(s.previous_promo_detected, false) = false then 'promo_started'
    when s.promo_detected = false and coalesce(s.previous_promo_detected, false) then 'promo_ended'
    when s.promo_share_pct >= coalesce(s.previous_promo_share_pct, 0) + 20 then 'promo_intensity_spike'
    when s.promo_share_pct <= coalesce(s.previous_promo_share_pct, 0) - 20 then 'promo_intensity_drop'
  end as event_type,
  case
    when coalesce(s.max_discount_pct, 0) >= 20
      or abs(s.promo_share_pct - coalesce(s.previous_promo_share_pct, 0)) >= 50
    then 'high'
    when coalesce(s.max_discount_pct, 0) >= 10
      or abs(s.promo_share_pct - coalesce(s.previous_promo_share_pct, 0)) >= 20
    then 'medium'
    else 'low'
  end as severity,
  s.observed_locations,
  s.visible_locations,
  s.available_locations,
  s.average_price,
  s.product_url,
  s.image_url
from sequenced as s
where s.previous_run_key is not null
  and (
    s.promo_detected is distinct from s.previous_promo_detected
    or abs(s.promo_share_pct - coalesce(s.previous_promo_share_pct, 0)) >= 20
  );

create or replace view public.mw_exp_intraday_radar_events as
select
  p.event_id,
  'price'::text as event_area,
  p.event_type,
  p.severity,
  p.business_date,
  p.date_key,
  p.client_id,
  p.client,
  p.campaign_id,
  p.campaign,
  p.chain,
  p.brand,
  p.product,
  p.gtin,
  p.product_key,
  p.content_quantity,
  p.content_unit,
  p.run_key,
  p.previous_run_key,
  p.previous_captured_at_cr,
  p.captured_at_cr,
  p.previous_average_price as previous_value,
  p.current_average_price as current_value,
  p.price_change_amount as change_amount,
  p.price_change_pct as change_pct,
  p.promo_share_pct,
  p.max_discount_pct as discount_pct,
  p.observed_locations,
  p.visible_locations,
  p.available_locations,
  p.product_url,
  p.image_url
from public.mw_exp_intraday_price_movement as p
union all
select
  m.event_id,
  'promotion'::text as event_area,
  m.event_type,
  m.severity,
  m.business_date,
  m.date_key,
  m.client_id,
  m.client,
  m.campaign_id,
  m.campaign,
  m.chain,
  m.brand,
  m.product,
  m.gtin,
  m.product_key,
  m.content_quantity,
  m.content_unit,
  m.run_key,
  m.previous_run_key,
  m.previous_captured_at_cr,
  m.captured_at_cr,
  m.previous_promo_share_pct as previous_value,
  m.current_promo_share_pct as current_value,
  m.promo_share_change_points as change_amount,
  null::numeric as change_pct,
  m.current_promo_share_pct as promo_share_pct,
  m.current_max_discount_pct as discount_pct,
  m.observed_locations,
  m.visible_locations,
  m.available_locations,
  m.product_url,
  m.image_url
from public.mw_exp_intraday_promo_movement as m
where m.event_type is not null;

comment on view public.mw_exp_intraday_sku_chain_capture is
  'Experimental Market Watch intraday SKU-chain capture aggregate. Grain: client/campaign/chain/product/run.';
comment on view public.mw_exp_intraday_price_movement is
  'Experimental Market Watch intraday price movement events between consecutive captures.';
comment on view public.mw_exp_intraday_promo_movement is
  'Experimental Market Watch intraday promotion movement events between consecutive captures.';
comment on view public.mw_exp_intraday_radar_events is
  'Experimental Market Watch unified intraday radar feed for price and promotion movements.';

commit;
