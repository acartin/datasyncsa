# Market Watch Operational Backlog

Pendientes operativos detectados durante la organizacion de Campaigns,
Catalog Sources y el flujo de catalogo canonico.

## Pendientes

### 1. Expirar listings no vistos recientemente

Estado: pendiente.

Hoy `mkt_dim_listing` es el puente operativo entre producto canonico y cadena:

```text
mkt_dim_product.product_key
  -> mkt_dim_listing.product_key
  -> mkt_dim_listing.chain_key
  -> mkt_dim_chain.chain_id
```

El flujo actual mantiene `mkt_dim_listing` con:

```text
commands/transform_stage_listings.py
commands/load_dim_listings.py
```

`load_dim_listings.py` hace upsert desde `mkt_stage_listing_candidate` y marca los
listings cargados como `is_active = true`, pero no desactiva los listings que ya
no aparecen en nuevas corridas. Eso significa que un producto que desaparecio de
una cadena puede seguir figurando como activo en `mkt_dim_listing` hasta una
reconstruccion controlada o una reconciliacion futura.

Pendiente sugerido:

- agregar una etapa de reconciliacion posterior al load
- marcar como `is_active = false` listings no vistos en la ventana esperada
- definir la ventana por `chain_id`, `run_kind` y fecha de negocio
- preservar historial en `mkt_fact_listing_snapshot`; no borrar facts

Impacto:

- mejora la lectura de cobertura producto/cadena
- evita que la web muestre disponibilidad estructural obsoleta
- hace mas confiable cualquier vista tipo `mw_product_chain_coverage`

### 2. Crear vistas semanticas de cobertura producto/cadena

Estado: resuelto inicialmente.

El dato base existe en `mkt_dim_listing`, pero no hay una vista semantica limpia
para que la API y la web consulten cobertura por producto canonico.

Vistas creadas:

```text
public.mw_product_chain_coverage
public.mw_product_chain_coverage_detail
```

La API ya puede consumir `mw_product_chain_coverage_detail` para enriquecer
cards y selectores de producto con cadenas donde existe el producto canonico.

Pendiente remanente:

- evaluar indices/materialized view solo si aparece un problema real de performance

No crear tabla duplicada salvo que aparezca un problema real de performance.
Primero usar vistas normales; evaluar materialized views solo si hace falta.

### 3. Separar descubrimiento de categorias vs configuracion activa

Estado: parcialmente resuelto.

Las categorias raiz deben venir de la cadena/API externa, no de captura manual en
la web. `Catalog Sources` debe limitarse a activar o desactivar categorias
descubiertas para alimentar el scraping/catalogo canonico.

Ya existe job manual Dagster:

```text
refresh_chain_root_categories_job
```

Pendiente sugerido:

- mostrar en la web evidencia de ultimo refresh por cadena/categoria
- agregar campos de auditoria si el modelo no los tiene: `last_seen_at`,
  `last_synced_at` o equivalente
- evitar que categorias no vistas recientemente parezcan vigentes sin evidencia

Impacto:

- reduce configuracion falsa o escrita a mano
- permite saber si `Catalog Sources` refleja la API actual de la cadena
- alinea la activacion de categorias con el proceso de generacion canonica

### 4. Refrescar materialized views `mw_app_*` despues del ETL

Estado: pendiente.

La ruta `/pricing/products/{product_key}` y su drill-down de tienda usan
materialized views estables de app:

```text
public.mw_app_product_chain_price_history
public.mw_app_product_store_activity
```

Estas vistas se crearon materializadas porque la vista normal obligaba a
recalcular agregaciones sobre `mw_core_sku_store_observation` durante requests
web. Con indices, el detalle del producto responde de forma usable.

Pendiente sugerido:

- agregar un paso post-ETL para ejecutar:

```sql
refresh materialized view public.mw_app_product_chain_price_history;
refresh materialized view public.mw_app_product_store_activity;
```

- ubicar ese refresh despues de las cargas que actualizan
  `mkt_fact_listing_snapshot`, `mkt_run`, `mkt_dim_listing`,
  `mkt_dim_product`, `mkt_dim_chain` o tiendas
- evaluar `refresh materialized view concurrently` solo si se agregan indices
  unicos compatibles y el bloqueo de refresh normal se vuelve un problema real

Impacto:

- mantiene rápida la página de producto
- evita que el portal muestre datos obsoletos después de un ETL exitoso
- concentra la excepción `mw_app_*` en un contrato de producto estable

Prompt pendiente para ejecutar en la noche, despues de que termine
`daily_active_campaigns_analytic_job`:

```text
Estamos en /srv/datasyncsa. Antes de tocar nada, lee:

- .agent/RULES.md
- .agent/PY_EXECUTION_MAP.md
- .agent/MARKET_WATCH_UI_STANDARDS.md

Contexto:

- El job daily_active_campaigns_analytic_job estaba corriendo durante el dia, por
  eso NO se modifico Dagster ni se reiniciaron contenedores.
- Ya existen en BD y en repo estas materialized views:
  - public.mw_app_product_chain_price_history
  - public.mw_app_product_store_activity
- Fueron creadas por:
  services/price-scrapper/seeds/2026-06-09_create_mw_app_product_activity_views.sql
- La API ya usa esas vistas para:
  - /pricing/products/{product_key}
  - drill-down de tienda del producto
- Validacion previa con product_key=4469:
  - product detail: ~0.633s
  - store drill-down: ~0.026s
- El problema pendiente es que las materialized views deben refrescarse despues
  del ETL, si no la pagina queda rapida pero puede mostrar datos viejos.

Objetivo:

Agregar al flujo Dagster correspondiente un paso post-ETL que refresque:

refresh materialized view public.mw_app_product_chain_price_history;
refresh materialized view public.mw_app_product_store_activity;

Alcance esperado:

1. No lanzar jobs manualmente.
2. No reiniciar contenedores si hay jobs corriendo.
3. Ubicar el refresh despues de load_fact_listing_snapshots dentro de
   daily_active_campaigns_analytic_job y antes o junto a la validacion final.
4. Implementarlo preferiblemente como comando de price-scrapper llamado desde
   Dagster, no como SQL embebido directamente en definitions.py.
5. Archivos probables:
   - services/price-scrapper/commands/refresh_app_materialized_views.py
   - services/dagster/src/market_watch_orchestration/price_scrapper/commands.py
   - services/dagster/src/market_watch_orchestration/resources.py
   - services/dagster/src/market_watch_orchestration/definitions.py
   - docs/market-watch-operational-backlog.md
6. El comando debe usar etl.postgres_cli.parse_env y run_psql, siguiendo el
   patron de los otros commands.
7. Si el refresh normal bloquea demasiado, NO cambiar a concurrently sin revisar:
   para concurrently se requieren indices unicos compatibles.
8. Validar sin correr el job:
   - python3 -m py_compile para el nuevo command en price-scrapper
   - docker compose up -d --build dagster-webserver dagster-daemon SOLO si no hay
     jobs corriendo y el usuario confirma
   - si no se puede rebuild por seguridad operativa, dejarlo documentado
9. Actualizar esta seccion del backlog marcando el pendiente como implementado
   cuando quede conectado.

Notas importantes:

- No crear mas vistas para grids.
- mw_app_* es una excepcion estable para API/portal, documentada en:
  - docs/market-watch-semantic-governance.md
  - docs/market-watch-semantic-layer.md
- No usar mw_exp_* para contratos estables. Es experimental y borrable.
- No usar mw_bi_* para nuevos contratos del portal propio.
```
