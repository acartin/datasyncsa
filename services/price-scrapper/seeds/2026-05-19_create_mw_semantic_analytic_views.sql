create or replace view public.mw_product_location_presence as
with base as (
  select
    f.*,
    coalesce(
      f.price_amount,
      f.spot_price_amount,
      f.price_without_discount_amount,
      f.list_price_amount
    ) as effective_price_amount,
    coalesce(
      f.list_price_amount,
      f.price_without_discount_amount,
      f.price_amount,
      f.spot_price_amount
    ) as reference_price_amount
  from public.mw_fact_analytic_listing_snapshot as f
)
select
  b.date_key,
  to_date(b.date_key::text, 'YYYYMMDD') as business_date,
  b.business_date_key,
  b.client_id,
  b.client_name,
  b.client_slug,
  b.campaign_id,
  b.campaign_name,
  b.campaign_slug,
  b.chain_key,
  b.chain_id,
  b.chain_name,
  b.chain_short_label,
  b.location_key,
  b.location_code,
  b.location_name,
  b.location_type,
  b.province,
  b.canton,
  b.district,
  b.sales_channel,
  b.region_id,
  b.product_key,
  b.gtin_norm,
  b.brand_name,
  b.product_name,
  b.content_quantity,
  b.content_unit,
  min(b.effective_price_amount) filter (where b.effective_price_amount is not null) as min_price_amount,
  max(b.effective_price_amount) filter (where b.effective_price_amount is not null) as max_price_amount,
  avg(b.effective_price_amount) filter (where b.effective_price_amount is not null) as avg_price_amount,
  min(b.effective_price_amount / nullif(b.content_quantity, 0))
    filter (where b.effective_price_amount is not null and b.content_quantity > 0) as min_price_per_unit_amount,
  avg(b.effective_price_amount / nullif(b.content_quantity, 0))
    filter (where b.effective_price_amount is not null and b.content_quantity > 0) as avg_price_per_unit_amount,
  count(*) as observed_listing_count,
  count(*) filter (where b.is_listed) as listed_listing_count,
  count(*) filter (where b.is_available) as available_listing_count,
  bool_or(coalesce(b.is_listed, false)) as is_visible,
  bool_or(coalesce(b.is_available, false)) as is_available,
  bool_or(coalesce(b.has_discount, false)) as has_discount,
  bool_or(
    coalesce(b.has_discount, false)
    or (
      b.reference_price_amount is not null
      and b.effective_price_amount is not null
      and b.reference_price_amount > b.effective_price_amount
    )
  ) as promo_detected,
  max(
    case
      when b.reference_price_amount is not null
        and b.effective_price_amount is not null
        and b.reference_price_amount > 0
      then (b.reference_price_amount - b.effective_price_amount) / b.reference_price_amount
    end
  ) as max_discount_pct,
  max(b.snapshot_ts) as last_snapshot_ts
from base as b
group by
  b.date_key,
  b.business_date_key,
  b.client_id,
  b.client_name,
  b.client_slug,
  b.campaign_id,
  b.campaign_name,
  b.campaign_slug,
  b.chain_key,
  b.chain_id,
  b.chain_name,
  b.chain_short_label,
  b.location_key,
  b.location_code,
  b.location_name,
  b.location_type,
  b.province,
  b.canton,
  b.district,
  b.sales_channel,
  b.region_id,
  b.product_key,
  b.gtin_norm,
  b.brand_name,
  b.product_name,
  b.content_quantity,
  b.content_unit;

