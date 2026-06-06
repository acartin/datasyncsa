begin;

drop view if exists public.mw_exp_intraday_price_movement;
drop view if exists public.mw_exp_intraday_promo_movement;

create or replace view public.mw_exp_intraday_sku_chain_capture as
select
  o.date_key,
  o.business_date,
  o.week_start_date as week_start,
  o.month_start_date as month_start,
  o.client_id,
  o.client_name as client,
  o.campaign_id,
  o.campaign_name as campaign,
  o.chain_key,
  o.chain_label as chain,
  o.product_key,
  o.gtin_norm as gtin,
  o.brand_name as brand,
  o.product_name as product,
  o.content_quantity,
  o.content_unit,
  o.run_key,
  min(o.captured_at_cr) as capture_started_at_cr,
  max(o.captured_at_cr) as captured_at_cr,
  count(distinct o.location_key) as observed_locations,
  count(distinct o.location_key) filter (where o.is_listed) as visible_locations,
  count(distinct o.location_key) filter (where o.is_available) as available_locations,
  count(distinct o.location_key) filter (where o.promo_detected) as promo_locations,
  round(avg(o.effective_price_amount) filter (where o.effective_price_amount is not null), 2) as average_price,
  round(min(o.effective_price_amount), 2) as min_price,
  round(max(o.effective_price_amount), 2) as max_price,
  round(avg(o.effective_price_per_unit_amount) filter (where o.effective_price_per_unit_amount is not null), 4) as average_unit_price,
  bool_or(coalesce(o.promo_detected, false)) as promo_detected,
  round(
    count(distinct o.location_key) filter (where o.promo_detected)::numeric
    / nullif(count(distinct o.location_key), 0)::numeric
    * 100,
    2
  ) as promo_share_pct,
  round(max(o.discount_pct) * 100, 2) as max_discount_pct,
  max(o.product_url) filter (where o.product_url is not null) as product_url,
  max(o.image_url) filter (where o.image_url is not null) as image_url
from public.mw_core_sku_store_observation as o
where o.is_listed
   or o.effective_price_amount is not null
group by
  o.date_key,
  o.business_date,
  o.week_start_date,
  o.month_start_date,
  o.client_id,
  o.client_name,
  o.campaign_id,
  o.campaign_name,
  o.chain_key,
  o.chain_label,
  o.product_key,
  o.gtin_norm,
  o.brand_name,
  o.product_name,
  o.content_quantity,
  o.content_unit,
  o.run_key;

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
  md5(concat_ws(':', 'intraday_price', date_key, client_id, campaign_id, chain_key, product_key, run_key)) as event_id,
  date_key,
  business_date,
  client_id,
  client,
  campaign_id,
  campaign,
  chain_key,
  chain,
  product_key,
  gtin,
  brand,
  product,
  content_quantity,
  content_unit,
  run_key,
  previous_run_key,
  previous_captured_at_cr,
  captured_at_cr,
  previous_average_price,
  average_price as current_average_price,
  round(average_price - previous_average_price, 2) as price_change_amount,
  round((average_price - previous_average_price) / nullif(previous_average_price, 0) * 100, 2) as price_change_pct,
  previous_average_unit_price,
  average_unit_price as current_average_unit_price,
  round(average_unit_price - previous_average_unit_price, 4) as unit_price_change_amount,
  round((average_unit_price - previous_average_unit_price) / nullif(previous_average_unit_price, 0) * 100, 2) as unit_price_change_pct,
  case
    when average_price > previous_average_price then 'price_increase'
    when average_price < previous_average_price then 'price_decrease'
  end as event_type,
  case
    when abs((average_price - previous_average_price) / nullif(previous_average_price, 0)) >= 0.10
      or abs(average_price - previous_average_price) >= 500 then 'high'
    when abs((average_price - previous_average_price) / nullif(previous_average_price, 0)) >= 0.05
      or abs(average_price - previous_average_price) >= 100 then 'medium'
    else 'low'
  end as severity,
  observed_locations,
  visible_locations,
  available_locations,
  promo_detected,
  promo_share_pct,
  max_discount_pct,
  product_url,
  image_url
from sequenced
where previous_average_price is not null
  and average_price <> previous_average_price
  and (
    abs((average_price - previous_average_price) / nullif(previous_average_price, 0)) >= 0.03
    or abs(average_price - previous_average_price) >= 50
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
  md5(concat_ws(':', 'intraday_promo', date_key, client_id, campaign_id, chain_key, product_key, run_key)) as event_id,
  date_key,
  business_date,
  client_id,
  client,
  campaign_id,
  campaign,
  chain_key,
  chain,
  product_key,
  gtin,
  brand,
  product,
  content_quantity,
  content_unit,
  run_key,
  previous_run_key,
  previous_captured_at_cr,
  captured_at_cr,
  previous_promo_detected,
  promo_detected as current_promo_detected,
  previous_promo_share_pct,
  promo_share_pct as current_promo_share_pct,
  round(promo_share_pct - coalesce(previous_promo_share_pct, 0), 2) as promo_share_change_points,
  previous_max_discount_pct,
  max_discount_pct as current_max_discount_pct,
  case
    when promo_detected and coalesce(previous_promo_detected, false) = false then 'promo_started'
    when promo_detected = false and coalesce(previous_promo_detected, false) then 'promo_ended'
    when promo_share_pct >= coalesce(previous_promo_share_pct, 0) + 20 then 'promo_intensity_spike'
    when promo_share_pct <= coalesce(previous_promo_share_pct, 0) - 20 then 'promo_intensity_drop'
  end as event_type,
  case
    when coalesce(max_discount_pct, 0) >= 20
      or abs(promo_share_pct - coalesce(previous_promo_share_pct, 0)) >= 50 then 'high'
    when coalesce(max_discount_pct, 0) >= 10
      or abs(promo_share_pct - coalesce(previous_promo_share_pct, 0)) >= 20 then 'medium'
    else 'low'
  end as severity,
  observed_locations,
  visible_locations,
  available_locations,
  average_price,
  product_url,
  image_url
from sequenced
where previous_run_key is not null
  and (
    promo_detected is distinct from previous_promo_detected
    or abs(promo_share_pct - coalesce(previous_promo_share_pct, 0)) >= 20
  );

commit;
