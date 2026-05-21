# Market Watch BI

## Estado

Superset vive fuera de este repo, en la VM BI:

- Superset: `http://192.168.10.32:8088`
- Metadatos internos de Superset: Postgres propio en la VM BI
- Datos de Market Watch: Postgres del producto, base `supermarket`, host `192.168.10.37`, puerto `5432`

Este repo no debe desplegar herramientas BI. Market Watch cliente debe funcionar con `market-watch-api` y `web/market-watch`.

## Limites

- Superset es BI interno.
- El portal cliente no depende de Superset para operar.
- No guardar usuarios, passwords o tokens de Superset en frontend.
- No hardcodear iframes de Superset en `services/web/market-watch`.

## Integracion futura

Si se habilitan embeds o APIs BI:

- `market-watch-api` debe resolver `client_id` desde auth del producto.
- `market-watch-api` debe solicitar/generar URLs o tokens firmados.
- `web/market-watch` solo consume endpoints propios del producto.
- Configurar allowlists de frame/origin en Superset para el dominio real del frontend.

Variables reservadas:

- `MARKET_WATCH_BI_PROVIDER=superset`
- `MARKET_WATCH_SUPERSET_BASE_URL`
- `MARKET_WATCH_SUPERSET_API_URL`
- `MARKET_WATCH_SUPERSET_EMBED_ALLOWED_ORIGIN`
- `MARKET_WATCH_SUPERSET_EMBED_ENABLED`
