# `mkt_dim_campaign`

## Qué es
Catálogo de campañas de monitoreo.

Cada campaña define el universo operativo para corridas analíticas. La relación con clientes/tenants no vive en esta tabla; se administra en `mkt_campaign_client_access`.

## Qué script correr
No tiene scraper propio.

Se mantiene por seed o carga administrativa.

## Qué hace
- define `name`, `slug` y `description`
- guarda `frequency_type` y `frequency_note`
- sirve como contexto persistente para `mkt_run.campaign_id`

## Tipo de actualización
`manual / upsert administrativo`

## Frecuencia recomendada
Baja.

Solo cuando se crea, cambia o desactiva una campaña.

## Notas
- `frequency_type` puede ser `manual`, `daily`, `weekly` o `custom`
- `deleted_at` permite baja lógica
- una campaña puede ser visible para varios clientes mediante `mkt_campaign_client_access`
- no reemplaza el `run`; define el marco operativo de futuras corridas analíticas
