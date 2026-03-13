# Scoring V2 Schema Reference

## Estado actual (2026-03-01)

Scoring v2 opera hoy con flujo **async + LLM-first**:

1. `POST /api/v2/chat` responde primero el mensaje conversacional.
2. Se encola/actualiza un job en `lead_scoring_jobs` (unico por `conversation_id`).
3. El worker hace polling y claim atomico del job.
4. El LLM devuelve `scores` + `extracted_data` (y opcionalmente `score_reasons`, `slot_hints`, `confidence`).
5. El backend aplica defaults conservadores por criterio si faltan scores validos.
6. Se hace upsert de `lead_scorecards` + replace de `lead_score_items`.
7. Se actualiza `lead_leads.current_scorecard_id`.

`lead_type` ya no se usa en v2 (fue removido de `lead_leads`). El enrutamiento es por tenant (`client_id`) y contexto `lead_clients.vertical_id + lead_clients.scoring_model_id`.

---

## Principios operativos vigentes

- Resolucion de modelo por tenant: `lead_clients.vertical_id` + `lead_clients.scoring_model_id`.
- Scoring asincrono: el chat no bloquea esperando score.
- Un job por conversacion: `lead_scoring_jobs.conversation_id` es `UNIQUE`.
- Proteccion anti-stale por generacion: `generation` + `running_generation`.
- Trazabilidad: `prompt_id`, `prompt_snapshot`, `raw_payload`, estado de job, latencias.
- Tenancy estricto en lecturas operativas (`client_id`).

---

## Diagrama de entidades

```text
lead_client_verticals (1) ──< lead_scoring_models (N)
                                      │
                                      ├──< lead_scoring_criteria (N)
                                      │         └──< lead_scoring_bands (N)
                                      │
                                      └──< lead_scoring_prompts (N)

lead_clients (1) ──< lead_leads (N) ──< lead_conversations (N)
      │                 │
      │                 ├──< lead_scorecards (N*) ──< lead_score_items (N)
      │                 │
      │                 └──< lead_scoring_jobs (N, UNIQUE conversation_id)
      │
      └── scoring_model_id ───────────> lead_scoring_models.id
```

`N*`: en runtime actual se usa `upsert` de scorecard por lead (no siempre inserta una nueva fila por corrida).

---

## Tablas de configuracion

### `lead_client_verticals`

Define verticales.

Campos clave:
- `id` (PK)
- `name`
- `slug`

### `lead_scoring_models`

Define modelo por vertical.

Campos clave:
- `id` (PK)
- `vertical_id` (FK)
- `name`
- `version`
- `prompt_version` (legacy)
- `is_active`
- `normalization_strategy`
- `business_domain` (opcional, segun datos existentes)

### `lead_scoring_criteria`

Criterios activos del modelo.

Campos clave:
- `model_id`
- `criterion_key`
- `label`
- `weight`
- `min_score`, `max_score`
- `display_order`
- `is_active`

### `lead_scoring_bands`

Bandas visuales por criterio.

Campos clave:
- `criterion_id`
- `band_key`
- `label`
- `min_score`, `max_score`
- `icon`, `color`

### `lead_scoring_prompts`

Prompt activo/versionado por modelo.

Campos clave:
- `id`
- `model_id`
- `version`
- `prompt_template`
- `extraction_schema` (JSONB)
- `is_active`
- `created_by`

#### Placeholders validos en `prompt_template`

- `{vertical_name}`
- `{criteria_text}`
- `{extraction_text}`
- `{business_domain}`
- `{locale}`
- `{timestamp_utc}`

Tokens legacy normalizados en runtime:
- `{conversation_text}` -> eliminado
- `{lead_type}` -> `{vertical_name}`

#### Contrato real de `extraction_schema`

`extraction_schema` hoy soporta estas llaves (segun prompt + engine):

- `fields`: campos de `extracted_data`.
- `response_schema`: override completo del schema esperado del LLM.
- `slot_hints_schema`: schema de `slot_hints` (opcional).
- `scoring_contract`: reglas de fallback para scores faltantes.
- `deterministic_scoring`: configuracion legacy/auxiliar (hoy no gobierna el score final en runtime principal).

Ejemplo de contrato alineado al runtime LLM-first:

