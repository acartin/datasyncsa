begin;

drop view if exists public.mw_superset_eventos;
drop view if exists public.mw_superset_detalle_tienda_sku;
drop view if exists public.mw_superset_oportunidades_sku;
drop view if exists public.mw_superset_benchmark_marca_cadena;
drop view if exists public.mw_superset_senales_ejecutivas;

drop view if exists public.mw_executive_insights;
drop view if exists public.mw_visibility_events;
drop view if exists public.mw_price_change_events;
drop view if exists public.mw_brand_competitiveness;
drop view if exists public.mw_product_chain_benchmark;
drop view if exists public.mw_daily_price_metrics;
drop view if exists public.mw_product_location_presence;
drop view if exists public.mw_fact_analytic_listing_snapshot;

drop view if exists public.mw_bi_executive_signal_feed cascade;
drop view if exists public.mw_bi_radar_event_feed cascade;
drop view if exists public.mw_bi_sku_store_price_evidence cascade;
drop view if exists public.mw_bi_sku_price_drivers cascade;
drop view if exists public.mw_bi_brand_chain_price_index cascade;
drop view if exists public.mw_signal_promo_daily cascade;
drop view if exists public.mw_signal_price_change_daily cascade;
drop view if exists public.mw_signal_sku_store_observation cascade;
drop view if exists public.mw_signal_sku_chain_daily cascade;
drop view if exists public.mw_signal_brand_chain_daily cascade;
drop view if exists public.mw_core_promo_daily cascade;
drop view if exists public.mw_core_price_change_day cascade;
drop view if exists public.mw_core_brand_chain_day cascade;
drop view if exists public.mw_core_sku_chain_day cascade;

