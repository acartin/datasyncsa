# `mkt_run`

## Qué es
Bitácora persistente de corridas ETL de catálogo.

Cada fila representa una ejecución real del pipeline y es el contexto operativo de los snapshots y comparaciones.

## Qué script correr
```bash
python3 services/price-scrapper/commands/extract_catalog_to_stage.py --chain-id walmart_cr
```

Smoke corto:

```bash
python3 services/price-scrapper/commands/extract_catalog_to_stage.py \
  --chain-id walmart_cr \
  --max-categories 1 \
  --max-pages-per-category 1
```

## Qué hace
- corre el scraper del engine configurado para la cadena
- mantiene los sleeps y retries conservadores del engine actual
- registra una fila de `run` con estado `succeeded` o `failed`
- marca `run_kind` como `comparative` o `analytic`
- puede asociar la corrida a un `campaign_id`
- guarda metadata completa en `raw_metadata`

Fuente runtime:
- `mkt_dim_chain`
- `mkt_dim_category` para categorias raíz

No depende de archivos locales de configuración para ejecutar la extracción ETL.

## Tipo de actualización
`append-only`

No hace `upsert`.
Cada corrida agrega una fila nueva.

## Frecuencia recomendada
Alta o media, según necesidad operativa.

Recomendado:
- cada vez que quieras registrar una extracción real
- como job programable en un orquestador
- como fuente persistente de contexto para facts y comparadores

## Notas
- `mkt_run` ya no es stage; es la bitácora persistente del pipeline.
- `mkt_run` no guarda `client_id`; el tenant se resuelve por `mkt_campaign_client_access` a partir de `campaign_id`.
- `debug_output_dir` solo se llena si corres el job con `--write-debug-files`.
- La web comparativa y las transforms de catálogo usan por defecto `run_kind = comparative`.
