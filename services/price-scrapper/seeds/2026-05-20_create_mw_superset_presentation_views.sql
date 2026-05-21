drop view if exists public.mw_superset_eventos;
drop view if exists public.mw_superset_detalle_tienda_sku;
drop view if exists public.mw_superset_oportunidades_sku;
drop view if exists public.mw_superset_benchmark_marca_cadena;
drop view if exists public.mw_superset_senales_ejecutivas;

create or replace view public.mw_superset_senales_ejecutivas as
with latest as (
  select
    client_id,
    campaign_id,
    max(date_key) as ultima_fecha_key
  from public.mw_executive_insights
  group by client_id, campaign_id
)
select
  i.business_date as fecha,
  date_trunc('week', i.business_date)::date as semana_inicio,
  date_trunc('month', i.business_date)::date as mes_inicio,
  i.date_key as fecha_key,
  (i.date_key = l.ultima_fecha_key) as es_ultima_fecha,
  i.client_id,
  i.campaign_id,
  i.client_name as cliente,
  i.campaign_name as campana,
  i.brand_name as marca,
  i.product_name as producto,
  i.chain_short_label as cadena,
  i.location_name as tienda,
  i.province as provincia,
  i.canton,
  i.insight_area as area,
  i.insight_type as tipo_senal,
  i.severity as severidad,
  case i.severity
    when 'high' then 1
    when 'medium' then 2
    else 3
  end as prioridad,
  i.title as titulo,
  i.narrative as lectura,
  round(i.metric_amount, 2) as valor_colones,
  round(i.metric_pct * 100, 2) as valor_pct,
  i.source_view_name as fuente,
  case i.chain_short_label
    when 'Walmart' then 1
    when 'Más x Menos' then 2
    when 'Maxi Palí' then 3
    when 'Megasuper' then 4
    else 999
  end as cadena_orden
from public.mw_executive_insights as i
left join latest as l
  on l.client_id is not distinct from i.client_id
 and l.campaign_id is not distinct from i.campaign_id;

create or replace view public.mw_superset_benchmark_marca_cadena as
with latest as (
  select
    client_id,
    campaign_id,
    max(date_key) as ultima_fecha_key
  from public.mw_brand_competitiveness
  group by client_id, campaign_id
)
select
  b.business_date as fecha,
  date_trunc('week', b.business_date)::date as semana_inicio,
  date_trunc('month', b.business_date)::date as mes_inicio,
  b.date_key as fecha_key,
  (b.date_key = l.ultima_fecha_key) as es_ultima_fecha,
  b.client_id,
  b.campaign_id,
  b.client_name as cliente,
  b.campaign_name as campana,
  b.brand_name as marca,
  b.chain_short_label as cadena,
  b.tracked_product_count as productos_monitoreados,
  round(b.avg_price_position_index, 2) as indice_precio,
  round((b.avg_price_position_index - 100), 2) as diferencia_vs_mercado_pct,
  b.brand_chain_price_rank as ranking_precio,
  round(b.avg_sku_visibility_rate * 100, 2) as visibilidad_pct,
  round(b.avg_sku_availability_rate * 100, 2) as disponibilidad_pct,
  round(b.avg_promo_share * 100, 2) as promocion_pct,
  b.lowest_price_product_count as productos_con_mejor_precio,
  b.competitive_product_count as productos_competitivos,
  b.premium_product_count as productos_sobre_mercado,
  case
    when b.avg_price_position_index is null then 'Sin lectura'
    when b.avg_price_position_index < 95 then 'Precio agresivo'
    when b.avg_price_position_index <= 105 then 'Precio alineado'
    when b.avg_price_position_index <= 115 then 'Sobre mercado'
    else 'Premium alto'
  end as lectura_precio,
  case
    when b.avg_sku_visibility_rate is null then 'Sin lectura'
    when b.avg_sku_visibility_rate >= 0.95 then 'Cobertura alta'
    when b.avg_sku_visibility_rate >= 0.75 then 'Cobertura media'
    else 'Cobertura baja'
  end as lectura_visibilidad
  ,round(b.avg_price_amount, 2) as precio_promedio_colones
  ,round(b.avg_price_per_unit_amount, 4) as precio_promedio_por_unidad
  ,case b.chain_short_label
    when 'Walmart' then 1
    when 'Más x Menos' then 2
    when 'Maxi Palí' then 3
    when 'Megasuper' then 4
    else 999
  end as cadena_orden
from public.mw_brand_competitiveness as b
left join latest as l
  on l.client_id is not distinct from b.client_id
 and l.campaign_id is not distinct from b.campaign_id;

