# BRAIN_MAP

- Generated UTC: `2026-06-03T18:23:45Z`
- Repo root: `/srv/datasyncsa`
- Git branch: `HETZNER-LOCAL-2026-Junio-03`
- Git commit: `5dfa172`

## 1. MAPA DE INTENCIONES (MARKET WATCH)

| Carpeta | Responsabilidad Tecnica | Importancia (1-5) |
|---|---|---:|
| `docker-compose.yml` | Compose heredado/actual del repo; revisar antes de tocar infraestructura. | 4 |
| `services/dagster` | Orquestacion de Market Watch: assets, jobs, schedules y sensores para coordinar ETL. | 4 |
| `services/price-scrapper` | Bounded context de scraping, ETL, campañas, facts y queries base. | 5 |
| `services/market-watch-api` | API de producto: auth/multitenancy, datasets livianos, control de `client_id`. | 5 |
| `services/web/market-watch` | Frontend cliente: SEO, dashboards, tablas, pivots y reportes. | 5 |
| `.agent` | Reglas operativas para agentes en el repo recortado. | 4 |

## 2. LIMITES DE ARQUITECTURA

- `price-scrapper` no aloja el producto cliente final.
- `dagster` orquesta ETL/assets; no aloja portal cliente ni duplica scraping pesado.
- `market-watch-api` no ejecuta scraping ni ETL pesado durante requests web.
- `web/market-watch` no se conecta directo a Postgres.
- No reutilizar `services/web/admin-console` ni `services/web/chat-web-renderer` como base del producto.
- Mantener contratos simples para facilitar separacion futura del repo.

## 3. SERVICIOS DOCKER ACTUALES

```text
redis
postgres
admin-console-api
admin-console-web
market-watch-api
dagster-webserver
market-watch-web
portainer
dagster-daemon
```

## 4. TOPOLOGIA DE TRABAJO

```text
services/price-scrapper
services/price-scrapper/commands
services/price-scrapper/docs
services/price-scrapper/docs/tables
services/price-scrapper/engines
services/price-scrapper/etl
services/price-scrapper/schemas
services/price-scrapper/seeds
services/price-scrapper/web
services/price-scrapper/web_backend
services/dagster
services/dagster/docs
services/dagster/src
services/dagster/src/market_watch_orchestration
services/dagster/src/market_watch_orchestration/price_scrapper
services/market-watch-api
services/market-watch-api/app
services/market-watch-api/app/api
services/market-watch-api/app/api/routes
services/market-watch-api/app/core
services/market-watch-api/app/domain
services/market-watch-api/app/repositories
services/web/market-watch
services/web/market-watch/app
services/web/market-watch/app/[group]
services/web/market-watch/app/[group]/[module]
services/web/market-watch/app/api
services/web/market-watch/app/api/auth
services/web/market-watch/app/api/filters
services/web/market-watch/app/api/settings
services/web/market-watch/app/api/table-views
services/web/market-watch/app/login
services/web/market-watch/app/pricing
services/web/market-watch/app/pricing/executive-signals
services/web/market-watch/app/pricing/intraday-radar
services/web/market-watch/app/pricing/products
services/web/market-watch/app/pricing/signals
services/web/market-watch/components
services/web/market-watch/components/market-watch
services/web/market-watch/components/portal
services/web/market-watch/components/ui
services/web/market-watch/lib
services/web/market-watch/public
```

## 5. ARCHIVOS RELEVANTES

