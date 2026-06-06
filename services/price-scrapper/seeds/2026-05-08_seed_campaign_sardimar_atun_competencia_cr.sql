begin;

with upsert_campaign as (
  insert into public.mkt_dim_campaign (
    name,
    slug,
    description,
    frequency_type,
    frequency_note,
    is_active
  )
  values (
    'Sardimar Atun Competencia CR',
    'sardimar-atun-competencia-cr',
    'Campana vitrina para monitorear Sardimar contra Calvo, Great Value, Suli y Tesoro del Mar en las cadenas disponibles.',
    'manual',
    'Piloto inicial. Luego se puede calendarizar segun la necesidad comercial.',
    true
  )
  on conflict (slug) do update
  set
    name = excluded.name,
    description = excluded.description,
    frequency_type = excluded.frequency_type,
    frequency_note = excluded.frequency_note,
    is_active = excluded.is_active,
    updated_at = now(),
    deleted_at = null
  returning id
),
campaign_row as (
  select id from upsert_campaign
  union all
  select id
  from public.mkt_dim_campaign
  where slug = 'sardimar-atun-competencia-cr'
  limit 1
),
seed_products(product_key, product_role) as (
  values
    (5765, 'owned'),
    (5767, 'owned'),
    (5799, 'owned'),
    (5783, 'owned'),
    (5782, 'owned'),
    (5902, 'owned'),
    (5903, 'owned'),
    (5820, 'owned'),

    (4532, 'competitor'),
    (5935, 'competitor'),
    (4530, 'competitor'),
    (4468, 'competitor'),
    (7882, 'competitor'),
    (5793, 'competitor'),
    (7890, 'competitor'),
    (4466, 'competitor'),
    (7878, 'competitor'),
    (5794, 'competitor'),
    (7891, 'competitor'),
    (4469, 'competitor'),
    (7880, 'competitor'),
    (5792, 'competitor'),
    (7993, 'competitor'),
    (4536, 'competitor'),
    (8005, 'competitor'),
    (5894, 'competitor'),
    (4541, 'competitor'),
    (8006, 'competitor'),
    (5867, 'competitor'),
    (4488, 'competitor'),
    (7885, 'competitor'),
    (7887, 'competitor')
)
insert into public.mkt_campaign_product (
  campaign_id,
  product_key,
  product_role,
  created_at,
  updated_at
)
select
  c.id,
  s.product_key,
  s.product_role,
  now(),
  now()
from campaign_row c
join seed_products s
  on true
on conflict (campaign_id, product_key) do update
set
  product_role = excluded.product_role,
  updated_at = now();

commit;
