begin;

with megasuper_chain as (
  select chain_key
  from public.mkt_dim_chain
  where chain_id = 'megasuper_cr'
),
delete_targets as (
  select l.location_key
  from public.mkt_dim_location l
  join megasuper_chain c
    on c.chain_key = l.chain_key
  where l.location_name in (
    'Megasuper Alajuela Central',
    'Megasuper Heredia Centro'
  )
),
insert_targets as (
  select l.location_key
  from public.mkt_dim_location l
  join megasuper_chain c
    on c.chain_key = l.chain_key
  where l.location_name in (
    'Megasuper Alajuela Barrio San José',
    'Megasuper Valencia'
  )
)
delete from public.mkt_campaign_location cl
where cl.campaign_id = (
    select id
    from public.mkt_dim_campaign
    where slug = 'sardimar-atun-competencia-cr'
  )
  and cl.location_key in (select location_key from delete_targets);

with campaign as (
  select id
  from public.mkt_dim_campaign
  where slug = 'sardimar-atun-competencia-cr'
),
megasuper_chain as (
  select chain_key
  from public.mkt_dim_chain
  where chain_id = 'megasuper_cr'
),
insert_targets as (
  select l.location_key
  from public.mkt_dim_location l
  join megasuper_chain c
    on c.chain_key = l.chain_key
  where l.location_name in (
    'Megasuper Alajuela Barrio San José',
    'Megasuper Valencia'
  )
)
insert into public.mkt_campaign_location (
  campaign_id,
  location_key
)
select
  campaign.id,
  target.location_key
from campaign
cross join insert_targets target
on conflict (campaign_id, location_key) do update
set
  updated_at = now();

commit;
