# Legacy Inference Stack V2

Este stack se movio fuera del runtime activo el `2026-03-30`.

Motivo:

- `ai-runtime` es la autoridad conversacional actual.
- `chat-web-renderer` ya no depende de `inference-core-v2`, `inference-core-v3` ni `semantic-adapter-v2`.
- Este directorio se conserva solo para referencia historica, auditoria y migraciones controladas.

Reglas:

- no reactivar componentes de este stack sin revisar compose, docs y tests activos
- no implementar features nuevas aqui salvo instruccion explicita
- usar este directorio solo para consulta o comparacion historica
