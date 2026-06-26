# Motores de Scraping — Documentacion

## Arquitectura General

7 motores en `services/price-scrapper/engines/`, sin `__init__.py` (import directo por nombre desde `commands/`).

Cada motor sigue el patron:
1. `_build_session()` → configura rate limiter + sesion HTTP
2. Metodo `collect_*()` / `run()` → logica de negocio
3. `write_outputs()` → persiste a `catalog.json` + `metadata.json`

Todas heredan automaticamente proxy BrightData, rate limiter (5 req/s por dominio), jitter (1-3s pre-request), breaks (30-60s cada 100 reqs) y rotacion de headers via `etl/http_client.py`.

---

## 1. `vtex_catalog_engine.py` — Catalogo VTEX

**Provider:** VTEX Search GraphQL API
**Endpoint:** `{base_url}/_v/segment/graphql/v1`
**Category tree:** `{base_url}/api/catalog_system/pub/category/tree/{depth}`
**CLI:** `extract_chain_catalog.py` / `scrape_all_catalogs.py`

Clase `VTEXCatalogScraper`:
- Recorre arbol de categorias via API REST
- Planifica categorias con overflow (>500 prod) en subcategorias hijas
- Pagina via `productSearchV3` persisted query
- `_build_session()`: `set_rate_limiter(domain)` + `create_browser_session(...)` + cookie `vtex_segment` (para sales_channel)
- Output: `canonical_product_v1` con pricing, mediciones, atributos

Config `VTEXStoreConfig`:
- `base_url`, `display_name`, `pricing_scope`, `sales_channel`, `region_id`, `pricing_context`

---

## 2. `vtex_analytic_engine.py` — Analitico VTEX

**Provider:** VTEX per-product API
**Endpoint:** `{base_url}/api/catalog_system/pub/products/search`
**Fallback:** PDP HTML → `application/ld+json`
**CLI:** `extract_campaign_analytic_to_stage.py`

Clase `VtexAnalyticScraper`:
- Recorre targets (producto x tienda) uno por uno
- Fuente primaria: `GET .../products/search?fq=skuId:X&sc=Y`
- Fallback: pagina HTML del producto → JSON-LD
- `_build_session()`: `set_rate_limiter(domain)` + `create_browser_session(...)` + cookie `vtex_segment`
- Maneja `DomainCircuitOpen` explicitamente

Config `VtexAnalyticChainConfig` + `VtexAnalyticLocation`:
- `base_url`, `sales_channel`, `region_id` por tienda

---

## 3. `vtex_location_engine.py` — Ubicaciones VTEX

**Provider:** VTEX store-selector bundle
**Endpoint:** `{base_url}/` → JS bundle → `/api/checkout/pub/regions`
**CLI:** `extract_chain_locations.py`

Clase `VtexLocationScraper`:
- Descarga homepage → extrae bundle `store-selector@...` JS
- Extrae codigos postales del bundle
- Consulta `/api/checkout/pub/regions?country=CRI&sc=...&postalCode=...`
- Clasifica tipo: BODEGA / STORE / physical_store
- `_build_session()`: `set_rate_limiter(domain)` + `create_browser_session(...)`

Config `VtexLocationChainConfig`:
- `base_url`, `sales_channel`

---

## 4. `algolia_catalog_engine.py` — Catalogo Algolia

**Provider:** Algolia REST API (search-only, publica)
**Endpoint:** `https://{app_id}-dsn.algolia.net/1/indexes/{index}/query`
**CLI:** `extract_chain_catalog.py` / `scrape_all_catalogs.py`

Clase `AlgoliaCatalogScraper`:
- **No usa `create_browser_session`**: usa `requests.Session()` plano (Algolia publica no requiere proxy ni impersonacion)
- `_build_session()`: `set_rate_limiter(domain)` (sobre `base_url` del comercio, NO algolia.net) + headers `X-Algolia-API-Key` + `X-Algolia-Application-Id`
- Dos modos de recoleccion:
  - `--max-pages N`: paginacion simple (max 1000 prod, Algolia limita a 1000 hits/query)
  - Sin `--max-pages`: catalogo completo via split por categorias (consulta facets `categoryPageId`, agrupa roots ≤1000 y level-1 subs para roots >1000)
- `canonical_product_record()`: mapea `objectID`, `productNumber`, `hierarchicalCategories.lvl2` (category_path), `storeDetail.{id}.amount` (pricing por tienda)
- `_fetch_categories()`: obtiene facetas para planificar queries
- `_fetch_category_page()`: consulta con `facetFilters=["categoryPageId:CATEGORIA"]`

Config `AlgoliaConfig`:
- `algolia_app_id`, `algolia_api_key`, `algolia_index` (desde `engine_extras` en BD)
- `base_url`, `pricing_scope`

**Algolia API details (Automercado):**
- app_id: `FU5XFX7KNL`, api_key: `335287091ff4a66858e0ad021ca45b76` (search-only publica)
- index: `Product_CatalogueV2`, ~19,235 productos
- Max 1000 hits/query (incluso con paginacion)
- Precios por tienda en `storeDetail.{id}.amount`
- `hierarchicalCategories.lvl0/lvl1/lvl2` para taxonomia limpia
- `categoryPageId` array con niveles jerarquicos (root, level-1, level-2)

