# Agent Core Prompt Runtime

## Objetivo

Separar prompts por tipo de responsabilidad sin volver a mezclar reglas de negocio dentro de texto libre.

## Tablas existentes

### `ai_system_prompts`

Uso recomendado:

- prompts estructurales del sistema
- prompts por `node_slug`
- versionado por `vertical_slug`

Debe contener:

- planner prompts
- synthesizer prompts
- prompts de nodos internos de `agent-core`

### `lead_ai_prompts`

Uso recomendado:

- overrides y personalizacion por tenant
- tono de marca
- instrucciones tenant-specific que no cambian la arquitectura

Debe contener:

- tono por tenant
- restricciones editoriales del tenant
- overrides de slugs compatibles con el runtime

### `lead_scoring_prompts`

Uso:

- exclusivo de `scoring-core`
- fuera del flujo de `agent-core`

## Regla de resolucion

Para `agent-core`, el runtime recomendado es:

1. resolver `ai_system_prompts` por `node_slug + vertical_slug`
2. si no existe, fallback a `node_slug` global
3. aplicar override opcional desde `lead_ai_prompts`
4. nunca resolver prompts de scoring desde `agent-core`

## Node slugs recomendados

Planner:

- `planner_route_turn`
- `planner_generic_turn`
- `planner_realtor_turn`
- `planner_workflow_turn`

Synthesizer:

- `synth_generic_answer`
- `synth_realtor_answer`
- `synth_clarify_answer`

Guardrails de texto opcionales:

- `guardrail_answer_style`

## Reglas de prompt

Planner:

- responde solo JSON valido
- no habla al usuario final
- no ve `ToolResult`
- no escribe SQL
- no describe pasos internos del runtime

Synthesizer:

- solo ve `SynthesizerInput`
- no ve `RouterDecision`
- no decide `goal`
- no inventa evidencia
- no genera cards

## Que no debe ir en prompts

- reglas finitas del gate
- tools habilitadas por tenant
- card registry
- allowlist SQL
- compatibilidad de APIs

## Tono y marca

La personalizacion por tenant debe venir de `lead_ai_prompts` y no debe alterar:

- contratos del planner
- estructura de `ToolCall`
- rules del gate
- mapeo de cards
