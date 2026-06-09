begin;

alter table public.mkt_dim_campaign
  drop constraint if exists mkt_dim_campaign_frequency_type_chk;

alter table public.mkt_dim_campaign
  drop column if exists frequency_type,
  drop column if exists frequency_note;

comment on table public.mkt_dim_campaign is
  'Campañas de monitoreo comercial. Definen el universo objetivo para corridas analíticas; el acceso por cliente se administra en mkt_campaign_client_access.';

commit;
