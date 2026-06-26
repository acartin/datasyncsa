begin;

create table if not exists public.mkt_dim_geo_area (
  geo_area_key bigserial primary key,
  country_code text not null default 'CR',
  country_name text not null default 'Costa Rica',
  province_code integer not null,
  province text not null,
  canton_code integer not null,
  canton text not null,
  district_code integer not null,
  district text not null,
  postal_code text not null,
  commercial_zone text,
  coastal_zone text,
  mideplan_region text,
  area_km2 numeric(12, 2),
  approximate_nse text,
  tourism_level text,
  is_current boolean not null default true,
  source_name text not null default 'curated_geo_seed',
  source_version text not null default '2026-06-13',
  source_notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint mkt_dim_geo_area_country_chk
    check (country_code ~ '^[A-Z]{2}$'),
  constraint mkt_dim_geo_area_postal_code_chk
    check (postal_code ~ '^[0-9]{5}$'),
  constraint mkt_dim_geo_area_codes_chk
    check (
      province_code between 1 and 7
      and canton_code between 101 and 799
      and district_code between 10101 and 79999
    ),
  constraint mkt_dim_geo_area_area_chk
    check (area_km2 is null or area_km2 >= 0),
  constraint mkt_dim_geo_area_country_district_uk
    unique (country_code, district_code),
  constraint mkt_dim_geo_area_country_postal_uk
    unique (country_code, postal_code)
);

comment on table public.mkt_dim_geo_area is
  'Dimensión geográfica distrital para Market Watch. Separa la geografía analítica de la identidad operativa de mkt_dim_location.';
comment on column public.mkt_dim_geo_area.commercial_zone is
  'Zona comercial/analítica curada, por ejemplo GAM, Zona Norte, Caribe, Pacífico Central.';
comment on column public.mkt_dim_geo_area.coastal_zone is
  'Clasificación curada de costa/interior, por ejemplo Interior, Pacífico Norte, Caribe.';
comment on column public.mkt_dim_geo_area.approximate_nse is
  'Segmento NSE aproximado y curado para análisis agregado; no debe usarse como dato censal exacto.';
comment on column public.mkt_dim_geo_area.tourism_level is
  'Intensidad turística aproximada para análisis comercial agregado.';

alter table public.mkt_dim_location
  add column if not exists geo_area_key bigint;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'mkt_dim_location_geo_area_key_fkey'
  ) then
    alter table public.mkt_dim_location
      add constraint mkt_dim_location_geo_area_key_fkey
      foreign key (geo_area_key)
      references public.mkt_dim_geo_area (geo_area_key);
  end if;
end $$;

create index if not exists mkt_dim_geo_area_lookup_idx
  on public.mkt_dim_geo_area (country_code, province, canton, district);

create index if not exists mkt_dim_geo_area_zone_idx
  on public.mkt_dim_geo_area (commercial_zone, coastal_zone, mideplan_region);

create index if not exists mkt_dim_location_geo_area_key_idx
  on public.mkt_dim_location (geo_area_key);

create temp table tmp_mkt_dim_geo_area_seed (
  commercial_zone text,
  coastal_zone text,
  province text,
  canton text,
  district text,
  postal_code text,
  province_code integer,
  canton_code integer,
  district_code integer,
  area_km2 numeric(12, 2),
  approximate_nse text,
  tourism_level text,
  mideplan_region text,
  source_notes text
) on commit drop;

