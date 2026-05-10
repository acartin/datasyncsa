# `mkt_dim_product`

## Qué es
Catálogo único de productos canónicos, basado principalmente en `GTIN` válido.

## Qué script correr
Flujo actual:

```bash
python3 services/price-scrapper/commands/transform_stage_products.py
python3 services/price-scrapper/commands/load_dim_products.py
```

Bootstrap inicial limpio desde `stage`:

```bash
python3 services/price-scrapper/commands/load_dim_products.py --truncate-first
```

La fuente operativa correcta ahora es:

```text
public.mkt_stage_catalog_item
```

## Qué hace
- `transform_stage_products.py` construye:
  - `mkt_stage_product_candidate`
  - `mkt_stage_product_review`
- `load_dim_products.py` inserta o actualiza productos desde `mkt_stage_product_candidate`

## Tipo de actualización
`upsert`

En operación normal:
- actualiza productos existentes por `gtin_norm`
- inserta nuevos
- no borra productos viejos

Solo el bootstrap inicial usa `--truncate-first`.

## Frecuencia recomendada
Media.

Recomendado:
- correr `transform` después de nuevas corridas en `stage`
- correr `load` después del `transform`

## Notas
- Hoy la llave natural preferente es `GTIN` válido.
- Los casos problemáticos no se cargan automáticamente.
- Los casos problemáticos van a `mkt_stage_product_review`.
- Los JSON no deben considerarse fuente oficial del DW.
