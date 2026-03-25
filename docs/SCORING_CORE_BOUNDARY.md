# Scoring Core Boundary

## Objetivo

Desacoplar scoring de `ai-runtime` sin tocar BD ni logica funcional de scoring.

## Regla central

`scoring-core` es duenio de:

- `lead_scoring_jobs`
- `lead_scorecards`
- `lead_score_items`
- `lead_scoring_models`
- `lead_scoring_criteria`
- `lead_scoring_bands`
- `lead_scoring_prompts`

## Lo que se conserva

- tablas actuales
- worker async actual
- `ScoringEngine`
- prompt builder/linter de scoring
- fallback conservador por criterio
- politica anti-stale por `generation`

## Lo que sale de `ai-runtime`

- resolver `scoring_model_id`
- resolver `lead_scoring_prompts`
- hacer `upsert` en `lead_scoring_jobs`
- exponer operaciones de scorecard/job
- conocer detalle del scorecard

## Contrato minimo entre servicios

`ai-runtime` solo debe emitir:

- `conversation_id`
- `lead_id`
- `client_id`

Opcional:

- metadata tecnica de canal

No debe emitir:

- `model_id`
- `prompt_id`
- prompt snapshot
- reglas de scoring

## Fuente de codigo actual

La base funcional a extraer viene de:

- `services/inference-stack-v2/inference-core-v2/app/services/scoring_engine.py`
- `services/inference-stack-v2/inference-core-v2/app/services/scoring_worker.py`
- `services/inference-stack-v2/inference-core-v2/app/services/scoring_job_service.py`
- `services/inference-stack-v2/inference-core-v2/app/repositories/scoring_repository.py`

## Beneficio

`ai-runtime` puede reescribirse o cambiar planner/synth/tools sin afectar scoring.
