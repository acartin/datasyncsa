# Dagster Operations Guide

Esta guia es para operar los procesos Dagster de Market Watch. Describe que hace
cada job, cuando usarlo, como ejecutarlo y que revisar antes/despues de una
corrida.

Dagster es el orquestador. La logica de scraping, ETL y carga vive en
`services/price-scrapper`; Dagster solo coordina esos comandos y registra la
ejecucion.

## Servicios

Servicios del compose:

- `dagster-webserver`: UI y API de Dagster.
- `dagster-daemon`: ejecuta schedules y sensores.
- `postgres`: base operacional y base de metadatos de Dagster.

URL operativa por defecto:

```text
http://192.168.10.37:3010/
```

Levantar o reconstruir Dagster:

```bash
docker compose up -d --build dagster-webserver dagster-daemon
```

Ver logs:

```bash
docker compose logs -f dagster-webserver
docker compose logs -f dagster-daemon
```

Validacion tecnica despues de cambios Python en Dagster:

```bash
docker compose exec -T dagster-webserver /bin/bash -lc "find /opt/dagster/app/src -type f -name '*.py' -print0 | xargs -0 python -m py_compile"
```

## Preflight Operativo

Antes de lanzar jobs con DB o ETL real:

1. Confirmar que `postgres`, `market-watch-api`, `dagster-webserver` y
   `dagster-daemon` estan arriba.
2. Confirmar variables criticas sin imprimir secretos:

```bash
set -a; source .env; set +a
printf 'DB_USER=%s\nDB_NAME=%s\nDAGSTER_DB_USER=%s\nDAGSTER_DB_NAME=%s\n' \
  "${DB_USER:+set}" "${DB_NAME:+set}" "${DAGSTER_DB_USER:+set}" "${DAGSTER_DB_NAME:+set}"
```

3. Revisar que no haya otra corrida ETL activa sobre las mismas tablas stage.
4. Definir la fecha de negocio (`business_date`) en horario Costa Rica.
5. Decidir si la corrida debe ser incremental (`only_pending: true`) o si se
   espera una reejecucion controlada.

No usar `cat .env` completo para diagnostico: puede exponer secretos.

## Conceptos

`business_date`

Fecha de negocio en formato `YYYY-MM-DD`. Si un op permite omitirla, se calcula
con timezone `America/Costa_Rica`.

`only_pending`

Cuando esta en `true`, la extraccion intenta correr solo locations pendientes,
es decir, locations sin run analitico exitoso para esa campana y fecha. En el
job principal, si no hay extracciones nuevas, el job puede continuar usando
`run_keys` exitosos ya existentes para esa fecha.

`spread_until_cr`

Hora limite `HH:MM` en Costa Rica para repartir la extraccion. Se usa para no
disparar todas las consultas al mismo tiempo.

`run_keys`

Identificadores de corridas analiticas en `mkt_run`. Las transformaciones y
cargas usan esos `run_keys` para mover datos desde stage hacia dimensiones y
facts.

## Jobs

### `daily_active_campaigns_analytic_job`

Job recomendado para el ETL diario normal.

Que hace:

1. Limpia tablas stage de transformacion diaria.
2. Descubre campanas activas desde `mkt_dim_campaign.is_active = true`.
3. Agrupa extracciones por `campaign_id + engine`.
4. Ejecuta extracciones dinamicas por grupo.
5. Recolecta `run_keys` analiticos exitosos de la fecha.
6. Transforma productos y carga `mkt_dim_product`.
7. Transforma listings y carga `mkt_dim_listing`.
8. Transforma snapshots y carga `mkt_fact_listing_snapshot`.
9. Valida conteos entre stage y facts.

Schedule:

- `daily_active_campaigns_analytic_schedule`
- Cron: `0 8 * * *`
- Timezone: `America/Costa_Rica`
- Estado por defecto: apagado (`STOPPED`)

Cuando usarlo:

- Corrida diaria normal.
- Corrida manual de todas las campanas activas.
- Reprocesamiento controlado de una fecha donde ya existen runs exitosos.

Cuando no usarlo:

- Si hay un job legacy corriendo sobre la misma campana o mismas cadenas.
- Si se necesita probar una sola cadena de forma aislada; para eso puede ser
  mas claro usar un job legacy o comando directo de `price-scrapper`.

Run config manual recomendado:

```yaml
ops:
  discover_active_campaign_extract_groups:
    config:
      business_date: "2026-05-28"
      spread_until_cr: "18:00"
      only_pending: true
```

Notas operativas:

- Con `only_pending: true`, una corrida manual puede no extraer datos nuevos si
  ya hay runs exitosos para esa fecha.
- La validacion final falla el run si detecta diferencia stage vs fact,
  duplicados o runs sospechosos.
- Este job usa tablas stage compartidas; evitar correrlo en paralelo con jobs
  legacy.

### `campaign_analytic_walmart_family_job`

Job legacy para ejecutar un batch directo de la campana por cadenas Walmart
family.

Cadenas:

- `masxmenos_cr`
- `maxi_pali_cr`
- `walmart_cr`

Schedule:

- `daily_campaign_analytic_walmart_family_schedule`
- Cron: `0 5 * * *`
- Timezone: `America/Costa_Rica`
- Estado por defecto: apagado (`STOPPED`)

Cuando usarlo:

- Operacion manual puntual sobre Walmart family.
- Reintento aislado cuando el discovery automatico no es deseado.

Cuando no usarlo:

- Al mismo tiempo que `daily_active_campaigns_analytic_job` para la misma fecha.
- Como schedule permanente junto al job principal, salvo que se haya definido
  una politica clara de no solapamiento.

Run config manual:

```yaml
ops:
  run_campaign_analytic_batch:
    config:
      campaign_id: 1
      chain_ids:
        - masxmenos_cr
        - maxi_pali_cr
        - walmart_cr
      business_date: "2026-05-28"
      spread_until_cr: "20:00"
      only_pending: true
```

### `campaign_analytic_megasuper_job`

Job legacy para ejecutar un batch directo de la campana por Megasuper.

Cadenas:

- `megasuper_cr`

Schedule:

- `daily_campaign_analytic_megasuper_schedule`
- Cron: `15 5 * * *`
- Timezone: `America/Costa_Rica`
- Estado por defecto: apagado (`STOPPED`)

Cuando usarlo:

- Operacion manual puntual sobre Megasuper.
- Reintento aislado de una cadena.

Cuando no usarlo:

- Al mismo tiempo que `daily_active_campaigns_analytic_job` para la misma fecha.

Run config manual:

```yaml
ops:
  run_campaign_analytic_batch:
    config:
      campaign_id: 1
      chain_ids:
        - megasuper_cr
      business_date: "2026-05-28"
      spread_until_cr: "20:00"
      only_pending: true
```

### `daily_signal_generation_job`

Job para generar senales ejecutivas y eventos de transicion usando
`services/retail-signal-engine`.

Que hace:

1. Recibe `campaign_id`, `business_date` y `skip_llm`.
2. Ejecuta `commands/generate_daily_signals.py` en `retail-signal-engine`.
3. Lee facts/datasets disponibles para la campana y fecha.
4. Genera senales para consumo del producto Market Watch.

Schedule:

- No tiene schedule automatico.
- Se lanza manualmente desde Launchpad.

Cuando usarlo:

- Despues de que el ETL diario cargo facts para la fecha.
- Para regenerar senales historicas de una campana y fecha concreta.

Cuando no usarlo:

- Antes de que termine el ETL de la misma fecha.
- Si no hay facts cargados para `campaign_id + business_date`.

Run config manual:

```yaml
ops:
  generate_retail_signals:
    config:
      campaign_id: 1
      business_date: "2026-05-28"
      skip_llm: true
```

Notas:

- `skip_llm: true` usa narrativa deterministica.
- `skip_llm: false` puede requerir credenciales externas segun configuracion
  del engine.

## Ejecucion Manual Desde Dagster UI

1. Abrir la UI de Dagster.
2. Ir a `Jobs`.
3. Seleccionar el job.
4. Abrir `Launchpad`.
5. Pegar el run config YAML correspondiente.
6. Revisar `business_date`, `only_pending` y `spread_until_cr`.
7. Click en `Launch Run`.
8. Seguir logs por op.
9. Revisar metadata de outputs, especialmente `run_keys`, `run_count` y
   `validation`.