copy tmp_mkt_dim_geo_area_seed (
  commercial_zone,
  coastal_zone,
  province,
  canton,
  district,
  postal_code,
  province_code,
  canton_code,
  district_code,
  area_km2,
  approximate_nse,
  tourism_level,
  mideplan_region,
  source_notes
) from stdin with (format csv, header true);
commercial_zone,coastal_zone,province,canton,district,postal_code,province_code,canton_code,district_code,area_km2,approximate_nse,tourism_level,mideplan_region,source_notes
GAM,Interior,San José,San José,Carmen,10101,1,101,10101,1.49,B/C+,Bajo,Central,
GAM,Interior,San José,San José,Merced,10102,1,101,10102,2.20,B/C+,Bajo,Central,
GAM,Interior,San José,San José,Zapote,10105,1,101,10105,2.86,B/C+,Bajo,Central,
GAM,Interior,San José,San José,Mata Redonda,10108,1,101,10108,3.66,B/C+,Bajo,Central,
GAM,Interior,San José,Escazú,Escazú,10201,1,102,10201,4.53,A/B,Bajo,Central,
GAM,Interior,San José,Escazú,San Rafael,10203,1,102,10203,13.04,A/B,Bajo,Central,
GAM,Interior,San José,Desamparados,Desamparados,10301,1,103,10301,3.32,C+,Bajo,Central,
GAM,Interior,San José,Desamparados,Frailes,10306,1,103,10306,19.67,C+,Bajo,Central,
GAM,Interior,San José,Puriscal,Santiago,10401,1,104,10401,34.52,C/D,Bajo,Central,
GAM,Interior,San José,Aserrí,Aserrí,10601,1,106,10601,15.26,C/D,Bajo,Central,
GAM,Interior,San José,Mora,Colón,10701,1,107,10701,39.89,C/D,Bajo,Central,
GAM,Interior,San José,Goicoechea,Guadalupe,10801,1,108,10801,2.39,B/C+,Bajo,Central,
GAM,Interior,San José,Tibás,San Juan,11301,1,113,11301,3.51,C/D,Bajo,Central,
GAM,Interior,San José,Montes de Oca,San Pedro,11501,1,115,11501,4.74,A/B,Bajo,Central,
GAM,Interior,San José,Montes de Oca,San Rafael,11504,1,115,11504,7.82,A/B,Bajo,Central,
GAM,Interior,San José,Turrubares,San Pablo,11601,1,116,11601,26.41,C/D,Bajo,Central,
GAM,Interior,San José,Turrubares,Carara,11605,1,116,11605,220.55,C/D,Bajo,Central,
GAM,Interior,San José,Curridabat,Curridabat,11801,1,118,11801,6.17,A/B,Bajo,Central,
Zona Sur,Interior,San José,Pérez Zeledón,San Isidro de El General,11901,1,119,11901,191.82,C/D,Bajo,Brunca,
GAM,Interior,Alajuela,Alajuela,Alajuela,20101,2,201,20101,10.61,B/C+,Bajo,Central,
GAM,Interior,Alajuela,Alajuela,San Rafael,20108,2,201,20108,19.33,B/C+,Bajo,Central,
GAM,Interior,Alajuela,Alajuela,Garita,20113,2,201,20113,33.90,B/C+,Bajo,Central,
GAM,Interior,Alajuela,San Ramón,San Ramón,20201,2,202,20201,1.28,C/D,Bajo,Central,
GAM,Interior,Alajuela,San Ramón,Peñas Blancas,20213,2,202,20213,246.80,C/D,Bajo,Central,
GAM,Interior,Alajuela,Grecia,Grecia,20301,2,203,20301,7.57,C/D,Bajo,Central,
GAM,Interior,Alajuela,Naranjo,Naranjo,20601,2,206,20601,16.85,C/D,Bajo,Central,
GAM,Interior,Alajuela,Palmares,Palmares,20701,2,207,20701,1.19,C/D,Bajo,Central,
Zona Norte,Interior,Alajuela,San Carlos,Quesada,21001,2,210,21001,143.48,C/D,Bajo,Huetar Norte,
Zona Norte,Interior,Alajuela,San Carlos,Florencia,21002,2,210,21002,199.66,C/D,Bajo,Huetar Norte,
Zona Norte,Interior,Alajuela,Upala,Upala,21301,2,213,21301,148.65,C/D,Bajo,Huetar Norte,
GAM,Interior,Cartago,Cartago,Oriental,30101,3,301,30101,2.04,B/C+,Bajo,Central,
GAM,Interior,Cartago,Cartago,Carmen,30103,3,301,30103,4.33,B/C+,Bajo,Central,
GAM,Interior,Cartago,Cartago,San Nicolás,30104,3,301,30104,29.23,B/C+,Bajo,Central,
GAM,Interior,Cartago,Paraíso,Paraíso,30201,3,302,30201,18.29,C/D,Bajo,Central,
GAM,Interior,Cartago,La Unión,Tres Ríos,30301,3,303,30301,2.28,C/D,Bajo,Central,
GAM,Interior,Cartago,Jiménez,Juan Viñas,30401,3,304,30401,43.37,C/D,Bajo,Central,
GAM,Interior,Heredia,Heredia,Heredia,40101,4,401,40101,2.86,B/C+,Bajo,Central,
GAM,Interior,Heredia,Barva,San Pedro,40202,4,402,40202,7.17,C/D,Bajo,Central,
GAM,Interior,Heredia,Barva,San Pablo,40203,4,402,40203,6.83,C/D,Bajo,Central,
GAM,Interior,Heredia,Santo Domingo,Santo Domingo,40301,4,403,40301,0.78,C/D,Bajo,Central,
Guanacaste,Pacífico Norte,Guanacaste,Liberia,Liberia,50101,5,501,50101,563.02,C/D,Medio,Chorotega,
Guanacaste,Pacífico Norte,Guanacaste,Liberia,Nacascolo,50104,5,501,50104,326.91,C/D,Medio,Chorotega,
Guanacaste,Pacífico Norte,Guanacaste,Nicoya,Nicoya,50201,5,502,50201,310.66,C/D,Alto,Chorotega,
Guanacaste,Pacífico Norte,Guanacaste,Santa Cruz,Santa Cruz,50301,5,503,50301,288.92,C/D,Alto,Chorotega,
Guanacaste,Pacífico Norte,Guanacaste,Santa Cruz,Cabo Velas,50308,5,503,50308,73.70,C/D,Alto,Chorotega,
Guanacaste,Pacífico Norte,Guanacaste,Bagaces,Bagaces,50401,5,504,50401,889.07,C/D,Bajo,Chorotega,
Pacífico Central,Pacífico Central,Puntarenas,Puntarenas,Puntarenas,60101,6,601,60101,34.03,C/D,Bajo,Pacífico Central,
Pacífico Central,Interior,Puntarenas,Esparza,Espíritu Santo,60201,6,602,60201,18.91,C/D,Bajo,Pacífico Central,
Zona Sur,Pacífico Sur,Puntarenas,Osa,Bahía Ballena,60504,6,605,60504,158.33,C/D,Medio,Brunca,
Pacífico Central,Pacífico Central,Puntarenas,Quepos,Quepos,60601,6,606,60601,236.05,C/D,Alto,Pacífico Central,
Zona Sur,Pacífico Sur,Puntarenas,Golfito,Golfito,60701,6,607,60701,355.90,C/D,Medio,Brunca,
Pacífico Central,Pacífico Central,Puntarenas,Parrita,Parrita,60901,6,609,60901,483.22,C/D,Bajo,Pacífico Central,
Pacífico Central,Pacífico Central,Puntarenas,Garabito,Jacó,61101,6,611,61101,141.37,C/D,Alto,Pacífico Central,
Pacífico Central,Interior,Puntarenas,Monteverde,Monteverde,61201,6,612,61201,53.47,C/D,Alto,Pacífico Central,"Corregido: Monteverde es cantón 12 de Puntarenas, cantón 83 del país."
Zona Sur,Pacífico Sur,Puntarenas,Puerto Jiménez,Puerto Jiménez,61301,6,613,61301,,C/D,Medio,Brunca,"Corregido: Puerto Jiménez es cantón 13 de Puntarenas, cantón 84 del país; reemplaza el antiguo 60702."
Caribe,Caribe,Limón,Limón,Limón,70101,7,701,70101,59.18,C/D,Bajo,Huetar Caribe,
Caribe,Interior,Limón,Pococí,Guápiles,70201,7,702,70201,221.74,C/D,Bajo,Huetar Caribe,
Caribe,Interior,Limón,Pococí,Roxana,70204,7,702,70204,166.21,C/D,Bajo,Huetar Caribe,
Caribe,Interior,Limón,Siquirres,Siquirres,70301,7,703,70301,184.21,C/D,Bajo,Huetar Caribe,
\.

