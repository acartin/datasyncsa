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