```json
{
  "fields": [
    {"key": "extracted_name", "type": "string"},
    {"key": "extracted_email", "type": "string"},
    {"key": "extracted_phone", "type": "string"}
  ],
  "response_schema": {
    "type": "object",
    "required": ["reasoning", "scores", "extracted_data", "confidence"],
    "properties": {
      "reasoning": {"type": "string"},
      "scores": {
        "type": "object",
        "required": ["engagement", "intent", "timeline", "match", "finance"],
        "properties": {
          "engagement": {"type": "number", "minimum": 0, "maximum": 10},
          "intent": {"type": "number", "minimum": 0, "maximum": 10},
          "timeline": {"type": "number", "minimum": 0, "maximum": 10},
          "match": {"type": "number", "minimum": 0, "maximum": 10},
          "finance": {"type": "number", "minimum": 0, "maximum": 10}
        }
      },
      "score_reasons": {"type": "object"},
      "extracted_data": {"type": "object"},
      "slot_hints": {"type": "object"},
      "confidence": {"type": "number", "minimum": 0, "maximum": 1}
    }
  },
  "scoring_contract": {
    "missing_evidence_default_range": {"min": 4, "max": 5}
  }
}
```

---

## Tablas runtime

### `lead_leads`

Lead principal.

Campos relevantes para v2:
- `id`
- `client_id`
- `full_name`, `email`, `phone`
- `business_domain`
- `current_scorecard_id`

Notas:
- `lead_type` fue removido.
- Persisten columnas legacy v1 por compatibilidad historica.

### `lead_conversations`

Conversacion consolidada por lead.

Campos relevantes:
- `id` (uuid interno)
- `conversation_id` (id externo)
- `lead_id`
- `messages` (jsonb)
- `lead_messages`, `bot_messages`, `total_messages`
- `context_snapshot` (snapshot de vertical/modelo/prompt)

### `lead_scoring_jobs`

Cola persistente async (una fila por `conversation_id`).

Campos clave:
- `id`
- `lead_id`
- `conversation_id` (UNIQUE)
- `client_id`
- `model_id`, `prompt_id`
- `generation`
- `running_generation`
- `expected_lead_messages`
- `status`: `queued`, `running`, `rescheduled`, `completed`, `degraded`, `failed`, `cancelled`
- `attempts`, `max_attempts`
- `scheduled_for`, `started_at`, `finished_at`
- `last_error_code`, `last_error_message`
- `fallback_used`, `json_valid`, `latency_ms`, `response_chars`
- `created_at`, `updated_at`

### `lead_scorecards`

Resultado vigente de scoring para lead (upsert).

Campos clave:
- `id`
- `lead_id`
- `conversation_id`
- `model_id`
- `model_version`
- `prompt_version` (legacy)
- `prompt_id`
- `prompt_snapshot`
- `score_total`
- `priority_label`
- `reasoning`
- `extraction_result` (se mergea de forma acumulativa)
- `raw_payload`

### `lead_score_items`

Desglose por criterio.

Campos clave:
- `scorecard_id`
- `criterion_key`
- `score`
- `band_id`
- `explanation`
- `extracted_data`

---

## Flujo de ejecucion real

### 1) Chat request

`POST /api/v2/chat`:

1. Valida `client_id`.
2. Resuelve contexto tenant (`vertical_id`, `scoring_model_id`).
3. Carga modelo activo y prompt activo.
4. Genera respuesta de chat (Gemini + hybrid RAG).
5. Persiste/actualiza conversacion y snapshot.
6. Encola job en `lead_scoring_jobs` con debounce (`SCORING_JOB_DEBOUNCE_SECS`).
7. Retorna respuesta sin bloquear por scoring.

Respuesta incluye:
- `scoring_status`
- `scoring_job_id`
- `scoring_eta`

### 2) Worker async

Worker (`worker.py` + `ScoringWorker`) hace polling (`SCORING_WORKER_POLL_SECS`):

1. Claim del siguiente job runnable.
2. Verifica staleness (`expected_lead_messages` vs contador actual).
3. Verifica ownership por `running_generation`.
4. Construye `conversation_text` con solo turnos de usuario.
5. Llama `ScoringEngine.analyze_conversation(...)`.
6. Persiste scorecard/items.
7. Marca job `completed` o `degraded`.

Si entra un turno nuevo y el job queda viejo, se reschedulea o se descarta la escritura stale.

---

## Contrato LLM de scoring v2 (actual)

El contrato activo es **LLM-first con scores estructurados**.

Payload esperado (minimo practico):

```json
{
  "reasoning": "texto breve",
  "scores": {
    "engagement": 7.5,
    "intent": 8.0,
    "timeline": 5.0,
    "match": 7.0,
    "finance": 6.0
  },
  "extracted_data": {
    "extracted_name": "...",
    "extracted_email": "...",
    "extracted_phone": "..."
  },
  "score_reasons": {
    "intent": "evidencia..."
  },
  "slot_hints": {
    "intent": "interested"
  },
  "confidence": 0.82
}
```

