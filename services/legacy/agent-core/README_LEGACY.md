# Agent Core Legacy

`agent-core` se movio fuera del stack activo el `2026-03-30`.

Motivo:

- `ai-runtime` es la autoridad conversacional actual.
- `chat-web-renderer` y los flujos activos ya no dependen de este servicio.
- Este directorio se conserva solo para referencia historica, auditoria y comparacion tecnica.

Reglas:

- no reactivar este servicio sin revisar compose, docs, tests y contratos activos
- no implementar features nuevas aqui salvo instruccion explicita
- usar este directorio solo para consulta o migraciones controladas
