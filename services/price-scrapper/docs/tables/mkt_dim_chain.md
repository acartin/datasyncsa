# `mkt_dim_chain`

## Qué es
Catálogo de cadenas que usamos en `price-scrapper`.

## Fuente real
- `public.mkt_dim_chain`

## Cómo se llena
Hoy se sincroniza con la migración:

```bash
docker compose exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 < migrations/2026-05-04_create_mkt_dim_chain.sql
```

## Qué hace
- crea la tabla si no existe
- inserta las cadenas base actuales
- actualiza nombre, base URL, engine y scope si ya existen

## Tipo de actualización
`upsert`

No reconstruye completa por sí sola.

## Frecuencia recomendada
Baja.

Solo cuando:
- agregas una cadena nueva
- cambias `base_url`
- cambias `engine`
- cambias `pricing_scope`

## Notas
No hay scraper para esta tabla. Es una dimensión de configuración y runtime.
