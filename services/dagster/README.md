# Dagster Orchestration

Dagster vive en este repo como orquestador de Market Watch / pricing.

Guia operativa humana:

- `docs/OPERATIONS.md`: que hace cada job, cuando ejecutarlo, run configs,
  schedules, validacion y troubleshooting.

Responsabilidades:

- Orquestar jobs, schedules y sensores de `services/price-scrapper`.
- Ejecutar el pipeline de generacion de señales (`daily_signal_generation_job`).
- Exponer UI operativa en `DAGSTER_PORT` (`3010` por defecto).
- Mantener metadatos de orquestacion en la base `dagster` del Postgres principal del compose.

Limites:

- No aloja dashboards cliente.
- No reemplaza `market-watch-api`.
- No ejecuta scraping dentro de requests web.
- No importa codigo de `market-watch-api` ni del frontend.

## Estructura de codigo

```
src/market_watch_orchestration/
├── __init__.py
├── definitions.py          # ops, jobs, schedules
├── resources.py            # facade de recursos
└── price_scrapper/         # adapter del bounded context price-scrapper
    ├── command_runner.py   # ejecucion generica de scripts
    ├── commands.py         # API de comandos ETL disponibles
    ├── postgres_runner.py  # ejecucion SQL contra Postgres operacional
    └── repository.py       # queries SQL
```

Regla de crecimiento:

- Si aparece otro dominio (señales, rh, logistica, etc.), crear un paquete
  hermano con sus propios `commands.py`, `repository.py` y runners si aplica.
- No hacer crecer `resources.py` con SQL, transformaciones o logica de negocio.
- Dagster debe quedar como mapa operativo; la complejidad de cada dominio vive
  detras de adapters pequeños.

## Jobs

### ETL principal: `daily_active_campaigns_analytic_job`

- Descubre campañas activas desde `mkt_dim_campaign.is_active = true`
- Agrupa extracciones por `campaign_id + engine`
- Ejecuta extracciones en paralelo con spread hasta `18:00` Costa Rica
- Transforma y carga al final, usando todos los `run_keys` exitosos del día
- Schedule: `daily_active_campaigns_analytic_schedule` (`0 8 * * *`, apagado por defecto)

### ETL legacy: `campaign_analytic_walmart_family_job` / `campaign_analytic_megasuper_job`

- Ejecutan batch directo sin discovery de campañas
- Schedules sugeridos (apagados por defecto):
  - Walmart family: `daily_campaign_analytic_walmart_family_schedule` (`0 5 * * *`)
  - Megasuper: `daily_campaign_analytic_megasuper_schedule` (`15 5 * * *`)

### Señales: `daily_signal_generation_job`

- Ejecuta `generate_retail_signals` que llama al `retail-signal-engine`
- Lee datos de la campaña, genera señales ejecutivas y eventos de transicion
- No tiene schedule automatico; se lanza desde Launchpad

Run config para signals:

```yaml
ops:
  generate_retail_signals:
    config:
      campaign_id: 1
      business_date: "2026-05-27"
      skip_llm: true
```

## Servicios

- `dagster-webserver`: UI y API de Dagster.
- `dagster-daemon`: schedules y sensores.

## Comandos

```bash
docker compose up -d --build dagster-webserver dagster-daemon
docker compose logs -f dagster-webserver
```

URL:

```text
http://192.168.10.37:3010/
```