create or replace view public.mw_core_sku_store_observation as
select
  f.date_key,
  to_date(f.date_key::text, 'YYYYMMDD') as business_date,
  date_trunc('week', to_date(f.date_key::text, 'YYYYMMDD'))::date as week_start_date,
  date_trunc('month', to_date(f.date_key::text, 'YYYYMMDD'))::date as month_start_date,
  r.business_date_key,
  f.run_key,
  r.run_kind,
  r.run_status,
  cca.client_id,
  ac.name as client_name,
  ac.client_key as client_slug,
  r.campaign_id,
  camp.name as campaign_name,
  camp.slug as campaign_slug,
  f.chain_key,
  c.chain_id,
  c.chain_name,
  coalesce(c.short_label, c.chain_name) as chain_label,
  f.location_key,
  loc.location_code,
  loc.location_name,
  loc.location_type,
  loc.province,
  loc.canton,
  loc.district,
  loc.sales_channel,
  loc.region_id,
  f.product_key,
  p.gtin_norm,
  p.brand_name,
  p.product_name,
  p.content_quantity,
  p.content_unit,
  f.listing_key,
  l.source_product_id,
  l.source_sku,
  l.seller_id,
  l.seller_name,
  l.listing_name,
  l.root_category_slug,
  l.root_category_name,
  l.product_url,
  l.image_url,
  f.snapshot_ts,
  f.snapshot_ts at time zone 'America/Costa_Rica' as captured_at_cr,
  f.currency_code,
  f.is_listed,
  f.is_available,
  f.has_discount,
  f.price_amount,
  f.list_price_amount,
  f.price_without_discount_amount,
  f.spot_price_amount,
  case
    when coalesce(f.is_available, false)
      and coalesce(
        f.price_amount,
        f.spot_price_amount,
        f.price_without_discount_amount,
        f.list_price_amount
      ) > 0
    then coalesce(
      f.price_amount,
      f.spot_price_amount,
      f.price_without_discount_amount,
      f.list_price_amount
    )
  end as effective_price_amount,
  case
    when coalesce(f.is_available, false)
      and coalesce(
        f.price_amount,
        f.spot_price_amount,
        f.price_without_discount_amount,
        f.list_price_amount
      ) > 0
    then coalesce(
      f.list_price_amount,
      f.price_without_discount_amount,
      f.price_amount,
      f.spot_price_amount
    )
  end as reference_price_amount,
  case
    when p.content_quantity > 0
      and coalesce(f.is_available, false)
      and coalesce(
        f.price_amount,
        f.spot_price_amount,
        f.price_without_discount_amount,
        f.list_price_amount
      ) > 0
    then coalesce(
      f.price_amount,
      f.spot_price_amount,
      f.price_without_discount_amount,
      f.list_price_amount
    ) / p.content_quantity
  end as effective_price_per_unit_amount,
  bool_or(coalesce(f.has_discount, false)) over (
    partition by f.date_key, r.campaign_id, f.chain_key, f.location_key, f.product_key
  ) as discount_observed_for_store,
  (
    coalesce(f.is_available, false)
    and coalesce(
      f.price_amount,
      f.spot_price_amount,
      f.price_without_discount_amount,
      f.list_price_amount
    ) > 0
    and (
      coalesce(f.has_discount, false)
      or (
        coalesce(
          f.list_price_amount,
          f.price_without_discount_amount,
          f.price_amount,
          f.spot_price_amount
        ) is not null
        and coalesce(
          f.price_amount,
          f.spot_price_amount,
          f.price_without_discount_amount,
          f.list_price_amount
        ) is not null
        and coalesce(
          f.list_price_amount,
          f.price_without_discount_amount,
          f.price_amount,
          f.spot_price_amount
        ) > coalesce(
          f.price_amount,
          f.spot_price_amount,
          f.price_without_discount_amount,
          f.list_price_amount
        )
      )
    )
  ) as promo_detected,
  case
    when coalesce(f.is_available, false)
      and coalesce(
        f.price_amount,
        f.spot_price_amount,
        f.price_without_discount_amount,
        f.list_price_amount
      ) > 0
      and coalesce(
        f.list_price_amount,
        f.price_without_discount_amount,
        f.price_amount,
        f.spot_price_amount
      ) > 0
    then (
      coalesce(
        f.list_price_amount,
        f.price_without_discount_amount,
        f.price_amount,
        f.spot_price_amount
      ) - coalesce(
        f.price_amount,
        f.spot_price_amount,
        f.price_without_discount_amount,
        f.list_price_amount
      )
    ) / coalesce(
      f.list_price_amount,
      f.price_without_discount_amount,
      f.price_amount,
      f.spot_price_amount
    )
  end as discount_pct,
  f.available_quantity,
  f.price_valid_until_text,
  r.pricing_scope,
  r.catalog_id,
  r.source_engine,
  r.started_at as run_started_at,
  r.finished_at as run_finished_at,
  r.raw_metadata as run_metadata,
  f.created_at as fact_created_at
from public.mkt_fact_listing_snapshot as f
join public.mkt_run as r
  on r.run_key = f.run_key
join public.mkt_dim_chain as c
  on c.chain_key = f.chain_key
join public.mkt_dim_product as p
  on p.product_key = f.product_key
join public.mkt_dim_listing as l
  on l.listing_key = f.listing_key
left join public.mkt_dim_location as loc
  on loc.location_key = f.location_key
left join public.mkt_dim_campaign as camp
  on camp.id = r.campaign_id
join public.mkt_campaign_client_access as cca
  on cca.campaign_id = r.campaign_id
 and cca.is_active
 and (
   cca.valid_from is null
   or to_date(r.business_date_key::text, 'YYYYMMDD') >= cca.valid_from
 )
 and (
   cca.valid_to is null
   or to_date(r.business_date_key::text, 'YYYYMMDD') <= cca.valid_to
 )
join public.auth_clients as ac
  on ac.id = cca.client_id
 and ac.status = 'active'
where r.run_kind = 'analytic'
  and r.run_status = 'succeeded';

alter table if exists public.mkt_run
  drop constraint if exists mkt_stage_catalog_run_client_id_fkey,
  drop column if exists client_id;

alter table if exists public.mkt_dim_campaign
  drop constraint if exists mkt_dim_campaign_client_id_fkey,
  drop column if exists client_id;