Reglas runtime:
- `scores` y `extracted_data` son requeridos por schema default del engine (o por `response_schema` override).
- Si falta score valido por criterio, backend aplica default conservador (`missing_score_policy` / `scoring_contract`).
- `score_reasons`, `slot_hints`, `reasoning`, `confidence` son opcionales.
- `score_total` se calcula en backend como promedio ponderado por `weight` de criterios.
- El score final **no** sale directo del LLM como total unico.

---

## Variables operativas clave

- `SCORING_BG_ENABLED`
- `SCORING_JOB_DEBOUNCE_SECS` (agenda `scheduled_for`)
- `SCORING_WORKER_POLL_SECS`
- `SCORING_WORKER_CONCURRENCY`
- `SCORING_JOB_MAX_ATTEMPTS`
- `SCORING_JOB_LOCK_TTL_SECS`
- `SCORING_RETRY_DELAY_SECS`
- `SCORING_LLM_TIMEOUT_SECS`
- `SCORING_LLM_HARD_TIMEOUT_SECS`
- `SCORING_LLM_MAX_RETRIES`
- `SCORING_LLM_MAX_OUTPUT_TOKENS`

Compat legacy en config:
- `SCORING_IDLE_CLOSE_SECS` / `SCORING_IDLE_DELAY_SECS` existen como alias, pero el scheduling de jobs usa debounce.

---

## Consultas de verificacion

### Modelo activo por cliente

```sql
SELECT c.id AS client_id, c.vertical_id, c.scoring_model_id, m.name, m.version, m.is_active
FROM lead_clients c
LEFT JOIN lead_scoring_models m ON m.id = c.scoring_model_id
WHERE c.id = :client_id;
```

### Prompt activo + schema

```sql
SELECT p.id, p.model_id, p.version, p.is_active,
       (p.extraction_schema ? 'response_schema') AS has_response_schema,
       (p.extraction_schema ? 'deterministic_scoring') AS has_deterministic
FROM lead_scoring_prompts p
WHERE p.model_id = :model_id
ORDER BY p.version DESC;
```

### Timeline de job async (incluye generacion)

```sql
SELECT id, status, generation, running_generation, attempts,
       scheduled_for, started_at, finished_at, latency_ms, response_chars
FROM lead_scoring_jobs
WHERE conversation_id = :conversation_id
ORDER BY created_at DESC;
```

### Scorecard vigente de un lead

```sql
SELECT id, lead_id, score_total, priority_label, extraction_result, created_at
FROM lead_scorecards
WHERE lead_id = :lead_id
ORDER BY created_at DESC
LIMIT 1;
```

---

## Endpoints relevantes

- `POST /api/v2/chat`
- `GET /api/v2/scoring/jobs/{job_id}`
- `GET /api/v2/scoring/ops/summary` (interno, token si `INTERNAL_API_TOKEN` esta configurado)
- `GET /api/v2/leads/{lead_id}/scorecards/latest`
- `GET /api/v2/leads/{lead_id}/scorecards/{scorecard_id}`
- `GET /api/v2/scoring/models/active?client_id=...`
- `POST /api/v2/cache/invalidate`
- `GET /api/v2/health`
- `POST /api/v2/internal/memory/reset` (interno)

---

## Notas de compatibilidad

- `prompt_version` se conserva por compatibilidad; referencia fuerte: `prompt_id` + `prompt_snapshot`.
- `deterministic_scoring` puede existir en `extraction_schema`, pero el flujo principal actual calcula score desde `scores` del LLM con fallback conservador.
- `extraction_result` se acumula (merge) en `upsert_scorecard` para no perder datos previos validos.

---

## Referencias de implementacion

- `services/inference-stack-v2/inference-core-v2/app/api/chat_v2.py`
- `services/inference-stack-v2/inference-core-v2/app/services/scoring_orchestrator.py`
- `services/inference-stack-v2/inference-core-v2/app/services/scoring_worker.py`
- `services/inference-stack-v2/inference-core-v2/app/services/scoring_engine.py`
- `services/inference-stack-v2/inference-core-v2/app/services/scoring_job_service.py`
- `services/inference-stack-v2/inference-core-v2/app/services/prompt_builder.py`
- `services/inference-stack-v2/inference-core-v2/app/services/prompt_linter.py`
- `services/inference-stack-v2/inference-core-v2/app/repositories/scoring_repository.py`
- `migrations/2026-02-21_drop_lead_type_from_lead_leads.sql`
- `migrations/2026-02-22_create_lead_scoring_jobs.sql`
- `migrations/2026-02-26_add_generation_to_lead_scoring_jobs.sql`
- `migrations/2026-02-26_update_realtor_prompt_v3_llm_first.sql`
- `migrations/2026-02-26_update_lead_scoring_prompts_extraction_only.sql`
