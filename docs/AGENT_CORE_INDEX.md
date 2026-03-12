# Agent Core Index

Entrada canonica para entender el diseno nuevo de chat en este repo.

## Leer en este orden

1. `docs/AGENT_CORE_DIAGRAMS.md`
2. `docs/AGENT_CORE_RULES.md`
3. `docs/AGENT_CORE_ARCHITECTURE.md`
4. `docs/AGENT_CORE_PROMPT_RUNTIME.md`
5. `docs/SCORING_CORE_BOUNDARY.md`
6. `docs/AGENT_CORE_FILE_MAP.md`
7. `docs/AGENT_CORE_IMPLEMENTATION_PLAN.md`
8. `docs/AGENT_CORE_PROMPT_SEQUENCE.md`

## Servicios objetivo

- `agent-core`
- `scoring-core`

## Objetivo

Reemplazar la mezcla historica de `inference-core-v1` y `inference-core-v2` por una arquitectura con fronteras claras:

- `agent-core` decide y responde.
- `scoring-core` evalua scoring de manera asincrona e independiente.

## Principio central

Solo existe un decisor conversacional: el planner de `agent-core`.

Todo lo demas es:

- validacion determinista,
- ejecucion de tools,
- render de cards,
- scoring asincrono,
- o compatibilidad de APIs.