create or replace view public.mw_superset_oportunidades_sku as
with latest as (
  select
    client_id,
    campaign_id,
    max(date_key) as ultima_fecha_key
  from public.mw_product_chain_benchmark
  group by client_id, campaign_id
),
listing_links as (
  select distinct on (date_key, campaign_id, product_key, chain_key)
    date_key,
    campaign_id,
    product_key,
    chain_key,
    product_url,
    image_url
  from public.mw_fact_analytic_listing_snapshot
  where product_url is not null
     or image_url is not null
  order by
    date_key,
    campaign_id,
    product_key,
    chain_key,
    case when product_url is not null then 0 else 1 end,
    snapshot_ts desc
),
best_price as (
  select distinct on (date_key, client_id, campaign_id, product_key)
    date_key,
    client_id,
    campaign_id,
    product_key,
    chain_key,
    chain_short_label as cadena_mejor_precio,
    avg_price_amount as mejor_precio,
    avg_price_per_unit_amount as mejor_precio_por_unidad
  from public.mw_product_chain_benchmark
  where avg_price_amount is not null
  order by
    date_key,
    client_id,
    campaign_id,
    product_key,
    avg_price_amount asc nulls last,
    chain_short_label
)
select
  b.business_date as fecha,
  date_trunc('week', b.business_date)::date as semana_inicio,
  date_trunc('month', b.business_date)::date as mes_inicio,
  b.date_key as fecha_key,
  (b.date_key = l.ultima_fecha_key) as es_ultima_fecha,
  b.client_id,
  b.campaign_id,
  b.client_name as cliente,
  b.campaign_name as campana,
  b.brand_name as marca,
  b.product_name as producto,
  b.gtin_norm as gtin,
  b.chain_short_label as cadena,
  b.content_quantity as contenido,
  b.content_unit as unidad,
  round(b.avg_price_amount, 2) as precio_promedio,
  round(b.market_min_price_amount, 2) as mejor_precio_mercado,
  round(b.price_gap_vs_market_min_amount, 2) as brecha_colones,
  round(b.price_gap_vs_market_min_pct * 100, 2) as brecha_pct,
  round(b.price_position_index, 2) as indice_precio,
  b.chain_price_rank as ranking_precio,
  b.monitored_locations_count as tiendas_monitoreadas,
  b.visible_locations_count as tiendas_visibles,
  round(b.sku_visibility_rate * 100, 2) as visibilidad_pct,
  case
    when b.price_position_index is null then 'Sin lectura'
    when b.chain_price_rank = 1 then 'Mejor precio observado'
    when b.price_gap_vs_market_min_pct <= 0.02 then 'Precio competitivo'
    when b.price_gap_vs_market_min_pct <= 0.10 then 'Ligera brecha'
    when b.price_gap_vs_market_min_pct <= 0.20 then 'Brecha relevante'
    else 'Brecha alta'
  end as lectura_precio,
  case
    when b.price_position_index is null then 'Revisar datos'
    when b.chain_price_rank = 1 then 'Defender posicion'
    when b.price_gap_vs_market_min_pct <= 0.02 then 'Mantener vigilancia'
    when b.price_gap_vs_market_min_pct <= 0.10 then 'Validar elasticidad'
    when b.price_gap_vs_market_min_pct <= 0.20 then 'Revisar precio/promocion'
    else 'Prioridad comercial'
  end as accion_sugerida
  ,case b.chain_short_label
    when 'Walmart' then 1
    when 'Más x Menos' then 2
    when 'Maxi Palí' then 3
    when 'Megasuper' then 4
    else 999
  end as cadena_orden,
  ll.product_url as producto_url,
  ll.image_url as imagen_url,
  bp.cadena_mejor_precio,
  best_ll.product_url as mejor_precio_url,
  best_ll.image_url as mejor_precio_imagen_url
from public.mw_product_chain_benchmark as b
left join latest as l
  on l.client_id is not distinct from b.client_id
 and l.campaign_id is not distinct from b.campaign_id
left join listing_links as ll
  on ll.date_key = b.date_key
 and ll.campaign_id is not distinct from b.campaign_id
 and ll.product_key = b.product_key
 and ll.chain_key = b.chain_key
left join best_price as bp
  on bp.date_key = b.date_key
 and bp.client_id is not distinct from b.client_id
 and bp.campaign_id is not distinct from b.campaign_id
 and bp.product_key = b.product_key
left join listing_links as best_ll
  on best_ll.date_key = bp.date_key
 and best_ll.campaign_id is not distinct from bp.campaign_id
 and best_ll.product_key = bp.product_key
 and best_ll.chain_key = bp.chain_key
where b.avg_price_amount is not null
  and b.price_position_index is not null;

