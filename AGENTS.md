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
