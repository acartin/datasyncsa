# `mkt_stage_listing_review`

## Qué es
Cola de revisión manual para listings que no pudieron mapearse a un producto canónico.

## Qué script correr

```bash
python3 services/price-scrapper/commands/transform_stage_listings.py
```

## Qué hace
- captura publicaciones sin `product_key` resoluble
- guarda detalle de las filas stage involucradas en `review_payload`

## Tipo de actualización
`replace-all`

Cada corrida de `transform_stage_listings.py` reemplaza completa esta tabla.

## Frecuencia recomendada
La misma de `mkt_stage_listing_candidate`.

## Notas
- Hoy el motivo principal esperado es `missing_product_match`.
- Si esta tabla crece, normalmente primero hay que revisar `mkt_dim_product`.
