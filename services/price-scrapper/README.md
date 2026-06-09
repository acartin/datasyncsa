# Price Scrapper

Extraccion local de catalogos y precios de supermercados en Costa Rica.

## Nomenclatura

- `chain`: cadena comercial, por ejemplo `walmart_cr`
- `physical store`: sucursal concreta dentro de una cadena
- `engine`: plataforma tecnica origen, por ejemplo `vtex` o `instaleap`

En este servicio `chain_id` es el nombre canonico para la cadena.

## Estructura

```text
services/price-scrapper/
├── commands/
│   ├── extract_chain_catalog.py
│   ├── extract_catalog_to_stage.py
│   ├── extract_chain_locations.py
│   ├── transform_stage_products.py
│   ├── load_dim_products.py
│   ├── transform_stage_listings.py
│   ├── load_dim_listings.py
│   ├── transform_stage_listing_snapshots.py
│   ├── load_fact_listing_snapshots.py
│   ├── serve_web.py
│   └── update_chain_root_categories.py
├── etl/
│   ├── chain_runtime_db.py
│   ├── catalog_stage_loader.py
│   ├── normalize.py
│   └── postgres_cli.py
├── engines/
│   ├── vtex_catalog_engine.py
│   └── instaleap_catalog_engine.py
├── output/
│   └── chains/<chain_id>/
├── schemas/
└── web/
```

El runtime operativo del servicio vive en BD, principalmente en:

- `mkt_dim_chain`
- `mkt_dim_category`
- `mkt_dim_location`

## Comandos

```bash
cd /srv/datasyncsa/services/price-scrapper
python3 commands/extract_chain_catalog.py --chain-id walmart_cr
python3 commands/extract_chain_catalog.py --chain-id walmart_cr --max-categories 2 --max-pages-per-category 1 --sleep-min 0 --sleep-max 0
python3 commands/extract_chain_catalog.py --chain-id walmart_cr --root-category-slug abarrotes
python3 commands/reset_catalog_stage.py
python3 commands/extract_catalog_to_stage.py --chain-id walmart_cr
python3 commands/extract_catalog_to_stage.py --chain-id walmart_cr --max-categories 1 --max-pages-per-category 1
python3 commands/extract_chain_locations.py
python3 commands/extract_chain_locations.py --chain-id walmart_cr
python3 commands/transform_stage_products.py
python3 commands/load_dim_products.py --truncate-first
python3 commands/transform_stage_listings.py
python3 commands/load_dim_listings.py --truncate-first
python3 commands/transform_stage_listing_snapshots.py
python3 commands/load_fact_listing_snapshots.py --truncate-first
python3 commands/serve_web.py
python3 commands/update_chain_root_categories.py
python3 commands/update_chain_root_categories.py --chain-id walmart_cr
```

Convención operativa:
- `extract_*`: etapa de extracción del ETL o discovery contra APIs externas.
- `transform_*`: futura etapa de transformación desde `stage` hacia modelos intermedios.
- `load_*`: futura etapa de carga hacia dimensiones y facts.
- `update_*`: mantenimiento de configuración/runtime en BD.

`update_chain_root_categories.py` tambien esta expuesto como job manual de Dagster:
`refresh_chain_root_categories_job`. El launchpad acepta `chain_id` vacio para
refrescar todas las cadenas VTEX activas, o un `chain_id` especifico para acotar
la actualizacion. Este job solo descubre categorias raiz y preserva la bandera
`is_enabled`; no ejecuta scraping de productos ni regeneracion canonica.

## Runtime de cadenas

La cadena, engine, scope y contexto operativo salen de `mkt_dim_chain`.

Las categorías raíz que entran al scrape salen de `mkt_dim_category`:

- `is_enabled = true`: entra al scrape por defecto
- `is_enabled = false`: no entra al scrape por defecto

Las categorias no se crean manualmente desde la web. `Catalog Sources` permite
activar o desactivar categorias descubiertas; nombre, slug y URL vienen de la
cadena/API externa mediante el proceso de discovery.

## Salidas

Cada corrida escribe:

- `output/chains/<chain_id>/catalog.json`
- `output/chains/<chain_id>/metadata.json`

Esas salidas sirven para inspección manual, compatibilidad legacy o debug.
No son la fuente oficial del pipeline ETL.

La metadata distingue `chain_id` y `engine`. El `pricing_scope` actual puede ser:

- `chain_public_online`
- `default_store_online`

El segundo caso ya implica una tienda fisica implicita del engine, como
`storeReference` en Instaleap.

## ETL

`extract_catalog_to_stage.py` hace la extracción oficial a:

- `public.mkt_run`
- `public.mkt_stage_catalog_item`

Las corridas quedan etiquetadas con:

- `run_kind = comparative | analytic`
- `campaign_id` cuando pertenecen a una campaña/canasta analítica

Por defecto, los comandos actuales usan `comparative`.

Si quieres arrancar un batch con stage limpio:

- `reset_catalog_stage.py`
  - vacía solo tablas `mkt_stage_*`
  - no toca `mkt_run`
  - no toca dimensiones
  - no toca facts

Luego el flujo de productos queda así:

- `transform_stage_products.py`
  - lee `mkt_run` / `mkt_stage_catalog_item`
  - genera `mkt_stage_product_candidate`
  - genera `mkt_stage_product_review`
- `load_dim_products.py`
  - carga `mkt_stage_product_candidate` hacia `mkt_dim_product`

Luego el flujo de listings queda así:

- `transform_stage_listings.py`
  - lee `mkt_stage_catalog_item`
  - enlaza contra `mkt_dim_product`
  - genera `mkt_stage_listing_candidate`
  - genera `mkt_stage_listing_review`
