# AI Context Pack

- Generated UTC: `2026-06-02T22:30:38Z`
- Repo root: `/srv/datasyncsa`
- Git branch: `HETZNER-LOCAL-2026-Mayo-31`
- Git commit: `27aced8`
- Policy: high-signal only; enfocado en Market Watch / pricing.

## Contexto Maestro

### `.agent/BRAIN_MAP.md`

```
# BRAIN_MAP

- Generated UTC: `2026-06-02T22:30:38Z`
- Repo root: `/srv/datasyncsa`
- Git branch: `HETZNER-LOCAL-2026-Mayo-31`
- Git commit: `27aced8`

## 1. MAPA DE INTENCIONES (MARKET WATCH)

| Carpeta | Responsabilidad Tecnica | Importancia (1-5) |
|---|---|---:|
| `docker-compose.yml` | Compose heredado/actual del repo; revisar antes de tocar infraestructura. | 4 |
| `services/dagster` | Orquestacion de Market Watch: assets, jobs, schedules y sensores para coordinar ETL. | 4 |
| `services/price-scrapper` | Bounded context de scraping, ETL, campañas, facts y queries base. | 5 |
| `services/market-watch-api` | API de producto: auth/multitenancy, datasets livianos, control de `client_id`. | 5 |
| `services/web/market-watch` | Frontend cliente: SEO, dashboards, tablas, pivots y reportes. | 5 |
| `.agent` | Reglas operativas para agentes en el repo recortado. | 4 |

## 2. LIMITES DE ARQUITECTURA

- `price-scrapper` no aloja el producto cliente final.
- `dagster` orquesta ETL/assets; no aloja portal cliente ni duplica scraping pesado.
- `market-watch-api` no ejecuta scraping ni ETL pesado durante requests web.
- `web/market-watch` no se conecta directo a Postgres.
- No reutilizar `services/web/admin-console` ni `services/web/chat-web-renderer` como base del producto.
- Mantener contratos simples para facilitar separacion futura del repo.

## 3. SERVICIOS DOCKER ACTUALES

```text
postgres
admin-console-api
admin-console-web
market-watch-api
dagster-daemon
market-watch-web
portainer
redis
dagster-webserver
```

## 4. TOPOLOGIA DE TRABAJO

```text
services/price-scrapper
services/price-scrapper/commands
services/price-scrapper/docs
services/price-scrapper/docs/tables
services/price-scrapper/engines
services/price-scrapper/etl
services/price-scrapper/schemas
services/price-scrapper/seeds
services/price-scrapper/web
services/price-scrapper/web_backend
services/dagster
services/dagster/docs
services/dagster/src
services/dagster/src/market_watch_orchestration
services/dagster/src/market_watch_orchestration/price_scrapper
services/market-watch-api
services/market-watch-api/app
services/market-watch-api/app/api
services/market-watch-api/app/api/routes
services/market-watch-api/app/core
services/market-watch-api/app/domain
services/market-watch-api/app/repositories
services/web/market-watch
services/web/market-watch/app
services/web/market-watch/app/[group]
services/web/market-watch/app/[group]/[module]
services/web/market-watch/app/api
services/web/market-watch/app/api/auth
services/web/market-watch/app/api/filters
services/web/market-watch/app/api/settings
services/web/market-watch/app/api/table-views
services/web/market-watch/app/login
services/web/market-watch/app/pricing
services/web/market-watch/app/pricing/executive-signals
services/web/market-watch/app/pricing/intraday-radar
services/web/market-watch/app/pricing/products
services/web/market-watch/app/pricing/signals
services/web/market-watch/components
services/web/market-watch/components/market-watch
services/web/market-watch/components/portal
services/web/market-watch/components/ui
services/web/market-watch/lib
services/web/market-watch/public
```

## 5. ARCHIVOS RELEVANTES

```text
services/price-scrapper/README.md
services/price-scrapper/borrar_populate_mkt_dim_product.py
services/price-scrapper/commands/extract_campaign_analytic_to_stage.py
services/price-scrapper/commands/extract_catalog_to_stage.py
services/price-scrapper/commands/extract_chain_catalog.py
services/price-scrapper/commands/extract_chain_locations.py
services/price-scrapper/commands/load_dim_listings.py
services/price-scrapper/commands/load_dim_products.py
services/price-scrapper/commands/load_fact_listing_snapshots.py
services/price-scrapper/commands/reset_catalog_stage.py
services/price-scrapper/commands/run_campaign_analytic_batch.py
services/price-scrapper/commands/serve_web.py
services/price-scrapper/commands/transform_stage_listing_snapshots.py
services/price-scrapper/commands/transform_stage_listings.py
services/price-scrapper/commands/transform_stage_products.py
services/price-scrapper/commands/update_chain_root_categories.py
services/price-scrapper/docs/tables/README.md
services/price-scrapper/docs/tables/mkt_campaign_location.md
services/price-scrapper/docs/tables/mkt_campaign_product.md
services/price-scrapper/docs/tables/mkt_dim_campaign.md
services/price-scrapper/docs/tables/mkt_dim_category.md
services/price-scrapper/docs/tables/mkt_dim_chain.md
services/price-scrapper/docs/tables/mkt_dim_client.md
services/price-scrapper/docs/tables/mkt_dim_date.md
services/price-scrapper/docs/tables/mkt_dim_listing.md
services/price-scrapper/docs/tables/mkt_dim_location.md
services/price-scrapper/docs/tables/mkt_dim_market_event_type.md
services/price-scrapper/docs/tables/mkt_dim_product.md
services/price-scrapper/docs/tables/mkt_fact_listing_snapshot.md
services/price-scrapper/docs/tables/mkt_run.md
services/price-scrapper/docs/tables/mkt_stage_catalog_item.md
services/price-scrapper/docs/tables/mkt_stage_listing_candidate.md
services/price-scrapper/docs/tables/mkt_stage_listing_review.md
services/price-scrapper/docs/tables/mkt_stage_listing_snapshot_candidate.md
services/price-scrapper/docs/tables/mkt_stage_listing_snapshot_review.md
services/price-scrapper/docs/tables/mkt_stage_product_candidate.md
services/price-scrapper/docs/tables/mkt_stage_product_review.md
services/price-scrapper/engines/instaleap_analytic_engine.py
services/price-scrapper/engines/instaleap_catalog_engine.py
services/price-scrapper/engines/instaleap_location_engine.py
services/price-scrapper/engines/vtex_analytic_engine.py
services/price-scrapper/engines/vtex_catalog_engine.py
services/price-scrapper/engines/vtex_location_engine.py
services/price-scrapper/etl/__init__.py
services/price-scrapper/etl/business_date.py
services/price-scrapper/etl/campaign_runtime_db.py
services/price-scrapper/etl/catalog_stage_loader.py
services/price-scrapper/etl/catalog_stage_reset.py
services/price-scrapper/etl/chain_runtime_db.py
services/price-scrapper/etl/http_client.py
services/price-scrapper/etl/normalize.py
services/price-scrapper/etl/postgres_cli.py
services/price-scrapper/etl/run_runtime_db.py
services/price-scrapper/etl/stage_listing_snapshot_transform.py
services/price-scrapper/etl/stage_listing_transform.py
services/price-scrapper/etl/stage_product_transform.py
services/price-scrapper/requirements.txt
services/price-scrapper/schemas/canonical_product_v1.schema.json
services/price-scrapper/seeds/2026-05-08_adjust_campaign_locations_sardimar_atun_competencia_cr_megasuper.sql
services/price-scrapper/seeds/2026-05-08_seed_campaign_locations_sardimar_atun_competencia_cr.sql
services/price-scrapper/seeds/2026-05-08_seed_campaign_sardimar_atun_competencia_cr.sql
services/price-scrapper/seeds/2026-05-22_create_mw_tool_agnostic_semantic_layer.sql
services/price-scrapper/seeds/2026-05-26_create_auth_security_baseline.sql
services/price-scrapper/seeds/2026-05-27_create_mkt_campaign_client_access.sql
services/price-scrapper/seeds/2026-05-31_create_mkt_dim_market_event_type.sql
services/price-scrapper/web/app.js
services/price-scrapper/web/catalog-data.js
services/price-scrapper/web/compare.html
services/price-scrapper/web/compare.js
services/price-scrapper/web/index.html
services/price-scrapper/web/styles.css
services/price-scrapper/web_backend/__init__.py
services/price-scrapper/web_backend/catalog_db.py
services/dagster/Dockerfile
services/dagster/README.md
services/dagster/dagster.yaml
services/dagster/docs/OPERATIONS.md
services/dagster/requirements.txt
services/dagster/src/market_watch_orchestration/__init__.py
services/dagster/src/market_watch_orchestration/definitions.py
services/dagster/src/market_watch_orchestration/resources.py
services/dagster/workspace.yaml
services/market-watch-api/Dockerfile
services/market-watch-api/README.md
services/market-watch-api/app/__init__.py
services/market-watch-api/app/api/__init__.py
services/market-watch-api/app/api/router.py
services/market-watch-api/app/core/__init__.py
```

## Reglas Operativas

### `.agent/RULES.md`

```
# RULES

