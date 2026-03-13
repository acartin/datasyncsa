# Agent Core Prompt Runtime

## Objetivo

Definir cómo se cargan y usan prompts en runtime sin hardcodear negocio en código.

## Fuentes de prompt

1. `ai_system_prompts`
- fuente canónica de `planner_system` y `synthesizer_system` (global + vertical).

2. `lead_ai_prompts`
- overlay opcional de estilo/tono/contexto comercial por tenant.
- no define intención, SQL, contratos de salida, tools ni policy.

## Prompts mínimos requeridos

1. `planner_system`
- instrucciones de decisión y formato `RouterDecision`.

2. `synthesizer_system`
- instrucciones de redacción usando solo `SynthesizerInput`.

## Secuencia de uso en runtime

1. Resolver tenant/vertical/canal.
2. Resolver prompt de planner por prioridad:
- `ai_system_prompts` (`node_slug`, `vertical_slug`) -> base por vertical.
- `ai_system_prompts` (`node_slug`, global) -> fallback global.
3. Ejecutar planner con schema estricto.
4. Ejecutar tools y construir `SynthesizerInput`.
5. Resolver prompt de synthesizer con la misma prioridad anterior (`ai_system_prompts`).
6. Aplicar overlay opcional de estilo/tono por tenant desde `lead_ai_prompts` sin alterar contratos.
7. Ejecutar synthesizer con schema estricto.

## Reglas operativas

1. Planner y synthesizer no comparten el mismo prompt.
2. Prompt no define permisos; permisos viven en policy.
3. Versionado de prompts debe quedar trazable en persistencia.
4. `lead_ai_prompts` no puede sobreescribir reglas de routing, SQL ni esquema tipado.
