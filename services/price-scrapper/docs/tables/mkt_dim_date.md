# `mkt_dim_date`

## Qué es
Dimensión calendario para análisis por fecha. No depende de scraping.

## Cómo se llena
Se crea y puebla con la migración:

```bash
docker compose exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 < migrations/2026-05-04_create_mkt_dim_date.sql
```

## Qué hace
- genera el rango de fechas `2020-01-01` a `2035-12-31`
- inserta o actualiza por `date_key`
- no depende de catálogos ni APIs externas

## Tipo de actualización
`upsert`

No reconstruye la tabla completa. La migración vuelve a insertar/actualizar las fechas del rango definido.

## Frecuencia recomendada
Muy baja.

Solo cuando:
- el rango ya no alcance
- quieras agregar más atributos calendario

## Notas
Es una tabla estable. Normalmente se crea una vez y casi no se toca.