create or replace view public.mw_daily_price_metrics as
select
  p.date_key,
  p.business_date,
  p.business_date_key,
  p.client_id,
  p.client_name,
  p.client_slug,
  p.campaign_id,
  p.campaign_name,
  p.campaign_slug,
  p.chain_key,
  p.chain_id,
  p.chain_name,
  p.chain_short_label,
  p.product_key,
  p.gtin_norm,
  p.brand_name,
  p.product_name,
  p.content_quantity,
  p.content_unit,
  count(distinct p.location_key) as monitored_locations_count,
  count(distinct p.location_key) filter (where p.is_visible) as visible_locations_count,
  count(distinct p.location_key) filter (where p.is_available) as available_locations_count,
  count(distinct p.location_key) filter (where p.promo_detected) as promo_locations_count,
  (
    count(distinct p.location_key) filter (where p.is_visible)::numeric
    / nullif(count(distinct p.location_key), 0)
  ) as sku_visibility_rate,
  (
    count(distinct p.location_key) filter (where p.is_available)::numeric
    / nullif(count(distinct p.location_key), 0)
  ) as sku_availability_rate,
  (
    count(distinct p.location_key) filter (where p.promo_detected)::numeric
    / nullif(count(distinct p.location_key), 0)
  ) as promo_share,
  min(p.min_price_amount) as min_price_amount,
  max(p.max_price_amount) as max_price_amount,
  avg(p.avg_price_amount) filter (where p.avg_price_amount is not null) as avg_price_amount,
  percentile_cont(0.5) within group (order by p.avg_price_amount)
    filter (where p.avg_price_amount is not null) as median_price_amount,
  stddev_samp(p.avg_price_amount) filter (where p.avg_price_amount is not null) as price_stddev_amount,
  min(p.min_price_per_unit_amount) as min_price_per_unit_amount,
  avg(p.avg_price_per_unit_amount) filter (where p.avg_price_per_unit_amount is not null) as avg_price_per_unit_amount,
  case
    when min(p.min_price_amount) > 0
    then (max(p.max_price_amount) - min(p.min_price_amount)) / min(p.min_price_amount)
  end as price_dispersion_pct,
  bool_or(p.promo_detected) as promo_detected,
  max(p.max_discount_pct) as max_discount_pct,
  max(p.last_snapshot_ts) as last_snapshot_ts
from public.mw_product_location_presence as p
group by
  p.date_key,
  p.business_date,
  p.business_date_key,
  p.client_id,
  p.client_name,
  p.client_slug,
  p.campaign_id,
  p.campaign_name,
  p.campaign_slug,
  p.chain_key,
  p.chain_id,
  p.chain_name,
  p.chain_short_label,
  p.product_key,
  p.gtin_norm,
  p.brand_name,
  p.product_name,
  p.content_quantity,
  p.content_unit;

create or replace view public.mw_product_chain_benchmark as
with ranked as (
  select
    m.*,
    min(m.avg_price_amount) over (
      partition by m.date_key, m.client_id, m.campaign_id, m.product_key
    ) as market_min_price_amount,
    avg(m.avg_price_amount) over (
      partition by m.date_key, m.client_id, m.campaign_id, m.product_key
    ) as market_avg_price_amount,
    max(m.avg_price_amount) over (
      partition by m.date_key, m.client_id, m.campaign_id, m.product_key
    ) as market_max_price_amount,
    min(m.avg_price_per_unit_amount) over (
      partition by m.date_key, m.client_id, m.campaign_id, m.product_key
    ) as market_min_price_per_unit_amount,
    avg(m.avg_price_per_unit_amount) over (
      partition by m.date_key, m.client_id, m.campaign_id, m.product_key
    ) as market_avg_price_per_unit_amount,
    rank() over (
      partition by m.date_key, m.client_id, m.campaign_id, m.product_key
      order by m.avg_price_amount asc nulls last
    ) as chain_price_rank,
    rank() over (
      partition by m.date_key, m.client_id, m.campaign_id, m.product_key
      order by m.avg_price_per_unit_amount asc nulls last
    ) as chain_unit_price_rank,
    count(*) over (
      partition by m.date_key, m.client_id, m.campaign_id, m.product_key
    ) as competing_chain_count
  from public.mw_daily_price_metrics as m
)
select
  r.*,
  (r.avg_price_amount - r.market_min_price_amount) as price_gap_vs_market_min_amount,
  case
    when r.market_min_price_amount > 0
    then (r.avg_price_amount - r.market_min_price_amount) / r.market_min_price_amount
  end as price_gap_vs_market_min_pct,
  (r.avg_price_amount - r.market_avg_price_amount) as price_gap_vs_market_avg_amount,
  case
    when r.market_avg_price_amount > 0
    then (r.avg_price_amount / r.market_avg_price_amount) * 100
  end as price_position_index,
  (r.avg_price_per_unit_amount - r.market_min_price_per_unit_amount) as unit_price_gap_vs_market_min_amount,
  case
    when r.market_min_price_per_unit_amount > 0
    then (r.avg_price_per_unit_amount - r.market_min_price_per_unit_amount) / r.market_min_price_per_unit_amount
  end as unit_price_gap_vs_market_min_pct,
  case
    when r.market_avg_price_per_unit_amount > 0
    then (r.avg_price_per_unit_amount / r.market_avg_price_per_unit_amount) * 100
  end as unit_price_position_index
