# SCORING V2 Reingenieria Profunda

Fecha: 2026-02-22
Autor: Codex (analisis tecnico + blueprint de ejecucion)

## 1) Diseno tecnico objetivo

### 1.1 Decisiones de negocio (cerradas)

1. El scoring no bloquea chat ni se calcula por turno.
2. El scorecard se calcula post-chat (idle/cierre), orientado al vendedor.
3. `lead_type` queda deprecado; el scope de resolucion es `client_id` + configuracion de cliente/modelo.

### 1.2 Problemas confirmados en el estado actual

1. Fallback heuristico frecuente por timeout de LLM en scoring.
2. Inestabilidad severa de salida JSON estructurada (respuestas largas/invalidas con latencia alta).
3. Prompts activos con defectos de calidad:
   - placeholders inconsistentes (`{conversation_text}` no resuelto por el builder),
   - prompts guardados con `\\n` literal,
   - al menos un prompt activo practicamente vacio.
4. Pipeline de scoring basado en task en memoria del proceso API (fragil para reinicios/escalado).
5. Tests de inference-core-v2 desalineados con el codigo real.

### 1.3 Arquitectura objetivo (post-chat async real)

#### Flujo A: Chat (critico de UX)

1. `POST /api/v2/chat` solo:
   - resuelve contexto tenant (`client_id`),
   - genera respuesta de chat,
   - persiste mensajes/conversacion.
2. Al finalizar el turno, registra/actualiza un `scoring_job` diferido (`scheduled_for = now + idle_window`).
3. Responde sin scorecard, pero con estado:
   - `scoring_status = "pending"`,
   - `scoring_job_id`,
   - `scoring_eta`.

#### Flujo B: Scoring Worker (separado del API)

1. Worker dedicado consume jobs vencidos (`status=queued`, `scheduled_for <= now`).
2. Antes de evaluar:
   - verifica staleness por contadores de conversacion (`lead_messages`),
   - si hay mensajes nuevos, reprograma job (no scorea todavia).
3. Si no hay actividad nueva dentro de ventana de cierre:
   - ejecuta scoring una sola vez para ese corte,
   - persiste scorecard + score_items + metadata de ejecucion,
   - marca job `completed`.
4. Si falla LLM/parse:
   - marca job `failed` o `degraded`,
   - no sobreescribe ultimo scorecard valido con fallback silencioso.

#### Flujo C: Gobernanza de Prompt

1. Todo prompt pasa por lint/validacion antes de activar:
   - placeholders permitidos,
   - longitud minima/maxima,
   - coherencia con criterios activos,
   - JSON contract check.
2. Normalizacion:
   - conversion de `\\n` literal a saltos reales para runtime,
   - rechazo de placeholders no soportados (`conversation_text` dentro del template).

### 1.4 Modelo de estados

#### Job de scoring (`lead_scoring_jobs.status`)

- `queued`
- `running`
- `rescheduled`
- `completed`
- `degraded`
- `failed`
- `cancelled`

#### Scorecard (`lead_scorecards.status`)

- `ready`
- `degraded`

Regla: `ready` es util para ventas; `degraded/failed` es observable y no se disfraza como score confiable.

### 1.5 Contratos API objetivo

#### `POST /api/v2/chat` (respuesta)

- `answer`
- `conversationId`
- `leadId`
- `scorecardId` = `null` (normalmente)
- `scoringStatus` = `pending`
- `scoringJobId` = UUID
- `scoringEta` = timestamp UTC estimado

#### `GET /api/v2/leads/{lead_id}/scorecards/latest`

- si hay score valido: scorecard `status=ready/degraded`
- si aun no termina: `404` actual o (preferido) payload con estado pendiente.

#### Nuevo `GET /api/v2/scoring/jobs/{job_id}`

- estado de job, intentos, error_code/error_message, latencia, parse status.

## 2) Cambios exactos por archivo y fases pequenas

Nota: fases pensadas para PRs cortos, reversibles y testeables.

---

### Fase 1: Contratos y estado visible (sin romper chat)

Objetivo:
- Exponer `scoringStatus/scoringJobId/scoringEta` sin cambiar aun motor de scoring.

Archivos:

1. `services/inference-stack-v2/inference-core-v2/app/models/chat_v2.py`
   - agregar campos en `ChatV2Response`:
     - `scoring_status: Optional[str]`
     - `scoring_job_id: Optional[UUID]`
     - `scoring_eta: Optional[str]`

2. `services/inference-stack-v2/inference-core-v2/app/services/scoring_orchestrator.py`
   - devolver nuevos campos en `process_chat`.
   - mantener `scorecard_id=None` por defecto.

3. `services/inference-stack-v2/inference-core-v2/app/api/chat_v2.py`
   - no cambiar ruta, solo propagar contrato actualizado.

4. `services/generic-bridge-v2/main.py`
   - mapear campos de estado de scoring en respuesta del bridge.

5. `services/realtor-bridge-v2/main.py`
   - mapear campos de estado de scoring en respuesta del bridge.

6. `services/web/realtor-chat/backend/app/core/inference_bridge.py`
   - conservar backward compatibility y anexar campos de estado.

Validacion minima:
- tests de contrato API/bridges.

---

### Fase 2: Infra de job persistente + worker dedicado

Objetivo:
- Sacar scoring de task en memoria del API y moverlo a job persistente.

Archivos nuevos:

1. `migrations/2026-02-22_scoring_jobs_async.sql`
   - crear `lead_scoring_jobs`.
   - indices por (`status`, `scheduled_for`) y (`conversation_id`, `created_at desc`).
   - columnas de telemetria: `latency_ms`, `json_valid`, `fallback_used`, `error_code`, `error_message`.

2. `services/inference-stack-v2/inference-core-v2/app/services/scoring_job_service.py`
   - enqueue/upsert jobs post-chat.
   - reschedule por staleness.

3. `services/inference-stack-v2/inference-core-v2/app/services/scoring_worker.py`
   - loop de consumo y ejecucion de jobs.

4. `services/inference-stack-v2/inference-core-v2/worker.py`
   - entrypoint del worker.

Archivos modificados:

1. `services/inference-stack-v2/inference-core-v2/app/repositories/scoring_repository.py`
   - CRUD de `lead_scoring_jobs`.
   - utilidades de locking por job/conversation.

2. `services/inference-stack-v2/inference-core-v2/app/services/scoring_orchestrator.py`
   - reemplazar scheduler en memoria (`_scheduled_scoring_tasks`) por `enqueue`.

3. `services/inference-stack-v2/inference-core-v2/app/core/config.py`
   - nuevas env vars:
     - `SCORING_IDLE_CLOSE_SECS`
     - `SCORING_WORKER_POLL_SECS`
     - `SCORING_JOB_MAX_ATTEMPTS`
     - `SCORING_JOB_LOCK_TTL_SECS`

4. `docker-compose.yml`
   - agregar servicio `inference-core-v2-worker`.

Validacion minima:
- job se crea en cada chat.
- worker procesa job vencido.
- reinicio del API no pierde jobs.

---

### Fase 3: Hardening de prompt y parse

Objetivo:
- cortar raiz de fallback por prompt/schema inestable.

Archivos nuevos:

1. `services/inference-stack-v2/inference-core-v2/app/services/prompt_linter.py`
   - validaciones:
     - placeholders permitidos,
     - longitud minima/maxima,
     - prohibicion de placeholders no soportados,
     - deteccion de prompt vacio/generico.

Archivos modificados:

1. `services/inference-stack-v2/inference-core-v2/app/services/prompt_builder.py`
   - soportar placeholders oficialmente permitidos.
   - eliminar dependencia implicita de `{conversation_text}` dentro del template.
   - normalizar `\\n` literal a newline.

2. `services/inference-stack-v2/inference-core-v2/app/services/scoring_engine.py`
   - separar:
     - error de LLM,
     - error de parse,
     - resultado degradado.
   - quitar fallback heuristico por defecto (feature-flag opcional).
   - limitar salida y validar JSON contra contrato interno estable.

3. `services/inference-stack-v2/inference-core-v2/app/repositories/scoring_repository.py`
   - exponer metadata de prompt necesaria para lint/auditoria.

4. `services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_service.py`
   - validar prompt al activar/publicar.
   - bloquear activacion de prompt invalido.