drop table if exists public.mkt_dim_client;

create or replace view public.mw_core_sku_chain_day as
with store_day as (
  select
    o.date_key,
    o.business_date,
    o.week_start_date,
    o.month_start_date,
    o.business_date_key,
    o.client_id,
    o.client_name,
    o.client_slug,
    o.campaign_id,
    o.campaign_name,
    o.campaign_slug,
    o.chain_key,
    o.chain_id,
    o.chain_name,
    o.chain_label,
    o.location_key,
    o.location_code,
    o.location_name,
    o.province,
    o.canton,
    o.district,
    o.product_key,
    o.gtin_norm,
    o.brand_name,
    o.product_name,
    o.content_quantity,
    o.content_unit,
    count(*) as observed_listing_count,
    count(*) filter (where o.is_listed) as listed_listing_count,
    count(*) filter (where o.is_available) as available_listing_count,
    bool_or(coalesce(o.is_listed, false)) as is_visible,
    bool_or(coalesce(o.is_available, false)) as is_available,
    bool_or(coalesce(o.promo_detected, false)) as promo_detected,
    min(o.effective_price_amount) as min_price_amount,
    max(o.effective_price_amount) as max_price_amount,
    avg(o.effective_price_amount) filter (where o.effective_price_amount is not null) as avg_price_amount,
    min(o.effective_price_per_unit_amount) as min_price_per_unit_amount,
    avg(o.effective_price_per_unit_amount) filter (where o.effective_price_per_unit_amount is not null) as avg_price_per_unit_amount,
    max(o.discount_pct) as max_discount_pct,
    max(o.snapshot_ts) as last_snapshot_ts
  from public.mw_core_sku_store_observation as o
  group by
    o.date_key,
    o.business_date,
    o.week_start_date,
    o.month_start_date,
    o.business_date_key,
    o.client_id,
    o.client_name,
    o.client_slug,
    o.campaign_id,
    o.campaign_name,
    o.campaign_slug,
    o.chain_key,
    o.chain_id,
    o.chain_name,
    o.chain_label,
    o.location_key,
    o.location_code,
    o.location_name,
    o.province,
    o.canton,
    o.district,
    o.product_key,
    o.gtin_norm,
    o.brand_name,
    o.product_name,
    o.content_quantity,
    o.content_unit
),
chain_day as (
  select
    s.date_key,
    s.business_date,
    s.week_start_date,
    s.month_start_date,
    s.business_date_key,
    s.client_id,
    s.client_name,
    s.client_slug,
    s.campaign_id,
    s.campaign_name,
    s.campaign_slug,
    s.chain_key,
    s.chain_id,
    s.chain_name,
    s.chain_label,
    s.product_key,
    s.gtin_norm,
    s.brand_name,
    s.product_name,
    s.content_quantity,
    s.content_unit,
    count(distinct s.location_key) as monitored_locations_count,
    count(distinct s.location_key) filter (where s.is_visible) as visible_locations_count,
    count(distinct s.location_key) filter (where s.is_available) as available_locations_count,
    count(distinct s.location_key) filter (where s.promo_detected) as promo_locations_count,
    (
      count(distinct s.location_key) filter (where s.is_visible)::numeric
      / nullif(count(distinct s.location_key), 0)
    ) as visibility_rate,
    (
      count(distinct s.location_key) filter (where s.is_available)::numeric
      / nullif(count(distinct s.location_key), 0)
    ) as availability_rate,
    (
      count(distinct s.location_key) filter (where s.promo_detected)::numeric
      / nullif(count(distinct s.location_key), 0)
    ) as promo_share,
    min(s.min_price_amount) as min_price_amount,
    max(s.max_price_amount) as max_price_amount,
    avg(s.avg_price_amount) filter (where s.avg_price_amount is not null) as avg_price_amount,
    percentile_cont(0.5) within group (order by s.avg_price_amount)
      filter (where s.avg_price_amount is not null) as median_price_amount,
    stddev_samp(s.avg_price_amount) filter (where s.avg_price_amount is not null) as price_stddev_amount,
    min(s.min_price_per_unit_amount) as min_price_per_unit_amount,
    avg(s.avg_price_per_unit_amount) filter (where s.avg_price_per_unit_amount is not null) as avg_price_per_unit_amount,
    case
      when min(s.min_price_amount) > 0
      then (max(s.max_price_amount) - min(s.min_price_amount)) / min(s.min_price_amount)
    end as store_price_dispersion_pct,
    bool_or(s.promo_detected) as promo_detected,
    max(s.max_discount_pct) as max_discount_pct,
    max(s.last_snapshot_ts) as last_snapshot_ts
  from store_day as s
  group by
    s.date_key,
    s.business_date,
    s.week_start_date,
    s.month_start_date,
    s.business_date_key,
    s.client_id,
    s.client_name,
    s.client_slug,
    s.campaign_id,
    s.campaign_name,
    s.campaign_slug,
    s.chain_key,
    s.chain_id,
    s.chain_name,
    s.chain_label,
    s.product_key,
    s.gtin_norm,
    s.brand_name,
    s.product_name,
    s.content_quantity,
    s.content_unit
),
ranked as (
  select
    c.*,
    min(c.avg_price_amount) over (
      partition by c.date_key, c.client_id, c.campaign_id, c.product_key
    ) as market_best_price_amount,
    avg(c.avg_price_amount) over (
      partition by c.date_key, c.client_id, c.campaign_id, c.product_key
    ) as market_avg_price_amount,
    max(c.avg_price_amount) over (
      partition by c.date_key, c.client_id, c.campaign_id, c.product_key
    ) as market_max_price_amount,
    min(c.avg_price_per_unit_amount) over (
      partition by c.date_key, c.client_id, c.campaign_id, c.product_key
    ) as market_best_price_per_unit_amount,
    avg(c.avg_price_per_unit_amount) over (
      partition by c.date_key, c.client_id, c.campaign_id, c.product_key
    ) as market_avg_price_per_unit_amount,
    rank() over (
      partition by c.date_key, c.client_id, c.campaign_id, c.product_key
      order by c.avg_price_amount asc nulls last, c.chain_label
    ) as chain_price_rank,
    rank() over (
      partition by c.date_key, c.client_id, c.campaign_id, c.product_key
      order by c.avg_price_per_unit_amount asc nulls last, c.chain_label
    ) as chain_unit_price_rank,
    count(c.avg_price_amount) over (
      partition by c.date_key, c.client_id, c.campaign_id, c.product_key
    ) as competing_chain_count
  from chain_day as c
),
best_price as (
  select distinct on (date_key, client_id, campaign_id, product_key)
    date_key,
    client_id,
    campaign_id,
    product_key,
    chain_key as best_price_chain_key,
    chain_label as best_price_chain_label,
    avg_price_amount as best_price_amount
  from ranked
  where avg_price_amount is not null
  order by
    date_key,
    client_id,
    campaign_id,
    product_key,
    avg_price_amount asc nulls last,
    chain_label
),
chain_link as (
  select distinct on (date_key, campaign_id, product_key, chain_key)
    date_key,
    campaign_id,
    product_key,
    chain_key,
    product_url,
    image_url
  from public.mw_core_sku_store_observation
  where effective_price_amount is not null
    and (product_url is not null or image_url is not null)
  order by
    date_key,
    campaign_id,
    product_key,
    chain_key,
    case when product_url is not null then 0 else 1 end,
    snapshot_ts desc
)
select
  r.*,
  (r.avg_price_amount - r.market_best_price_amount) as gap_vs_market_best_amount,
  case
    when r.market_best_price_amount > 0
    then (r.avg_price_amount - r.market_best_price_amount) / r.market_best_price_amount
  end as gap_vs_market_best_pct,
  (r.avg_price_amount - r.market_avg_price_amount) as gap_vs_market_avg_amount,
  case
    when r.market_avg_price_amount > 0
    then (r.avg_price_amount / r.market_avg_price_amount) * 100
  end as price_position_index,
  (r.avg_price_per_unit_amount - r.market_best_price_per_unit_amount) as unit_gap_vs_market_best_amount,
  case
    when r.market_best_price_per_unit_amount > 0
    then (r.avg_price_per_unit_amount - r.market_best_price_per_unit_amount) / r.market_best_price_per_unit_amount
  end as unit_gap_vs_market_best_pct,
  case
    when r.market_avg_price_per_unit_amount > 0
    then (r.avg_price_per_unit_amount / r.market_avg_price_per_unit_amount) * 100
  end as unit_price_position_index,
  bp.best_price_chain_key,
  bp.best_price_chain_label,
  bp.best_price_amount,
  ll.product_url,
  ll.image_url,
  best_ll.product_url as best_price_product_url,
  best_ll.image_url as best_price_image_url
