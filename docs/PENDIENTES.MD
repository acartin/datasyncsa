# Pendientes Scoring V2 (Issues Tecnicos)

Fecha inicial: 2026-02-26  
Ultima actualizacion: 2026-02-27  
Scope: `services/inference-stack-v2/inference-core-v2`

## Estado General

El sistema ya tiene hardening de concurrencia y latencia en scoring async, pero aun faltan tareas de capacidad y operacion para carga sostenida alta.

## Definicion Operativa de Carga Alta

- `capacidad_worker ~= 1 / latencia_promedio_por_job`
- Se considera carga alta cuando la entrada sostenida supera esa capacidad y la cola crece.
- Umbral de alerta 1: `queued + rescheduled > 100` y en crecimiento continuo.
- Umbral de alerta 2: `p95 wait_time (created_at -> started_at) > 30-60s`.
- Umbral de alerta 3: `p95 end_to_end (created_at -> finished_at) > 2x-3x baseline`.
- Umbral de alerta 4: `timeouts LLM` o `failed/degraded` en tendencia ascendente.

## Cambios Aplicados (2026-02-27)

- Job versioning por conversacion: `generation` + `running_generation` en `lead_scoring_jobs`.
- `upsert` incrementa generacion; claim fija `running_generation`.
- `complete/fail/reschedule` condicionales por `running_generation` esperado.
- Re-check de stale antes de persistir scorecard.
- Re-check adicional antes de invocar LLM para evitar ejecucion inutil si el claim ya fue superseded.
- Timeout efectivo capado en scoring LLM (`min(configurado, hard_cap)`).
- Limite de salida del LLM con `max_output_tokens`.
- Debounce de encolado de jobs (`SCORING_JOB_DEBOUNCE_SECS`, default `1.5s`) para coalescer rafagas.
- Endpoint interno de observabilidad operativa: `GET /api/v2/scoring/ops/summary`.
- Concurrencia de worker configurable por env: `SCORING_WORKER_CONCURRENCY` (pool en un proceso worker).

## Validacion Reciente (2026-02-27)

- Suite unitaria: `36 passed`.
- `simulate_multichat_realtor.py --all` completado sin errores.
- Mejora observada: se eliminaron esperas extremas de scorecard de ~50s; wait final estable aprox `12.2s` a `13.8s` en los escenarios corridos.

## Backlog de Issues

### ISSUE-001 - Definir SLO y alertas de scoring async

Estado: IN_PROGRESS (2026-02-27)  
Prioridad: P0  
Problema: No hay SLO operativos explicitados ni alertas por degradacion de cola/latencia.  
Impacto: Degradacion detectada tarde y perdida de confianza en scorecards.  
Avance aplicado:
- Endpoint de resumen operativo disponible en `/api/v2/scoring/ops/summary` (window configurable).
Criterio de aceptacion:
- SLO documentado para `wait_time`, `end_to_end`, `%failed`, `%degraded`.
- Dashboard y alertas con los umbrales de carga alta definidos arriba.
- Runbook de respuesta a incidente.

### ISSUE-002 - Escalar el worker (actualmente secuencial por proceso)

Estado: IN_PROGRESS (2026-02-27)  
Prioridad: P0  
Problema: El worker procesa 1 job por loop/proceso, limitando throughput total.  
Impacto: Cola crece rapidamente cuando suben chats por minuto.  
Avance aplicado:
- Worker pool configurable por `SCORING_WORKER_CONCURRENCY`.
Criterio de aceptacion:
- Concurrency configurable (`WORKER_CONCURRENCY`) o despliegue N workers.
- Prueba de carga con objetivo de throughput definido por SLO.
- Sin regresion de consistencia en jobs y scorecards.

### ISSUE-003 - Corregir posibles carreras en ciclo de vida de jobs

Estado: RESUELTO (2026-02-27)  
Prioridad: P0  
Problema original: Riesgo de carrera entre `upsert` de job por conversacion y `complete` de corrida previa.  
Implementado:
- Mecanismo de version/revision (`generation`/`running_generation`).
- `complete/fail/reschedule` validan que actualizan la corrida reclamada.
- Tests de concurrencia para este flujo.

### ISSUE-004 - Unificar limites transaccionales

Estado: OPEN  
Prioridad: P1  
Problema: Hay commits en repositorio y tambien en capas superiores.  
Impacto: Transacciones fragmentadas, rollback parcial y mayor complejidad operativa.  
Criterio de aceptacion:
- Definir una sola capa dueña de `commit/rollback`.
- Repositorio sin commits implicitos para operaciones del flujo de negocio.
- Tests de atomicidad en rutas criticas.

### ISSUE-005 - Sustituir `NullPool` por pool async ajustado

Estado: OPEN  
Prioridad: P1  
Problema: `NullPool` abre/cierra conexion por uso y penaliza throughput bajo carga.  
Impacto: Mayor latencia y presion sobre Postgres.  
Criterio de aceptacion:
- Pool configurado (`pool_size`, `max_overflow`, `pool_timeout`, `pool_recycle`).
- Medicion comparativa antes/despues (p95 latencia DB y throughput).

### ISSUE-006 - Endurecer observabilidad de pipeline de scoring

Estado: OPEN  
Prioridad: P1  
Problema: Falta instrumentacion estandar de cola y capacidad.  
Impacto: Dificil estimar saturacion real o planificar capacidad.  
Criterio de aceptacion:
- Metricas: queue_depth, claim_rate, completion_rate, retry_rate, stale_rate, timeout_rate.
- Trazas con `job_id`, `conversation_id`, `attempt`, `latency_ms`.
- Panel de capacidad efectiva (`jobs/min`) por worker.

### ISSUE-007 - Prueba de carga reproducible y gate de release

Estado: OPEN  
Prioridad: P1  
Problema: No hay gate obligatorio de rendimiento/confiabilidad previo a release.  
Impacto: Cambios correctos funcionalmente que rompen SLA en runtime.  
Criterio de aceptacion:
- Escenario base de carga (ramp + sustained) versionado.
- Gate CI/CD: falla release si incumple SLO acordado.
- Reporte historico de tendencia por version.

### ISSUE-008 - Parametrizar runtime en Compose para hardening aplicado

Estado: OPEN  
Prioridad: P1  
Problema: El runtime actual de Compose no declara explicitamente `SCORING_LLM_HARD_TIMEOUT_SECS`, `SCORING_LLM_MAX_OUTPUT_TOKENS`, `SCORING_JOB_DEBOUNCE_SECS`.  
Impacto: Riesgo de comportamiento distinto entre ambientes por defaults implícitos.  
Criterio de aceptacion:
- Variables declaradas en compose/env por ambiente.
- Documento de valores recomendados por entorno (dev/staging/prod).
- Verificacion de arranque con log de configuracion efectiva.

## Notas de Implementacion

- Mantener multi-tenant estricto (`client_id`) en todas las consultas operativas.
- No mezclar resultados de performance: reportar separado `latencia LLM`, `latencia DB` y `wait time` de cola.
