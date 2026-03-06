# SQL Planner (Realtor Chat)

## Objetivo
Resolver consultas de inventario inmobiliario con SQL controlado en tiempo real, sin depender de reglas dispersas en `main.py`.

## Ubicacion
- `services/web/realtor-chat/backend/app/planner/sql_planner.py`
- `services/web/realtor-chat/backend/app/planner/models.py`

## Flujo runtime
1. `POST /chat` recibe mensaje usuario.
2. `InferenceClient` genera respuesta conversacional base.
3. Si el vertical es `realtor` y no hubo `sources`, el bridge llama `SQLPlanner`.
4. `SQLPlanner.plan(...)` decide intent estructurado:
   - `property_inventory`
   - `property_search`
   - `property_price_range`
   - `none`
5. `SQLPlanner.execute(...)` usa `SDUITransformer` + `DatabaseManager` para ejecutar SQL seguro tenant-scoped.
6. El planner puede devolver:
   - `answer_override` (texto final basado en SQL real)
   - `components` (`property-card`)
   - `session_updates` (contexto para follow-ups)

## Contexto conversacional
Se persiste en session Redis la clave:
- `planner_last_property_query`

Esto permite resolver follow-ups como:
- Usuario: "tienes casas en heredia?"
- Usuario: "cual es el rango de precios de ellas?"

## SQL soportado (v1)
- Conteo de inventario (`COUNT(*)`).
- Búsqueda de propiedades con filtros (`SELECT ... LIMIT N`).
- Rango de precios (`MIN(price), MAX(price)`).

## Filtros soportados (v1)
- Ubicación textual (en `title`, `features->>'address'`, `features::text`).
- Rango de precio (`min_price`, `max_price`).
- Habitaciones y baños (`features->>'bedrooms[_clean]'`, `features->>'bathrooms[_clean]'`).

## Guardrails
- Scope obligatorio por `client_id`.
- Solo lecturas (`SELECT`) en tablas allowlisted del bridge.
- Sin SQL libre generado por LLM.

## Evolucion a planner LLM (siguiente paso)
Este planner v1 es estructural y determinista. Para evolucionar sin riesgo:
1. Añadir etapa LLM que produzca JSON validado (`intent + filters`), no SQL raw.
2. Mantener compilador SQL server-side con allowlist/tenant scope.
3. Reusar `SQLPlanner.execute(...)` como backend de ejecución.