## Activar Schedules

Los schedules principales estan apagados por defecto. Antes de activarlos:

1. Confirmar que no se solapan con jobs legacy.
2. Confirmar ventana horaria esperada en Costa Rica.
3. Confirmar que `dagster-daemon` esta arriba.
4. Activar solo un camino de ETL diario salvo decision explicita.

Politica recomendada:

- Usar `daily_active_campaigns_analytic_schedule` como schedule principal.
- Mantener schedules legacy apagados salvo operacion puntual.
- Mantener senales manuales hasta que exista dependencia post-ETL formal.

## Validacion Despues de una Corrida

En Dagster UI:

- Confirmar que todos los ops terminaron en verde.
- Revisar metadata de `extract_campaign_analytic_group`:
  - `campaign_id`
  - `engine`
  - `chain_ids`
  - `run_keys`
  - `run_count`
- Revisar metadata de `collect_daily_analytic_run_keys`:
  - `business_date`
  - `campaign_ids`
  - `run_keys`
  - `run_count`
- Revisar metadata de `validate_daily_analytic_counts`:
  - `stage_items`
  - `fact_rows`
  - `stage_minus_fact`
  - `duplicate_facts`
  - `suspect_runs`

La corrida diaria debe quedar con:

- `stage_minus_fact = 0`
- `duplicate_facts = 0`
- `suspect_runs = 0`

## Troubleshooting

### No aparecen campanas activas

Sintoma:

- `discover_active_campaign_extract_groups` reporta `0 active campaign extract groups`.

Revisar:

- `mkt_dim_campaign.is_active`
- locations activas en `mkt_dim_location`
- relaciones en `mkt_campaign_location`
- chains asociadas a locations

### No hay `run_keys`

Sintoma:

- Extraccion termina sin `run_keys`.
- Transformaciones se saltan por falta de trabajo.

Posibles causas:

- `only_pending: true` y ya existen runs exitosos para esa fecha.
- La campana no tiene productos o locations validas.
- El extractor fallo antes de cargar stage.

Accion:

- Revisar logs del op de extraccion.
- Confirmar si se esperaba reusar runs existentes o forzar trabajo nuevo.

### Falla la validacion final

Sintoma:

- `validate_daily_analytic_counts` falla el run.

Revisar metadata:

- `stage_minus_fact`
- `duplicate_facts`
- `suspect_runs`

Accion:

- Si `stage_minus_fact != 0`, hay diferencia entre items stage y facts.
- Si `duplicate_facts != 0`, revisar duplicados por `date_key + run_key + listing_key`.
- Si `suspect_runs != 0`, hay runs con stage pero sin facts.

### El job queda colgado

Actualmente los ops no tienen timeout explicito. Revisar:

- logs del contenedor `dagster-webserver`
- logs del run en Dagster UI
- si el subprocess de `price-scrapper` sigue vivo
- conectividad contra Postgres

### Senales sin datos

Sintoma:

- `daily_signal_generation_job` corre pero no produce senales esperadas.

Revisar:

- que el ETL diario haya terminado para el mismo `business_date`
- que existan facts para `campaign_id`
- logs de `generate_retail_signals`
- valor de `skip_llm`

## Riesgos Conocidos

- Los jobs legacy y el job principal usan tablas stage compartidas; no deben
  correr en paralelo sin coordinacion.
- `only_pending: true` puede hacer que una corrida manual no extraiga trabajo
  nuevo y continue con runs existentes.
- El ETL principal esta modelado como ops imperativos, no como asset graph
  particionado por fecha.
- No hay retries ni timeouts configurados en los ops.
- La generacion de senales no depende automaticamente del exito del ETL.

## Comandos Directos de Referencia

Para operar fuera de Dagster, usar los comandos de `price-scrapper` documentados
en `services/price-scrapper/README.md`. Ejemplo:

```bash
cd /srv/datasyncsa/services/price-scrapper
python3 commands/run_campaign_analytic_batch.py --campaign-id 1 --chain-id megasuper_cr --only-pending
```

Preferir Dagster para corridas operativas visibles en UI y con metadata de
orquestacion.
