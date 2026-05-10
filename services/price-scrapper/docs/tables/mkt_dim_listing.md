# `mkt_dim_listing`

## Qué es
Publicación específica de un producto dentro de una cadena.

No es el producto canónico abstracto; es cómo una cadena concreta lo publica.

## Qué script correr

```bash
python3 services/price-scrapper/commands/transform_stage_listings.py
python3 services/price-scrapper/commands/load_dim_listings.py
```

Bootstrap inicial limpio:

```bash
python3 services/price-scrapper/commands/load_dim_listings.py --truncate-first
```

## Qué hace
- `transform_stage_listings.py` construye:
  - `mkt_stage_listing_candidate`
  - `mkt_stage_listing_review`
- `load_dim_listings.py` inserta o actualiza `mkt_dim_listing`

## Tipo de actualización
`upsert`

En operación normal:
- actualiza listings existentes por llave natural
- inserta nuevos
- no borra listings viejos

Solo el bootstrap inicial usa `--truncate-first`.

## Frecuencia recomendada
Después de actualizar `mkt_dim_product` y antes de cargar facts.

## Notas
- La llave natural actual es:
  - `chain_key + source_product_id + source_sku + seller_id`
- Esta tabla será la base para snapshots/facts.
