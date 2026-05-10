begin;

with campaign_row as (
  select id
  from public.mkt_dim_campaign
  where slug = 'sardimar-atun-competencia-cr'
  limit 1
),
seed_locations(location_key) as (
  values
    -- masxmenos_cr
    (19),  -- MxM-ALAJUELA
    (17),  -- MxM-CARTAGO
    (15),  -- MxM-GRECIA
    (11),  -- MxM-HEREDIA SUR
    (10),  -- MxM-JACO
    (9),   -- MxM-LIBERIA
    (8),   -- MxM-LIMÓN
    (7),   -- MxM-SABANA
    (3),   -- MxM-SAN RAMON
    (2),   -- MxM-SANTA ANA

    -- maxi_pali_cr
    (64),  -- MP Alajuela
    (58),  -- MP Ciudad Quesada
    (55),  -- MP Esparza
    (54),  -- MP Guápiles
    (51),  -- MP Liberia
    (50),  -- MP Limón
    (41),  -- MP Pavas
    (39),  -- MP Quepos
    (34),  -- MP Santa Ana
    (31),  -- MP Tibás

    -- megasuper_cr
    (112), -- Megasuper La Paz
    (140), -- Megasuper Alajuela Central
    (133), -- Megasuper Cartago Centro
    (116), -- Megasuper Heredia Centro
    (115), -- Megasuper Jacó
    (108), -- Megasuper Liberia
    (105), -- Megasuper Limón Centro
    (93),  -- Megasuper Puntarenas
    (83),  -- Megasuper Santa Ana
    (71),  -- Megasuper Turrialba

    -- walmart_cr
    (158), -- WM-ALAJUELA
    (157), -- WM-CARTAGO
    (156), -- WM-CIUDAD QUESADA
    (154), -- WM-DESAMPARADOS
    (151), -- WM-HEREDIA
    (148), -- WM-LIBERIA
    (147), -- WM-PEREZ ZELEDON
    (159), -- WM Santa Ana
    (145), -- WM-TIBAS
    (153)  -- WM-ESCAZU
)
insert into public.mkt_campaign_location (
  campaign_id,
  location_key,
  created_at,
  updated_at
)
select
  c.id,
  s.location_key,
  now(),
  now()
from campaign_row c
join seed_locations s
  on true
on conflict (campaign_id, location_key) do update
set
  updated_at = now();

commit;
