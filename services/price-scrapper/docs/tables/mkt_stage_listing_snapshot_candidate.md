# `mkt_stage_listing_snapshot_candidate`

## Qué es
Salida transformada de snapshots lista para cargar a la fact.

Cada fila representa un listing observado en una corrida stage y ya resuelto contra `mkt_dim_listing`.

## Qué script correr

```bash
python3 services/price-scrapper/commands/transform_stage_listing_snapshots.py
```

## Qué hace
- lee `mkt_run` y `mkt_stage_catalog_item`
- toma por defecto las últimas corridas `succeeded` con `run_kind = comparative`
- enlaza cada item contra `mkt_dim_listing`
- deriva `date_key` de negocio en horario `America/Costa_Rica`
- deja solo snapshots auto-cargables

## Tipo de actualización
`replace-complete`

Cada corrida de `transform_stage_listing_snapshots.py` reemplaza completa esta tabla.

## Frecuencia recomendada
Después de refrescar `mkt_dim_listing` y antes de cargar la fact.

## Notas
- Alimenta `mkt_fact_listing_snapshot`.
- Si un item no encuentra `listing_key`, no entra aquí; pasa a `mkt_stage_listing_snapshot_review`.