from ranked as r
left join best_price as bp
  on bp.date_key = r.date_key
 and bp.client_id is not distinct from r.client_id
 and bp.campaign_id is not distinct from r.campaign_id
 and bp.product_key = r.product_key
left join chain_link as ll
  on ll.date_key = r.date_key
 and ll.campaign_id is not distinct from r.campaign_id
 and ll.product_key = r.product_key
 and ll.chain_key = r.chain_key
left join chain_link as best_ll
  on best_ll.date_key = bp.date_key
 and best_ll.campaign_id is not distinct from bp.campaign_id
 and best_ll.product_key = bp.product_key
 and best_ll.chain_key = bp.best_price_chain_key;

create or replace view public.mw_core_brand_chain_day as
with brand_chain as (
  select
    s.date_key,
    s.business_date,
    s.week_start_date,
    s.month_start_date,
    s.business_date_key,
    s.client_id,
    s.client_name,
    s.client_slug,
    s.campaign_id,
    s.campaign_name,
    s.campaign_slug,
    s.chain_key,
    s.chain_id,
    s.chain_name,
    s.chain_label,
    s.brand_name,
    count(distinct s.product_key) as tracked_product_count,
    avg(s.avg_price_amount) filter (where s.avg_price_amount is not null) as avg_price_amount,
    avg(s.avg_price_per_unit_amount) filter (where s.avg_price_per_unit_amount is not null) as avg_price_per_unit_amount,
    avg(s.gap_vs_market_best_pct) filter (where s.gap_vs_market_best_pct is not null) as avg_gap_vs_market_best_pct,
    avg(s.price_position_index) filter (where s.price_position_index is not null) as avg_price_position_index,
    avg(s.unit_price_position_index) filter (where s.unit_price_position_index is not null) as avg_unit_price_position_index,
    avg(s.visibility_rate) filter (where s.visibility_rate is not null) as avg_visibility_rate,
    avg(s.availability_rate) filter (where s.availability_rate is not null) as avg_availability_rate,
    avg(s.promo_share) filter (where s.promo_share is not null) as avg_promo_share,
    count(*) filter (where s.chain_price_rank = 1) as lowest_price_product_count,
    count(*) filter (where s.gap_vs_market_best_pct <= 0.02) as competitive_product_count,
    count(*) filter (where s.gap_vs_market_best_pct >= 0.10) as over_market_product_count
  from public.mw_core_sku_chain_day as s
  group by
    s.date_key,
    s.business_date,
    s.week_start_date,
    s.month_start_date,
    s.business_date_key,
    s.client_id,
    s.client_name,
    s.client_slug,
    s.campaign_id,
    s.campaign_name,
    s.campaign_slug,
    s.chain_key,
    s.chain_id,
    s.chain_name,
    s.chain_label,
    s.brand_name
)
select
  b.*,
  rank() over (
    partition by b.date_key, b.client_id, b.campaign_id, b.brand_name
    order by b.avg_price_position_index asc nulls last, b.chain_label
  ) as brand_chain_price_rank,
  rank() over (
    partition by b.date_key, b.client_id, b.campaign_id, b.brand_name
    order by b.avg_visibility_rate desc nulls last, b.chain_label
  ) as brand_chain_visibility_rank
