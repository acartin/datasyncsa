# Scoring Core API Contract

Contrato de borde para el servicio `scoring-core`.

## Objetivo

Mantener scoring como dominio independiente de `ai-runtime`, conservando la BD y logica actual.

## Endpoints canonicos

- `POST {SCORING_API_PREFIX}/scoring/jobs/enqueue` (interno)
- `GET {SCORING_API_PREFIX}/scoring/jobs/{job_id}`
- `GET {SCORING_API_PREFIX}/leads/{lead_id}/scorecards/latest`
- `GET {SCORING_API_PREFIX}/leads/{lead_id}/scorecards/{scorecard_id}`
- `GET {SCORING_API_PREFIX}/scoring/models/active?client_id=...`
- `GET {SCORING_API_PREFIX}/scoring/ops/summary` (interno, token)
- `GET {SCORING_API_PREFIX}/health`
- `POST {SCORING_API_PREFIX}/cache/invalidate` (interno)

`SCORING_API_PREFIX` recomendado: `/api/v1`.

## Enqueue interno

Request:

```json
{
  "client_id": "019b4872-51f6-72d3-84c9-45183ff700d0",
  "lead_id": "5db698dd-1b64-4a40-b365-c5bcc1553f8e",
  "conversation_id": "9f579ceb-5f9e-45f7-8408-906f6a36e326",
  "channel": "web_html"
}
```

Response:

```json
{
  "id": "de3ce3af-4d74-4af0-b6a0-b4f5683018f5",
  "status": "queued",
  "scheduled_for": "2026-03-12T12:00:00Z"
}
```

## Lectura de scorecards

`GET /leads/{lead_id}/scorecards/latest` devuelve:

- `id`
- `leadId`
- `conversationId`
- `modelId`
- `modelVersion`
- `promptVersion`
- `promptId`
- `scoreTotal`
- `priorityLabel`
- `reasoning`
- `extractionResult`
- `scoreItems`
- `createdAt`

## Lectura de jobs

`GET /scoring/jobs/{job_id}` devuelve:

- `id`
- `leadId`
- `conversationId`
- `clientId`
- `status`
- `attempts`
- `maxAttempts`
- `expectedLeadMessages`
- `scheduledFor`
- `startedAt`
- `finishedAt`
- `lastErrorCode`
- `lastErrorMessage`
- `fallbackUsed`
- `jsonValid`
- `latencyMs`
- `responseChars`

## Consumidores internos detectados (prompt 01)

- `tests/system/test_chat_e2e.py`
  - usa `GET /health`
  - usa `GET /leads/{lead_id}/scorecards/latest`
- `tests/sandbox/realtor/simulate_chat_realtor.py`
  - usa `GET /health`
  - usa `GET /leads/{lead_id}/scorecards/latest`
- `tests/sandbox/dentist/simulate_chat_dentist.py`
  - usa `GET /health`
  - usa `GET /leads/{lead_id}/scorecards/latest`
- tests de integración v2 ya cubren además:
  - `GET /scoring/jobs/{job_id}`
  - `GET /scoring/models/active`
  - `GET /leads/{lead_id}/scorecards/{scorecard_id}`

## Reglas de borde con ai-runtime

- `ai-runtime` no resuelve `scoring_model_id` ni `prompt_id`.
- `ai-runtime` no calcula scorecards.
- `ai-runtime` solo dispara el enqueue con identidad minima del caso.
- `scoring-core` es duenio de jobs, worker, scorecards y modelos/prompts de scoring.
