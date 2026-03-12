# AGENT CORE BOOTSTRAP

Usar este archivo cuando la tarea toque:

- `agent-core`
- `scoring-core`
- rediseño del stack conversacional
- retiro progresivo de `inference-core-v1/v2`

## Lectura mínima obligatoria

1. `docs/AGENT_CORE_INDEX.md`
2. `docs/AGENT_CORE_DIAGRAMS.md`
3. `docs/AGENT_CORE_RULES.md`
4. `docs/AGENT_CORE_ARCHITECTURE.md`
5. `docs/AGENT_CORE_PROMPT_RUNTIME.md`
6. `docs/SCORING_CORE_BOUNDARY.md`
7. `docs/AGENT_CORE_FILE_MAP.md`
8. `docs/AGENT_CORE_IMPLEMENTATION_PLAN.md`

## Contratos y configuracion estructurada

Leer segun concern:

- `schemas/agent_core/contracts/*`
- `schemas/agent_core/runtime/*`
- `schemas/scoring_core/contracts/*`

## Reglas de interpretacion

- `agent-core` es el unico decisor conversacional.
- `scoring-core` es independiente y conserva su BD/logica actual.
- `generic` y `realtor` son verticales del mismo runtime, no dos arquitecturas distintas.
- `policy gate`, `tool registry` y `card registry` viven en archivos de `schemas/`, no en prompts.

## Fuentes legacy

Usar solo como material de extraccion:

- `services/inference-stack-v2/inference-core-v2`
- `services/inference-stack-v2/inference-core-v3`

No usarlos como referencia arquitectonica objetivo.
