# Plan operativo de prompts (ejecutable por IA)

Usa esta secuencia sin saltos. Cada prompt debe entregarse y persistirse en su rama de trabajo antes de pasar al siguiente.

Formato común para cada ejecución:
- Rol de la IA: `senior backend engineer + arquitecto de sistemas`.
- Entregable explícito: archivos tocados, tests/lint pendientes, contrato de aceptación.
- Criterio de no-negociación: no agregar heurística hardcodeada ni lógica de intención en reglas locales.

## Prompt 01 — Cortafuegos de contexto (lectura obligatoria)

`Lee y alinea: docs/AGENT_CORE_INDEX.md, docs/AGENT_CORE_RULES.md, docs/AGENT_CORE_ARCHITECTURE.md, docs/AGENT_CORE_PROMPT_RUNTIME.md, docs/AGENT_CORE_FILE_MAP.md, docs/AGENT_CORE_IMPLEMENTATION_PLAN.md, .agent/AGENT_CORE_BOOTSTRAP.md, .agent/PY_EXECUTION_MAP.md y la salida del estado actual docs/AGENT_CORE_PROMPT_STATUS.md.`

Si algo contradice estas fuentes, prioriza `AGENT_CORE_RULES` y luego el código.

Actualiza el estado del prompt como `in_progress` y solo propone cambios que respeten LangGraph en `agent-core`.

## Prompt 02 — Contratos base tipados

Implementa o ajusta los contratos Pydantic de `agent-core` en `schemas/agent_core/contracts` con estructura cerrada:

- `RouterDecision`, `ToolCall`, `ToolResult`
- `SynthesizerInput`, `SynthesizerOutput`
- `GateResult`, `GuardrailResult`
- `AnswerEnvelope`, `CardModel`, enums y códigos de rechazo

Reglas:
1. Ninguna propiedad opcional debe permitir `Any` como atajo.
2. `goal` solo enum, sin cadenas libres.
3. Planner nunca recibe `ToolResult`.
4. Synthesizer nunca recibe `RouterDecision`.

Incluye validaciones Pydantic mínimas y serialización JSON estable.

### Resultado esperado
Archivo de contratos compilable y referencias en `docs/AGENT_CORE_FILE_MAP.md`.

## Prompt 03 — Estado de LangGraph y grafo canónico

Construye estado del grafo en `services/agent-core/app/graph/state.py` y flujo en `services/agent-core/app/graph/workflow.py`.

Nodos obligatorios:
1. `normalize_input`
2. `plan_turn`
3. `policy_gate`
4. `clarify_response`
5. `execute_tools`
6. `synthesize`
7. `answer_guardrail`
8. `persist`

Conexiones obligatorias:
- `policy_gate` debe recibir `RouterDecision`.
- `clarify_response` sólo en `goal=clarify`.
- `execute_tools` no debe correr si `goal=clarify`.
- `answer_guardrail` valida salida del `synthesizer`.
- `persist` siempre finaliza el turno.

Invariantes:
1. Solo binarios en gate/guardrail.
2. Sin branching implícito por regex/keywords en `graph.py`.

## Prompt 04 — Planner LLM con schema estrictamente tipado

Implementa `planner` como nodo LangGraph usando:
- `planner_system_prompt` cargado desde DB
- `history` + `context_snapshot`
- `response_format=RouterDecision` en llamada LLM

Reglas de rechazo explícito:
1. Si no puede completar slots obligatorios, produce `goal=clarify`.
2. Si no cumple schema, no hacer fallback local con reglas.
3. `confidence` obligatorio y persistido.

No ejecutar tools desde planner.

## Prompt 05 — Policy gate binario y determinista

Implementa gate como función pura sobre `RouterDecision` y config de tenant.

Campos de salida únicamente:
- `accepted: bool`
- `reject_code: GateRejectCode | null`

