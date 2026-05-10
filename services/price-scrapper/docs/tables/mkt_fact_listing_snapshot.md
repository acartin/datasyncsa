# `mkt_fact_listing_snapshot`

## Qué es
Fact principal de snapshots de precio y existencia por listing.

El grano actual es:
- `run_key`
- `listing_key`

Particionada por `date_key`.

## Qué script correr

```bash
python3 services/price-scrapper/commands/transform_stage_listing_snapshots.py
python3 services/price-scrapper/commands/load_fact_listing_snapshots.py
```

Bootstrap inicial limpio:

```bash
python3 services/price-scrapper/commands/load_fact_listing_snapshots.py --truncate-first
```

## Qué hace
- `transform_stage_listing_snapshots.py` construye:
  - `mkt_stage_listing_snapshot_candidate`
  - `mkt_stage_listing_snapshot_review`
- `load_fact_listing_snapshots.py` inserta o actualiza la fact

## Tipo de actualización
`upsert`

En operación normal:
- inserta snapshots nuevos
- si repites una corrida sobre el mismo `run + listing`, actualiza esa fila

## Frecuencia recomendada
Después de cargar `mkt_dim_listing`.

## Notas
- `date_key` se deriva en horario `America/Costa_Rica`, aunque `snapshot_ts` se guarda en UTC.
- Esta es la base correcta para comparador histórico y analítica.
