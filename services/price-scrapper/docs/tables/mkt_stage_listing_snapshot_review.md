# `mkt_stage_listing_snapshot_review`

## Qué es
Cola de revisión manual para snapshots que no pudieron enlazarse a `mkt_dim_listing`.

## Qué script correr

```bash
python3 services/price-scrapper/commands/transform_stage_listing_snapshots.py
```

## Qué hace
- guarda los casos que no pudieron resolver `listing_key`
- hoy el motivo principal es `missing_listing_match`
- conserva suficiente payload para revisión humana

## Tipo de actualización
`replace-complete`

Cada corrida de `transform_stage_listing_snapshots.py` reemplaza completa esta tabla.

## Frecuencia recomendada
La misma de `mkt_stage_listing_snapshot_candidate`.

## Notas
- Si esta tabla crece, normalmente primero hay que revisar `mkt_dim_product` o `mkt_dim_listing`.