## 1. Fuente de Verdad de Contexto

Precondicion obligatoria al iniciar cada nueva sesion:

1. Carga base obligatoria:
   - Leer `.agent/RULES.md`
   - Leer `.agent/PY_EXECUTION_MAP.md`
   - Leer `.agent/MARKET_WATCH_UI_STANDARDS.md`
2. Determinar si se requiere regeneracion de contexto:
   - faltan `.agent/BRAIN_MAP.md` o `.agent/AI_CONTEXT_PACK.md`
   - el commit actual difiere del commit registrado en `.agent/BRAIN_MAP.md`
   - el usuario pide actualizacion completa de contexto
   - hubo cambio grande de arquitectura, compose o estructura de `services/price-scrapper` / `services/web/market-watch`
3. Solo si aplica el punto 2, ejecutar `bash .agent/regenerar_contexto.sh`
4. Leer `.agent/BRAIN_MAP.md` y `.agent/AI_CONTEXT_PACK.md` solo por secciones necesarias.
5. Recien despues iniciar implementacion, debug o review.

Preflight obligatorio para tareas con DB/Docker:

- Validar variables criticas (`DB_USER`, `DB_NAME`, `DATABASE_URL`) sin volcar secretos.
- Prohibido hacer `cat .env` completo salvo instruccion explicita del usuario.
- Para comandos SQL/DB en shell, usar wrapper:
  `set -a; source .env; set +a; <comando>`
- Si falta una variable critica, detener ejecucion y reportar.

Regla de precedencia:

1. Codigo ejecutable vigente
2. `.agent/RULES.md`
3. `.agent/PY_EXECUTION_MAP.md`
4. `.agent/MARKET_WATCH_UI_STANDARDS.md`
5. `.agent/BRAIN_MAP.md`
6. `.agent/AI_CONTEXT_PACK.md`

## 2. Scope Operativo Actual

El repo fue recortado. El foco de trabajo actual es el producto Market Watch / pricing dentro del monorepo.

Servicios principales:

- `services/price-scrapper`
  - scraping
  - ETL
  - campañas
  - facts
  - queries base
  - herramientas internas existentes para operacion de datos
- `services/dagster`
  - orquestacion de assets, jobs, schedules y sensores
  - punto operativo para coordinar `price-scrapper`
  - metadatos de orquestacion separados de la base de negocio
- `services/web/market-watch`
  - frontend del producto cliente
  - SEO
  - dashboards/tablas/pivots ligeros
  - consumo de datasets publicados por API

Servicio previsto, si se crea en este repo:

- `services/market-watch-api`
  - auth/multitenancy
  - endpoints por menu o modulo de producto
  - datasets livianos para tablas/pivots/reportes
  - control autoritativo de `client_id`

Servicios o carpetas no autoritativas para este producto:

- `services/web/admin-console`: no reutilizar para Market Watch cliente.
- `services/web/chat-web-renderer`: no reutilizar para Market Watch cliente.
- `services/price-scrapper/web`: puede servir como herramienta interna o referencia historica, pero no alojar el producto final cliente.

## 3. Arquitectura Innegociable

- `services/price-scrapper` es bounded context de datos/ETL. No debe absorber auth, portal cliente ni UI final.
- `services/dagster` orquesta jobs y assets. No debe contener portal cliente, endpoints de producto ni logica de scraping pesada duplicada.
- `services/market-watch-api` es el borde de producto para clientes. Debe filtrar por tenant/client antes de devolver datos.
- `services/web/market-watch` es frontend del producto. No debe conectarse directo a Postgres ni leer archivos internos del ETL.
- El producto cliente final no debe depender de herramientas BI internas como portal.
- Mantener todo dentro del repo por ahora, pero evitar acoplamientos que dificulten separar el producto mas adelante.
- Preferir contratos claros entre servicios: HTTP/API, variables de entorno y esquemas SQL estables; evitar imports cruzados entre servicios.
- `main.py` de cada API debe ser minimo: app init, middleware, routers.

## 4. Multi-Tenant y Seguridad

- Toda consulta de producto cliente debe tener scope por `client_id` o tenant equivalente.
- No confiar en `client_id` enviado libremente por el frontend si existe sesion/JWT/API key que lo pueda resolver.
- Ningun endpoint debe exponer datos cross-client por ausencia de filtro.
- Endpoints internos sensibles deben validar token interno cuando aplique.
- Credenciales y conexiones via variables de entorno; nunca hardcodeadas.