from ranked as r;

create or replace view public.mw_brand_competitiveness as
with brand_chain as (
  select
    b.date_key,
    b.business_date,
    b.business_date_key,
    b.client_id,
    b.client_name,
    b.client_slug,
    b.campaign_id,
    b.campaign_name,
    b.campaign_slug,
    b.chain_key,
    b.chain_id,
    b.chain_name,
    b.chain_short_label,
    b.brand_name,
    count(distinct b.product_key) as tracked_product_count,
    avg(b.avg_price_amount) filter (where b.avg_price_amount is not null) as avg_price_amount,
    avg(b.avg_price_per_unit_amount) filter (where b.avg_price_per_unit_amount is not null) as avg_price_per_unit_amount,
    avg(b.price_gap_vs_market_min_pct) filter (where b.price_gap_vs_market_min_pct is not null) as avg_gap_vs_market_min_pct,
    avg(b.price_position_index) filter (where b.price_position_index is not null) as avg_price_position_index,
    avg(b.unit_price_position_index) filter (where b.unit_price_position_index is not null) as avg_unit_price_position_index,
    avg(b.sku_visibility_rate) filter (where b.sku_visibility_rate is not null) as avg_sku_visibility_rate,
    avg(b.sku_availability_rate) filter (where b.sku_availability_rate is not null) as avg_sku_availability_rate,
    avg(b.promo_share) filter (where b.promo_share is not null) as avg_promo_share,
    count(*) filter (where b.chain_price_rank = 1) as lowest_price_product_count,
    count(*) filter (where b.price_gap_vs_market_min_pct <= 0.02) as competitive_product_count,
    count(*) filter (where b.price_gap_vs_market_min_pct >= 0.10) as premium_product_count
  from public.mw_product_chain_benchmark as b
  group by
    b.date_key,
    b.business_date,
    b.business_date_key,
    b.client_id,
    b.client_name,
    b.client_slug,
    b.campaign_id,
    b.campaign_name,
    b.campaign_slug,
    b.chain_key,
    b.chain_id,
    b.chain_name,
    b.chain_short_label,
    b.brand_name
)
select
  bc.*,
  rank() over (
    partition by bc.date_key, bc.client_id, bc.campaign_id, bc.brand_name
    order by bc.avg_price_position_index asc nulls last
  ) as brand_chain_price_rank,
  rank() over (
    partition by bc.date_key, bc.client_id, bc.campaign_id, bc.brand_name
    order by bc.avg_sku_visibility_rate desc nulls last
  ) as brand_chain_visibility_rank
from brand_chain as bc;