from brand_chain as b;

create or replace view public.mw_core_price_change_day as
with sequenced as (
  select
    s.*,
    lag(s.avg_price_amount) over (
      partition by s.client_id, s.campaign_id, s.chain_key, s.product_key
      order by s.date_key
    ) as previous_avg_price_amount,
    lag(s.avg_price_per_unit_amount) over (
      partition by s.client_id, s.campaign_id, s.chain_key, s.product_key
      order by s.date_key
    ) as previous_avg_price_per_unit_amount,
    lag(s.monitored_locations_count) over (
      partition by s.client_id, s.campaign_id, s.chain_key, s.product_key
      order by s.date_key
    ) as previous_monitored_locations_count,
    lag(s.visible_locations_count) over (
      partition by s.client_id, s.campaign_id, s.chain_key, s.product_key
      order by s.date_key
    ) as previous_visible_locations_count,
    lag(s.available_locations_count) over (
      partition by s.client_id, s.campaign_id, s.chain_key, s.product_key
      order by s.date_key
    ) as previous_available_locations_count,
    lag(s.date_key) over (
      partition by s.client_id, s.campaign_id, s.chain_key, s.product_key
      order by s.date_key
    ) as previous_date_key
  from public.mw_core_sku_chain_day as s
)
select
  md5(concat_ws(':', 'price', q.date_key, q.client_id, q.campaign_id, q.chain_key, q.product_key)) as event_id,
  q.date_key,
  q.business_date,
  q.week_start_date,
  q.month_start_date,
  q.business_date_key,
  q.previous_date_key,
  q.client_id,
  q.client_name,
  q.client_slug,
  q.campaign_id,
  q.campaign_name,
  q.campaign_slug,
  q.chain_key,
  q.chain_id,
  q.chain_name,
  q.chain_label,
  q.product_key,
  q.gtin_norm,
  q.brand_name,
  q.product_name,
  q.content_quantity,
  q.content_unit,
  q.monitored_locations_count,
  q.visible_locations_count,
  q.available_locations_count,
  q.previous_monitored_locations_count,
  q.previous_visible_locations_count,
  q.previous_available_locations_count,
  q.previous_avg_price_amount,
  q.avg_price_amount as current_avg_price_amount,
  (q.avg_price_amount - q.previous_avg_price_amount) as price_change_amount,
  case
    when q.previous_avg_price_amount > 0
    then (q.avg_price_amount - q.previous_avg_price_amount) / q.previous_avg_price_amount
  end as price_change_pct,
  q.previous_avg_price_per_unit_amount,
  q.avg_price_per_unit_amount as current_avg_price_per_unit_amount,
  (q.avg_price_per_unit_amount - q.previous_avg_price_per_unit_amount) as unit_price_change_amount,
  case
    when q.previous_avg_price_per_unit_amount > 0
    then (q.avg_price_per_unit_amount - q.previous_avg_price_per_unit_amount) / q.previous_avg_price_per_unit_amount
  end as unit_price_change_pct,
  case
    when q.avg_price_amount > q.previous_avg_price_amount then 'price_increase'
    when q.avg_price_amount < q.previous_avg_price_amount then 'price_decrease'
  end as event_type,
  case
    when abs((q.avg_price_amount - q.previous_avg_price_amount) / nullif(q.previous_avg_price_amount, 0)) >= 0.10
      or abs(q.avg_price_amount - q.previous_avg_price_amount) >= 1000
    then 'high'
    when abs((q.avg_price_amount - q.previous_avg_price_amount) / nullif(q.previous_avg_price_amount, 0)) >= 0.05
      or abs(q.avg_price_amount - q.previous_avg_price_amount) >= 500
    then 'medium'
    else 'low'
  end as severity
