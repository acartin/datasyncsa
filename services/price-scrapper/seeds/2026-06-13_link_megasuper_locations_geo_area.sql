begin;

alter table public.mkt_dim_location
  add column if not exists geo_match_method text,
  add column if not exists geo_match_confidence numeric(5, 4),
  add column if not exists geo_match_notes text;

create temp table tmp_mkt_dim_geo_area_megasuper_seed (
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
  mideplan_region text
) on commit drop;

copy tmp_mkt_dim_geo_area_megasuper_seed (
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
  mideplan_region
) from stdin with (format csv, header true);
commercial_zone,coastal_zone,province,canton,district,postal_code,province_code,canton_code,district_code,area_km2,approximate_nse,tourism_level,mideplan_region
GAM,Interior,San José,San José,San Francisco de Dos Ríos,10106,1,101,10106,2.64,B/C+,Bajo,Central
GAM,Interior,San José,San José,Uruca,10107,1,101,10107,8.39,B/C+,Bajo,Central
GAM,Interior,San José,San José,San Sebastián,10111,1,101,10111,3.97,B/C+,Bajo,Central
GAM,Interior,San José,Desamparados,San Antonio,10305,1,103,10305,2.07,C+,Bajo,Central
GAM,Interior,San José,Desamparados,San Rafael Abajo,10311,1,103,10311,2.02,C+,Bajo,Central
GAM,Interior,San José,Alajuelita,Alajuelita,11001,1,110,11001,1.27,C/D,Bajo,Central
GAM,Interior,San José,Vázquez de Coronado,Patalillo,11104,1,111,11104,1.92,B/C+,Bajo,Central
GAM,Interior,San José,Acosta,San Ignacio,11201,1,112,11201,22.74,C/D,Bajo,Central
GAM,Interior,San José,Tibás,Colima,11305,1,113,11305,2.01,C/D,Bajo,Central
GAM,Interior,San José,Moravia,San Vicente,11401,1,114,11401,5.40,B/C+,Bajo,Central
GAM,Interior,San José,Montes de Oca,Sabanilla,11502,1,115,11502,1.79,A/B,Bajo,Central
GAM,Interior,San José,Santa Ana,Santa Ana,10901,1,109,10901,5.44,A/B,Bajo,Central
Zona Sur,Interior,San José,Pérez Zeledón,San Isidro de El General,11901,1,119,11901,191.82,C/D,Bajo,Brunca
GAM,Interior,Alajuela,Alajuela,San Isidro,20106,2,201,20106,34.69,B/C+,Bajo,Central
GAM,Interior,Alajuela,Alajuela,Sabanilla,20107,2,201,20107,43.18,B/C+,Bajo,Central
GAM,Interior,Alajuela,Alajuela,Turrucares,20111,2,201,20111,35.89,B/C+,Bajo,Central
GAM,Interior,Alajuela,Atenas,Atenas,20501,2,205,20501,9.76,C/D,Bajo,Central
GAM,Interior,Alajuela,Poás,San Pedro,20801,2,208,20801,13.58,C/D,Bajo,Central
GAM,Interior,Alajuela,Orotina,Orotina,20901,2,209,20901,21.56,C/D,Bajo,Central
Zona Norte,Interior,Alajuela,San Carlos,Aguas Zarcas,21004,2,210,21004,185.70,C/D,Bajo,Huetar Norte
Zona Norte,Interior,Alajuela,San Carlos,La Fortuna,21007,2,210,21007,229.59,C/D,Bajo,Huetar Norte
Zona Norte,Interior,Alajuela,Upala,Bijagua,21304,2,213,21304,186.80,C/D,Bajo,Huetar Norte
Zona Norte,Interior,Alajuela,Guatuso,San Rafael,21501,2,215,21501,303.99,C/D,Bajo,Huetar Norte
GAM,Interior,Cartago,Cartago,Aguacaliente o San Francisco,30105,3,301,30105,99.26,B/C+,Bajo,Central
GAM,Interior,Cartago,Cartago,Tierra Blanca,30108,3,301,30108,12.80,B/C+,Bajo,Central
GAM,Interior,Cartago,Turrialba,Turrialba,30501,3,305,30501,56.63,C/D,Bajo,Central
GAM,Interior,Cartago,Turrialba,Tres Equis,30510,3,305,30510,36.95,C/D,Bajo,Central
GAM,Interior,Cartago,Alvarado,Cervantes,30602,3,306,30602,15.18,C/D,Bajo,Central
GAM,Interior,Cartago,El Guarco,El Tejar,30801,3,308,30801,6.12,C/D,Bajo,Central
GAM,Interior,Heredia,Heredia,San Francisco,40103,4,401,40103,6.56,B/C+,Bajo,Central
GAM,Interior,Heredia,Heredia,Ulloa,40104,4,401,40104,11.38,B/C+,Bajo,Central
GAM,Interior,Heredia,Barva,Barva,40201,4,402,40201,0.84,C/D,Bajo,Central
GAM,Interior,Heredia,Santa Bárbara,Santa Bárbara,40401,4,404,40401,1.28,C/D,Bajo,Central
GAM,Interior,Heredia,San Rafael,San Rafael,40501,4,405,40501,1.33,C/D,Bajo,Central
GAM,Interior,Heredia,San Isidro,San Isidro,40601,4,406,40601,2.67,C/D,Bajo,Central
GAM,Interior,Heredia,Belén,La Ribera,40702,4,407,40702,4.26,A/B,Bajo,Central
GAM,Interior,Heredia,Flores,Barrantes,40802,4,408,40802,2.14,C/D,Bajo,Central
Caribe,Interior,Heredia,Sarapiquí,La Virgen,41002,4,410,41002,514.19,C/D,Bajo,Huetar Caribe
Guanacaste,Pacífico Norte,Guanacaste,Carrillo,Sardinal,50503,5,505,50503,260.17,C/D,Alto,Chorotega
Guanacaste,Interior,Guanacaste,Bagaces,Mogote,50403,5,504,50403,181.77,C/D,Bajo,Chorotega
Guanacaste,Interior,Guanacaste,Abangares,Las Juntas,50701,5,507,50701,228.71,C/D,Bajo,Chorotega
Guanacaste,Interior,Guanacaste,Tilarán,Tilarán,50801,5,508,50801,144.75,C/D,Bajo,Chorotega
Guanacaste,Pacífico Norte,Guanacaste,La Cruz,La Cruz,51001,5,510,51001,344.39,C/D,Bajo,Chorotega
Pacífico Central,Pacífico Central,Puntarenas,Puntarenas,Paquera,60105,6,601,60105,335.63,C/D,Bajo,Pacífico Central
Pacífico Central,Pacífico Central,Puntarenas,Puntarenas,Cóbano,60111,6,601,60111,319.27,C/D,Alto,Pacífico Central
Pacífico Central,Pacífico Central,Puntarenas,Puntarenas,El Roble,60115,6,601,60115,7.93,C/D,Bajo,Pacífico Central
Zona Sur,Pacífico Sur,Puntarenas,Corredores,Corredor,61001,6,610,61001,275.67,C/D,Bajo,Brunca
Zona Sur,Pacífico Sur,Puntarenas,Corredores,Laurel,61004,6,610,61004,188.85,C/D,Bajo,Brunca
Guanacaste,Pacífico Norte,Guanacaste,Santa Cruz,Tamarindo,50309,5,503,50309,126.09,C/D,Alto,Chorotega
Caribe,Caribe,Limón,Talamanca,Cahuita,70403,7,704,70403,234.07,C/D,Medio,Huetar Caribe
Caribe,Caribe,Limón,Matina,Batán,70502,7,705,70502,213.41,C/D,Bajo,Huetar Caribe
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
  source_name,
  source_version,
  source_notes,
  updated_at
)
select
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
  'curated_megasuper_geo_seed',
  '2026-06-13',
  'Distrito agregado para enlazar sucursales Megasuper por nombre/source_payload.',
  now()
