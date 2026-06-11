begin;

do $$
declare
  relation_kind char;
begin
  select c.relkind
    into relation_kind
  from pg_class c
  join pg_namespace n
    on n.oid = c.relnamespace
  where n.nspname = 'public'
    and c.relname = 'mw_app_product_store_activity';

  if relation_kind = 'm' then
    execute 'drop materialized view public.mw_app_product_store_activity';
  elsif relation_kind = 'v' then
    execute 'drop view public.mw_app_product_store_activity';
  end if;
end $$;

do $$
declare
  relation_kind char;
begin
  select c.relkind
    into relation_kind
  from pg_class c
  join pg_namespace n
    on n.oid = c.relnamespace
  where n.nspname = 'public'
    and c.relname = 'mw_app_product_chain_price_history';

  if relation_kind = 'm' then
    execute 'drop materialized view public.mw_app_product_chain_price_history';
  elsif relation_kind = 'v' then
    execute 'drop view public.mw_app_product_chain_price_history';
  end if;
end $$;

create materialized view public.mw_app_product_chain_price_history as
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
  max(o.product_url) filter (where o.product_url is not null) as product_url,
  max(o.image_url) filter (where o.image_url is not null) as image_url
from public.mw_core_sku_store_observation as o
left join public.mw_signal_sku_chain_daily as s
  on s.date_key = o.date_key
 and s.client_id = o.client_id
 and s.campaign_id = o.campaign_id
 and s.product_key = o.product_key
 and s.chain_key = o.chain_key
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

create materialized view public.mw_app_product_store_activity as
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
  o.run_key,
  o.location_key,
  o.location_code,
  o.location_name,
  o.location_type,
  o.province,
  o.canton,
  o.district,
  o.sales_channel,
  o.region_id,
  o.listing_key,
  o.source_product_id,
  o.source_sku,
  o.seller_id,
  o.seller_name,
  o.listing_name,
  o.root_category_slug,
  o.root_category_name,
  o.captured_at_cr,
  o.currency_code,
  o.is_listed,
  o.is_available,
  o.has_discount,
  o.price_amount,
  o.list_price_amount,
  o.price_without_discount_amount,
  o.spot_price_amount,
  o.effective_price_amount,
  o.reference_price_amount,
  o.effective_price_per_unit_amount,
  o.discount_pct,
  round(o.discount_pct * 100, 2) as discount_pct_display,
  o.promo_detected,
  o.available_quantity,
  o.product_url,
  o.image_url,
  o.source_engine
from public.mw_core_sku_store_observation as o
where o.is_listed
   or o.effective_price_amount is not null;

create index mw_app_product_chain_price_history_lookup_idx
  on public.mw_app_product_chain_price_history (client_id, product_key, date_key desc);

create index mw_app_product_chain_price_history_campaign_idx
  on public.mw_app_product_chain_price_history (client_id, campaign_id, product_key, date_key desc);

create index mw_app_product_chain_price_history_chain_idx
  on public.mw_app_product_chain_price_history (client_id, product_key, chain, date_key desc);

create index mw_app_product_store_activity_lookup_idx
  on public.mw_app_product_store_activity (client_id, product_key, date_key desc);

create index mw_app_product_store_activity_store_idx
  on public.mw_app_product_store_activity (client_id, product_key, location_key, date_key desc);

create index mw_app_product_store_activity_campaign_idx
  on public.mw_app_product_store_activity (client_id, campaign_id, product_key, date_key desc);

comment on materialized view public.mw_app_product_chain_price_history is
  'Stable materialized app dataset for the product detail page. Grain: client, campaign, product, chain and date.';

comment on materialized view public.mw_app_product_store_activity is
  'Stable materialized app dataset for product store drill-down evidence. Grain: client, campaign, product, chain, store, date, run and listing.';

commit;