insert into public.mkt_dim_geo_area (
  commercial_zone,
  coastal_zone,
  province,
  canton,
  district,
  postal_code,
  province_code,
  canton_code,
  district_code,
  area_km2,
  approximate_nse,
  tourism_level,
  mideplan_region,
  source_notes,
  updated_at
)
select
  nullif(trim(commercial_zone), ''),
  nullif(trim(coastal_zone), ''),
  trim(province),
  trim(canton),
  trim(district),
  trim(postal_code),
  province_code,
  canton_code,
  district_code,
  area_km2,
  nullif(trim(approximate_nse), ''),
  nullif(trim(tourism_level), ''),
  nullif(trim(mideplan_region), ''),
  nullif(trim(source_notes), ''),
  now()
from tmp_mkt_dim_geo_area_seed
on conflict (country_code, district_code) do update
set
  commercial_zone = excluded.commercial_zone,
  coastal_zone = excluded.coastal_zone,
  province = excluded.province,
  canton = excluded.canton,
  district = excluded.district,
  postal_code = excluded.postal_code,
  province_code = excluded.province_code,
  canton_code = excluded.canton_code,
  area_km2 = excluded.area_km2,
  approximate_nse = excluded.approximate_nse,
  tourism_level = excluded.tourism_level,
  mideplan_region = excluded.mideplan_region,
  is_current = true,
  source_name = excluded.source_name,
  source_version = excluded.source_version,
  source_notes = excluded.source_notes,
  updated_at = now();

update public.mkt_dim_location as l
set
  geo_area_key = g.geo_area_key,
  province = coalesce(l.province, g.province),
  canton = coalesce(l.canton, g.canton),
  district = coalesce(l.district, g.district),
  updated_at = now()
from public.mkt_dim_geo_area as g
where g.country_code = 'CR'
  and g.is_current
  and l.postal_code = g.postal_code
  and (
    l.geo_area_key is distinct from g.geo_area_key
    or l.province is null
    or l.canton is null
    or l.district is null
  );

commit;
