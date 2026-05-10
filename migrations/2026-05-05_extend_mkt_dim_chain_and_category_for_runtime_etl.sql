begin;

alter table public.mkt_dim_chain
  add column if not exists pricing_context jsonb not null default '{}'::jsonb,
  add column if not exists engine_settings jsonb not null default '{}'::jsonb;

alter table public.mkt_dim_chain
  add constraint mkt_dim_chain_pricing_context_obj_chk
    check (jsonb_typeof(pricing_context) = 'object') not valid;

alter table public.mkt_dim_chain
  validate constraint mkt_dim_chain_pricing_context_obj_chk;

alter table public.mkt_dim_chain
  add constraint mkt_dim_chain_engine_settings_obj_chk
    check (jsonb_typeof(engine_settings) = 'object') not valid;

alter table public.mkt_dim_chain
  validate constraint mkt_dim_chain_engine_settings_obj_chk;

comment on column public.mkt_dim_chain.pricing_context is
  'Contexto operativo de pricing para runtime ETL. Reemplaza dependencia a JSON locales para jobs de extraccion.';

comment on column public.mkt_dim_chain.engine_settings is
  'Configuracion especifica del engine para runtime ETL, por ejemplo storeReference/clientId de Instaleap.';

update public.mkt_dim_chain
set
  pricing_context = case chain_id
    when 'megasuper_cr' then jsonb_build_object(
      'uses_selected_store', true,
      'uses_postal_code', false,
      'uses_access_control_list', false,
      'store_reference', 'M102',
      'description', 'Consulta publica al endpoint Instaleap (nextgentheadless) con la tienda por defecto M102.'
    )
    else jsonb_build_object(
      'uses_selected_store', false,
      'uses_postal_code', false,
      'uses_access_control_list', false,
      'description', 'Consulta publica de catalogo sin seleccionar tienda fisica ni contexto logistico local.'
    )
  end,
  engine_settings = case chain_id
    when 'megasuper_cr' then jsonb_build_object(
      'client_id', 'MEGASUPER',
      'store_reference', 'M102',
      'store_internal_id', '3645',
      'graphql_endpoint', 'https://nextgentheadless.instaleap.io/api/v3',
      'currency', 'CRC',
      'locale', 'es-CR'
    )
    else '{}'::jsonb
  end,
  updated_at = now()
where chain_id in ('walmart_cr', 'maxi_pali_cr', 'masxmenos_cr', 'megasuper_cr');

alter table public.mkt_dim_category
  add column if not exists category_url text;

comment on column public.mkt_dim_category.category_url is
  'URL publica de la categoria cuando existe. Sirve para runtime ETL y trazabilidad sin depender de JSON locales.';

update public.mkt_dim_category as cat
set
  category_url = case
    when chain.chain_id = 'megasuper_cr' then chain.base_url || '/ca/' || cat.category_slug
    else chain.base_url || '/' || cat.category_slug
  end,
  updated_at = now()
from public.mkt_dim_chain as chain
where chain.chain_key = cat.chain_key
  and (cat.category_url is null or btrim(cat.category_url) = '');

commit;
