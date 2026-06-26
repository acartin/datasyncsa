begin;

do $$
declare
  relation record;
begin
  for relation in
    select n.nspname, c.relname, c.relkind
    from pg_class c
    join pg_namespace n
      on n.oid = c.relnamespace
    where n.nspname = 'public'
      and c.relname in (
        'mw_app_product_chain_price_history',
        'mw_app_product_store_activity',
        'mw_app_product_chain_day',
        'mw_app_product_store_day'
      )
  loop
    if relation.relkind = 'm' then
      execute format('drop materialized view %I.%I cascade', relation.nspname, relation.relname);
    elsif relation.relkind = 'v' then
      execute format('drop view %I.%I cascade', relation.nspname, relation.relname);
    elsif relation.relkind in ('r', 'p') then
      execute format('drop table %I.%I cascade', relation.nspname, relation.relname);
    end if;
  end loop;
end $$;

create table public.mw_app_product_chain_day as
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
  o.chain_id,
  o.chain_name,
  o.chain_label as chain,
  o.product_key,
  o.gtin_norm as gtin,
  o.brand_name as brand,
  o.product_name as product,
  o.content_quantity,
  o.content_unit,
  min(o.captured_at_cr) as capture_started_at_cr,
  max(o.captured_at_cr) as captured_at_cr,
  count(distinct o.run_key)::int as runs_seen,
  count(distinct o.location_key)::int as observed_locations,
  count(distinct o.location_key) filter (where o.is_listed)::int as visible_locations,
  count(distinct o.location_key) filter (where o.is_available)::int as available_locations,
  count(distinct o.location_key) filter (
    where o.is_available
      and o.spot_price_amount is not null
  )::int as promo_locations,
  round(avg(coalesce(o.spot_price_amount, o.effective_price_amount)) filter (
    where o.is_available
      and coalesce(o.spot_price_amount, o.effective_price_amount) is not null
  ), 2) as average_price,
  round(avg(o.effective_price_per_unit_amount) filter (
    where o.is_available
      and o.effective_price_per_unit_amount is not null
  ), 4) as average_unit_price,
  round(min(coalesce(o.spot_price_amount, o.effective_price_amount)) filter (where o.is_available), 2) as min_price,
  round(max(coalesce(o.spot_price_amount, o.effective_price_amount)) filter (where o.is_available), 2) as max_price,
  round(avg(o.reference_price_amount) filter (
    where o.is_available
      and o.reference_price_amount is not null
  ), 2) as reference_price_amount,
  round(avg(o.spot_price_amount) filter (
    where o.is_available
      and o.spot_price_amount is not null
  ), 2) as promo_price_amount,
  bool_or(o.is_available and o.spot_price_amount is not null) as promo_detected,
  round(
    count(distinct o.location_key) filter (
      where o.is_available
        and o.spot_price_amount is not null
    )::numeric
    / nullif(count(distinct o.location_key), 0)::numeric
    * 100,
    2
  ) as promo_share_pct,
  case
    when (avg(o.reference_price_amount) filter (where o.is_available)) > 0
      and (avg(o.spot_price_amount) filter (where o.is_available and o.spot_price_amount is not null)) is not null
    then round(
      (
        (
          avg(o.reference_price_amount) filter (where o.is_available)
        ) - (
          avg(o.spot_price_amount) filter (where o.is_available and o.spot_price_amount is not null)
        )
      ) / (avg(o.reference_price_amount) filter (where o.is_available))
      * 100,
      2
    )
  end as max_discount_pct,
  round(max(o.discount_pct) * 100, 2) as discount_pct,
  round(s.gap_vs_market_best_pct * 100, 2) as gap_pct,
  round(s.price_position_index, 2) as price_index,
  s.price_reading,
  s.suggested_action,
  case
    when count(distinct o.location_key) filter (where o.is_available) > 0 then 'available'
    when count(distinct o.location_key) filter (where o.is_listed) > 0 then 'listed_unavailable'
    else 'unobserved'
  end as availability_state,
  max(o.product_url) filter (where o.product_url is not null) as product_url,
  max(o.image_url) filter (where o.image_url is not null) as image_url