## 5. Acceso a Datos

- `price-scrapper` puede escribir y transformar datos operativos, stage, dims, facts y resultados analiticos.
- `market-watch-api` debe leer datasets preparados o vistas estables; no debe ejecutar scraping ni ETL pesado durante requests web.
- Priorizar SQL explicito y payloads compactos para tablas, pivots y reportes.
- Evitar N+1 y consultas sin limites en endpoints de producto.
- Si se comparte SQL entre ETL y API, hacerlo mediante vistas, funciones SQL versionadas o modulos claramente separados, no mediante dependencia informal de scripts de campaña.

## 6. Frontend Market Watch

- `services/web/market-watch` debe ser independiente de `admin-console` y `chat-web-renderer`.
- El frontend cliente debe consumir API propia o mocks locales explicitamente marcados.
- No meter el producto final dentro de `services/price-scrapper/web`.
- Las pantallas deben priorizar workflows de producto: dashboards, tablas, pivots, reportes, filtros y seleccion de cliente/mercado cuando aplique.
- SEO pertenece al frontend del producto, no al ETL.
- Toda implementacion visual o CRUD debe seguir `.agent/MARKET_WATCH_UI_STANDARDS.md`.

## 7. Infra y Operacion

- Orquestacion existente: `docker-compose.yml`.
- Compose operativo unico: `docker-compose.yml`.
- Dagster corre dentro del compose unico como `dagster-webserver`, `dagster-daemon` y `dagster-db`.
- No cambiar nombres de servicios, puertos o URLs base sin ajustar:
  - `docker-compose.yml`
  - `.env.example`
  - `.agent/*` relevante
- No inventar infraestructura adicional sin necesidad clara.
- Si se reutiliza Postgres/Redis del compose actual, declararlo explicitamente y mantener los nombres de red/servicio simples.

## 7.1 Superset / BI

- Cualquier objeto creado o propuesto para Superset debe seguir la nomenclatura de `docs/market-watch-superset-naming.md`.
- Aplica para dashboards, charts, datasets, tags, saved queries, vistas SQL y objetos analiticos relacionados con Market Watch.
- Objetos visibles en Superset deben usar prefijo `MW` y nombres estructurados.
- Objetos tecnicos de base de datos o datasets deben usar prefijo `mw_` y `snake_case`.
- No crear nombres genericos como `Dashboard precios final v2`, `test`, `reporte nuevo` o similares.

## 8. Testing Minimo por Cambio

Regla general:

- Usar `.agent/PY_EXECUTION_MAP.md` para decidir host vs contenedor.
- No correr `pytest` en host salvo instruccion explicita del usuario.
- Si cambias codigo en un servicio Docker que no monta el codigo fuente completo, hacer rebuild antes de validar.
- Si no se ejecutan pruebas, documentar exactamente que no se valido y por que.

Minimos por area:

- `services/price-scrapper/**`
  - Para cambios Python de ETL/scripts: `python3 -m py_compile` segun el mapa de ejecucion vigente.
  - Para pruebas funcionales con DB: usar el contenedor/compose indicado por `.agent/PY_EXECUTION_MAP.md`.
- `services/market-watch-api/**`
  - Si existe Dockerfile/compose: validar dentro del contenedor.
  - Si aun es esqueleto sin contenedor: usar solo `python3 -m py_compile` o comandos `--help`/`--list` cuando aplique.
- `services/dagster/**`
  - Para cambios Python: validar dentro de `dagster-webserver` si el servicio existe.
  - Para cambios de compose/config: `docker compose config` y smoke de UI si se levanta.
- `services/web/market-watch/**`
  - Validar con el gestor del proyecto si existe (`npm`, `pnpm`, etc.) o con smoke HTTP si corre bajo Nginx/Vite/Next.
  - No usar Python salvo scripts auxiliares.

En tareas de reorganizacion o documentacion de tests:

- validar con `python3 -m py_compile`, `docker compose config`, `--help` o `--list` cuando baste.
- evitar suites pesadas si el trabajo no cambia comportamiento.

Para tareas de alto impacto, dejar claro:

- archivo objetivo
- servicios afectados
- validacion minima esperada

## 9. Checklist de Rechazo Inmediato

Rechazar cambios que:

- rompen aislamiento por `client_id`
- mueven ETL/scraping al frontend
- hacen que el producto cliente dependa de herramientas BI internas como portal
- reutilizan `admin-console` o `chat-web-renderer` como base del producto Market Watch
- meten el producto cliente final en `services/price-scrapper/web`
- eliminan validaciones de seguridad
- dejan `.agent` o `.env.example` desalineados despues de cambiar compose/naming

## 10. Convencion de Trabajo con IA

Antes de empezar trabajo nuevo:

```
### `.agent/PY_EXECUTION_MAP.md`

```
# PY Execution Map (Host vs Container)

## Objetivo

Este archivo define, por ruta del repo recortado, donde ejecutar comandos Python y que rebuilds son obligatorios.

Reglas base:

1. Si el codigo vive en un servicio Docker activo, ejecutar Python en su contenedor.
2. Si el servicio aun no tiene contenedor o compose operativo, usar validaciones livianas en host.
3. Si el servicio no monta el codigo fuente completo, hacer rebuild antes de validar cambios funcionales.
4. No correr `pytest` en host salvo instruccion explicita del usuario.

## Decision Rapida

1. Identifica la ruta del archivo que tocaste.
2. Busca el prefijo en la tabla.
3. Ejecuta el comando base en el entorno indicado.
4. Si el cambio toca DB/Docker, aplica el preflight de `.agent/RULES.md`.

## Mapa por Rutas

| Prefijo de ruta | Ejecutar `py` en | Paso previo obligatorio | Comando base |
|---|---|---|---|
| `services/price-scrapper/` | Host por defecto, salvo que exista servicio Docker especifico para la tarea | Para pruebas reales con DB, cargar `.env` y usar compose/contenedor si el servicio queda definido | `python3 -m py_compile $(find services/price-scrapper -path '*/__pycache__' -prune -o -name '*.py' -print)` |
| `services/dagster/` | Contenedor `dagster-webserver` si existe; host solo para esqueleto sin compose | Si cambiaste codigo: `docker compose up -d --build dagster-webserver dagster-daemon` | `docker compose exec -T dagster-webserver /bin/bash -lc "find /opt/dagster/app/src -type f -name '*.py' -print0 | xargs -0 python -m py_compile"` |
| `services/market-watch-api/` | Contenedor `market-watch-api` si existe; host solo para esqueleto sin compose | Si hay Dockerfile/compose y cambiaste codigo: `docker compose up -d --build market-watch-api` | `docker compose exec -T market-watch-api /bin/bash -lc "find . -type f -name '*.py' -print0 | xargs -0 python -m py_compile"` |
| `services/web/market-watch/` | No aplica Python por defecto | Usar el gestor del frontend definido en el servicio; si corre en compose, levantar solo ese stack | Smoke HTTP o build/lint del frontend segun `package.json` local |
| `docker-compose.yml` | No aplica Python | Validar sintaxis compose | `docker compose config` |
| `.agent/` y `AGENTS.md` | Host | No aplica | No requiere Python; validar leyendo diff y, si cambia script shell, `bash -n <script>` |
| `.env.example` | No aplica Python | Revisar alineacion con compose afectado | No aplica |
| `services/web/admin-console/` | Fuera del scope Market Watch | No tocar salvo instruccion explicita | No aplica |
| `services/web/chat-web-renderer/` | Fuera del scope Market Watch | No tocar salvo instruccion explicita | No aplica |

