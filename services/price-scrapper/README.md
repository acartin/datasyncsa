# VTEX CR Price Scrapper

Motor local para extraer catalogos de supermercados VTEX en Costa Rica desde
`services/price-scrapper`, con:

- configuracion por tienda en `config/stores/*.json`
- categorias raiz con bandera `enabled`
- esquema canónico de producto
- metadata comun de pricing
- web local para navegar y comparar por `EAN`

## Estructura

- `run_store_scraper.py`
  runner generico por `store_id`
- `refresh_store_categories.py`
  refresca categorias raiz por tienda y preserva `enabled`
- `vtex_abarrotes_scraper.py`
  motor VTEX compartido
- `store_catalog_config.py`
  definiciones locales de tiendas y rutas
- `config/stores/*.json`
  configuracion editable por tienda
- `schemas/canonical_product_v1.schema.json`
  esquema canonico de salida
- `web/`
  interfaz estatica local

## Config de categorias

Cada tienda tiene un JSON en `config/stores/`. Ejemplo:

```json
{
  "store_id": "walmart_cr",
  "catalog_id": "walmart_cr_catalog",
  "default_output_dir": "output/walmart_cr_abarrotes",
  "pricing_scope": "chain_public_online",
  "categories": [
    {
      "name": "Abarrotes",
      "slug": "abarrotes",
      "url": "https://www.walmart.co.cr/abarrotes",
      "enabled": true
    }
  ]
}
```

Para controlar que se scrapea, edita solo `enabled`.

## Refrescar categorias

Actualiza las categorias raiz publicas y preserva los flags existentes:

```bash
cd /srv/datasyncsa/services/price-scrapper
python3 refresh_store_categories.py
```

Solo una tienda:

```bash
python3 refresh_store_categories.py --store-id walmart_cr
```

## Ejecucion

### Runner generico

```bash
cd /srv/datasyncsa/services/price-scrapper
python3 run_store_scraper.py --store-id walmart_cr
```

Smoke test corto:

```bash
python3 run_store_scraper.py --store-id walmart_cr --max-categories 2 --max-pages-per-category 1 --sleep-min 0 --sleep-max 0
```

Limitar temporalmente a una categoria raiz por slug:

```bash
python3 run_store_scraper.py --store-id walmart_cr --root-category-slug abarrotes
```

### Wrappers por tienda

```bash
python3 walmart_cr_abarrotes_scraper.py
python3 maxi_pali_abarrotes_scraper.py
python3 masxmenos_cr_abarrotes_scraper.py
```

## Salidas

Cada corrida escribe:

- `catalog.json`
- `metadata.json`

El catalogo ahora usa `canonical_product_v1` y la metadata incluye:

- `pricing_scope`
- `pricing_context`
- `started_at`
- `finished_at`
- `elapsed_seconds`
- `enabled_root_categories`
- `category_runs`
- `overflow_categories`

## Alcance de pricing

La salida actual representa el precio online publico por cadena:

- `pricing_scope: chain_public_online`
- no selecciona tienda fisica
- no selecciona codigo postal
- no inyecta `accesscontrollist` ni `regionId`

Eso nos deja una base consistente para el comparador de precios entre cadenas.

## Notas VTEX

`productSearchV3` puede reportar miles de productos en `recordsFiltered`, pero
deja de responder de forma confiable cuando una misma consulta supera
aproximadamente las `50` paginas. Por eso el motor:

1. usa GraphQL paginado con `from`/`to`
2. intenta payload `base64` en modo `auto`
3. cae a JSON serializado si el endpoint rechaza esa codificacion
4. divide categorias grandes por subcategorias publicas

## Vista web local

La interfaz estatica de `web/` lee las salidas locales, soporta el esquema
canonico y permite comparar por `EAN`.

```bash
cd /srv/datasyncsa/services/price-scrapper
python3 -m http.server 8765
```

Luego abre:

```text
http://127.0.0.1:8765/web/
```

La vista principal permite filtrar por salida y cada card tiene un boton
`Comparar` que abre:

```text
http://127.0.0.1:8765/web/compare.html?ean=...
```

## Tiendas soportadas hoy

- `walmart_cr` (engine VTEX)
- `maxi_pali_cr` (engine VTEX)
- `masxmenos_cr` (engine VTEX)
- `megasuper_cr` (engine Instaleap, GraphQL `nextgentheadless.instaleap.io/api/v3`,
  clientId `MEGASUPER`, storeReference `M102`)

## Motor Instaleap (megasuper)

Megasuper no corre sobre VTEX sino sobre Instaleap. La salida sigue usando
`canonical_product_v1` y la metadata `catalog_metadata_v1` para que el comparador
por EAN siga funcionando con todas las cadenas.

```bash
python3 megasuper_cr_abarrotes_scraper.py
# o via runner generico:
python3 run_store_scraper.py --store-id megasuper_cr
```

Smoke test corto:

```bash
python3 megasuper_cr_abarrotes_scraper.py --max-pages-per-category 1 --page-size 5 --sleep-min 0 --sleep-max 0
```

Notas:

- el motor pagina `getProductsByCategory` con `currentPage`/`pageSize` (default 100)
- la respuesta ya incluye toda la subcategoria, no hay que recursar en el arbol
- `pricing_scope` se reporta como `default_store_online` porque Instaleap exige
  `storeReference` (la web fija `M102` para usuarios anonimos)
- `refresh_store_categories.py` ignora tiendas con engine distinto a VTEX
