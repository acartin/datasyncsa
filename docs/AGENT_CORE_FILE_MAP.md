# Agent Core File Map

## Objetivo

Dar a cualquier IA o desarrollador una ruta corta para ubicar prompts, contratos, runtime y servicios objetivo.

## Servicios objetivo

```text
services/
  agent-core/
  scoring-core/
```

## Estructura recomendada de `agent-core`

```text
services/agent-core/
  app/
    api/
    core/
    planners/
    synthesizers/
    runtime/
    tools/
    renderers/
    repositories/
    models/
```

## Estructura recomendada de `scoring-core`

```text
services/scoring-core/
  app/
    api/
    core/
    services/
    repositories/
    models/
  worker.py
```

## Contratos y configuracion estructurada

```text
schemas/
  agent_core/
    contracts/
    runtime/
  scoring_core/
    contracts/
```

## Fuentes existentes que sirven como base

Conversacional legacy:

- `services/inference-stack-v2/inference-core-v2/`
- `services/inference-stack-v2/inference-core-v3/`

Scoring funcional:

- `services/inference-stack-v2/inference-core-v2/app/services/scoring_engine.py`
- `services/inference-stack-v2/inference-core-v2/app/services/scoring_worker.py`
- `services/inference-stack-v2/inference-core-v2/app/services/scoring_job_service.py`

Prompts:

- `ai_system_prompts`
- `lead_ai_prompts`
- `lead_scoring_prompts`

Documentacion:

- `docs/AGENT_CORE_INDEX.md`
- `docs/AGENT_CORE_DIAGRAMS.md`
- `docs/Manuales/SCORING_V2_SCHEMA.md`

## Regla de lectura para IA

1. entender diagramas y reglas
2. leer contratos en `schemas/agent_core/contracts`
3. leer runtime config en `schemas/agent_core/runtime`
4. leer frontera de `scoring-core`
