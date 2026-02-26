# Pendientes Scoring V2 (Issues Tecnicos)

Fecha: 2026-02-26
Scope: `services/inference-stack-v2/inference-core-v2`

## Estado

El sistema funciona en carga baja/media, pero requiere hardening para sostener concurrencia, latencia y confiabilidad bajo carga alta.

## Definicion Operativa de Carga Alta

- `capacidad_worker ~= 1 / latencia_promedio_por_job`
- Se considera carga alta cuando la entrada sostenida supera esa capacidad y la cola crece.
- Umbral de alerta 1: `queued + rescheduled > 100` y en crecimiento continuo.
- Umbral de alerta 2: `p95 wait_time (created_at -> started_at) > 30-60s`.
- Umbral de alerta 3: `p95 end_to_end (created_at -> finished_at) > 2x-3x baseline`.
- Umbral de alerta 4: `timeouts LLM` o `failed/degraded` en tendencia ascendente.

## Backlog de Issues

### ISSUE-001 - Definir SLO y alertas de scoring async

Prioridad: P0  
Problema: No hay SLO operativos explicitados ni alertas por degradacion de cola/latencia.  
Impacto: Degradacion detectada tarde y perdida de confianza en scorecards.  
Criterio de aceptacion:
- SLO documentado para `wait_time`, `end_to_end`, `%failed`, `%degraded`.
- Dashboard y alertas con los umbrales de carga alta definidos arriba.
- Runbook de respuesta a incidente.

### ISSUE-002 - Escalar el worker (actualmente secuencial por proceso)

Prioridad: P0  
Problema: El worker procesa 1 job por loop/proceso, limitando throughput total.  
Impacto: Cola crece rapidamente cuando suben chats por minuto.  
Criterio de aceptacion:
- Concurrency configurable (`WORKER_CONCURRENCY`) o despliegue N workers.
- Prueba de carga con objetivo de throughput definido por SLO.
- Sin regresion de consistencia en jobs y scorecards.

### ISSUE-003 - Corregir posibles carreras en ciclo de vida de jobs

Prioridad: P0  
Problema: Riesgo de carrera entre `upsert` de job por conversacion y `complete` de corrida previa.  
Impacto: Estados inconsistentes (`queued/running/completed`) y trazabilidad confusa.  
Criterio de aceptacion:
- Mecanismo de version/revision de job o token de ejecucion.
- `complete/fail/reschedule` validan que actualizan la misma corrida reclamada.
- Tests de concurrencia para este flujo.

### ISSUE-004 - Unificar limites transaccionales

Prioridad: P1  
Problema: Hay commits en repositorio y tambien en capas superiores.  
Impacto: Transacciones fragmentadas, rollback parcial y mayor complejidad operativa.  
Criterio de aceptacion:
- Definir una sola capa dueña de `commit/rollback`.
- Repositorio sin commits implicitos para operaciones del flujo de negocio.
- Tests de atomicidad en rutas criticas.

### ISSUE-005 - Sustituir `NullPool` por pool async ajustado

Prioridad: P1  
Problema: `NullPool` abre/cierra conexion por uso y penaliza throughput bajo carga.  
Impacto: Mayor latencia y presion sobre Postgres.  
Criterio de aceptacion:
- Pool configurado (`pool_size`, `max_overflow`, `pool_timeout`, `pool_recycle`).
- Medicion comparativa antes/despues (p95 latencia DB y throughput).

### ISSUE-006 - Endurecer observabilidad de pipeline de scoring

Prioridad: P1  
Problema: Falta instrumentacion estandar de cola y capacidad.  
Impacto: Dificil estimar saturacion real o planificar capacidad.  
Criterio de aceptacion:
- Metricas: queue_depth, claim_rate, completion_rate, retry_rate, stale_rate, timeout_rate.
- Trazas con `job_id`, `conversation_id`, `attempt`, `latency_ms`.
- Panel de capacidad efectiva (`jobs/min`) por worker.

### ISSUE-007 - Prueba de carga reproducible y gate de release

Prioridad: P1  
Problema: No hay gate obligatorio de rendimiento/confiabilidad previo a release.  
Impacto: Cambios correctos funcionalmente que rompen SLA en runtime.  
Criterio de aceptacion:
- Escenario base de carga (ramp + sustained) versionado.
- Gate CI/CD: falla release si incumple SLO acordado.
- Reporte historico de tendencia por version.

## Notas de Implementacion

- Mantener multi-tenant estricto (`client_id`) en todas las consultas operativas.
- No mezclar resultados de performance: reportar separado `latencia LLM`, `latencia DB` y `wait time` de cola.
