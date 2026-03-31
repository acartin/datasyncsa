# Legacy Bridges

Estos bridges HTTP se movieron fuera del stack activo el `2026-03-30`.

Motivo:

- `chat-web-renderer` ya consume `ai-runtime` de forma directa.
- `generic-bridge` y `property-bridge` dejaron de ser servicios requeridos por `docker-compose`.
- Se conservan aqui solo como referencia historica de contratos y compatibilidad previa.

Reglas:

- no reactivar estos servicios sin revisar compose, docs y flujos de canal
- no implementar features nuevas aqui salvo instruccion explicita
- usar este directorio solo para consultas o migraciones controladas
