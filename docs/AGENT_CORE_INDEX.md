# Agent Core Index (LangGraph Canonical)

Este índice reemplaza la documentación anterior de `AGENT_CORE`.

Estado actual:
- Arquitectura objetivo: `agent-core` con `LangGraph`.
- Alcance de esta fase: conversación y runtime del agente.
- Fuera de alcance en esta fase: refactor interno de `scoring`.

## Orden de lectura obligatorio

1. `docs/AGENT_CORE_EVAL_PROMPT.md`
2. `docs/AGENT_CORE_RULES.md`
3. `docs/AGENT_CORE_ARCHITECTURE.md`
4. `docs/AGENT_CORE_DIAGRAMS.md`
5. `docs/AGENT_CORE_API_CONTRACT.md`
6. `docs/AGENT_CORE_PROMPT_RUNTIME.md`
7. `docs/AGENT_CORE_FILE_MAP.md`
8. `docs/AGENT_CORE_IMPLEMENTATION_PLAN.md`
9. `docs/AGENT_CORE_PROMPT_SEQUENCE.md`
10. `docs/AGENT_CORE_PROMPT_STATUS.md`

## Objetivo

Construir un `agent-core` nuevo con orquestación `LangGraph`, contratos tipados y fronteras estrictas:
- lógica conversacional probabilística en LLMs
- ejecución de herramientas determinista
- control de riesgo determinista por `accept/reject`

## Regla de precedencia

Si hay contradicción:
1. Código ejecutable vigente.
2. `docs/AGENT_CORE_RULES.md`.
3. Resto de documentos `AGENT_CORE`.
