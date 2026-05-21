# Market Watch Portal

Portal administrativo y operativo del producto Market Watch.

## Responsabilidad

- Configurar y operar campañas, catálogos, productos monitoreados y competidores.
- Exponer navegación por rol para clientes y operadores internos.
- Enlazar o embeber Superset como portal analítico cuando se habilite.
- Consumir `services/market-watch-api`.

## Fuera de alcance

- No se conecta directo a Postgres.
- No ejecuta scraping ni ETL.
- No reutiliza `admin-console`.
- No reutiliza `chat-web-renderer`.
- No vive dentro de `services/price-scrapper/web`.

## Implementacion inicial

Next.js App Router + TypeScript + Tailwind con componentes estilo shadcn/ui.

La autenticacion real con Keycloak queda preparada, pero en esta iteracion el rol se simula con query string:

```text
/?role=system-admin
/?role=client-admin
/?role=client-viewer
/?role=system-user
```

## Servicios externos previstos

- Keycloak: identidad, login, roles y grupos.
- Superset: dashboards y reportes analiticos.
- Dagster: orquestacion ETL.