Validacion minima:
- prompts invalidos no pueden activarse.
- scoring deja de persistir fallback silencioso como exito.

---

### Fase 4: Observabilidad operativa

Objetivo:
- operar scoring con metricas reales, no ciegas.

Archivos:

1. `services/inference-stack-v2/inference-core-v2/app/services/scoring_worker.py`
   - logs estructurados por `job_id`.

2. `services/inference-stack-v2/inference-core-v2/app/api/chat_v2.py`
   - endpoint `GET /api/v2/scoring/jobs/{job_id}`.

3. `services/inference-stack-v2/inference-core-v2/app/repositories/scoring_repository.py`
   - persistencia de `latency_ms`, `json_valid`, `response_chars`, `error_code`.

Validacion minima:
- trazabilidad completa por job y scorecard.

---

### Fase 5: Reparacion de suite de tests

Objetivo:
- volver a tener red de seguridad real.

Archivos:

1. `services/inference-stack-v2/inference-core-v2/tests/conftest.py`
   - quitar dependencia rota de `Base` inexistente.

2. `services/inference-stack-v2/inference-core-v2/tests/unit/test_scoring_orchestrator.py`
   - alinear con metodos reales (eliminar tests a metodos inexistentes).

3. `services/inference-stack-v2/inference-core-v2/tests/integration/test_api_chat_v2.py`
   - cubrir nuevo contrato de estado de scoring.

4. nuevos tests:
   - `tests/unit/test_prompt_linter.py`
   - `tests/unit/test_scoring_job_service.py`
   - `tests/integration/test_scoring_worker_flow.py`

Validacion minima:
- `docker compose exec -T inference-core-v2 env PYTHONPATH=/app pytest -q tests` en verde.

## Orden sugerido de ejecucion (PRs)

1. PR-1: Fase 1 (contrato + estado pending)
2. PR-2: Fase 2 (jobs persistentes + worker)
3. PR-3: Fase 3 (prompt hardening + parse robusto)
4. PR-4: Fase 4 (observabilidad + endpoint de jobs)
5. PR-5: Fase 5 (tests reales)

## Criterio de exito operativo

1. Chat p95 no depende de scoring.
2. Scoring post-chat con estado auditable por job.
3. Reduccion drástica de `fallback_used`.
4. Sin scorecards "exitosos" cuando el LLM falla/parsea mal.
5. Suite de tests alineada y ejecutable.

## 3) Contrato de slots deterministicos (implementado)

### 3.1 Slots canonicos cerrados

1. `intent`: `unknown | exploring | interested | ready_to_advance`
2. `timeline_bucket`: `unknown | immediate | short_term | mid_term | long_term`
3. `urgency_level`: `unknown | low | medium | high`
4. `budget_bucket`: `unknown | mentioned | quantified`
5. `financing_readiness`: `unknown | partial | approved`
6. `product_fit`: `unknown | weak | medium | strong`
7. `contactability`: `none | partial | full`
8. `data_quality`: `low | medium | high`
9. `engagement_level`: `low | medium | high`

### 3.2 Regla de arquitectura

1. El LLM ya no es fuente de verdad de `scores`.
2. El LLM entrega solo `extracted_data` (+ `slot_hints` opcionales).
3. El backend calcula `slot_state` y `scores` con reglas reproducibles.
4. Las reglas viven en BD (`lead_scoring_prompts.extraction_schema.deterministic_scoring`), no en hardcode de Python.
5. Mismo input de texto + extraccion + config de modelo/prompt -> mismo score siempre.

### 3.3 Matriz deterministica por criterio

1. `intent` <- `intent`
2. `timeline` <- `timeline_bucket`
3. `urgency` <- `urgency_level`
4. `finance` <- `financing_readiness + budget_bucket`
5. `match` <- `product_fit`
6. `data_quality` <- `data_quality`
7. `engagement` <- `engagement_level`

Notas:
1. Los scores internos se calculan en escala 0..10.
2. Luego se escalan al rango configurado de cada criterio (`min_score..max_score`).
3. Cada criterio activo debe tener regla en `criteria_rules`; si falta, el worker falla de forma explicita para evitar scoring opaco.
