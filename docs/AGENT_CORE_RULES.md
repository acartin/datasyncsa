# Agent Core Rules (LangGraph)

## Reglas de arquitectura

1. `LangGraph` es la orquestación obligatoria del turno.
2. Planner y synthesizer son LLMs separados con responsabilidades distintas.
3. Planner produce solo `RouterDecision` tipado.
4. Synthesizer produce solo texto final y evidencia tipada.
5. `policy_gate` no corrige plan; solo acepta o rechaza.
6. `answer_guardrail` no reescribe texto; solo acepta o rechaza.
7. Tools son funciones puras con contratos tipados.
8. SQL se compila desde slots tipados (`slots -> AST -> SQL`).
9. Cards se renderizan desde `ToolResult`, no desde texto del LLM.
10. Cualquier fallback debe ser parametrizable, nunca heurística ad-hoc fija.
11. La normalización de salida LLM es única y centralizada en `app/core/llm_contract_normalizer.py`; no se permiten normalizadores/parches dispersos en nodos o servicios.

## Reglas de prompts

1. `planner_system` y `synthesizer_system` viven en `ai_system_prompts` y son versionables.
2. `lead_ai_prompts` se limita a estilo/tono/contexto de tenant; no define intents, SQL ni contratos.
3. Prompt no reemplaza contratos tipados; los complementa.
4. Si el gate crece por excepciones, es señal de prompt defectuoso.

## Reglas de evolución

1. No introducir rutas paralelas legacy para “parchar” el flujo.
2. No crear segundo decisor implícito fuera del planner.
3. No mezclar scoring en runtime conversacional de `agent-core`.
