# Scoring V2 Schema Reference

## Estado actual (2026-02-25)

Scoring v2 opera con este flujo real:

1. `POST /api/v2/chat` responde primero el mensaje conversacional.
2. El scoring se agenda en background en `lead_scoring_jobs`.
3. Un worker toma el job luego del idle delay.
4. El LLM extrae datos (`extracted_data`) y hints opcionales (`slot_hints`).
5. El score final se calcula de forma determinista desde `extraction_schema.deterministic_scoring`.
6. Se persiste `lead_scorecards` + `lead_score_items` y se actualiza `lead_leads.current_scorecard_id`.

`lead_type` ya no se usa en v2 (fue removido de `lead_leads`). El enrutamiento es por `client_id`.

---

## Principios de diseño

- Resolución de modelo por tenant: `lead_clients.vertical_id` + `lead_clients.scoring_model_id`.
- Prompt orientado a extracción, no a scoring numérico.
- Scoring determinista y configurable por BD.
- Scoring asíncrono e invisible para el usuario final de chat.
- Trazabilidad completa: `prompt_id`, `prompt_snapshot`, `raw_payload`, estado de job y latencias.

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
      │                 ├──< lead_scorecards (N) ──< lead_score_items (N)
      │                 │
      │                 └──< lead_scoring_jobs (N)
      │
      └── scoring_model_id ───────────> lead_scoring_models.id