```text
services/price-scrapper/README.md
services/price-scrapper/borrar_populate_mkt_dim_product.py
services/price-scrapper/commands/extract_campaign_analytic_to_stage.py
services/price-scrapper/commands/extract_catalog_to_stage.py
services/price-scrapper/commands/extract_chain_catalog.py
services/price-scrapper/commands/extract_chain_locations.py
services/price-scrapper/commands/load_dim_listings.py
services/price-scrapper/commands/load_dim_products.py
services/price-scrapper/commands/load_fact_listing_snapshots.py
services/price-scrapper/commands/reset_catalog_stage.py
services/price-scrapper/commands/run_campaign_analytic_batch.py
services/price-scrapper/commands/serve_web.py
services/price-scrapper/commands/transform_stage_listing_snapshots.py
services/price-scrapper/commands/transform_stage_listings.py
services/price-scrapper/commands/transform_stage_products.py
services/price-scrapper/commands/update_chain_root_categories.py
services/price-scrapper/docs/tables/README.md
services/price-scrapper/docs/tables/mkt_campaign_location.md
services/price-scrapper/docs/tables/mkt_campaign_product.md
services/price-scrapper/docs/tables/mkt_dim_campaign.md
services/price-scrapper/docs/tables/mkt_dim_category.md
services/price-scrapper/docs/tables/mkt_dim_chain.md
services/price-scrapper/docs/tables/mkt_dim_client.md
services/price-scrapper/docs/tables/mkt_dim_date.md
services/price-scrapper/docs/tables/mkt_dim_listing.md
services/price-scrapper/docs/tables/mkt_dim_location.md
services/price-scrapper/docs/tables/mkt_dim_market_event_type.md
services/price-scrapper/docs/tables/mkt_dim_product.md
services/price-scrapper/docs/tables/mkt_fact_listing_snapshot.md
services/price-scrapper/docs/tables/mkt_run.md
services/price-scrapper/docs/tables/mkt_stage_catalog_item.md
services/price-scrapper/docs/tables/mkt_stage_listing_candidate.md
services/price-scrapper/docs/tables/mkt_stage_listing_review.md
services/price-scrapper/docs/tables/mkt_stage_listing_snapshot_candidate.md
services/price-scrapper/docs/tables/mkt_stage_listing_snapshot_review.md
services/price-scrapper/docs/tables/mkt_stage_product_candidate.md
services/price-scrapper/docs/tables/mkt_stage_product_review.md
services/price-scrapper/engines/instaleap_analytic_engine.py
services/price-scrapper/engines/instaleap_catalog_engine.py
services/price-scrapper/engines/instaleap_location_engine.py
services/price-scrapper/engines/vtex_analytic_engine.py
services/price-scrapper/engines/vtex_catalog_engine.py
services/price-scrapper/engines/vtex_location_engine.py
services/price-scrapper/etl/__init__.py
services/price-scrapper/etl/business_date.py
services/price-scrapper/etl/campaign_runtime_db.py
services/price-scrapper/etl/catalog_stage_loader.py
services/price-scrapper/etl/catalog_stage_reset.py
services/price-scrapper/etl/chain_runtime_db.py
services/price-scrapper/etl/http_client.py
services/price-scrapper/etl/normalize.py
services/price-scrapper/etl/postgres_cli.py
services/price-scrapper/etl/run_runtime_db.py
services/price-scrapper/etl/stage_listing_snapshot_transform.py
services/price-scrapper/etl/stage_listing_transform.py
services/price-scrapper/etl/stage_product_transform.py
services/price-scrapper/requirements.txt
services/price-scrapper/schemas/canonical_product_v1.schema.json
services/price-scrapper/seeds/2026-05-08_adjust_campaign_locations_sardimar_atun_competencia_cr_megasuper.sql
services/price-scrapper/seeds/2026-05-08_seed_campaign_locations_sardimar_atun_competencia_cr.sql
services/price-scrapper/seeds/2026-05-08_seed_campaign_sardimar_atun_competencia_cr.sql
services/price-scrapper/seeds/2026-05-22_create_mw_tool_agnostic_semantic_layer.sql
services/price-scrapper/seeds/2026-05-26_create_auth_security_baseline.sql
services/price-scrapper/seeds/2026-05-27_create_mkt_campaign_client_access.sql
services/price-scrapper/seeds/2026-05-31_create_mkt_dim_market_event_type.sql
services/price-scrapper/web/app.js
services/price-scrapper/web/catalog-data.js
services/price-scrapper/web/compare.html
services/price-scrapper/web/compare.js
services/price-scrapper/web/index.html
services/price-scrapper/web/styles.css
services/price-scrapper/web_backend/__init__.py
services/price-scrapper/web_backend/catalog_db.py
services/dagster/Dockerfile
services/dagster/README.md
services/dagster/dagster.yaml
services/dagster/docs/OPERATIONS.md
services/dagster/requirements.txt
services/dagster/src/market_watch_orchestration/__init__.py
services/dagster/src/market_watch_orchestration/definitions.py
services/dagster/src/market_watch_orchestration/resources.py
services/dagster/workspace.yaml
services/market-watch-api/Dockerfile
services/market-watch-api/README.md
services/market-watch-api/app/__init__.py
services/market-watch-api/app/api/__init__.py
services/market-watch-api/app/api/router.py
services/market-watch-api/app/core/__init__.py
services/market-watch-api/app/core/config.py
services/market-watch-api/app/core/db.py
services/market-watch-api/app/core/security.py
services/market-watch-api/app/domain/__init__.py
services/market-watch-api/app/domain/navigation.py
services/market-watch-api/app/domain/placeholders.py
services/market-watch-api/app/main.py
services/market-watch-api/app/repositories/__init__.py
services/market-watch-api/app/repositories/auth_repository.py
services/market-watch-api/app/repositories/market_repository.py
services/market-watch-api/main.py
services/market-watch-api/requirements.txt
services/web/market-watch/Dockerfile
services/web/market-watch/README.md
services/web/market-watch/app/globals.css
services/web/market-watch/app/layout.tsx
services/web/market-watch/app/login/page.tsx
services/web/market-watch/app/not-found.tsx
services/web/market-watch/app/page.tsx
services/web/market-watch/components/market-watch/chain-tag.tsx
services/web/market-watch/components/market-watch/crud-toolbar.tsx
services/web/market-watch/components/market-watch/data-grid.tsx
services/web/market-watch/components/market-watch/data-view-toolbar.tsx
services/web/market-watch/components/market-watch/executive-signals-page.tsx
services/web/market-watch/components/market-watch/filter-bar.tsx
services/web/market-watch/components/market-watch/intraday-product-grids.tsx
services/web/market-watch/components/market-watch/intraday-product-page.tsx
services/web/market-watch/components/market-watch/intraday-radar-filters-form.tsx
services/web/market-watch/components/market-watch/intraday-radar-grid.tsx
services/web/market-watch/components/market-watch/intraday-radar-page.tsx
services/web/market-watch/components/market-watch/kpi-card.tsx
services/web/market-watch/components/market-watch/product-history-chart.tsx
services/web/market-watch/components/market-watch/product-visual.tsx
services/web/market-watch/components/market-watch/row-actions.tsx
services/web/market-watch/components/market-watch/signal-detail-page.tsx
services/web/market-watch/components/market-watch/signal-filters-form.tsx
services/web/market-watch/components/market-watch/signal-grid.tsx
services/web/market-watch/components/market-watch/signal-kpi-cards.tsx
services/web/market-watch/components/market-watch/signal-severity-badge.tsx
services/web/market-watch/components/market-watch/signal-status-badge.tsx
services/web/market-watch/components/market-watch/sku-price-drivers-grid.tsx
services/web/market-watch/components/market-watch/store-evidence-grid.tsx
services/web/market-watch/components/portal/app-shell.tsx
services/web/market-watch/components/portal/focus-mode-toggle.tsx
services/web/market-watch/components/portal/module-view.tsx
services/web/market-watch/components/portal/role-simulator.tsx
services/web/market-watch/components/portal/shell-state.tsx
services/web/market-watch/components/portal/sidebar.tsx
services/web/market-watch/components/portal/topbar.tsx
services/web/market-watch/components/ui/alert.tsx
services/web/market-watch/components/ui/badge.tsx
services/web/market-watch/components/ui/button.tsx
services/web/market-watch/components/ui/card.tsx
services/web/market-watch/components/ui/empty-state.tsx
services/web/market-watch/components/ui/loading-state.tsx
services/web/market-watch/components/ui/modal.tsx
services/web/market-watch/components/ui/tabs.tsx
services/web/market-watch/components/ui/theme-toggle.tsx
services/web/market-watch/lib/api.ts
services/web/market-watch/lib/closed-day.ts
services/web/market-watch/lib/data-views.ts
services/web/market-watch/lib/event-presentation.ts
services/web/market-watch/lib/feedback.ts
services/web/market-watch/lib/modules.ts
services/web/market-watch/lib/pricing-types.ts
services/web/market-watch/lib/request-url.ts
services/web/market-watch/lib/types.ts
services/web/market-watch/lib/utils.ts
services/web/market-watch/next-env.d.ts
services/web/market-watch/next.config.mjs
services/web/market-watch/package-lock.json
services/web/market-watch/package.json
services/web/market-watch/postcss.config.mjs
services/web/market-watch/tailwind.config.ts
services/web/market-watch/tsconfig.json
```