## Nota Critica de Montajes

El producto Market Watch esta en proceso de aislamiento. Antes de asumir que un cambio entra por volumen o por build, revisar el compose correspondiente.

Implicaciones:

- cambio en codigo copiado en imagen => requiere rebuild/recreate del servicio
- cambio en archivos montados por volumen => normalmente requiere restart del proceso si el runtime no hace hot reload
- cambio de contratos DB/API => actualizar docs/README/`.env.example` y validar consumidores afectados

## Variables Clave

- DB: `DB_USER`, `DB_PASS`, `DB_NAME`, `DB_PORT`, `DATABASE_URL`
- Seguridad interna: `INTERNAL_API_TOKEN`
- Market Watch API: `MARKET_WATCH_API_PORT`, `MARKET_WATCH_API_PREFIX`
- Market Watch Web: `MARKET_WATCH_WEB_PORT`
- Dagster: `DAGSTER_PORT`, `DAGSTER_DB_USER`, `DAGSTER_DB_PASSWORD`, `DAGSTER_DB_NAME`
- Storage/ETL si aplica: variables ya existentes en `.env.example`

Referencia contractual: `.env.example`

## Checklist Operativo Minimo

1. Confirmar ruta del cambio.
2. Ejecutar en el entorno correcto.
3. Hacer rebuild si aplica.
4. Correr la validacion minima del servicio afectado.
5. Si no se valido, documentarlo explicitamente.
```
### `AGENTS.md`

```
# AGENTS

## Bootstrap obligatorio por sesion

1. Leer en este orden:
   - `.agent/RULES.md`
   - `.agent/PY_EXECUTION_MAP.md`
   - `.agent/MARKET_WATCH_UI_STANDARDS.md`
2. Regenerar contexto (`bash .agent/regenerar_contexto.sh`) solo si aplica:
   - faltan `.agent/BRAIN_MAP.md` o `.agent/AI_CONTEXT_PACK.md`
   - cambio de commit vs `BRAIN_MAP.md`
   - solicitud explicita del usuario
   - cambio grande en `services/price-scrapper`, `services/dagster`, `services/web/market-watch`, `services/market-watch-api` o `docker-compose.yml`
3. Leer `BRAIN_MAP.md` y `AI_CONTEXT_PACK.md` solo por secciones necesarias, sin carga masiva.

No iniciar implementacion/debug/review sin los pasos anteriores.

## Scope operativo actual

El trabajo actual se concentra en Market Watch / pricing dentro del monorepo:

- `services/price-scrapper`: bounded context de scraping, ETL, campañas, facts y queries base.
- `services/dagster`: orquestacion de ETL/assets/schedules para Market Watch; coordina `price-scrapper` sin absorber producto cliente.
- `services/market-watch-api`: API de producto si existe o se crea; auth/multitenancy, endpoints por menu, datasets livianos y control de `client_id`.
- `services/web/market-watch`: frontend cliente, SEO, dashboards, tablas y pivots.

No reutilizar como base del producto cliente:

- `services/web/admin-console`
- `services/web/chat-web-renderer`
- `services/price-scrapper/web`

## Fuente operativa para ejecutar Python

Usar siempre `.agent/PY_EXECUTION_MAP.md` para decidir:

- host vs contenedor
- comandos base por servicio
- necesidad de rebuild/restart antes de pruebas

Regla de ejecucion:

- No correr `pytest` en host, salvo que el usuario lo pida explicitamente.
- Si la tarea es reorganizacion/documentacion de tests, validar solo con `--help`/`--list`, `python3 -m py_compile`, `bash -n` o `docker compose config` segun aplique.
- Para pruebas funcionales/reales, usar el contenedor del servicio correspondiente cuando exista.

## Limites de arquitectura

