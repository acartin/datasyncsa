begin;

drop view if exists public.mw_product_chain_coverage_detail;
drop view if exists public.mw_product_chain_coverage;

create or replace view public.mw_product_chain_coverage_detail as
select
  p.product_key,
  p.gtin_norm,
  p.brand_name,
  p.product_name,
  p.content_quantity,
  p.content_unit,
  c.chain_key,
  c.chain_id,
  c.chain_name,
  c.engine,
  count(*)::int as listings_seen,
  count(*) filter (where l.is_active)::int as active_listings,
  max(l.product_url) filter (where l.product_url is not null) as sample_product_url,
  max(l.image_url) filter (where l.image_url is not null) as sample_image_url,
  string_agg(distinct l.root_category_slug, ', ' order by l.root_category_slug)
    filter (where l.root_category_slug is not null) as root_category_slugs,
  min(l.created_at) as first_listing_created_at,
  max(l.updated_at) as last_listing_updated_at
from public.mkt_dim_product as p
join public.mkt_dim_listing as l
  on l.product_key = p.product_key
join public.mkt_dim_chain as c
  on c.chain_key = l.chain_key
group by
  p.product_key,
  p.gtin_norm,
  p.brand_name,
  p.product_name,
  p.content_quantity,
  p.content_unit,
  c.chain_key,
  c.chain_id,
  c.chain_name,
  c.engine;

create or replace view public.mw_product_chain_coverage as
select
  d.product_key,
  d.gtin_norm,
  d.brand_name,
  d.product_name,
  d.content_quantity,
  d.content_unit,
  count(distinct d.chain_key)::int as chains_seen,
  count(distinct d.chain_key) filter (where d.active_listings > 0)::int as active_chains_seen,
  sum(d.listings_seen)::int as listings_seen,
  sum(d.active_listings)::int as active_listings,
  string_agg(distinct d.chain_id, ', ' order by d.chain_id) as chain_ids,
  string_agg(distinct d.chain_name, ', ' order by d.chain_name) as chain_names,
  min(d.first_listing_created_at) as first_listing_created_at,
  max(d.last_listing_updated_at) as last_listing_updated_at
from public.mw_product_chain_coverage_detail as d
group by
  d.product_key,
  d.gtin_norm,
  d.brand_name,
  d.product_name,
  d.content_quantity,
  d.content_unit;

comment on view public.mw_product_chain_coverage_detail is
  'Producto canonico por cadena donde existe al menos un listing conocido.';

comment on view public.mw_product_chain_coverage is
  'Cobertura agregada por producto canonico a partir de listings por cadena.';

commit;