---

## 5. `instaleap_catalog_engine.py` — Catalogo Instaleap

**Provider:** Instaleap GraphQL
**Endpoint:** `{graphql_endpoint}` (default: `https://nextgentheadless.instaleap.io/api/v3`)
**CLI:** `extract_chain_catalog.py` / `scrape_all_catalogs.py`

Clase `InstaleapCatalogScraper`:
- Query `getProductsByCategory` con variables en params
- Recorre root categories → pagina por categoria
- `_build_session()`: `set_rate_limiter(domain)` (sobre graphql_endpoint host) + `create_browser_session(...)` con Origin/Referer

Config `InstaleapStoreConfig`:
- `client_id`, `store_reference`, `graphql_endpoint`, `currency`, `locale`, `store_internal_id`

---

## 6. `instaleap_analytic_engine.py` — Analitico Instaleap

**Provider:** Instaleap GraphQL
**Endpoint:** `{graphql_endpoint}`
**CLI:** `extract_campaign_analytic_to_stage.py`

Clase `InstaleapAnalyticScraper`:
- Query `getProductsBySKU` con lista de SKUs (batch)
- `_build_session()`: `set_rate_limiter(domain)` + `create_browser_session(...)`

Config `InstaleapAnalyticChainConfig` + `InstaleapAnalyticLocation`:
- `client_id`, `graphql_endpoint`, `store_reference` por tienda

---

## 7. `instaleap_location_engine.py` — Ubicaciones Instaleap

**Provider:** HTML + KML + Instaleap GraphQL
**Sources:** HTML sucursales → Google Maps KML → GraphQL `getStoresNearbyByCoords`
**CLI:** `extract_chain_locations.py`

Clase `InstaleapLocationScraper`:
- Pipeline: HTML → parse entries → KML → placemarks → GraphQL → enrich
- `SucursalesHtmlParser`: HTMLParser custom para extraer sucursales
- `_build_session()`: `set_rate_limiter(domain)` (sobre graphql_v2_endpoint host) + `create_browser_session(...)`

Config `InstaleapLocationChainConfig`:
- `client_id`, `graphql_v2_endpoint`, `default_store_reference`, `default_store_internal_id`

---

## Tabla Resumen

| Archivo | Provider | Tipo | `create_browser_session`? | Dominio rate-limit | CLI |
|---------|----------|------|--------------------------|-------------------|-----|
| `vtex_catalog_engine.py` | VTEX | Catalogo | Si | `base_url` | `extract_chain_catalog.py` |
| `vtex_analytic_engine.py` | VTEX | Analitico | Si | `base_url` | `extract_campaign_analytic_to_stage.py` |
| `vtex_location_engine.py` | VTEX | Ubicaciones | Si | `base_url` | `extract_chain_locations.py` |
| `algolia_catalog_engine.py` | Algolia | Catalogo | **No** (requests.Session) | `base_url` (no algolia.net) | `extract_chain_catalog.py` |
| `instaleap_catalog_engine.py` | Instaleap | Catalogo | Si | `graphql_endpoint` | `extract_chain_catalog.py` |
| `instaleap_analytic_engine.py` | Instaleap | Analitico | Si | `graphql_endpoint` | `extract_campaign_analytic_to_stage.py` |
| `instaleap_location_engine.py` | Instaleap | Ubicaciones | Si | `graphql_v2_endpoint` | `extract_chain_locations.py` |

## Patron Comun `_build_session()`

```python
def _build_session(self) -> requests.Session:
    domain = <extraer host de base_url o graphql_endpoint>
    set_rate_limiter(domain)                          # TokenBucket 5 req/s
    return create_browser_session(headers={...})       # curl_cffi + BrightData + header rotation
```

Excepcion: `algolia_catalog_engine.py` usa `requests.Session()` plano (Algolia publica no necesita proxy ni impersonacion).

## Flujo HTTP en `request_with_retry()`

1. Rotar headers (User-Agent Chrome 132-136, Accept-Language es-variantes)
2. Jitter aleatorio `random.uniform(1.0, 3.0)` pre-request
3. Structural break 30-60s cada 100 requests
4. Adquirir token rate limiter (5 req/s por dominio)
5. Ejecutar request
6. Actualizar circuit breaker

## Output Schema

Todos los catalogos producen `canonical_product_v1`:
- `catalog_id`, `pricing_scope`, `store` (store_id, display_name, base_url)
- `identity` (product_id, sku, ean, brand, seller)
- `taxonomy` (category_path, category_id, root_categories)
- `content` (name, description, link, image)
- `measurement` (quantity, unit)
- `pricing` (currency, price, list_price, has_discount)
- `availability` (available_quantity)
- `attributes` (datos especificos del provider)

Metadata produce `catalog_metadata_v1` con timestamps, conteos, config del scraper.
