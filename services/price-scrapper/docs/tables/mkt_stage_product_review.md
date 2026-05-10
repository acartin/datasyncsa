# `mkt_stage_product_review`

## Qué es
Cola de revisión manual para productos que no deben canonizarse automáticamente.

## Qué script correr

```bash
python3 services/price-scrapper/commands/transform_stage_products.py
```

## Qué hace
- captura `GTIN` inválidos o no estándar
- captura colisiones dentro de una misma cadena para el mismo `GTIN`
- guarda detalle en `review_payload`

## Tipo de actualización
`replace-all`

Cada corrida de `transform_stage_products.py` reemplaza completa esta tabla.

## Frecuencia recomendada
La misma de `mkt_stage_product_candidate`.

## Notas
- Es la salida de control de calidad del `transform`.
- No carga directo a `mkt_dim_product`.