from sequenced as q
where q.previous_avg_price_amount is not null
  and q.avg_price_amount is not null
  and q.avg_price_amount <> q.previous_avg_price_amount
  and (
    abs((q.avg_price_amount - q.previous_avg_price_amount) / nullif(q.previous_avg_price_amount, 0)) >= 0.03
    or abs(q.avg_price_amount - q.previous_avg_price_amount) >= 100
  );

create or replace view public.mw_core_promo_daily as
with sequenced as (
  select
    s.*,
    lag(s.promo_detected) over (
      partition by s.client_id, s.campaign_id, s.chain_key, s.product_key
      order by s.date_key
    ) as previous_promo_detected,
    lag(s.promo_share) over (
      partition by s.client_id, s.campaign_id, s.chain_key, s.product_key
      order by s.date_key
    ) as previous_promo_share
  from public.mw_core_sku_chain_day as s
)
select
  md5(concat_ws(':', 'promo', p.date_key, p.client_id, p.campaign_id, p.chain_key, p.product_key)) as event_id,
  p.date_key,
  p.business_date,
  p.week_start_date,
  p.month_start_date,
  p.client_id,
  p.client_name,
  p.client_slug,
  p.campaign_id,
  p.campaign_name,
  p.campaign_slug,
  p.chain_key,
  p.chain_id,
  p.chain_name,
  p.chain_label,
  p.product_key,
  p.gtin_norm,
  p.brand_name,
  p.product_name,
  p.promo_detected,
  p.previous_promo_detected,
  p.promo_share,
  p.previous_promo_share,
  p.max_discount_pct,
  case
    when p.promo_detected and coalesce(p.previous_promo_detected, false) = false then 'promo_detected'
    when p.promo_detected = false and coalesce(p.previous_promo_detected, false) then 'promo_ended'
    when p.promo_share > coalesce(p.previous_promo_share, 0) + 0.20 then 'promo_intensity_spike'
  end as event_type,
  case
    when p.max_discount_pct >= 0.20 or p.promo_share >= 0.75 then 'high'
    when p.max_discount_pct >= 0.10 or p.promo_share >= 0.35 then 'medium'
    else 'low'
  end as severity
