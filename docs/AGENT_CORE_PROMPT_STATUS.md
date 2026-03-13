# Agent Core Prompt Status

Estado inicial para seguimiento de implementación.

| Prompt | Estado | Criterio de salida |
|---|---|---|
| 01 Cortafuegos de contexto | completed | Contexto cargado y sin contradicciones con RULES/BOOTSTRAP |
| 02 Contratos base tipados | completed | Contratos compilados y referenciados en file map |
| 03 Estado de LangGraph y grafo canónico | completed | Nodos y edges ejecutables en `agent-core/app/graph` |
| 04 Planner LLM con schema tipado | in_progress | `planner` devuelve siempre `RouterDecision` válido |
| 05 Policy gate binario | completed | `GateResult` solo acepta/rechaza |
| 06 Tool runtime determinista | completed | Ejecución de RAG/SQL/workflow con `ToolResult` |
| 07 Card renderer sin LLM | completed | Cards solo de `ToolResult` |
| 08 Synthesizer restringido | completed | `SynthesizerInput` no incluye `RouterDecision` |
| 09 Answer guardrail binario | completed | reject sin reescritura |
| 10 API y respuesta final | completed | `POST /api/v1/chat` produce `AnswerEnvelope` |
| 11 Persistencia y trazas | completed | Artefactos por turno persistidos |
| 12 Integración scoring-core | in_progress | enqueue+estado por cliente API |
| 13 Despliegue/configuración | completed | `AGENT_CORE_API` y `SCORING_CORE_API` en compose/env |
| 14 Ajuste de pruebas objetivo | pending | Casos clave de cobertura listos/en curso |
| 15 Cierre de secuencia | pending | Resumen ejecutivo actualizado y next prompt habilitado |

## Convenciones

- `pending`: no iniciado
- `in_progress`: en ejecución
- `completed`: finalizado
- `blocked`: requiere decisión externa

## Política de avance

- Marcar `in_progress` solo cuando el prompt 01–01+ ya aprobó contexto.
- Marcar `completed` únicamente si el código compila y responde al criterio mínimo.
- Mantener no más de un prompt `in_progress` si coincide con ejecución secuencial.