create or replace view public.mw_price_change_events as
with sequenced as (
  select
    m.*,
    lag(m.avg_price_amount) over (
      partition by m.client_id, m.campaign_id, m.chain_key, m.product_key
      order by m.date_key
    ) as previous_avg_price_amount,
    lag(m.avg_price_per_unit_amount) over (
      partition by m.client_id, m.campaign_id, m.chain_key, m.product_key
      order by m.date_key
    ) as previous_avg_price_per_unit_amount,
    lag(m.date_key) over (
      partition by m.client_id, m.campaign_id, m.chain_key, m.product_key
      order by m.date_key
    ) as previous_date_key
  from public.mw_daily_price_metrics as m
)
select
  md5(concat_ws(':', 'price', s.date_key, s.client_id, s.campaign_id, s.chain_key, s.product_key)) as event_id,
  s.date_key,
  s.business_date,
  s.business_date_key,
  s.previous_date_key,
  s.client_id,
  s.client_name,
  s.client_slug,
  s.campaign_id,
  s.campaign_name,
  s.campaign_slug,
  s.chain_key,
  s.chain_id,
  s.chain_name,
  s.chain_short_label,
  s.product_key,
  s.gtin_norm,
  s.brand_name,
  s.product_name,
  s.content_quantity,
  s.content_unit,
  s.previous_avg_price_amount,
  s.avg_price_amount as current_avg_price_amount,
  (s.avg_price_amount - s.previous_avg_price_amount) as price_change_amount,
  case
    when s.previous_avg_price_amount > 0
    then (s.avg_price_amount - s.previous_avg_price_amount) / s.previous_avg_price_amount
  end as price_change_pct,
  s.previous_avg_price_per_unit_amount,
  s.avg_price_per_unit_amount as current_avg_price_per_unit_amount,
  (s.avg_price_per_unit_amount - s.previous_avg_price_per_unit_amount) as unit_price_change_amount,
  case
    when s.previous_avg_price_per_unit_amount > 0
    then (s.avg_price_per_unit_amount - s.previous_avg_price_per_unit_amount) / s.previous_avg_price_per_unit_amount
  end as unit_price_change_pct,
  case
    when s.avg_price_amount > s.previous_avg_price_amount then 'price_increase'
    when s.avg_price_amount < s.previous_avg_price_amount then 'price_decrease'
  end as event_type,
  case
    when abs((s.avg_price_amount - s.previous_avg_price_amount) / nullif(s.previous_avg_price_amount, 0)) >= 0.10
      or abs(s.avg_price_amount - s.previous_avg_price_amount) >= 1000
    then 'high'
    when abs((s.avg_price_amount - s.previous_avg_price_amount) / nullif(s.previous_avg_price_amount, 0)) >= 0.05
      or abs(s.avg_price_amount - s.previous_avg_price_amount) >= 500
    then 'medium'
    else 'low'
  end as severity
from sequenced as s
where s.previous_avg_price_amount is not null
  and s.avg_price_amount is not null
  and s.avg_price_amount <> s.previous_avg_price_amount
  and (
    abs((s.avg_price_amount - s.previous_avg_price_amount) / nullif(s.previous_avg_price_amount, 0)) >= 0.03
    or abs(s.avg_price_amount - s.previous_avg_price_amount) >= 100
  );

create or replace view public.mw_visibility_events as
with sequenced as (
  select
    p.*,
    lag(p.is_visible) over (
      partition by p.client_id, p.campaign_id, p.chain_key, p.location_key, p.product_key
      order by p.date_key
    ) as previous_is_visible,
    lag(p.is_available) over (
      partition by p.client_id, p.campaign_id, p.chain_key, p.location_key, p.product_key
      order by p.date_key
    ) as previous_is_available,
    lag(p.date_key) over (
      partition by p.client_id, p.campaign_id, p.chain_key, p.location_key, p.product_key
      order by p.date_key
    ) as previous_date_key
  from public.mw_product_location_presence as p
)
select
  md5(concat_ws(':', 'visibility', s.date_key, s.client_id, s.campaign_id, s.chain_key, s.location_key, s.product_key)) as event_id,
  s.date_key,
  s.business_date,
  s.business_date_key,
  s.previous_date_key,
  s.client_id,
  s.client_name,
  s.client_slug,
  s.campaign_id,
  s.campaign_name,
  s.campaign_slug,
  s.chain_key,
  s.chain_id,
  s.chain_name,
  s.chain_short_label,
  s.location_key,
  s.location_code,
  s.location_name,
  s.location_type,
  s.province,
  s.canton,
  s.district,
  s.sales_channel,
  s.region_id,
  s.product_key,
  s.gtin_norm,
  s.brand_name,
  s.product_name,
  s.content_quantity,
  s.content_unit,
  s.previous_is_visible,
  s.is_visible as current_is_visible,
  s.previous_is_available,
  s.is_available as current_is_available,
  case
    when coalesce(s.previous_is_visible, false) = false and s.is_visible then 'sku_listed'
    when coalesce(s.previous_is_visible, false) = true and s.is_visible = false then 'sku_unlisted'
    when coalesce(s.previous_is_available, false) = false and s.is_available then 'sku_available'
    when coalesce(s.previous_is_available, false) = true and s.is_available = false then 'sku_unavailable'
  end as event_type,
  case
    when coalesce(s.previous_is_visible, false) = true and s.is_visible = false then 'high'
    when coalesce(s.previous_is_available, false) = true and s.is_available = false then 'medium'
    else 'low'
  end as severity