from tmp_mkt_dim_geo_area_megasuper_seed
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

create temp table tmp_megasuper_location_geo_match (
  location_key bigint primary key,
  postal_code text not null,
  match_method text not null,
  match_confidence numeric(5, 4) not null,
  match_notes text not null
) on commit drop;

copy tmp_megasuper_location_geo_match (
  location_key,
  postal_code,
  match_method,
  match_confidence,
  match_notes
) from stdin with (format csv, header true);
location_key,postal_code,match_method,match_confidence,match_notes
144,50701,curated_name_payload,0.98,"location_name Abangares + resolved_store_address Las Juntas de Abangares"
143,30105,curated_name_address,0.98,"location_name/address Agua Caliente Cartago"
142,21004,curated_name_address,0.98,"location_name/address Aguas Zarcas"
141,20101,curated_name_address,0.90,"Alajuela Barrio San Jose; distrito Alajuela por coordenada/nombre urbano"
140,20101,curated_name,0.98,"Alajuela Central"
139,11001,curated_name,0.98,"Alajuelita"
138,20501,curated_name_address,0.98,"Atenas"
137,40201,curated_name,0.98,"Barva de Heredia"
136,70502,curated_name,0.98,"Bataan/Batan"
135,21304,curated_name_address,0.98,"Bijagua de Upala"
134,50503,curated_name_address,0.95,"Playas del Coco pertenece al distrito Sardinal"
133,30103,curated_address,0.95,"Cartago Centro junto a Iglesia del Carmen"
132,30104,curated_address,0.85,"Parque Industrial Cartago asociado a San Nicolas"
131,30602,curated_name,0.98,"Cervantes"
130,61001,curated_name,0.95,"Ciudad Neilly asociado al distrito Corredor"
129,11104,curated_name_address_external,0.95,"San Antonio de Coronado + Escuela Estado de Israel asociada a Patalillo"
128,11305,curated_name_address_external,0.95,"Cuatro Reinas/Metalco asociado a Colima de Tibas"
127,60111,curated_name,0.98,"Cobano"
126,10301,curated_name,0.98,"Desamparados centro"
125,50503,curated_name_payload,0.95,"El Coco/Playas del Coco pertenece al distrito Sardinal"
124,60115,curated_name_payload,0.98,"El Roble Puntarenas"
123,20107,curated_name_address_external,0.98,"Fraijanes asociado a Sabanilla de Alajuela por direccion/source_payload"
122,10306,curated_name,0.98,"Frailes"
121,60701,curated_name,0.98,"Golfito"
120,10801,curated_name,0.98,"Guadalupe"
119,70201,curated_name,0.98,"Guapiles"
118,21501,curated_address,0.95,"San Rafael de Guatuso"
117,50403,curated_name_coordinates_external,0.98,"Guayabo asociado a Mogote de Bagaces por ubicacion"
116,40101,curated_name,0.98,"Heredia Centro"
115,61101,curated_name,0.98,"Jaco"
114,51001,curated_name_address,0.98,"La Cruz Guanacaste"
113,21007,curated_name_payload,0.98,"La Fortuna"
112,10111,curated_name_address_local,0.98,"La Paz/Rotonda Guacamaya asociado a San Sebastian de San Jose"
111,40702,curated_name_address,0.98,"La Ribera de Belen"
110,41002,curated_name,0.98,"La Virgen de Sarapiqui"
109,61004,curated_name,0.98,"Laurel de Corredores"
108,50101,curated_name,0.98,"Liberia"
107,50101,curated_name,0.95,"Liberia Barrio"
106,70101,curated_name,0.98,"Limon La Colina"
105,70101,curated_name,0.98,"Limon Centro"
104,61201,curated_name,0.98,"Monteverde"
103,11401,curated_name,0.95,"Moravia cabecera San Vicente"
102,10106,curated_address,0.98,"Okayama en San Francisco de Dos Rios"
101,20901,curated_name,0.98,"Orotina"
100,60105,curated_name,0.98,"Paquera"
99,30201,curated_name,0.98,"Paraiso Centro"
98,60901,curated_name_address,0.98,"Parrita Centro"
97,11901,curated_name_address,0.90,"Perez Zeledon asociado a San Isidro de El General por cabecera cantonal"
96,30201,curated_name_address,0.98,"Plaza Paraiso"
95,20801,curated_name,0.85,"Poas asociado a cabecera San Pedro"
94,70403,curated_address,0.90,"Puerto Viejo de Limon asociado a Cahuita"
93,60101,curated_name,0.98,"Puntarenas centro"
92,11502,curated_name_address,0.98,"Sabanilla Montes de Oca"
91,10305,curated_name_address,0.98,"San Antonio de Desamparados"
90,10106,curated_name_address,0.98,"San Francisco de Dos Rios"
89,11201,curated_name_address,0.98,"San Ignacio de Acosta"
88,40601,curated_name_address,0.98,"San Isidro de Heredia"
87,40802,curated_name_address_external,0.92,"San Lorenzo asociado a Barrantes de Flores por referencias de ubicacion"
86,10311,curated_name,0.98,"San Rafael Abajo de Desamparados"
85,20108,curated_name,0.98,"San Rafael de Alajuela"
84,40501,curated_name_address,0.98,"San Rafael de Heredia"
83,10901,curated_name,0.98,"Santa Ana"
82,40401,curated_name_address,0.98,"Santa Barbara"
81,50301,curated_name,0.98,"Santa Cruz"
80,60111,curated_address,0.90,"Santa Teresa/Playa Carmen asociado a Cobano"
79,70301,curated_name,0.98,"Siquirres"
78,50309,curated_name_address,0.98,"Tamarindo"
77,30801,curated_name_address,0.98,"Tejar"
76,30108,curated_name_address,0.98,"Tierra Blanca"
75,50801,curated_name_address,0.98,"Tilaran"
74,30510,curated_name_address,0.98,"Tres Equis"
73,30301,curated_name,0.98,"Tres Rios Centro"
72,30301,curated_name_address,0.98,"Tres Rios Nuevo"
71,30501,curated_name_payload,0.98,"Turrialba"
70,20111,curated_name,0.98,"Turrucares"
69,21301,curated_name_address,0.98,"Upala"
68,10107,curated_name_coordinates,0.90,"Uruca corregida por nombre/coordenadas; provincia original parece venir mal clasificada"
67,40104,curated_address_external,0.95,"Valencia de Heredia + Parque Industrial Zeta asociado a Ulloa"
\.

update public.mkt_dim_location as l
set
  geo_area_key = g.geo_area_key,
  postal_code = coalesce(l.postal_code, g.postal_code),
  province = g.province,
  canton = g.canton,
  district = g.district,
  geo_match_method = m.match_method,
  geo_match_confidence = m.match_confidence,
  geo_match_notes = m.match_notes,
  source_payload = jsonb_set(
    coalesce(l.source_payload, '{}'::jsonb),
    '{geo_match}',
    jsonb_build_object(
      'method', m.match_method,
      'confidence', m.match_confidence,
      'postal_code', g.postal_code,
      'province', g.province,
      'canton', g.canton,
      'district', g.district,
      'notes', m.match_notes,
      'matched_at', now()
    ),
    true
  ),
  updated_at = now()
from tmp_megasuper_location_geo_match as m
join public.mkt_dim_geo_area as g
  on g.country_code = 'CR'
 and g.postal_code = m.postal_code
 and g.is_current
where l.location_key = m.location_key;

commit;