Comportamiento:
1. Rechazo si tenant no autorizado.
2. Rechazo si `confidence` < umbral configurable.
3. Rechazo si herramienta o permisos no válidos.
4. Rechazo si faltan slots obligatorios.

No producir plan alternativo, no redirigir, no rellenar campos.

## Prompt 06 — Normalización y ejecución de tool calls deterministas

Implementa tool runtime en `services/agent-core/app/tools`:
1. `rag` usando contrato `RAGQuery`.
2. `realtor_sql` con translator `slots -> AST -> SQL`.
3. `workflow` con validador de registry.

Regla crítica:
- El LLM nunca recibe SQL ni puede escribir SQL.
- Cada tool call genera `ToolResult`.
- Errores de tool se modelan con `error` pero no rompen el grafo.

## Prompt 07 — Card renderer sin LLM

Implementa render de `ToolResult` a `CardModel` en ruta determinista.

Reglas:
1. `PropertyCard` desde listados con precio/rooms/area.
2. `SearchSummaryCard` derivada de resultados SQL.
3. `RAGSourceCard` desde chunks recuperados.
4. No usar LLM para decidir qué card mostrar.

## Prompt 08 — Synthesizer restringido

Implementa síntesis en `services/agent-core/app/nodes/synthesize.py`:

- Input: solo `SynthesizerInput`.
- Output: `SynthesizerOutput` con `text`, `evidence_ids`, `needs_cards`.

`synthesizer` no recibe estado de routing ni decisiones.

Se requiere:
1. citar `evidence_ids` consistentes con `tool_results`.
2. respetar `tenant_tone` y estilo del prompt de síntesis.

## Prompt 09 — Answer guardrail binario

Implementa guardrail final en `services/agent-core/app/nodes/answer_guardrail.py`.

Reglas:
1. Acepta/rechaza únicamente.
2. Si rechaza, no reescribir texto.
3. Debe detectar:
   - claims sin evidencia
   - IDs de listing inexistentes
   - schema inválido
4. En reject, retorna error técnico estandarizado.

## Prompt 10 — API y respuesta final

Conecta `POST /api/v1/chat` al grafo y garantiza `AnswerEnvelope`.

`AnswerEnvelope` debe incluir:
- `goal`, `confidence`, `evidence_ids`, `cards`, `clarify_message` cuando aplique

Si `goal=clarify`, ruta limpia sin tool execution.
Si reject de gate/guardrail, ruta de error técnico sin texto improvisado.

## Prompt 11 — Persistencia, trazas y métricas de grafo

Implementa persistencia mínima de:
- `RouterDecision`
- `ToolResult[]`
- `GuardrailResult`
- `AnswerEnvelope`
- `latency_ms` por nodo

Añade correlación con `conversation_id`.

## Prompt 12 — Integración scoring-core (sin refactor de scoring)

Solo adaptar clientes de API:
1. enqueue score job (async)
2. leer estado de score
3. no incluir lógica de scoring en `agent-core`.

Define cliente HTTP dedicado en configuración y timeout.

## Prompt 13 — Contratos de despliegue y configuración

Completa:
- `AGENT_CORE_API` y `SCORING_CORE_API` en `docker-compose.yml` y `.env.example`.
- `docs` actualizados con estos nombres y su responsabilidad.
- Ajustes de healthcheck mínimos en `agent-core` y `scoring-core`.

## Prompt 14 — Ajuste de pruebas objetivo

Actualiza/crea pruebas de regresión de conversación en `tests/system` y `tests/smoke-stack`.

No inventar nuevos casos con regresión de intent; cubrir:
1. classify direct answer
2. clarify con slots faltantes
3. tool execution
4. guardrail reject
5. scoring enqueue

No ejecutar suite completa si no hay aprobación explícita.

## Prompt 15 — Cierre de secuencia

Actualiza `docs/AGENT_CORE_PROMPT_STATUS.md` marcando avance por prompt y genera un resumen de:
1. prompts completados
2. cambios tocados
3. bloqueos actuales
4. siguiente prompt habilitado