from sequenced as p
where p.promo_detected
   or p.previous_promo_detected;

create or replace view public.mw_signal_brand_chain_daily as
select
  b.*,
  case
    when b.avg_price_position_index is null then 'no_reading'
    when b.avg_price_position_index < 95 then 'aggressive_pricing'
    when b.avg_price_position_index <= 105 then 'market_aligned'
    when b.avg_price_position_index <= 115 then 'above_market'
    else 'high_premium'
  end as price_reading,
  case
    when b.avg_visibility_rate is null then 'no_reading'
    when b.avg_visibility_rate >= 0.95 then 'high_coverage'
    when b.avg_visibility_rate >= 0.75 then 'medium_coverage'
    else 'low_coverage'
  end as visibility_reading
from public.mw_core_brand_chain_day as b;

create or replace view public.mw_signal_sku_chain_daily as
select
  s.*,
  case
    when s.price_position_index is null then 'no_reading'
    when s.chain_price_rank = 1 then 'best_observed_price'
    when s.gap_vs_market_best_pct <= 0.02 then 'competitive_price'
    when s.gap_vs_market_best_pct <= 0.10 then 'light_gap'
    when s.gap_vs_market_best_pct <= 0.20 then 'relevant_gap'
    else 'high_gap'
  end as price_reading,
  case
    when s.price_position_index is null then 'review_data'
    when s.chain_price_rank = 1 then 'defend_position'
    when s.gap_vs_market_best_pct <= 0.02 then 'monitor'
    when s.gap_vs_market_best_pct <= 0.10 then 'validate_elasticity'
    when s.gap_vs_market_best_pct <= 0.20 then 'review_price_or_promo'
    else 'commercial_priority'
  end as suggested_action
from public.mw_core_sku_chain_day as s
where s.avg_price_amount is not null
  and s.price_position_index is not null;

create or replace view public.mw_signal_sku_store_observation as
select
  o.*
