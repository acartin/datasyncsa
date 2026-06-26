# Resumen de Sesión — Integración BrightData + Rate Limiter

## Objetivo
Integrar proxy residencial BrightData y rate limiter (5 req/s por dominio) en el scraping de Market Watch, de forma que todas las engines lo hereden automáticamente sin cambios en su código interno.

---

## Archivos Creados

### `services/proxy-residencial/brightdata.py`
Config builder para BrightData. `config_from_env()` construye un `BrightDataConfig` desde variables de entorno (`BRIGHTDATA_CUSTOMER_ID`, `BRIGHTDATA_ZONE`, `BRIGHTDATA_ZONE_PASSWORD`, `BRIGHTDATA_COUNTRY`). Incluye `as_proxies_dict()` y `as_curl_cffi_kwargs()` para integración con `curl_cffi`.

### `services/proxy-residencial/rate_limiter.py`
TokenBucket thread-safe (referencia independiente). No se usa desde el runtime — el canónico vive en `http_client.py`.

### `services/proxy-residencial/__init__.py`
Expone solo `BrightDataConfig` y `config_from_env`. Se eliminó `TokenBucket` del `__all__` porque la implementación canónica está en `http_client.py`.

### `services/proxy-residencial/test_rate.py`
Prueba de concurrencia multi-dominio que verifica proxy + rate limiter funcionando juntos.

### `services/proxy-residencial/test_brd.py`
Prueba básica de conexión BrightData (referencia).

### `services/proxy-residencial/simulate.py`
Script de simulación para probar el pipeline proxy + rate (referencia).

### `services/proxy-residencial/requirements.txt`
Dependencias: `curl_cffi`.

### `services/price-scrapper/commands/scrape_all_catalogs.py`
Orquestador concurrente de scraping de catálogos. Lanza un thread por cadena activa, configura rate limiter por dominio, usa proxy BrightData auto-detectado. Soporta `--max-chains`, `--max-categories`, `--max-pages-per-category`, `--dry-run`, `--rate`.

---

## Archivos Modificados

### `services/price-scrapper/etl/http_client.py`
**Archivo central del cambio.** Se le añadió:

- `TokenBucket` class — token bucket thread-safe con `wait()` bloqueante.
- `_RATE_LIMITERS: dict[str, TokenBucket]` — registro global por dominio.
- `set_rate_limiter(domain, rate)` — configura rate limiter para un dominio.
- `_acquire_rate_token(url)` — adquiere token antes de cada request, auto-detecta dominio desde la URL.
- `_build_proxies_from_env()` — construye proxy BrightData desde `.env`. Si faltan vars, retorna `None` (sin proxy).
- `create_browser_session(proxies=None, ...)` — si `proxies` es `None`, auto-detecta proxy desde `.env`. Esto es clave: ninguna engine pasa `proxies` explícitamente, así que el proxy se activa automáticamente cuando las variables `BRIGHTDATA_*` existen.
- `request_with_retry(url, ...)` — ahora llama `_acquire_rate_token(url)` antes de cada intento.

**No se modificó la firma de `create_browser_session` ni `request_with_retry`** — 100% backward compatible.

### `services/price-scrapper/engines/*.py` (6 archivos)
Cada uno recibió dos cambios mínimos:
1. Import de `set_rate_limiter` desde `etl.http_client`
2. Llamada a `set_rate_limiter(domain)` en `_build_session()`, donde `domain` se extrae de `base_url` o `graphql_v2_endpoint`

Archivos:
- `vtex_analytic_engine.py` — `set_rate_limiter` en `_build_session` (dominio desde `chain.base_url`)
- `instaleap_analytic_engine.py` — idem
- `vtex_catalog_engine.py` — idem (dominio desde `config.base_url`)
- `instaleap_catalog_engine.py` — idem (dominio desde `config.base_url`)
- `vtex_location_engine.py` — idem
- `instaleap_location_engine.py` — idem (dominio desde `config.graphql_v2_endpoint`)

**No se modificó la lógica de negocio de ninguna engine.**

### `services/dagster/src/market_watch_orchestration/price_scrapper/repository.py`
Se modificó y luego se revirtió la SQL de `discover_active_campaign_extract_groups`. **Estado final: SIN CAMBIOS** respecto al original (agrupa chains por engine con `string_agg`).

### `services/dagster/src/market_watch_orchestration/definitions.py`
Se modificó y luego se revirtió el `mapping_key` de `DynamicOutput`. **Estado final: SIN CAMBIOS** respecto al original.

### `.env.example`
Se añadió el bloque `BRIGHTDATA_*` (líneas 71-75) con valores de ejemplo.

---

## Comportamiento Resultante

### Proxy BrightData
- Se activa automáticamente cuando `BRIGHTDATA_CUSTOMER_ID`, `BRIGHTDATA_ZONE` y `BRIGHTDATA_ZONE_PASSWORD` están en el entorno.
- Cualquier engine que llame `create_browser_session(headers=...)` sin `proxies` obtiene el proxy.
- Si faltan vars, no hay proxy (comportamiento legacy).

### Rate Limiter (5 req/s por dominio)
- Se activa cuando la engine llama `set_rate_limiter(domain)` en su `_build_session()`.
- `request_with_retry()` bloquea hasta tener token antes de cada request.
- Dominios diferentes tienen buckets independientes (ej: `www.masxmenos.cr` no comparte con `www.walmart.co.cr`).
- Las chains Instaleap comparten dominio `nextgentheadless.instaleap.io`.

