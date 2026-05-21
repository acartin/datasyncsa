# Dagster Orchestration

Dagster vive en este repo como orquestador de Market Watch / pricing.

Responsabilidades:

- Orquestar jobs, assets, schedules y sensores de `services/price-scrapper`.
- Exponer UI operativa en `DAGSTER_PORT` (`3010` por defecto).
- Mantener metadatos de orquestacion en la base `dagster` del Postgres principal del compose.

Limites:

- No aloja dashboards cliente.
- No reemplaza `market-watch-api`.
- No ejecuta scraping dentro de requests web.
- No importa codigo de `market-watch-api` ni del frontend.

Estructura de codigo:

- `src/market_watch_orchestration/definitions.py`
  - define assets, ops, jobs y schedules de Dagster.
  - debe describir el flujo, no contener SQL largo ni armado detallado de comandos.
- `src/market_watch_orchestration/resources.py`
  - facade liviana para recursos de Dagster.
  - mantiene compatibilidad con `definitions.py` y delega a adapters por dominio.
- `src/market_watch_orchestration/price_scrapper/`
  - adapter del bounded context `services/price-scrapper`.
  - `command_runner.py`: ejecucion generica de scripts.
  - `commands.py`: API de comandos ETL disponibles.
  - `postgres_runner.py`: ejecucion SQL contra Postgres operacional.
  - `repository.py`: queries SQL usadas por la orquestacion.

Regla de crecimiento:

- Si aparece otro dominio (`rh`, `logistica`, `mantenimiento`, etc.), crear un paquete
  hermano con sus propios `commands.py`, `repository.py` y runners si aplica.
- No hacer crecer `resources.py` con SQL, transformaciones o logica de negocio.
- Dagster debe quedar como mapa operativo; la complejidad de cada dominio vive
  detras de adapters pequeños.

Servicios:

- `dagster-webserver`: UI y API de Dagster.
- `dagster-daemon`: schedules y sensores.

Job recomendado:

- `daily_active_campaigns_analytic_job`
  - descubre campañas activas desde `mkt_dim_campaign.is_active = true`
  - agrupa extracciones por `campaign_id + engine`
  - ejecuta extracciones `extract-only` en paralelo
  - reparte cada extracción hasta `18:00` hora Costa Rica
  - transforma y carga una sola vez al final, usando todos los `run_keys` exitosos del día
  - schedule sugerido: `daily_active_campaigns_analytic_schedule`
  - cron: `0 8 * * *` en `America/Costa_Rica`

Jobs legacy/manuales:

- `campaign_analytic_walmart_family_job`
  - equivalente al comando diario con `masxmenos_cr`, `maxi_pali_cr`, `walmart_cr`
  - schedule sugerido: `daily_campaign_analytic_walmart_family_schedule`
- `campaign_analytic_megasuper_job`
  - equivalente al comando diario con `megasuper_cr`
  - schedule sugerido: `daily_campaign_analytic_megasuper_schedule`

Ambos schedules quedan apagados por defecto. Dagster genera `business_date`
con la fecha local de `America/Costa_Rica` al momento programado. Para corridas
manuales se puede sobrescribir `business_date` en la config del launchpad.

Run config manual recomendado:

```yaml
ops:
  discover_active_campaign_extract_groups:
    config:
      business_date: "2026-05-14"
      spread_until_cr: "18:00"
      only_pending: true
```

Run config manual legacy de ejemplo:

```yaml
ops:
  run_campaign_analytic_batch:
    config:
      campaign_id: 1
      chain_ids:
        - masxmenos_cr
        - maxi_pali_cr
        - walmart_cr
      business_date: "2026-05-11"
      spread_until_cr: "20:00"
      only_pending: true
```

Comandos:

```bash
docker compose up -d --build dagster-webserver dagster-daemon
docker compose logs -f dagster-webserver
```

URL:

```text
http://192.168.10.37:3010/
```