- El frontend Market Watch no debe conectarse directo a Postgres.
- La API Market Watch no debe ejecutar scraping ni ETL pesado durante requests web.
- Dagster no debe alojar auth, portal cliente ni endpoints de producto.
- `price-scrapper` no debe alojar auth ni portal cliente final.
- Todo dataset cliente debe estar filtrado por `client_id` o tenant equivalente antes de salir de la API.
- Mantener contratos simples para facilitar separar estos servicios del repo mas adelante.
```

## Compose y Variables

### Servicios del compose principal

```text
postgres
admin-console-api
admin-console-web
market-watch-api
dagster-daemon
dagster-webserver
portainer
redis
market-watch-web
```
### `docker-compose.yml:1-220`

```
services:
  # ---------------------------------------------------------------------------
  # INFRASTRUCTURE
  # ---------------------------------------------------------------------------
  postgres:
    image: datasyncsa-postgres:latest
    container_name: ${ENV_PREFIX:-ds-dev}-infra-postgres
    restart: always
    command: ["postgres", "-c", "timezone=${TZ:-UTC}"]
    environment:
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASS}
      POSTGRES_DB: ${DB_NAME}
      TZ: ${TZ:-UTC}
    ports:
      - "${DB_PORT:-5432}:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - internal_network

  redis:
    image: redis:alpine
    container_name: ${ENV_PREFIX:-ds-dev}-infra-redis
    restart: always
    command: redis-server --appendonly yes
    environment:
      TZ: ${TZ:-UTC}
    volumes:
      - redis_data:/data
    networks:
      - internal_network

  portainer:
    image: portainer/portainer-ce:latest
    container_name: ${ENV_PREFIX:-ds-dev}-infra-portainer
    restart: always
    security_opt:
      - no-new-privileges:true
    volumes:
      - /etc/localtime:/etc/localtime:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - portainer_data:/data
    ports:
      - "${PORTAINER_PORT:-9000}:9000"
    environment:
      TZ: ${TZ:-UTC}
    networks:
      - internal_network

  # ---------------------------------------------------------------------------
  # DATA ORCHESTRATION
  # ---------------------------------------------------------------------------
  dagster-webserver:
    build:
      context: ./services/dagster
      dockerfile: Dockerfile
    container_name: ${ENV_PREFIX:-ds-dev}-dagster-webserver
    restart: unless-stopped
    command: ["dagster-webserver", "-h", "0.0.0.0", "-p", "3000", "-w", "/opt/dagster/app/workspace.yaml"]
    ports:
      - "${DAGSTER_PORT:-3010}:3000"
    environment:
      - TZ=${TZ:-UTC}
      - DAGSTER_HOME=/opt/dagster/dagster_home
      - DAGSTER_POSTGRES_HOST=postgres
      - DAGSTER_POSTGRES_USER=${DAGSTER_DB_USER:-dagster}
      - DAGSTER_POSTGRES_PASSWORD=${DAGSTER_DB_PASSWORD:-dagster}
      - DAGSTER_POSTGRES_DB=${DAGSTER_DB_NAME:-dagster}
      - PRICE_SCRAPPER_ROOT=/workspace/services/price-scrapper
      - RETAIL_SIGNAL_ENGINE_ROOT=/workspace/services/retail-signal-engine
      - PRICE_SCRAPPER_DB_MODE=direct
      - RETAIL_SIGNAL_DB_MODE=direct
      - DB_HOST=postgres
      - DB_PORT=5432
      - DB_NAME=${DB_NAME}
      - DB_USER=${DB_USER}
      - DB_PASS=${DB_PASS}
      - MARKET_WATCH_API_URL=http://market-watch-api:8000
    volumes:
      - dagster_home:/opt/dagster/dagster_home
      - ./services/price-scrapper:/workspace/services/price-scrapper:ro
      - ./services/retail-signal-engine:/workspace/services/retail-signal-engine:ro
    depends_on:
      - postgres
      - market-watch-api
    networks:
      - internal_network

  dagster-daemon:
    build:
      context: ./services/dagster
      dockerfile: Dockerfile
    container_name: ${ENV_PREFIX:-ds-dev}-dagster-daemon
    restart: unless-stopped
    command: ["dagster-daemon", "run", "-w", "/opt/dagster/app/workspace.yaml"]
    environment:
      - TZ=${TZ:-UTC}
      - DAGSTER_HOME=/opt/dagster/dagster_home
      - DAGSTER_POSTGRES_HOST=postgres
      - DAGSTER_POSTGRES_USER=${DAGSTER_DB_USER:-dagster}
      - DAGSTER_POSTGRES_PASSWORD=${DAGSTER_DB_PASSWORD:-dagster}
      - DAGSTER_POSTGRES_DB=${DAGSTER_DB_NAME:-dagster}
      - PRICE_SCRAPPER_ROOT=/workspace/services/price-scrapper
      - RETAIL_SIGNAL_ENGINE_ROOT=/workspace/services/retail-signal-engine
      - PRICE_SCRAPPER_DB_MODE=direct
      - RETAIL_SIGNAL_DB_MODE=direct
      - DB_HOST=postgres
      - DB_PORT=5432
      - DB_NAME=${DB_NAME}
      - DB_USER=${DB_USER}
      - DB_PASS=${DB_PASS}
      - MARKET_WATCH_API_URL=http://market-watch-api:8000
    volumes:
      - dagster_home:/opt/dagster/dagster_home
      - ./services/price-scrapper:/workspace/services/price-scrapper:ro
      - ./services/retail-signal-engine:/workspace/services/retail-signal-engine:ro
    depends_on:
      - postgres
      - market-watch-api
    networks:
      - internal_network

  # ---------------------------------------------------------------------------
  # MARKET WATCH PRODUCT
  # ---------------------------------------------------------------------------
  market-watch-api:
    build:
      context: ./services/market-watch-api
      dockerfile: Dockerfile
    container_name: ${ENV_PREFIX:-ds-dev}-market-watch-api
    restart: unless-stopped
    ports:
      - "${MARKET_WATCH_API_PORT:-8100}:8000"
    environment:
      - TZ=${TZ:-UTC}
      - DATABASE_URL=${DATABASE_URL}
      - MARKET_WATCH_API_PREFIX=${MARKET_WATCH_API_PREFIX:-/api/v1}
      - MARKET_WATCH_API_TOKEN=${MARKET_WATCH_API_TOKEN:-}
      - MARKET_WATCH_DEMO_CLIENT_ID=${MARKET_WATCH_DEMO_CLIENT_ID:-}
      - MARKET_WATCH_DEMO_ROLE=${MARKET_WATCH_DEMO_ROLE:-system-admin}
      - MARKET_WATCH_ALLOWED_ORIGINS=${MARKET_WATCH_ALLOWED_ORIGINS:-http://localhost:8101,http://127.0.0.1:8101}
      - MARKET_WATCH_SUPERSET_BASE_URL=${MARKET_WATCH_SUPERSET_BASE_URL:-http://192.168.10.32:8088}
      - MARKET_WATCH_KEYCLOAK_ISSUER_URL=${MARKET_WATCH_KEYCLOAK_ISSUER_URL:-}
    depends_on:
      - postgres
    networks:
      - internal_network

  market-watch-web:
    build:
      context: ./services/web/market-watch
      dockerfile: Dockerfile
    container_name: ${ENV_PREFIX:-ds-dev}-market-watch-web
    restart: unless-stopped
    ports:
      - "${MARKET_WATCH_WEB_PORT:-8101}:3000"
    environment:
      - TZ=${TZ:-UTC}
      - MARKET_WATCH_API_BASE_URL=http://market-watch-api:8000/api/v1
      - MARKET_WATCH_PUBLIC_SUPERSET_URL=${MARKET_WATCH_SUPERSET_BASE_URL:-http://192.168.10.32:8088}
      - MARKET_WATCH_SECURE_COOKIES=${MARKET_WATCH_SECURE_COOKIES:-false}
    depends_on:
      - market-watch-api
    networks:
      - internal_network

  # ---------------------------------------------------------------------------
  # TEMPORARY ADMIN CONSOLE
  # ---------------------------------------------------------------------------
  admin-console-api:
    build:
      context: ./services/web/admin-console/backend
      dockerfile: Dockerfile
      args:
        INSTALL_DEV_DEPS: "true"
    container_name: ${ENV_PREFIX:-ds-dev}-web-admin-console-api
    restart: unless-stopped
    ports:
      - "${ADMIN_CONSOLE_API_PORT:-8084}:8000"
    environment:
      - TZ=${TZ:-UTC}
      - DB_HOST=postgres
      - DB_PORT=5432
      - DB_NAME=${DB_NAME}
      - DB_USER=${DB_USER}
      - DB_PASS=${DB_PASS}
      - DATABASE_URL=${DATABASE_URL}
      - ETL_SERVICE_URL=${ETL_SERVICE_URL:-}
      - GOOGLE_API_KEY=${GOOGLE_API_KEY:-}
    volumes:
      - ./schemas:/app/schemas:ro
    depends_on:
      - postgres
    networks:
      - internal_network

  admin-console-web:
    image: nginx:alpine
    container_name: ${ENV_PREFIX:-ds-dev}-web-admin-console-ui
    restart: unless-stopped
    ports:
      - "${ADMIN_CONSOLE_WEB_PORT:-8085}:80"
    volumes:
      - ./services/web/admin-console/frontend:/usr/share/nginx/html:ro
      - ./services/web/admin-console/frontend/nginx.conf.template:/etc/nginx/templates/default.conf.template:ro
    environment:
      - TZ=${TZ:-UTC}
      - API_HOST=admin-console-api
      - APP_VERSION=${APP_VERSION:-1}
    depends_on:
      - admin-console-api
    networks:
      - internal_network

networks:
  internal_network:
    driver: bridge

volumes:
```
### `.env.example`

```
# --- INFRASTRUCTURE ---
ENV_PREFIX=ds-dev
TZ=UTC

# DB credentials
DB_USER=postgres
DB_PASS=change-me
DB_NAME=supermarket
DB_PORT=5432

# Internal Docker connection string
DATABASE_URL=postgresql://${DB_USER}:${DB_PASS}@postgres:5432/${DB_NAME}

# --- SECURITY ---
SECRET_KEY=replace-with-long-random-secret
INTERNAL_API_TOKEN=replace-with-internal-service-token

# --- MARKET WATCH PRODUCT ---
MARKET_WATCH_API_PORT=8100
MARKET_WATCH_WEB_PORT=8101
MARKET_WATCH_API_PREFIX=/api/v1
MARKET_WATCH_API_TOKEN=
MARKET_WATCH_DEMO_CLIENT_ID=
MARKET_WATCH_DEMO_ROLE=system-admin
MARKET_WATCH_ALLOWED_ORIGINS=http://localhost:8101,http://127.0.0.1:8101
MARKET_WATCH_SECURE_COOKIES=false

# --- MARKET WATCH AUTH / KEYCLOAK (PLANNED) ---
MARKET_WATCH_KEYCLOAK_BASE_URL=http://192.168.10.37:8080
MARKET_WATCH_KEYCLOAK_REALM=market-watch
MARKET_WATCH_KEYCLOAK_CLIENT_ID=market-watch-web
MARKET_WATCH_KEYCLOAK_ISSUER_URL=${MARKET_WATCH_KEYCLOAK_BASE_URL}/realms/${MARKET_WATCH_KEYCLOAK_REALM}

# --- MARKET WATCH BI / SUPERSET (EXTERNAL VM) ---
# Superset is not deployed from this repo. These values are reserved for future
# signed embed/API integration through market-watch-api.
MARKET_WATCH_BI_PROVIDER=superset
MARKET_WATCH_SUPERSET_BASE_URL=http://192.168.10.32:8088
MARKET_WATCH_SUPERSET_API_URL=http://192.168.10.32:8088/api/v1
MARKET_WATCH_SUPERSET_EMBED_ALLOWED_ORIGIN=http://192.168.10.37:8101
MARKET_WATCH_SUPERSET_EMBED_ENABLED=false

# --- DATA ORCHESTRATION / DAGSTER ---
DAGSTER_PORT=3010
DAGSTER_DB_USER=dagster
DAGSTER_DB_PASSWORD=change-me
DAGSTER_DB_NAME=dagster

# --- TEMPORARY ADMIN CONSOLE ---
ADMIN_CONSOLE_API_PORT=8084
ADMIN_CONSOLE_WEB_PORT=8085
APP_VERSION=1
GOOGLE_API_KEY=replace-with-real-key
LLM_DEFAULT_MODEL=gemini-2.5-flash-lite
ETL_SERVICE_URL=

# --- OPERATIONS ---
PORTAINER_PORT=9000
```

## Topologia Market Watch

```text
services/price-scrapper
services/price-scrapper/commands
services/price-scrapper/docs
services/price-scrapper/docs/tables
services/price-scrapper/engines
services/price-scrapper/etl
services/price-scrapper/schemas
services/price-scrapper/seeds
services/price-scrapper/web
services/price-scrapper/web_backend
services/dagster
services/dagster/docs
services/dagster/src
services/dagster/src/market_watch_orchestration
services/dagster/src/market_watch_orchestration/price_scrapper
services/market-watch-api
services/market-watch-api/app
services/market-watch-api/app/api
services/market-watch-api/app/api/routes
services/market-watch-api/app/core
services/market-watch-api/app/domain
services/market-watch-api/app/repositories
services/web/market-watch
services/web/market-watch/app
services/web/market-watch/app/[group]
services/web/market-watch/app/[group]/[module]
services/web/market-watch/app/api
services/web/market-watch/app/api/auth
services/web/market-watch/app/api/filters
services/web/market-watch/app/api/settings
services/web/market-watch/app/api/table-views
services/web/market-watch/app/login
services/web/market-watch/app/pricing
services/web/market-watch/app/pricing/executive-signals
services/web/market-watch/app/pricing/intraday-radar
services/web/market-watch/app/pricing/products
services/web/market-watch/app/pricing/signals
services/web/market-watch/components
services/web/market-watch/components/market-watch
services/web/market-watch/components/portal
services/web/market-watch/components/ui
services/web/market-watch/lib
services/web/market-watch/public
```

## Archivos Market Watch

```text
services/price-scrapper/README.md
services/price-scrapper/borrar_populate_mkt_dim_product.py
services/price-scrapper/commands/extract_campaign_analytic_to_stage.py
services/price-scrapper/commands/extract_catalog_to_stage.py
services/price-scrapper/commands/extract_chain_catalog.py
services/price-scrapper/commands/extract_chain_locations.py
services/price-scrapper/commands/load_dim_listings.py
services/price-scrapper/commands/load_dim_products.py
services/price-scrapper/commands/load_fact_listing_snapshots.py
services/price-scrapper/commands/reset_catalog_stage.py
services/price-scrapper/commands/run_campaign_analytic_batch.py
services/price-scrapper/commands/serve_web.py
services/price-scrapper/commands/transform_stage_listing_snapshots.py
services/price-scrapper/commands/transform_stage_listings.py
services/price-scrapper/commands/transform_stage_products.py
services/price-scrapper/commands/update_chain_root_categories.py
services/price-scrapper/docs/tables/README.md
services/price-scrapper/docs/tables/mkt_campaign_location.md
services/price-scrapper/docs/tables/mkt_campaign_product.md
services/price-scrapper/docs/tables/mkt_dim_campaign.md
services/price-scrapper/docs/tables/mkt_dim_category.md
services/price-scrapper/docs/tables/mkt_dim_chain.md
services/price-scrapper/docs/tables/mkt_dim_client.md
services/price-scrapper/docs/tables/mkt_dim_date.md
services/price-scrapper/docs/tables/mkt_dim_listing.md
services/price-scrapper/docs/tables/mkt_dim_location.md
services/price-scrapper/docs/tables/mkt_dim_market_event_type.md
services/price-scrapper/docs/tables/mkt_dim_product.md
services/price-scrapper/docs/tables/mkt_fact_listing_snapshot.md
services/price-scrapper/docs/tables/mkt_run.md
services/price-scrapper/docs/tables/mkt_stage_catalog_item.md
services/price-scrapper/docs/tables/mkt_stage_listing_candidate.md
services/price-scrapper/docs/tables/mkt_stage_listing_review.md
services/price-scrapper/docs/tables/mkt_stage_listing_snapshot_candidate.md
services/price-scrapper/docs/tables/mkt_stage_listing_snapshot_review.md
services/price-scrapper/docs/tables/mkt_stage_product_candidate.md
services/price-scrapper/docs/tables/mkt_stage_product_review.md
services/price-scrapper/engines/instaleap_analytic_engine.py
services/price-scrapper/engines/instaleap_catalog_engine.py
services/price-scrapper/engines/instaleap_location_engine.py
services/price-scrapper/engines/vtex_analytic_engine.py
services/price-scrapper/engines/vtex_catalog_engine.py
services/price-scrapper/engines/vtex_location_engine.py
services/price-scrapper/etl/__init__.py
services/price-scrapper/etl/business_date.py
services/price-scrapper/etl/campaign_runtime_db.py
services/price-scrapper/etl/catalog_stage_loader.py
services/price-scrapper/etl/catalog_stage_reset.py
services/price-scrapper/etl/chain_runtime_db.py
services/price-scrapper/etl/http_client.py
services/price-scrapper/etl/normalize.py
services/price-scrapper/etl/postgres_cli.py
services/price-scrapper/etl/run_runtime_db.py
services/price-scrapper/etl/stage_listing_snapshot_transform.py
services/price-scrapper/etl/stage_listing_transform.py
services/price-scrapper/etl/stage_product_transform.py
services/price-scrapper/requirements.txt
services/price-scrapper/schemas/canonical_product_v1.schema.json
services/price-scrapper/seeds/2026-05-08_adjust_campaign_locations_sardimar_atun_competencia_cr_megasuper.sql
services/price-scrapper/seeds/2026-05-08_seed_campaign_locations_sardimar_atun_competencia_cr.sql
services/price-scrapper/seeds/2026-05-08_seed_campaign_sardimar_atun_competencia_cr.sql
services/price-scrapper/seeds/2026-05-22_create_mw_tool_agnostic_semantic_layer.sql
services/price-scrapper/seeds/2026-05-26_create_auth_security_baseline.sql
services/price-scrapper/seeds/2026-05-27_create_mkt_campaign_client_access.sql
services/price-scrapper/seeds/2026-05-31_create_mkt_dim_market_event_type.sql
services/price-scrapper/web/app.js
services/price-scrapper/web/catalog-data.js
services/price-scrapper/web/compare.html
services/price-scrapper/web/compare.js
services/price-scrapper/web/index.html
services/price-scrapper/web/styles.css
services/price-scrapper/web_backend/__init__.py
services/price-scrapper/web_backend/catalog_db.py
services/dagster/Dockerfile
services/dagster/README.md
services/dagster/dagster.yaml
services/dagster/docs/OPERATIONS.md
services/dagster/requirements.txt
services/dagster/src/market_watch_orchestration/__init__.py
services/dagster/src/market_watch_orchestration/definitions.py
services/dagster/src/market_watch_orchestration/resources.py
services/dagster/workspace.yaml
services/market-watch-api/Dockerfile
services/market-watch-api/README.md
services/market-watch-api/app/__init__.py
services/market-watch-api/app/api/__init__.py
services/market-watch-api/app/api/router.py
services/market-watch-api/app/core/__init__.py
services/market-watch-api/app/core/config.py
services/market-watch-api/app/core/db.py
services/market-watch-api/app/core/security.py
services/market-watch-api/app/domain/__init__.py
services/market-watch-api/app/domain/navigation.py
services/market-watch-api/app/domain/placeholders.py
services/market-watch-api/app/main.py
services/market-watch-api/app/repositories/__init__.py
services/market-watch-api/app/repositories/auth_repository.py
services/market-watch-api/app/repositories/market_repository.py
services/market-watch-api/main.py
services/market-watch-api/requirements.txt
services/web/market-watch/Dockerfile
services/web/market-watch/README.md
services/web/market-watch/app/globals.css
services/web/market-watch/app/layout.tsx
services/web/market-watch/app/login/page.tsx
services/web/market-watch/app/not-found.tsx
services/web/market-watch/app/page.tsx
services/web/market-watch/components/market-watch/chain-tag.tsx
services/web/market-watch/components/market-watch/crud-toolbar.tsx
services/web/market-watch/components/market-watch/data-grid.tsx
services/web/market-watch/components/market-watch/data-view-toolbar.tsx
services/web/market-watch/components/market-watch/executive-signals-page.tsx
services/web/market-watch/components/market-watch/filter-bar.tsx
services/web/market-watch/components/market-watch/intraday-product-grids.tsx
services/web/market-watch/components/market-watch/intraday-product-page.tsx
services/web/market-watch/components/market-watch/intraday-radar-filters-form.tsx
services/web/market-watch/components/market-watch/intraday-radar-grid.tsx
services/web/market-watch/components/market-watch/intraday-radar-page.tsx
services/web/market-watch/components/market-watch/kpi-card.tsx
services/web/market-watch/components/market-watch/product-history-chart.tsx
services/web/market-watch/components/market-watch/product-visual.tsx
services/web/market-watch/components/market-watch/row-actions.tsx
services/web/market-watch/components/market-watch/signal-detail-page.tsx
services/web/market-watch/components/market-watch/signal-filters-form.tsx
services/web/market-watch/components/market-watch/signal-grid.tsx
services/web/market-watch/components/market-watch/signal-kpi-cards.tsx
services/web/market-watch/components/market-watch/signal-severity-badge.tsx
services/web/market-watch/components/market-watch/signal-status-badge.tsx
services/web/market-watch/components/market-watch/sku-price-drivers-grid.tsx
services/web/market-watch/components/market-watch/store-evidence-grid.tsx
services/web/market-watch/components/portal/app-shell.tsx
services/web/market-watch/components/portal/focus-mode-toggle.tsx
services/web/market-watch/components/portal/module-view.tsx
services/web/market-watch/components/portal/role-simulator.tsx
services/web/market-watch/components/portal/shell-state.tsx
services/web/market-watch/components/portal/sidebar.tsx
services/web/market-watch/components/portal/topbar.tsx
services/web/market-watch/components/ui/alert.tsx
services/web/market-watch/components/ui/badge.tsx
services/web/market-watch/components/ui/button.tsx
services/web/market-watch/components/ui/card.tsx
services/web/market-watch/components/ui/empty-state.tsx
services/web/market-watch/components/ui/loading-state.tsx
services/web/market-watch/components/ui/modal.tsx
services/web/market-watch/components/ui/tabs.tsx
services/web/market-watch/components/ui/theme-toggle.tsx
services/web/market-watch/lib/api.ts
services/web/market-watch/lib/closed-day.ts
services/web/market-watch/lib/data-views.ts
services/web/market-watch/lib/event-presentation.ts
services/web/market-watch/lib/feedback.ts
services/web/market-watch/lib/modules.ts
services/web/market-watch/lib/pricing-types.ts
services/web/market-watch/lib/request-url.ts
services/web/market-watch/lib/types.ts
services/web/market-watch/lib/utils.ts
services/web/market-watch/next-env.d.ts
services/web/market-watch/next.config.mjs
services/web/market-watch/package-lock.json
services/web/market-watch/package.json
services/web/market-watch/postcss.config.mjs
services/web/market-watch/tailwind.config.ts
services/web/market-watch/tsconfig.json
```

## Extractos de Servicio

### `services/price-scrapper/README.md`

```
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

## Runtime de cadenas

La cadena, engine, scope y contexto operativo salen de `mkt_dim_chain`.

Las categorías raíz que entran al scrape salen de `mkt_dim_category`:

- `is_enabled = true`: entra al scrape por defecto
- `is_enabled = false`: no entra al scrape por defecto

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
- `client_id` opcional

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
```
### `services/price-scrapper/requirements.txt`

```
curl_cffi>=0.11.4,<1.0.0
```
### `services/dagster/README.md`

```
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
```
### `services/dagster/workspace.yaml`

```
load_from:
  - python_module: market_watch_orchestration.definitions

```
### `services/dagster/dagster.yaml`

```
storage:
  postgres:
    postgres_db:
      hostname:
        env: DAGSTER_POSTGRES_HOST
      username:
        env: DAGSTER_POSTGRES_USER
      password:
        env: DAGSTER_POSTGRES_PASSWORD
      db_name:
        env: DAGSTER_POSTGRES_DB
      port: 5432

run_launcher:
  module: dagster.core.launcher
  class: DefaultRunLauncher

schedules:
  use_threads: true
  num_workers: 2

sensors:
  use_threads: true
  num_workers: 2

telemetry:
  enabled: false

```
### `services/market-watch-api/README.md`

```
# Market Watch API

API de producto para Market Watch.

## Responsabilidad

- Resolver auth/multitenancy del producto cliente.
- Exponer endpoints por menu/modulo.
- Publicar datasets livianos para dashboards, tablas, pivots y reportes.
- Aplicar control de `client_id` antes de consultar o devolver datos.

## Fuera de alcance

- No ejecuta scraping.
- No ejecuta ETL pesado durante requests web.
- No importa modulos de `services/price-scrapper`.
- No reemplaza Superset para uso BI interno.

## Integracion futura con Superset

Superset vive fuera de este repo, en la VM BI. La API de producto no debe depender de Superset para servir datasets cliente.

Si mas adelante se habilitan embeds o enlaces internos:

- La API debe emitir tokens o URLs firmadas desde endpoints propios.
- El `client_id` debe resolverse desde auth del producto antes de solicitar cualquier recurso BI.
- No exponer credenciales de Superset al frontend.

## Contrato inicial

Base path: `/api/v1`

- `GET /api/v1/health`
- `GET /api/v1/menu`
- `GET /api/v1/datasets/overview`
- `GET /api/v1/datasets/products`
- `GET /api/v1/datasets/price-matrix`

Los endpoints de datasets requieren identidad de cliente resuelta. En el esqueleto inicial:

- Si `MARKET_WATCH_API_TOKEN` existe, se exige `Authorization: Bearer <token>`.
- `X-Client-Id` define el cliente para desarrollo o integraciones internas.
- Si falta `X-Client-Id`, puede usarse `MARKET_WATCH_DEMO_CLIENT_ID` solo para entornos no productivos.

Antes de produccion, `client_id` debe derivarse de sesion/JWT/API key, no de un header libre del navegador.
```
### `services/web/market-watch/README.md`

```
# Market Watch Portal

Portal administrativo y operativo del producto Market Watch.

## Responsabilidad

- Configurar y operar campañas, catálogos, productos monitoreados y competidores.
- Exponer navegación por rol para clientes y operadores internos.
- Enlazar o embeber Superset como portal analítico cuando se habilite.
- Consumir `services/market-watch-api`.

## Fuera de alcance

- No se conecta directo a Postgres.
- No ejecuta scraping ni ETL.
- No reutiliza `admin-console`.
- No reutiliza `chat-web-renderer`.
- No vive dentro de `services/price-scrapper/web`.

## Implementacion inicial

Next.js App Router + TypeScript + Tailwind con componentes estilo shadcn/ui.

La autenticacion real con Keycloak queda preparada, pero en esta iteracion el rol se simula con query string:

```text
/?role=system-admin
/?role=client-admin
/?role=client-viewer
/?role=system-user
```

## Servicios externos previstos

- Keycloak: identidad, login, roles y grupos.
- Superset: dashboards y reportes analiticos.
- Dagster: orquestacion ETL.
```
### `services/web/market-watch/package.json`

```
{
  "name": "market-watch-portal",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev --hostname 0.0.0.0 --port 3000",
    "build": "next build",
    "start": "next start --hostname 0.0.0.0 --port 3000",
    "lint": "next lint"
  },
  "dependencies": {
    "@radix-ui/react-slot": "1.1.0",
    "class-variance-authority": "0.7.1",
    "clsx": "2.1.1",
    "lucide-react": "0.468.0",
    "next": "16.2.6",
    "react": "19.2.4",
    "react-dom": "19.2.4",
    "recharts": "^3.8.1",
    "tailwind-merge": "2.5.5"
  },
  "devDependencies": {
    "@types/node": "20.17.12",
    "@types/react": "19.2.8",
    "@types/react-dom": "19.2.3",
    "autoprefixer": "10.4.20",
    "eslint": "9.39.2",
    "eslint-config-next": "16.2.6",
    "postcss": "8.5.10",
    "tailwindcss": "3.4.17",
    "typescript": "5.7.2"
  },
  "overrides": {
    "postcss": "8.5.10"
  }
}
```
