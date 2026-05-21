# Market Watch API

API de producto para Market Watch.

## Responsabilidad

- Resolver auth/multitenancy del producto cliente.
- Exponer endpoints por menu/modulo.
- Publicar datasets livianos para dashboards, tablas, pivots y reportes.
- Aplicar control de `client_id` antes de consultar o devolver datos.

## Fuera de alcance

- No ejecuta scraping.
- No ejecuta ETL pesado durante requests web.
- No importa modulos de `services/price-scrapper`.
- No reemplaza Superset para uso BI interno.

## Integracion futura con Superset

Superset vive fuera de este repo, en la VM BI. La API de producto no debe depender de Superset para servir datasets cliente.

Si mas adelante se habilitan embeds o enlaces internos:

- La API debe emitir tokens o URLs firmadas desde endpoints propios.
- El `client_id` debe resolverse desde auth del producto antes de solicitar cualquier recurso BI.
- No exponer credenciales de Superset al frontend.

## Contrato inicial

Base path: `/api/v1`

- `GET /api/v1/health`
- `GET /api/v1/menu`
- `GET /api/v1/datasets/overview`
- `GET /api/v1/datasets/products`
- `GET /api/v1/datasets/price-matrix`

Los endpoints de datasets requieren identidad de cliente resuelta. En el esqueleto inicial:

- Si `MARKET_WATCH_API_TOKEN` existe, se exige `Authorization: Bearer <token>`.
- `X-Client-Id` define el cliente para desarrollo o integraciones internas.
- Si falta `X-Client-Id`, puede usarse `MARKET_WATCH_DEMO_CLIENT_ID` solo para entornos no productivos.

Antes de produccion, `client_id` debe derivarse de sesion/JWT/API key, no de un header libre del navegador.
