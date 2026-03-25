# PY Execution Map (Host vs Container)

## Objetivo

Este archivo define, por ruta del repo, donde ejecutar comandos Python y que rebuilds son obligatorios.

Reglas base:

1. Si el codigo vive en un servicio Docker activo, ejecutar Python en su contenedor.
2. Si el codigo vive en `tests/` de raiz, ejecutar en host o en el contenedor indicado por la prueba.
3. Si el servicio no monta el codigo fuente completo, hacer `docker compose up -d --build ...` antes de validar.
4. No correr `pytest` en host salvo instruccion explicita del usuario.

## Decision Rapida

1. Identifica la ruta del archivo que tocaste.
2. Busca el prefijo en la tabla.
3. Ejecuta el comando base en el entorno indicado.

## Mapa por Rutas

| Prefijo de ruta | Ejecutar `py` en | Paso previo obligatorio | Comando base |
|---|---|---|---|
| `services/ai_runtime/` | `ai-runtime` | Rebuild si cambiaste codigo: `docker compose up -d --build ai-runtime` | `docker compose exec -T ai-runtime /bin/bash -lc "cd /app/services/ai_runtime && find . -type f -name '*.py' -print0 | xargs -0 python -m py_compile"` |
| `services/data/` | `ai-runtime` | Rebuild de `ai-runtime` porque el codigo se copia dentro de la imagen del runtime: `docker compose up -d --build ai-runtime` | `docker compose exec -T ai-runtime /bin/bash -lc "cd /app && find services/ai_runtime services/data -type f -name '*.py' -print0 | xargs -0 python -m py_compile"` |
| `services/bridges/generic-bridge/` | `generic-bridge` | Rebuild si cambiaste codigo: `docker compose up -d --build generic-bridge` | `docker compose exec -T generic-bridge python -m py_compile main.py` |
| `services/bridges/property-bridge/` | `property-bridge` | Rebuild si cambiaste codigo: `docker compose up -d --build property-bridge` | `docker compose exec -T property-bridge python -m py_compile main.py` |
| `services/scoring-core/` | `scoring-core` o `scoring-core-worker` | Rebuild de ambos si cambiaste codigo: `docker compose up -d --build scoring-core scoring-core-worker` | `docker compose exec -T scoring-core /bin/bash -lc "find . -type f -name '*.py' -print0 | xargs -0 python -m py_compile"` |
| `services/web/admin-console/backend/` | `admin-console-api` | Rebuild si cambiaste codigo: `docker compose up -d --build admin-console-api` | `docker compose exec -T admin-console-api pytest -q tests` |
| `services/web/chat-web-renderer/backend/` | `chat-web-renderer-api` | Rebuild si cambiaste codigo: `docker compose up -d --build chat-web-renderer-api` | `docker compose exec -T chat-web-renderer-api pytest -q tests` |
| `services/etl-docs/` | `etl-docs` o `etl-docs-worker` | Rebuild de ambos si cambiaste codigo: `docker compose up -d --build etl-docs etl-docs-worker` | `docker compose exec -T etl-docs pytest -q tests` |
| `services/web/*/frontend/` | No aplica Python | No aplica | Validar con navegador, `curl` o smoke HTTP |
| `schemas/` | Contenedores consumidores | Reiniciar consumidores tras cambio de contrato | `docker compose restart ai-runtime scoring-core scoring-core-worker admin-console-api chat-web-renderer-api etl-docs etl-docs-worker` |
| `migrations/` | `postgres` | Cargar variables primero | `docker compose exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -f /ruta/al.sql` |
| `tests/sandbox/realtor/` y `tests/sandbox/dentist/` | Host (`/srv/datasyncsa`) | Stack levantado | `python3 tests/sandbox/realtor/simulate_chat_realtor.py` |
| `tests/system/` y `tests/smoke-stack/` | Host o runner dedicado | Stack levantado y endpoints accesibles | `pytest -q tests/system` |
| `services/agent-core/` | No usar por defecto | Solo lectura salvo instruccion explicita | `N/A` |
| `services/inference-stack-v2/` | No usar por defecto | Solo lectura salvo instruccion explicita | `N/A` |
| `services/ai-agents/` | Host, solo exploracion | No es parte del compose activo | `python3 -m py_compile ...` si el usuario lo pide |

## Nota Critica de Montajes

En el compose actual, la mayoria de backends no montan el codigo fuente completo de `services/...` dentro del contenedor; copian el codigo en build y solo montan `schemas` y/o `log`.

Implicaciones:

- cambio en `services/...` => requiere rebuild/recreate del servicio para reflejarse
- cambio en `schemas/...` => el archivo entra por volumen, pero normalmente requiere restart del proceso Python

## Variables Clave

- DB: `DB_USER`, `DB_PASS`, `DB_NAME`, `DB_PORT`, `DATABASE_URL`
- Seguridad interna: `INTERNAL_API_TOKEN`
- Runtime conversacional: `AI_RUNTIME_API`, `AI_RUNTIME_API_PREFIX`, `AI_RUNTIME_RESET_URL`, `AI_RUNTIME_PORT`
- Scoring: `SCORING_CORE_API`, `SCORING_CORE_RESET_URL`, `SCORING_CORE_PORT`
- Storage ETL: `HOST_PATH_STAGING`, `HOST_PATH_STORAGE`
- Admin Console: `ETL_SERVICE_URL`

Referencia contractual: `.env.example`

## Checklist Operativo Minimo

1. Confirmar ruta del cambio.
2. Ejecutar en el entorno correcto.
3. Hacer rebuild si aplica.
4. Correr la validacion minima del servicio afectado.
5. Si no se valido, documentarlo explicitamente.