### Flujo Dagster (sin cambios)
```
daily_active_campaigns_analytic_job
  → discover_active_campaign_extract_groups (2 grupos: VTEX + Instaleap)
  → extract_campaign_analytic_group × 2 (subprocess)
      → extract_campaign_analytic_to_stage.py
        → engines (build_session → set_rate_limiter + proxy auto)
        → request_with_retry (rate limit + proxy activos)
  → transform + load (sin cambios, no usan HTTP)
```

---

## Problemas Encontrados y Resueltos

1. **DynamicOutput mapping_key duplicado** al desagrupar chains: al cambiar la SQL para retornar un grupo por chain, 3 grupos VTEX tenían el mismo `mapping_key` (`campaign_1_vtex`) porque el key se derivaba solo de `campaign_id + engine`. Solución: revertir el agrupado original (por engine con `string_agg`). No es necesario desagrupar porque el executor de Dagster corre los dynamic ops secuencialmente de todas formas.

2. **Código Dagster no se refleja sin rebuild**: `services/dagster/src/` se copia en la imagen Docker (`COPY src /opt/dagster/app/src`), no se monta por volumen. Cada cambio requiere `docker compose up -d --build dagster-webserver dagster-daemon`.

3. **Rate limiter sin interfaz en engines**: se resolvió inyectando `set_rate_limiter` dentro de `_build_session()` de cada engine, que es el hook natural de inicialización.

---

## Pendientes / No Resuelto

- Las 4 chains activas (masxmenos_cr, maxi_pali_cr, walmart_cr, megasuper_cr) corren secuencialmente dentro de cada grupo VTEX/Instaleap en Dagster. No hay paralelismo real entre chains del mismo engine. Si se requiere paralelismo, habría que inyectar un executor configurable en Dagster.
- `scrape_all_catalogs.py` (orquestador concurrente CLI) no está integrado en Dagster — es una herramienta standalone para pruebas manuales.
- No se implementó un mecanismo de failover si BrightData falla (caer a conexión directa).
- Las engines aún tienen parámetros `sleep_min`/`sleep_max` y métodos `_sleep_if_needed()` que ahora son redundantes con el behavioral delay centralizado. Limpiarlos es opcional pero recomendado.

---

## Behavioral Simulation (Añadido en esta sesión)

### `services/price-scrapper/etl/http_client.py` — 3 nuevas funciones

**`configure_behavioral()`** — Ajusta los parámetros de simulación humana:
- `jitter_min`/`jitter_max`: rango de delay aleatorio pre-request (default 1.0-3.0s)
- `break_interval`: cada N requests se toma una pausa larga (default 100)
- `break_min`/`break_max`: duración de la pausa larga (default 30-60s)
- `rotate_headers`: activa/desactiva rotación de User-Agent y Accept-Language
- `enabled`: activa/desactiva toda la simulación conductual

**`_rotate_session_headers(session)`** — Rotación de headers por request:
- `User-Agent`: elige aleatoriamente entre Chrome 132-136
- `Accept-Language`: elige aleatoriamente entre 5 variantes de español (CR, 419, general)

**`_behavioral_delay()`** — Jitter pre-request: `random.uniform(1.0, 3.0)` antes de cada request.

**`_structural_break()`** — Pausa de "lectura humana" cada 100 requests: 30-60s.

### Integración en `request_with_retry()`
Las 3 funciones se ejecutan al inicio de cada llamada, en orden:
1. `_rotate_session_headers(session)` — headers actualizados
2. `_behavioral_delay()` — jitter
3. `_structural_break()` — break si corresponde
4. `_acquire_rate_token(url)` — rate limiter (existente)

No se modificó la firma de `request_with_retry()` — ningún caller existente requiere cambios.

### curl_cffi TLS Impersonation
Ya está activo desde `create_browser_session()` vía `requests.Session(impersonate="chrome136")`. El TLS fingerprinting se maneja a nivel de conexión por curl_cffi, independiente de la rotación de headers HTTP.

---

## Cadenas Activas (Jun 2026)

| chain_id | engine | dominio | rate limiter |
|---|---|---|---|
| masxmenos_cr | vtex | www.masxmenos.cr | 5 req/s |
| maxi_pali_cr | vtex | www.maxipali.co.cr | 5 req/s |
| walmart_cr | vtex | www.walmart.co.cr | 5 req/s |
| megasuper_cr | instaleap | nextgentheadless.instaleap.io | 5 req/s |

---

## Cómo Validar

```bash
# 1. Compilación de todos los archivos
find services/price-scrapper services/proxy-residencial -name '*.py' -not -path '*__pycache__*' -exec python3 -m py_compile {} \;

# 2. Prueba de integración proxy + rate
python3 services/proxy-residencial/test_rate.py

# 3. Verificar discover groups en Dagster
docker compose exec dagster-webserver python3 -c "
from market_watch_orchestration.price_scrapper.repository import MarketWatchRepository
from market_watch_orchestration.price_scrapper.postgres_runner import PostgresRunner
repo = MarketWatchRepository(postgres=PostgresRunner())
for g in repo.discover_active_campaign_extract_groups():
    print(g)
"

# 4. Dry-run del orquestador concurrente
set -a; source .env; set +a
python3 services/price-scrapper/commands/scrape_all_catalogs.py --dry-run
```
