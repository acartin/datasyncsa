# `mkt_stage_catalog_item`

## Qué es
Detalle append-only de productos scrapeados en una corrida de `mkt_run`.

Cada fila representa un item del catálogo tal como quedó normalizado por el scraper antes de pasar a dimensiones o facts.

## Qué script correr
Se alimenta indirectamente con:

```bash
python3 services/price-scrapper/commands/extract_catalog_to_stage.py --chain-id walmart_cr
```

## Qué hace
- guarda una fila por item scrapeado
- conserva campos útiles ya aplanados para ETL
- también guarda `raw_payload` completo por trazabilidad

## Tipo de actualización
`append-only`

No reconstruye ni hace `upsert`.
Cada corrida agrega un set nuevo de items asociado a su `run_key`.

## Frecuencia recomendada
La misma de `mkt_run`.

## Notas
- Es la fuente recomendada para construir después `mkt_dim_product`, `mkt_dim_category`, `mkt_dim_listing` y facts.
- Si quieres artifacts JSON para inspección manual, usa `--write-debug-files`, pero esos archivos ya no son la fuente oficial del pipeline.