- `load_dim_listings.py`
  - carga `mkt_stage_listing_candidate` hacia `mkt_dim_listing`

Luego el flujo de snapshots/fact queda así:

- `transform_stage_listing_snapshots.py`
  - lee `mkt_run` / `mkt_stage_catalog_item`
  - enlaza contra `mkt_dim_listing`
  - genera `mkt_stage_listing_snapshot_candidate`
  - genera `mkt_stage_listing_snapshot_review`
- `load_fact_listing_snapshots.py`
  - carga `mkt_stage_listing_snapshot_candidate` hacia `mkt_fact_listing_snapshot`

## ETL a stage

El comando ETL nuevo es:

```bash
cd /srv/datasyncsa/services/price-scrapper
python3 commands/extract_catalog_to_stage.py --chain-id walmart_cr
```

Idempotencia operativa diaria:

- `mkt_run` registra `business_date_key` en horario `America/Costa_Rica`
- si ya existe una corrida `succeeded` para la misma combinación diaria, el comando se omite
- combinación comparativa:
  - `business_date_key + run_kind + chain`
- combinación analítica:
  - `business_date_key + run_kind + campaign + chain + location`
- esto evita duplicar snapshots por reruns accidentales del mismo día

Qué hace:

- corre el engine configurado para la cadena
- conserva los sleeps y retries ya definidos en el scraper
- toma su runtime desde `mkt_dim_chain` y `mkt_dim_category`
- carga el resultado en:
  - `public.mkt_run`
  - `public.mkt_stage_catalog_item`
- opcionalmente escribe JSON de debug si agregas `--write-debug-files`

Esto deja a los JSON como artifacts opcionales de inspección, no como fuente oficial del pipeline ETL.

En `mkt_dim_category` solo viven categorías raíz por cadena, con `is_enabled` como switch simple de extracción.

## Engines soportados hoy

- `walmart_cr`: `vtex`
- `maxi_pali_cr`: `vtex`
- `masxmenos_cr`: `vtex`
- `megasuper_cr`: `instaleap`

## Vista web local

```bash
cd /srv/datasyncsa/services/price-scrapper
python3 commands/serve_web.py
```

Luego abre `http://127.0.0.1:8765/web/`.

La web ya no consume `output/chains/*.json`; ahora lee las últimas corridas `succeeded`
con `run_kind = comparative` y resuelve productos desde:

- `mkt_fact_listing_snapshot`
- `mkt_dim_listing`
- `mkt_dim_product`

## Corrida operativa

```bash
cd /srv/datasyncsa/services/price-scrapper
python3 commands/reset_catalog_stage.py
python3 commands/extract_catalog_to_stage.py --chain-id masxmenos_cr --run-kind comparative
python3 commands/extract_catalog_to_stage.py --chain-id maxi_pali_cr --run-kind comparative
python3 commands/extract_catalog_to_stage.py --chain-id megasuper_cr --run-kind comparative
python3 commands/extract_catalog_to_stage.py --chain-id walmart_cr --run-kind comparative
python3 commands/transform_stage_products.py
python3 commands/load_dim_products.py
python3 commands/transform_stage_listings.py
python3 commands/load_dim_listings.py
python3 commands/transform_stage_listing_snapshots.py
python3 commands/load_fact_listing_snapshots.py
```

## Corrida analítica operativa

Esta corrida usa los engines analíticos por plataforma:

- `vtex_analytic_engine.py`
  - aplica a `walmart_cr`, `maxi_pali_cr`, `masxmenos_cr`
  - consulta producto puntual por tienda usando el contexto VTEX de la location
- `instaleap_analytic_engine.py`
  - aplica a `megasuper_cr`
  - consulta producto puntual por tienda usando `storeReference` / `storeId`

La campaña define:

- qué productos monitorear: `mkt_campaign_product`
- qué tiendas monitorear: `mkt_campaign_location`
- fecha de negocio diaria:
  - `--business-date YYYY-MM-DD`
  - si se omite, usa hoy en `America/Costa_Rica`

### Corrida analítica completa

Corre toda la campaña, aunque ya existan runs analíticos exitosos previos para esas tiendas.

```bash
cd /srv/datasyncsa/services/price-scrapper
python3 commands/run_campaign_analytic_batch.py --campaign-id 1
```

### Corrida analítica solo pendientes

Corre solo las `locations` de la campaña que todavía no tengan un run analítico `succeeded`
para esa misma campaña.

```bash
cd /srv/datasyncsa/services/price-scrapper
python3 commands/run_campaign_analytic_batch.py --campaign-id 1 --only-pending
```

Aunque no uses `--only-pending`, si una `location` de esa campaña ya tiene una corrida analítica
`succeeded` para la misma fecha de negocio, el comando la omite y no duplica facts.

### Corrida analítica parcial por cadena

Sirve para lanzar o relanzar solo una cadena de la campaña.

```bash
cd /srv/datasyncsa/services/price-scrapper
python3 commands/run_campaign_analytic_batch.py --campaign-id 1 --chain-id walmart_cr
python3 commands/run_campaign_analytic_batch.py --campaign-id 1 --chain-id maxi_pali_cr
python3 commands/run_campaign_analytic_batch.py --campaign-id 1 --chain-id masxmenos_cr
python3 commands/run_campaign_analytic_batch.py --campaign-id 1 --chain-id megasuper_cr
```

### Corrida analítica parcial por cadena solo pendientes

Útil para retomar una cadena incompleta sin repetir tiendas ya exitosas.

```bash
cd /srv/datasyncsa/services/price-scrapper
python3 commands/run_campaign_analytic_batch.py --campaign-id 1 --chain-id megasuper_cr --only-pending
```
