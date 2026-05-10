# `mkt_dim_client`

## Qué es
Catálogo simple de clientes que pueden solicitar corridas analíticas o comparativas.

## Qué script correr
No tiene scraper propio.

Se mantiene por carga manual o seed administrativo.

## Qué hace
- provee `id`, `name`, `slug` y `country_id`
- sirve como referencia opcional desde `mkt_run.client_id`

## Tipo de actualización
`manual / upsert administrativo`

## Frecuencia recomendada
Baja.

Solo cuando entra un cliente nuevo o cambia su metadata básica.

## Notas
- `deleted_at` permite baja lógica.
- No participa directamente en scraping; solo contextualiza corridas.
