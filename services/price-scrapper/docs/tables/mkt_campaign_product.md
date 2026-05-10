# `mkt_campaign_product`

## Qué es
Relación entre campañas y productos canónicos.

## Qué script correr
No tiene scraper propio.

Se mantiene por seed o carga administrativa.

## Qué hace
- vincula una campaña con los `product_key` que se van a monitorear
- permite marcar `product_role` como `owned`, `competitor`, `tracked` o `reference`

## Tipo de actualización
`manual / upsert administrativo`

## Frecuencia recomendada
Media.

Cada vez que cambie el set de SKUs monitoreados por una campaña.

## Notas
- la llave es compuesta: `campaign_id + product_key`
- esta tabla define el universo de productos del run analítico