```

---

## Tablas de configuración

### `lead_client_verticals`

Define verticales (industria).

Campos clave:
- `id` (PK)
- `name`
- `slug`

### `lead_scoring_models`

Define modelo de scoring por vertical/tenant scope.

Campos clave:
- `id` (PK)
- `vertical_id` (FK)
- `business_domain` (opcional)
- `name`
- `version`
- `prompt_version` (legacy numérico)
- `is_active`
- `normalization_strategy`

Relación tenant:
- `lead_clients.scoring_model_id` apunta al modelo que debe usar ese cliente.

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

Prompt versionado por modelo.

Campos clave:
- `id`
- `model_id`
- `version`
- `prompt_template`
- `extraction_schema` (JSONB)
- `is_active`
- `created_by`

#### Placeholders válidos en `prompt_template`

- `{vertical_name}`
- `{criteria_text}`
- `{extraction_text}`
- `{business_domain}`
- `{locale}`
- `{timestamp_utc}`

Tokens legacy normalizados en runtime:
- `{conversation_text}` -> eliminado
- `{lead_type}` -> `{vertical_name}`

#### Contrato de `extraction_schema`

`extraction_schema` soporta:
- `fields` o `properties`: campos a extraer.
- `deterministic_scoring`: reglas para slots y scoring final.

Ejemplo mínimo:

```json
{
  "fields": [
    {"key": "extracted_name", "type": "string", "description": "Nombre"},
    {"key": "extracted_email", "type": "string", "description": "Correo"},
    {"key": "extracted_phone", "type": "string", "description": "Telefono"}
  ],
  "deterministic_scoring": {
    "slots": {
      "intent": {
        "default": "unknown",
        "rules": [
          {"set": "ready_to_advance", "contains_any": ["agendar", "visitar"]},
          {"set": "interested", "contains_any": ["me interesa", "precio"]}
        ]
      }
    },
    "derived_slots": [
      {
        "slot": "contactability",
        "type": "count_present_fields",
        "fields": ["extracted_name", "extracted_email", "extracted_phone"],
        "default": "none",
        "thresholds": [
          {"min": 2, "set": "full"},
          {"min": 1, "set": "partial"}
        ]
      }
    ],
    "criteria_rules": {
      "intent": {
        "type": "slot_map",
        "slot": "intent",
        "default": 3.0,
        "mapping": {
          "ready_to_advance": 9.0,
          "interested": 7.0,
          "unknown": 3.0
        }
      }
    }
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
- `lead_type` fue removido de esta tabla.
- Siguen existiendo columnas legacy v1 (`score_engagement`, `score_finance`, etc.) por compatibilidad.

### `lead_conversations`

Conversación consolidada por lead.

Campos relevantes:
- `id` (uuid interno)
- `conversation_id` (id externo de sesión)
- `lead_id`
- `messages` (jsonb)
- `lead_messages`, `bot_messages`, `total_messages`
- `context_snapshot` (snapshot de vertical/modelo/prompt)

### `lead_scoring_jobs`

Cola persistente de scoring async.

Campos clave:
- `id`
- `lead_id`
- `conversation_id` (UNIQUE)
- `client_id`
- `model_id`, `prompt_id`
- `expected_lead_messages`
- `status`: `queued`, `running`, `rescheduled`, `completed`, `degraded`, `failed`, `cancelled`
- `attempts`, `max_attempts`
- `scheduled_for`, `started_at`, `finished_at`
- `last_error_code`, `last_error_message`
- `fallback_used`, `json_valid`, `latency_ms`, `response_chars`

### `lead_scorecards`

Resultado final por corrida de scoring.

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
- `extraction_result`
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

## Flujo de ejecución

### 1) Chat request

`POST /api/v2/chat`:

1. Valida `client_id`.
2. Resuelve contexto tenant (`vertical_id` y `scoring_model_id`).
3. Carga modelo activo y prompt activo.
4. Genera respuesta de chat (Gemini + RAG).
5. Persiste mensaje y actualiza lead.
6. Encola job en `lead_scoring_jobs` con `scheduled_for = now + SCORING_IDLE_CLOSE_SECS`.
7. Retorna respuesta sin bloquear por scoring.

Respuesta incluye:
- `scoring_status`
- `scoring_job_id`
- `scoring_eta`

### 2) Worker async

Worker (`worker.py` + `ScoringWorker`) hace polling (`SCORING_WORKER_POLL_SECS`):

1. Claim del siguiente job runnable.
2. Verifica staleness (`expected_lead_messages` vs contador actual).
3. Construye `conversation_text` con solo turnos de usuario.
4. Llama `ScoringEngine.analyze_conversation(...)`.
5. Persiste `lead_scorecards` + `lead_score_items`.
6. Marca job `completed` o `degraded`.

---

## Contrato LLM de scoring v2

El LLM no decide el score final. Solo extrae señales.

Payload esperado del LLM:

```json
{
  "reasoning": "texto breve",
  "extracted_data": {
    "extracted_name": "...",
    "extracted_email": "...",
    "extracted_phone": "..."
  },
  "slot_hints": {
    "intent": "interested"
  },
  "confidence": 0.82
}
```

Reglas:
- `extracted_data` es requerido.
- `slot_hints`, `reasoning` y `confidence` son opcionales.
- No se espera objeto `scores` desde el LLM.
- El score final se calcula con `deterministic_scoring.criteria_rules`.

---

## Variables operativas clave

- `SCORING_BG_ENABLED`
- `SCORING_IDLE_CLOSE_SECS` (alias legacy: `SCORING_IDLE_DELAY_SECS`)
- `SCORING_WORKER_POLL_SECS`
- `SCORING_JOB_MAX_ATTEMPTS`
- `SCORING_JOB_LOCK_TTL_SECS`
- `SCORING_RETRY_DELAY_SECS`

---

## Consultas de verificación

### Modelo activo por cliente

```sql
SELECT c.id AS client_id, c.vertical_id, c.scoring_model_id, m.name, m.version, m.is_active
FROM lead_clients c
LEFT JOIN lead_scoring_models m ON m.id = c.scoring_model_id
WHERE c.id = :client_id;
```

### Prompt activo + deterministic config

```sql
SELECT p.id, p.model_id, p.version, p.is_active,
       (p.extraction_schema ? 'deterministic_scoring') AS has_deterministic
FROM lead_scoring_prompts p
WHERE p.model_id = :model_id
ORDER BY p.version DESC;
```

### Timeline de job async

```sql
SELECT id, status, attempts, scheduled_for, started_at, finished_at, latency_ms, response_chars
FROM lead_scoring_jobs
WHERE conversation_id = :conversation_id
ORDER BY created_at DESC;
```

### Último scorecard

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
- `GET /api/v2/leads/{lead_id}/scorecards/latest`
- `GET /api/v2/leads/{lead_id}/scorecards/{scorecard_id}`
- `GET /api/v2/scoring/models/active?client_id=...`
- `POST /api/v2/cache/invalidate`

---

## Notas de compatibilidad

- `prompt_version` se conserva por compatibilidad histórica, pero la referencia exacta es `prompt_id` + `prompt_snapshot`.
- Columnas v1 de score en `lead_leads` siguen presentes por compatibilidad, pero v2 persiste en `lead_scorecards` y `lead_score_items`.
- Las plantillas de prompt en BD deben ser de extracción (no scoring numérico).

---

## Referencias de implementación

- `services/inference-stack-v2/inference-core-v2/app/services/scoring_orchestrator.py`
- `services/inference-stack-v2/inference-core-v2/app/services/scoring_worker.py`
- `services/inference-stack-v2/inference-core-v2/app/services/scoring_engine.py`
- `services/inference-stack-v2/inference-core-v2/app/services/deterministic_scoring.py`
- `services/inference-stack-v2/inference-core-v2/app/services/prompt_linter.py`
- `services/inference-stack-v2/inference-core-v2/app/repositories/scoring_repository.py`
- `migrations/2026-02-21_drop_lead_type_from_lead_leads.sql`
- `migrations/2026-02-22_create_lead_scoring_jobs.sql`
- `migrations/2026-02-25_seed_deterministic_scoring_config.sql`
- `migrations/2026-02-26_update_lead_scoring_prompts_extraction_only.sql`