from sequenced as s
where s.previous_date_key is not null
  and (
    s.is_visible is distinct from s.previous_is_visible
    or s.is_available is distinct from s.previous_is_available
  );

create or replace view public.mw_executive_insights as
select
  concat('price:', e.event_id) as insight_id,
  e.date_key,
  e.business_date,
  e.business_date_key,
  e.client_id,
  e.client_name,
  e.client_slug,
  e.campaign_id,
  e.campaign_name,
  e.campaign_slug,
  e.chain_key,
  e.chain_id,
  e.chain_name,
  e.chain_short_label,
  null::bigint as location_key,
  null::text as location_code,
  null::text as location_name,
  null::text as province,
  null::text as canton,
  null::text as district,
  e.product_key,
  e.gtin_norm,
  e.brand_name,
  e.product_name,
  e.severity,
  e.event_type as insight_type,
  'price_intelligence'::text as insight_area,
  case
    when e.event_type = 'price_increase' then 'Aumento relevante de precio'
    when e.event_type = 'price_decrease' then 'Reduccion relevante de precio'
  end as title,
  concat(
    e.product_name,
    ' en ',
    e.chain_short_label,
    case
      when e.event_type = 'price_increase' then ' subio '
      else ' bajo '
    end,
    'de ',
    round(e.previous_avg_price_amount, 2),
    ' a ',
    round(e.current_avg_price_amount, 2),
    ' colones.'
  ) as narrative,
  e.price_change_amount as metric_amount,
  e.price_change_pct as metric_pct,
  e.event_id as source_event_id,
  'mw_price_change_events'::text as source_view_name
from public.mw_price_change_events as e
union all
select
  concat('visibility:', e.event_id) as insight_id,
  e.date_key,
  e.business_date,
  e.business_date_key,
  e.client_id,
  e.client_name,
  e.client_slug,
  e.campaign_id,
  e.campaign_name,
  e.campaign_slug,
  e.chain_key,
  e.chain_id,
  e.chain_name,
  e.chain_short_label,
  e.location_key,
  e.location_code,
  e.location_name,
  e.province,
  e.canton,
  e.district,
  e.product_key,
  e.gtin_norm,
  e.brand_name,
  e.product_name,
  e.severity,
  e.event_type as insight_type,
  'sku_visibility'::text as insight_area,
  case
    when e.event_type = 'sku_listed' then 'SKU aparecio en tienda'
    when e.event_type = 'sku_unlisted' then 'SKU desaparecio de tienda'
    when e.event_type = 'sku_available' then 'SKU volvio a estar disponible'
    when e.event_type = 'sku_unavailable' then 'SKU dejo de estar disponible'
  end as title,
  concat(
    e.product_name,
    ' en ',
    e.chain_short_label,
    ' / ',
    e.location_name,
    case
      when e.event_type = 'sku_listed' then ' aparecio listado.'
      when e.event_type = 'sku_unlisted' then ' dejo de aparecer listado.'
      when e.event_type = 'sku_available' then ' volvio a estar disponible.'
      when e.event_type = 'sku_unavailable' then ' dejo de estar disponible.'
    end
  ) as narrative,
  null::numeric as metric_amount,
  null::numeric as metric_pct,
  e.event_id as source_event_id,
  'mw_visibility_events'::text as source_view_name
from public.mw_visibility_events as e;
