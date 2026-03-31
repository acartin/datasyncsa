# AI Runtime Index

Indice canonico del runtime conversacional activo.

Estado actual:

- Runtime operativo: `services/ai_runtime`
- Canal web principal: `services/web/chat-web-renderer`
- Dominio separado de scoring: `services/scoring-core`
- Bridges HTTP legacy: `services/legacy/bridges/*` solo como referencia historica

## Orden de lectura recomendado

1. `services/ai_runtime/ARCHITECTURE.md`
2. `services/ai_runtime/docs/graphs/README.md`
3. `docs/AI_RUNTIME_API_CONTRACT.md`
4. `docs/AI_RUNTIME_FILE_MAP.md`
5. `docs/AI_RUNTIME_PROMPT_RUNTIME.md`
6. `docs/AI_RUNTIME_HYBRID_SCORING_MOMENTS.md`
7. `docs/SCORING_CORE_BOUNDARY.md`
8. `docs/SCORING_CORE_API_CONTRACT.md`

## Regla de precedencia

Si hay contradiccion:

1. codigo ejecutable vigente
2. `services/ai_runtime/ARCHITECTURE.md`
3. `.agent/RULES.md`
4. este indice y el resto de docs `AI_RUNTIME_*`

## Notas

- `services/legacy/agent-core` ya no es la autoridad conversacional del compose actual
- `docs/AGENT_CORE_*` fueron archivados en `docs/OLD/agent-core/`
- la documentacion activa debe describir el stack real: `chat-web-renderer -> ai-runtime`, con `scoring-core` aparte
- el runtime usa `flow` interno para seleccionar `grafo_realtor` o `grafo_basico`
- los diagramas vivos del runtime se regeneran en `services/ai_runtime/docs/graphs/`
- la consola de trazas por turno vive en `services/ai_runtime/web/turn_trace/` y el runtime expone `/api/v1/debug/turn-trace/`
- `docs/AI_RUNTIME_PROMPT_RUNTIME.md` documenta la carga real desde DB: `planner_system`/`synthesizer_system` salen de `system_prompts` o `ai_system_prompts`, mientras `lead_ai_prompts` solo aporta `tone_prompt`
