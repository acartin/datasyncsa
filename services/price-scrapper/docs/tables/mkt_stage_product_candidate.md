# `mkt_stage_product_candidate`

## Qué es
Salida transformada desde `mkt_stage_catalog_item` hacia productos auto-cargables.

Cada fila representa un `GTIN` válido que el ETL considera suficientemente confiable para poblar `mkt_dim_product`.

## Qué script correr

```bash
python3 services/price-scrapper/commands/transform_stage_products.py
```

## Qué hace
- toma corridas `succeeded` de `mkt_run`
- lee sus items desde `mkt_stage_catalog_item`
- agrupa por `GTIN`
- deja aquí solo los grupos auto-resolubles

## Tipo de actualización
`replace-all`

Cada corrida de `transform_stage_products.py` reemplaza completa esta tabla.

## Frecuencia recomendada
Cada vez que quieras reconstruir el set actual de candidatos desde `stage`.

## Notas
- Es una tabla intermedia de `transform`, no una dimensión final.
- La fuente oficial aquí es `stage`, no los JSON de `output/`.
