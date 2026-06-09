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
