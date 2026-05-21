create or replace view public.mw_fact_analytic_listing_snapshot as
select
  f.date_key,
  r.business_date_key,
  f.run_key,
  r.run_kind,
  coalesce(r.client_id, camp.client_id) as client_id,
  client.name as client_name,
  client.slug as client_slug,
  r.campaign_id,
  camp.name as campaign_name,
  camp.slug as campaign_slug,
  f.chain_key,
  c.chain_id,
  c.chain_name,
  coalesce(c.short_label, c.chain_name) as chain_short_label,
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
  f.source_stage_catalog_item_key,
  f.snapshot_ts,
  f.currency_code,
  f.is_listed,
  f.is_available,
  f.has_discount,
  f.price_amount,
  f.list_price_amount,
  f.price_without_discount_amount,
  f.spot_price_amount,
  f.available_quantity,
  f.price_valid_until_text,
  r.pricing_scope,
  r.catalog_id,
  r.source_engine,
  r.started_at as run_started_at,
  r.finished_at as run_finished_at,
  r.catalog_records,
  r.unique_products,
  r.duplicates_skipped,
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
left join public.mkt_dim_client as client
  on client.id = coalesce(r.client_id, camp.client_id)
where r.run_kind = 'analytic'
  and r.run_status = 'succeeded';
