# Agent Core Implementation Plan

## Objetivo

Construir `agent-core` y `scoring-core` en orden, sin reintroducir arquitectura por heuristicas.

## Fase 0 - Congelar contexto

- aprobar diagramas
- aprobar reglas canonicamente
- aprobar contratos de `schemas/agent_core/*`
- aprobar frontera de `scoring-core`

Resultado esperado:

- no mas discusiones sobre ubicacion de responsabilidades

## Fase 1 - `agent-core`

- implementar `normalize_input`
- implementar planner -> gate -> tools -> cards -> synth -> guardrail -> persist
- usar prompts desde `ai_system_prompts` + `lead_ai_prompts`
- implementar verticales `generic` y `realtor` como configuracion

Resultado esperado:

- reemplazo real del cerebro conversacional

## Fase 2 - `scoring-core`

- extraer motor actual de scoring de `inference-core-v2`
- mantener la misma BD y tablas
- dejar a `agent-core` solo el disparo del side effect

Resultado esperado:

- scoring independiente del agente

## Fase 3 - Corte de consumidores

- adaptar bridges y consumidores internos al nuevo borde de `agent-core`
- cortar dependencias directas a `inference-core-v1`
- cortar dependencias directas a `inference-core-v2`

Resultado esperado:

- el monorepo deja de depender de inference core legacy

## Criterios de done

- `agent-core` es el unico decisor conversacional
- `scoring-core` es el unico duenio del scoring async
- `inference-core-v1/v2` quedan fuera del camino principal
