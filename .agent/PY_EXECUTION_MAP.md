# PY Execution Map (Host vs Container)

## Objetivo
Este archivo define, por ruta del repo, **donde ejecutar comandos Python** y que pasos previos son obligatorios.

Regla general:
1. Si el codigo vive en un servicio Docker, ejecutar Python en su contenedor.
2. Si es un script de soporte en `tests/` raiz, ejecutar en host (o en el contenedor indicado por el propio script).
3. Si hay cambio de codigo en un servicio sin volumen de codigo montado, hacer `docker compose up -d --build ...` antes de probar.

## Decision Rapida (20 segundos)
1. Mira la ruta del archivo que tocaste.
2. Busca el prefijo en la tabla de abajo.
3. Ejecuta el comando recomendado (host o contenedor).

## Mapa Por Rutas

| Prefijo de ruta | Ejecutar `py` en | Paso previo obligatorio | Comando base |
|---|---|---|---|
| `services/inference-stack-v2/inference-core-v2/` | `inference-core-v2` o `inference-core-v2-worker` | **Siempre rebuild de ambos** si hubo cambios de codigo: `docker compose up -d --build inference-core-v2 inference-core-v2-worker` | API/test: `docker compose exec -T inference-core-v2 env PYTHONPATH=/app pytest -q tests` / Worker check: `docker compose exec -T inference-core-v2-worker /bin/bash -lc "grep -n 'deterministic_scoring_service' app/services/scoring_engine.py"` |
| `services/inference-stack-v2/semantic-adapter-v2/` | `semantic-adapter-v2` | Rebuild si cambiaste codigo: `docker compose up -d --build semantic-adapter-v2` | `docker compose exec -T semantic-adapter-v2 pytest -q tests` |
| `services/etl-docs/` | `etl-docs` (API) o `etl-docs-worker` (colas) | Rebuild si cambiaste codigo: `docker compose up -d --build etl-docs etl-docs-worker` | `docker compose exec -T etl-docs pytest -q tests` |
| `services/web/admin-console/backend/` | `admin-console-api` | Rebuild si cambiaste codigo: `docker compose up -d --build admin-console-api` | `docker compose exec -T admin-console-api pytest -q tests` |
| `services/web/realtor-chat/backend/` | `realtor-api` | Rebuild si cambiaste codigo: `docker compose up -d --build realtor-api` | `docker compose exec -T realtor-api pytest -q tests` |
| `services/generic-bridge-v2/` | `generic-bridge-v2` | Rebuild si cambiaste codigo: `docker compose up -d --build generic-bridge-v2` | `docker compose exec -T generic-bridge-v2 python -V` (y/o pytest si el servicio incorpora tests) |
| `services/realtor-bridge-v2/` | `realtor-bridge-v2` | Rebuild si cambiaste codigo: `docker compose up -d --build realtor-bridge-v2` | `docker compose exec -T realtor-bridge-v2 python -V` (y/o pytest si el servicio incorpora tests) |
| `services/web/*/frontend/` | No aplica Python (Nginx estatico) | No aplica | Validar con navegador/curl |
| `schemas/` | Contenedores que consumen `schemas` | Reiniciar servicios consumidores tras cambio de contrato | `docker compose restart inference-core-v2 inference-core-v2-worker semantic-adapter-v2 admin-console-api realtor-api etl-docs etl-docs-worker` |
| `migrations/` | No aplica Python directo | Aplicar SQL en `postgres` | `docker compose exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -f /ruta/al.sql` |
| `tests/sandbox/realtor/` y `tests/sandbox/dentist/` | Host (`/srv/datasyncsa`) | Stack levantado | `python3 tests/sandbox/realtor/simulate_chat_realtor.py` |
| `tests/sandbox/*.py` (wrappers legacy) | Host (`/srv/datasyncsa`) | Stack levantado | `python3 tests/sandbox/simulate_chat_realtor.py` |
| `tests/system/` y `tests/smoke-stack/` (raiz) | Host o runner dedicado | Stack levantado y endpoints accesibles | `pytest -q tests/system` |

## Nota Critica de Montajes (evita confusiones)
En este compose, la mayoria de backends **no montan el codigo fuente de `services/...` en `/app`**; montan principalmente `./schemas:/app/schemas:ro`.

Implicacion:
- Cambio de codigo en `services/...` => no se refleja en runtime hasta rebuild/recreate del servicio.
- Cambio en `schemas/...` => el archivo existe en contenedor por volumen, pero normalmente requiere `restart` para que el proceso Python recargue imports.

## Claves/Variables que gobiernan ejecucion (sin secretos)
- DB: `DB_USER`, `DB_PASS`, `DB_NAME`, `DB_PORT`, `DATABASE_URL`
- Seguridad interna: `INTERNAL_API_TOKEN`
- IA: `GOOGLE_API_KEY`, `LLM_MODEL`, `EMBEDDING_MODEL`
- Rutas storage ETL: `HOST_PATH_STAGING`, `HOST_PATH_STORAGE`
- URL externa obligatoria admin-console: `ETL_SERVICE_URL`

Referencia contractual de variables: `.env.example`.

## Checklist Operativo Minimo
1. Confirmar ruta del cambio.
2. Ejecutar en el entorno correcto (host/servicio).
3. Si aplica, rebuild obligatorio.
4. Correr pruebas minimas del servicio afectado.
5. Si no se probaron, documentar que no se valido y por que.
