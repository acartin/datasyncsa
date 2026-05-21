# Market Watch Superset Naming

## Objetivo

Mantener dashboards, charts, datasets y objetos analiticos de Market Watch ordenados, buscables y faciles de administrar conforme crezca el contenido en Superset.

Superset no usa colecciones tipo Metabase como mecanismo principal de organizacion. Para Market Watch se usara una combinacion de nombres estructurados, tags, roles, permisos, owners y dashboards publicados.

## Prefijos

Todo objeto visible relacionado con Market Watch debe iniciar con:

```text
MW
```

Para objetos tecnicos en base de datos, vistas o datasets se usara:

```text
mw_
```

Ejemplos:

```text
mw_fact_listing_snapshots
mw_dim_product
mw_dim_chain
mw_price_positioning
```

## Dashboards

Los dashboards visibles en Superset deben distinguir entre objetos reutilizables de producto y objetos especificos por cliente.

Regla principal:

- Usar `MW Product` cuando el dashboard pueda servir para multiples clientes, marcas o campañas mediante filtros.
- Usar `MW Client` solo cuando el dashboard sea una variante curada, contractual o narrativa para un cliente especifico.
- Usar `MW Internal` para operacion, QA, ETL, data quality o administracion.

Formato para dashboards reutilizables:

```text
MW Product | <Dominio> | <Nombre>
```

Ejemplos:

```text
MW Product | Executive | Overview
MW Product | Pricing | Price Intelligence
MW Product | Pricing | Product Chain Benchmark
MW Product | Catalog | SKU Visibility
MW Product | Alerts | Price Change Events
MW Product | Competitive | Brand Benchmark
```

Formato para dashboards especificos por cliente:

```text
MW <Audiencia> | <Cliente o Area> | <Dominio> | <Nombre>
```

Ejemplos:

```text
MW Client | Sardimar | Executive | Monthly Report
MW Client | Sardimar | Pricing | Tuna Category Deep Dive
MW Internal | Operations | ETL Runs
MW Internal | Data Quality | Product Matching
```

## Charts

Los charts deben seguir la misma regla de reutilizacion que los dashboards.

Formato para charts reutilizables:

```text
MW Product | <Dominio> | <Metrica o Vista>
```

Ejemplos:

```text
MW Product | Pricing | Average Price by Chain
MW Product | Pricing | Price Gap vs Market Minimum
MW Product | Pricing | Unit Price Trend
MW Product | Catalog | SKU Visibility by Chain
MW Product | Executive | Latest Price Events
MW Product | Executive | Brand Competitiveness Ranking
```

Formato para charts especificos por cliente o area interna:

```text
MW <Audiencia> | <Cliente o Area> | <Dominio> | <Metrica o Vista>
```

Ejemplos:

```text
MW Client | Sardimar | Executive | Monthly Strategic Highlights
MW Internal | Operations | Run Duration by Chain
MW Internal | Data Quality | Products Without Match
```

## Datasets

Los datasets deben usar nombres tecnicos en `snake_case`.

Ejemplos:

```text
mw_fact_listing_snapshots
mw_dim_product
mw_dim_chain
mw_dim_client
mw_campaign_performance
mw_price_positioning
```

Evitar crear datasets excesivamente especificos por cliente si el mismo dataset puede filtrarse por `client_id`, `campaign_id`, `chain_id` o `business_date`.

## Tags

Usar tags para facilitar busqueda y filtrado.

Tags recomendados:

```text
client:sardimar
client:demo
scope:product
scope:client-specific
domain:pricing
domain:catalog
domain:executive
domain:competitive
domain:alerts
domain:operations
domain:data-quality
visibility:client
visibility:internal
env:prod
```

## Audiencias

Usar solamente estas audiencias en nombres de dashboards y charts:

```text
MW Product
MW Client
MW Internal
```

`MW Product` identifica contenido reutilizable para multiples clientes, marcas o campañas. Es la audiencia por defecto para dashboards y charts de producto.

`MW Client` identifica contenido visible para clientes finales.

`MW Internal` identifica contenido operativo interno, QA, ETL, monitoreo o administracion.

## Dominios Iniciales

Dominios permitidos al inicio:

```text
Pricing
Catalog
Competitive
Alerts
Operations
Data Quality
Executive
```

## Instrucciones Para IA

Cuando una IA cree o proponga objetos de Superset para Market Watch:

1. Debe preferir `MW Product` para dashboards y charts reutilizables.
2. No debe incluir nombres de clientes, marcas o campañas en el nombre del objeto si el mismo dashboard/chart puede funcionar con filtros como `client_id`, `campaign_id`, `brand_name`, `chain_id` o rango de fechas.
3. Debe usar `MW Client | <Cliente> | ...` solo para entregables realmente especificos, como reportes mensuales, deep dives curados o vistas contractuales.
4. Debe evitar duplicar dashboards por cliente cuando baste con aplicar filtros, permisos, roles, RLS o parametros de embedding.
5. Debe mantener datasets tecnicos con nombres `mw_` en `snake_case`.
6. Debe agregar tags de `scope`, `domain` y `visibility` para compensar que Superset no organiza objetos como Metabase.

Ejemplo correcto para producto reusable:

```text
MW Product | Pricing | Price Intelligence
MW Product | Pricing | Average Price by Chain
```

Ejemplo correcto para entregable cliente:

```text
MW Client | Sardimar | Executive | Monthly Report
```

Ejemplo incorrecto si solo cambia el filtro:

```text
MW Client | Sardimar | Pricing | Price Intelligence
MW Client | Calvo | Pricing | Price Intelligence
MW Client | Tesoro del Mar | Pricing | Price Intelligence
```

## Regla de Oro

Todo objeto debe responder rapidamente:

```text
De que producto es?
Para quien es?
De que area trata?
Que muestra?
```

Ejemplo correcto:

```text
MW Product | Pricing | Price Intelligence
```

Ejemplo incorrecto:

```text
Dashboard precios final v2
```
