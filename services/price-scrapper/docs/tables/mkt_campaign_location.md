# `mkt_campaign_location`

## Qué es
Relación entre campañas y locations.

## Qué script correr
No tiene scraper propio.

Se mantiene por seed o carga administrativa.

## Qué hace
- vincula una campaña con las tiendas o contexts que se van a monitorear
- permite limitar una corrida analítica a un conjunto manejable de locations

## Tipo de actualización
`manual / upsert administrativo`

## Frecuencia recomendada
Media.

Cada vez que cambie el universo de tiendas a monitorear.

## Notas
- la llave es compuesta: `campaign_id + location_key`
- esta tabla ayuda a evitar corridas analíticas demasiado grandes
