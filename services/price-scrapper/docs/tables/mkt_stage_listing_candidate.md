# `mkt_stage_listing_candidate`

## Qué es
Salida transformada desde `mkt_stage_catalog_item` hacia listings auto-cargables.

## Qué script correr

```bash
python3 services/price-scrapper/commands/transform_stage_listings.py
```

## Qué hace
- toma corridas `succeeded` de `mkt_run`
- enlaza cada item stage contra `mkt_dim_product`
- deja aquí solo las publicaciones que sí pudieron mapearse a `product_key`

## Tipo de actualización
`replace-all`

Cada corrida de `transform_stage_listings.py` reemplaza completa esta tabla.

## Frecuencia recomendada
Después de actualizar `mkt_dim_product` desde `stage`.

## Notas
- Es una tabla intermedia de `transform`.
- Alimenta `mkt_dim_listing`.
