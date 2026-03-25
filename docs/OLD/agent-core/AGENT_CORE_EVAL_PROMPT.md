# Agent Core - Prompt Inicial de Evaluación

Usa este archivo como contexto inicial para cualquier IA que evalúe o implemente `agent-core`.

## Diagnóstico base

El problema a evitar es epistemológico: forzar decisiones probabilísticas con pipelines rígidos y reglas hardcodeadas crecientes.

La arquitectura objetivo invierte esa relación:
- el LLM planifica
- el runtime valida y ejecuta
- los contratos tipados cierran superficie

## Invariantes no negociables

1. Solo el planner decide el plan conversacional.
2. `policy_gate` y `answer_guardrail` solo hacen `YES/NO` (`accept/reject + reason_code`).
3. SQL y cards son deterministas y nunca se generan como texto libre por LLM.
4. Salidas del planner son cerradas y tipadas.
5. El planner nunca ve `ToolResult`.
6. El synthesizer no decide plan ni herramientas.
7. No se permite lógica de intención hardcodeada con `if/regex/keywords` para compensar prompt.

## Flujo objetivo

`normalize_input -> planner -> policy_gate -> tools -> synthesizer -> answer_guardrail -> envelope -> persist`

Notas:
- `goal=clarify` es ruta de negocio normal.
- `reject` del gate/guardrail es control interno, no “plan alternativo”.
- cards se renderizan en paralelo desde `ToolResult`.

## Fronteras de servicio

- `agent-core`: runtime conversacional LangGraph.
- `scoring-core`: dominio de scoring asíncrono independiente.
- En esta fase no reingenierizar scoring; solo definir punto de integración.

## Criterios de evaluación para la IA

1. ¿Existe grafo LangGraph real en runtime y no wrapper secuencial legacy?
2. ¿Se cumple aislamiento planner/synthesizer por contrato de datos?
3. ¿Gate/guardrail no mutan plan ni texto?
4. ¿SQL/cards se producen de forma determinista?
5. ¿No hay dependencia funcional a inference legacy en el camino principal objetivo?
