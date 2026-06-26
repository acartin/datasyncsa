# Market Watch Bootstrap

Este archivo resume el foco operativo del repo recortado. Las reglas autoritativas siguen en `.agent/RULES.md`.

## Foco

- `services/price-scrapper`: scraping, ETL, campañas, facts y queries base.
- `services/proxy-residencial`: proxy residencial BrightData para rotacion de IP en scrappers.
- `services/market-watch-api`: API de producto, auth/multitenancy, datasets livianos y control de `client_id`.
- `services/web/market-watch`: frontend cliente, SEO, dashboards, tablas y pivots.

## No reutilizar

- `services/web/admin-console`
- `services/web/chat-web-renderer`
- `services/price-scrapper/web` como producto final cliente

## Regla de separacion

El ETL prepara datos. La API publica datasets acotados y seguros. El frontend consume la API y no toca Postgres ni scripts internos.