from public.mw_core_sku_store_observation as o
where o.effective_price_amount is not null
  and coalesce(o.is_available, false);

create or replace view public.mw_signal_price_change_daily as
select *
from public.mw_core_price_change_day;

create or replace view public.mw_signal_promo_daily as
select *
from public.mw_core_promo_daily
where event_type is not null;

create or replace view public.mw_bi_brand_chain_price_index as
select
  b.business_date,
  b.week_start_date as week_start,
  b.month_start_date as month_start,
  b.date_key,
  b.client_id,
  b.campaign_id,
  b.client_name as client,
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
from public.mw_signal_brand_chain_daily as b;

create or replace view public.mw_bi_sku_price_drivers as
select
  s.business_date,
  s.week_start_date as week_start,
  s.month_start_date as month_start,
  s.date_key,
  s.client_id,
  s.campaign_id,
  s.client_name as client,
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
from public.mw_signal_sku_chain_daily as s;

create or replace view public.mw_bi_sku_store_price_evidence as
select
  o.business_date,
  o.week_start_date as week_start,
  o.month_start_date as month_start,
  o.date_key,
  o.client_id,
  o.campaign_id,
  o.client_name as client,
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
from public.mw_signal_sku_store_observation as o;

create or replace view public.mw_bi_radar_event_feed as
select
  md5(concat_ws(':', 'radar', e.date_key, e.client_id, e.campaign_id, e.chain_label, e.event_type, e.gtin_norm)) as event_id,
  e.business_date,
  e.week_start_date as week_start,
  e.month_start_date as month_start,
  e.date_key,
  null::int as previous_date_key,
  e.client_id,
  e.campaign_id,
  e.client_name as client,
  e.campaign_name as campaign,
  e.brand_name as brand,
  e.product_name as product,
  e.gtin_norm as gtin,
  null::text as product_key,
  null::numeric as content_quantity,
  null::text as content_unit,
  e.chain_label as chain,
  'price'::text as event_area,
  e.event_type as event_type,
  e.severity,
  e.business_date::text as captured_at_cr,
  null::text as previous_captured_at_cr,
  round(e.previous_avg_price_amount, 2) as previous_value,
  round(e.current_avg_price_amount, 2) as current_value,
  round(e.price_change_amount, 2) as change_amount,
  round(e.price_change_pct * 100, 2) as change_pct,
  null::numeric as promo_share_pct,
  null::numeric(5,2) as discount_pct,
  e.monitored_locations_count::int as observed_locations,
  e.visible_locations_count::int as visible_locations,
  e.available_locations_count::int as available_locations,
  null::text as product_url,
  null::text as image_url
from public.mw_signal_price_change_daily as e
union all
select
  md5(concat_ws(':', 'radar', p.date_key, p.client_id, p.campaign_id, p.chain_label, p.event_type, p.gtin_norm)) as event_id,
  p.business_date,
  p.week_start_date as week_start,
  p.month_start_date as month_start,
  p.date_key,
  null::int as previous_date_key,
  p.client_id,
  p.campaign_id,
  p.client_name as client,
  p.campaign_name as campaign,
  p.brand_name as brand,
  p.product_name as product,
  p.gtin_norm as gtin,
  null::text as product_key,
  null::numeric as content_quantity,
  null::text as content_unit,
  p.chain_label as chain,
  'promotion'::text as event_area,
  p.event_type,
  p.severity,
  p.business_date::text as captured_at_cr,
  null::text as previous_captured_at_cr,
  round(p.previous_promo_share * 100, 2) as previous_value,
  round(p.promo_share * 100, 2) as current_value,
  null::numeric as change_amount,
  round((p.promo_share - coalesce(p.previous_promo_share, 0)) * 100, 2) as change_pct,
  round(p.promo_share * 100, 2) as promo_share_pct,
  null::numeric(5,2) as discount_pct,
  null::int as observed_locations,
  null::int as visible_locations,
  null::int as available_locations,
  null::text as product_url,
  null::text as image_url
from public.mw_signal_promo_daily as p;

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