create or replace view public.mw_superset_detalle_tienda_sku as
select
  f.date_key,
  to_date(f.date_key::text, 'YYYYMMDD') as fecha,
  date_trunc('week', to_date(f.date_key::text, 'YYYYMMDD'))::date as semana_inicio,
  date_trunc('month', to_date(f.date_key::text, 'YYYYMMDD'))::date as mes_inicio,
  f.client_id,
  f.campaign_id,
  f.client_name as cliente,
  f.campaign_name as campana,
  f.brand_name as marca,
  f.product_name as producto,
  f.gtin_norm as gtin,
  f.chain_short_label as cadena,
  f.location_name as tienda,
  f.location_code as tienda_codigo,
  f.province as provincia,
  f.canton,
  f.district as distrito,
  round(f.price_amount, 2) as precio_observado,
  round(f.list_price_amount, 2) as precio_lista,
  f.is_available as disponible,
  f.has_discount as descuento_detectado,
  f.available_quantity as cantidad_disponible,
  f.snapshot_ts at time zone 'America/Costa_Rica' as capturado_en_cr,
  f.product_url as producto_url,
  case f.chain_short_label
    when 'Walmart' then 1
    when 'Más x Menos' then 2
    when 'Maxi Palí' then 3
    when 'Megasuper' then 4
    else 999
  end as cadena_orden
from public.mw_fact_analytic_listing_snapshot as f
where f.price_amount is not null;

create or replace view public.mw_superset_eventos as
select
  e.business_date as fecha,
  date_trunc('week', e.business_date)::date as semana_inicio,
  date_trunc('month', e.business_date)::date as mes_inicio,
  e.date_key as fecha_key,
  e.client_id,
  e.campaign_id,
  e.client_name as cliente,
  e.campaign_name as campana,
  e.brand_name as marca,
  e.product_name as producto,
  e.gtin_norm as gtin,
  e.chain_short_label as cadena,
  null::text as tienda,
  null::text as provincia,
  null::text as canton,
  'precio'::text as tipo_evento,
  e.event_type as evento,
  e.severity as severidad,
  case e.severity
    when 'high' then 1
    when 'medium' then 2
    else 3
  end as prioridad,
  round(e.previous_avg_price_amount, 2) as valor_anterior,
  round(e.current_avg_price_amount, 2) as valor_actual,
  round(e.price_change_amount, 2) as cambio_colones,
  round(e.price_change_pct * 100, 2) as cambio_pct,
  case
    when e.event_type = 'price_increase' then 'Aumento de precio'
    when e.event_type = 'price_decrease' then 'Reduccion de precio'
    else 'Cambio de precio'
  end as titulo,
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
  ) as lectura
  ,case e.chain_short_label
    when 'Walmart' then 1
    when 'Más x Menos' then 2
    when 'Maxi Palí' then 3
    when 'Megasuper' then 4
    else 999
  end as cadena_orden
from public.mw_price_change_events as e
union all
select
  e.business_date as fecha,
  date_trunc('week', e.business_date)::date as semana_inicio,
  date_trunc('month', e.business_date)::date as mes_inicio,
  e.date_key as fecha_key,
  e.client_id,
  e.campaign_id,
  e.client_name as cliente,
  e.campaign_name as campana,
  e.brand_name as marca,
  e.product_name as producto,
  e.gtin_norm as gtin,
  e.chain_short_label as cadena,
  e.location_name as tienda,
  e.province as provincia,
  e.canton,
  'visibilidad'::text as tipo_evento,
  e.event_type as evento,
  e.severity as severidad,
  case e.severity
    when 'high' then 1
    when 'medium' then 2
    else 3
  end as prioridad,
  null::numeric as valor_anterior,
  null::numeric as valor_actual,
  null::numeric as cambio_colones,
  null::numeric as cambio_pct,
  case
    when e.event_type = 'sku_listed' then 'SKU aparecio'
    when e.event_type = 'sku_unlisted' then 'SKU desaparecio'
    when e.event_type = 'sku_available' then 'SKU disponible'
    when e.event_type = 'sku_unavailable' then 'SKU no disponible'
    else 'Cambio de visibilidad'
  end as titulo,
  concat(
    e.product_name,
    ' en ',
    e.chain_short_label,
    coalesce(' / ' || e.location_name, ''),
    case
      when e.event_type = 'sku_listed' then ' aparecio listado.'
      when e.event_type = 'sku_unlisted' then ' dejo de aparecer listado.'
      when e.event_type = 'sku_available' then ' volvio a estar disponible.'
      when e.event_type = 'sku_unavailable' then ' dejo de estar disponible.'
      else ' tuvo un cambio de visibilidad.'
    end
  ) as lectura
  ,case e.chain_short_label
    when 'Walmart' then 1
    when 'Más x Menos' then 2
    when 'Maxi Palí' then 3
    when 'Megasuper' then 4
    else 999
  end as cadena_orden
from public.mw_visibility_events as e;
