# Market Watch Semantic Layer

## Objetivo

La capa semantica queda separada de la herramienta BI. Superset, Metabase o el
portal propio deben consumir datasets de presentacion, no facts crudos.

## Capas

```text
facts/dims
  -> mw_core_*
  -> mw_signal_*
  -> mw_bi_*
```

## Core

Vistas tool-agnostic, con grano claro y nombres tecnicos:

- `mw_core_sku_store_observation`: SKU/tienda/captura.
- `mw_core_sku_chain_day`: SKU/cadena/dia.
- `mw_core_brand_chain_day`: marca/cadena/dia.
- `mw_core_price_change_day`: cambios de precio vs corte anterior.
- `mw_core_promo_daily`: senales base de promocion.

## Signal

Contrato estable para `services/retail-signal-engine`:

- `mw_signal_brand_chain_daily`
- `mw_signal_sku_chain_daily`
- `mw_signal_sku_store_observation`
- `mw_signal_price_change_daily`
- `mw_signal_promo_daily`

El Signal Engine no debe depender de vistas de BI.

## BI / Presentation

Datasets para Superset, Metabase o portal:

- `mw_bi_brand_chain_price_index`
- `mw_bi_sku_price_drivers`
- `mw_bi_sku_store_price_evidence`
- `mw_bi_radar_event_feed`
- `mw_bi_executive_signal_feed`

Estas vistas pueden tener nombres mas amigables y columnas pensadas para
filtros, tablas, pivots y graficos.

Las columnas expuestas por `mw_bi_*` deben usar ingles en `snake_case`, porque
son la base visible para Superset, Metabase o el portal.

## Autorizacion Campana-Cliente

La visibilidad cliente de campanas se resuelve con
`public.mkt_campaign_client_access`.

Una campana puede ser visible para uno o varios clientes. Las vistas `mw_bi_*`
deben exponer filas por `client_id` autorizado desde esa tabla puente, no asumir
que `mkt_dim_campaign.client_id` o `mkt_client_signal.perspective_client_id`
siempre estaran poblados.

Regla:

- `market-watch-api` filtra siempre por el `client_id` de sesion.
- Las vistas `mw_bi_*` deben poblar `client_id` mediante
  `mkt_campaign_client_access`.
- Si una senal ya trae `perspective_client_id`, debe coincidir con el cliente
  autorizado por la campana.
- El frontend no debe recibir ni filtrar campanas no autorizadas.

## Navegacion Desde Senales

Cada fila de `mkt_client_signal` puede traer `navigation_json` con:

- dashboard objetivo
- vista sugerida
- dataset preferido
- dataset de evidencia
- filtros de `campaign_id`, `date_key`, `brand`, `chain` y productos

El portal debe traducir ese contrato a Superset, Metabase o UI propia.
