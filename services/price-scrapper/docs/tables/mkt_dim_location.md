# `mkt_dim_location`

## Qué es
Catálogo de locations por cadena.

Hoy distingue:
- `physical_store`
- `distribution_store`
- `online_store`

## Qué script correr

```bash
python3 services/price-scrapper/commands/extract_chain_locations.py
```

Por cadena:

```bash
python3 services/price-scrapper/commands/extract_chain_locations.py --chain-id walmart_cr
```

## Qué hace
Lee las cadenas activas desde `mkt_dim_chain` y despacha por engine:

- VTEX:
  - usa `vtex_location_engine.py`
  - descubre sellers/locations desde el `store-selector` público
  - consulta `regions` por códigos postales
- Instaleap:
  - usa `instaleap_location_engine.py`
  - toma la página pública de sucursales de Megasuper
  - cruza el mapa público KML de sucursales
  - consulta `api/v2` de Instaleap para resolver `storeReference` y `storeId` cuando la sucursal tiene contexto online

## Tipo de actualización
`upsert`

El runner:
- inserta nuevas locations
- actualiza las existentes por `chain + location_code`
- no reconstruye completa por sí solo

Si quieres reconstrucción limpia:
- borrar la tabla
- recrearla con su migración
- volver a correr el comando

## Frecuencia recomendada
Baja a media.

Recomendado:
- semanal
- o cuando sospeches apertura/cierre/cambio de sucursales

## Notas
- En `Megasuper`, las locations actuales sí son sucursales físicas.
- No todas las sucursales físicas de `Megasuper` tienen contexto ecommerce resoluble; las que sí lo tienen llenan `source_location_ref` y `source_internal_id`.
- En VTEX, muchas locations ya identifican tienda física bastante bien.
- Algunos casos VTEX se clasifican como `distribution_store` para excluir nodos genéricos o logísticos del análisis por tienda.
