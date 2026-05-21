# RULES

## 1. Fuente de Verdad de Contexto

Precondicion obligatoria al iniciar cada nueva sesion:

1. Carga base obligatoria:
   - Leer `.agent/RULES.md`
   - Leer `.agent/PY_EXECUTION_MAP.md`
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
4. `.agent/BRAIN_MAP.md`
5. `.agent/AI_CONTEXT_PACK.md`

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

1. aplicar la seccion 1
2. usar `.agent/RULES.md` + `.agent/PY_EXECUTION_MAP.md` como base
3. consultar `BRAIN_MAP` y `AI_CONTEXT_PACK` solo lo necesario
4. limitar exploracion inicial a `services/price-scrapper`, `services/web/market-watch`, `services/market-watch-api` si existe, `docker-compose*.yml` y `.env.example`, salvo que el usuario pida mas

Si aparece una instruccion heredada del stack conversacional anterior, tratarla como legacy y no aplicarla al producto Market Watch salvo pedido explicito del usuario.