from public.mw_core_sku_store_observation as o
left join public.mw_signal_sku_chain_daily as s
  on s.date_key = o.date_key
 and s.client_id = o.client_id
 and s.campaign_id = o.campaign_id
 and s.product_key = o.product_key
 and s.chain_key = o.chain_key
where false
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
  o.chain_id,
  o.chain_name,
  o.chain_label,
  o.product_key,
  o.gtin_norm,
  o.brand_name,
  o.product_name,
  o.content_quantity,
  o.content_unit,
  s.gap_vs_market_best_pct,
  s.price_position_index,
  s.price_reading,
  s.suggested_action;

create table public.mw_app_product_store_day as
with ranked as (
  select
    o.*,
    row_number() over (
      partition by
        o.date_key,
        o.client_id,
        o.campaign_id,
        o.chain_key,
        o.product_key,
        o.location_key
      order by
        o.captured_at_cr desc nulls last,
        o.is_available desc nulls last,
        o.is_listed desc nulls last,
        coalesce(o.spot_price_amount, o.effective_price_amount, o.price_amount) nulls last,
        o.listing_key desc
    ) as row_rank
  from public.mw_core_sku_store_observation as o
  where false
)
select
  r.date_key,
  r.business_date,
  r.week_start_date as week_start,
  r.month_start_date as month_start,
  r.client_id,
  r.client_name as client,
  r.campaign_id,
  r.campaign_name as campaign,
  r.chain_key,
  r.chain_id,
  r.chain_name,
  r.chain_label as chain,
  r.product_key,
  r.gtin_norm as gtin,
  r.brand_name as brand,
  r.product_name as product,
  r.content_quantity,
  r.content_unit,
  r.location_key,
  coalesce(loc.location_code, r.location_code) as location_code,
  coalesce(loc.location_name, r.location_name) as location_name,
  coalesce(loc.location_type, r.location_type) as location_type,
  coalesce(loc.province, r.province) as province,
  coalesce(loc.canton, r.canton) as canton,
  coalesce(loc.district, r.district) as district,
  coalesce(loc.sales_channel, r.sales_channel) as sales_channel,
  coalesce(loc.region_id, r.region_id) as region_id,
  r.captured_at_cr,
  r.currency_code,
  r.is_listed,
  r.is_available,
  r.has_discount,
  r.price_amount,
  r.list_price_amount,
  r.price_without_discount_amount,
  r.spot_price_amount,
  r.effective_price_amount,
  r.reference_price_amount,
  r.effective_price_per_unit_amount,
  r.discount_pct,
  round(r.discount_pct * 100, 2) as discount_pct_display,
  r.promo_detected,
  r.available_quantity,
  case
    when r.is_available then 'available'
    when r.is_listed then 'listed_unavailable'
    else 'unobserved'
  end as availability_state,
  r.product_url,
  r.image_url,
  r.source_engine
from ranked as r
left join public.mkt_dim_location as loc
  on loc.location_key = r.location_key
where r.row_rank = 1;

create unique index mw_app_product_chain_day_uq
  on public.mw_app_product_chain_day (client_id, campaign_id, product_key, chain_key, date_key);

create index mw_app_product_chain_day_lookup_idx
  on public.mw_app_product_chain_day (client_id, product_key, date_key desc);

create index mw_app_product_chain_day_campaign_idx
  on public.mw_app_product_chain_day (client_id, campaign_id, product_key, date_key desc);

create index mw_app_product_chain_day_chain_idx
  on public.mw_app_product_chain_day (client_id, product_key, chain, date_key desc);

create unique index mw_app_product_store_day_uq
  on public.mw_app_product_store_day (client_id, campaign_id, product_key, chain_key, location_key, date_key);

create index mw_app_product_store_day_lookup_idx
  on public.mw_app_product_store_day (client_id, product_key, date_key desc);

create index mw_app_product_store_day_store_idx
  on public.mw_app_product_store_day (client_id, product_key, location_key, date_key desc);

create index mw_app_product_store_day_campaign_idx
  on public.mw_app_product_store_day (client_id, campaign_id, product_key, date_key desc);

comment on table public.mw_app_product_chain_day is
  'Stable app table for Market Watch product drill-down. Grain: client, campaign, product, chain and day.';

comment on table public.mw_app_product_store_day is
  'Stable app table for Market Watch store drill-down. Grain: client, campaign, product, chain, store and day.';

commit;
