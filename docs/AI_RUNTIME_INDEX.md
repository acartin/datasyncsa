# AI Runtime Index

Indice canonico del runtime conversacional activo.

Estado actual:

- Runtime operativo: `services/ai_runtime`
- Bridges operativos: `services/bridges/generic-bridge` y `services/bridges/property-bridge`
- Canal web principal: `services/web/chat-web-renderer`
- Dominio separado de scoring: `services/scoring-core`

## Orden de lectura recomendado

1. `services/ai_runtime/ARCHITECTURE.md`
2. `services/ai_runtime/docs/graphs/README.md`
3. `docs/AI_RUNTIME_API_CONTRACT.md`
4. `docs/AI_RUNTIME_FILE_MAP.md`
5. `docs/AI_RUNTIME_PROMPT_RUNTIME.md`
6. `docs/SCORING_CORE_BOUNDARY.md`
7. `docs/SCORING_CORE_API_CONTRACT.md`

## Regla de precedencia

Si hay contradiccion:

1. codigo ejecutable vigente
2. `services/ai_runtime/ARCHITECTURE.md`
3. `.agent/RULES.md`
4. este indice y el resto de docs `AI_RUNTIME_*`

## Notas

- `agent-core` ya no es la autoridad conversacional del compose actual
- `docs/AGENT_CORE_*` fueron archivados en `docs/OLD/agent-core/`
- la documentacion activa debe describir el stack real: `ai-runtime -> bridges -> renderer`, con `scoring-core` aparte
- los diagramas vivos del runtime se regeneran en `services/ai_runtime/docs/graphs/`
- la consola de trazas por turno vive en `services/ai_runtime/web/turn_trace/` y el runtime expone `/api/v1/debug/turn-trace/`
