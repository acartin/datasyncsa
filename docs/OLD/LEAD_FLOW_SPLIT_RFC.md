# RFC: Rediseño Fuerte de Scoring y Flujos con `inference-stack-v2`

## 0. Directiva Operativa para IAs Ejecutoras (obligatorio leer antes de codificar)

Este documento define un esquema de ejecución multi-IA.  
**Codex (Master Architect)** mantiene la autoridad de diseño y validación final.

Asignación oficial por fase:
- `Qwen-2.5-Coder`: Fases **1 y 4** (SQL, persistencia y API backend admin).
- `DeepSeek-V3`: Fases **2 y 3** (inference engine v2 y rutas de chat/bridges).
- `MiniMax M2.5`: Fases **5 y 6** (frontend dinámico, migración de datos y cutover).

Reglas de coordinación:
1. Ninguna IA cambia el alcance de su fase sin aprobación del Master Architect.
2. Ninguna IA modifica decisiones de modelo de datos fuera de este RFC.
3. Cada fase debe entregar artefactos verificables:
   - código,
   - pruebas,
   - evidencias de ejecución,
   - checklist de aceptación.
4. !
5. Antes de cerrar fase, la IA responsable debe dejar:
   - `CHANGELOG_PHASE_X.md` en `docs/`,
   - lista de riesgos abiertos,
   - instrucciones de rollback de su fase.

Contrato de calidad mínimo por fase:
- Sin regresiones en tests existentes.
- Tests nuevos para funcionalidad nueva.
- Logs y errores sanitizados.
- Multi-tenant isolation preservado.
- Feature flags respetados.

Protocolo de handoff entre IAs:
1. IA saliente deja estado exacto y pendientes.
2. IA entrante no reescribe lo aceptado; solo extiende su fase.
3. Si detecta conflicto estructural, documenta y escala al Master Architect.

## 1. Decisión Ejecutiva

Se adopta un **rediseño fuerte** porque el flujo `realtor` **no está en producción**.

Decisión:
- Crear `inference-stack-v2` como nuevo estándar.
- Mantener el stack actual solo como referencia temporal.
- Rediseñar el modelo de scoring para eliminar acoplamiento rígido en `lead_leads`.
- Migrar el panel de control a consumo de scoring dinámico por tipo de lead.

---

## 2. Problema actual

Hoy el scoring está fuertemente acoplado a `lead_leads`:
- Columnas fijas: `score_engagement`, `score_finance`, `score_timeline`, `score_match`, `score_info`, `score_total`.
- FK fijas a definiciones: `eng_def_id`, `fin_def_id`, `timeline_def_id`, `match_def_id`, `info_def_id`, `priority_def_id`.
- Inference actual escribe directo en ese modelo.
- Admin Console renderiza pilares fijos inmobiliarios.

Este modelo no escala para dominios genéricos (`medico`, `dental`, `automotriz`, etc.).

---

## 3. Objetivo del rediseño

1. Permitir múltiples tipos de lead sin tocar código core por cada vertical.
2. Configurar pilares, pesos, rangos y etiquetas desde DB.
3. Hacer que el panel consuma estructura dinámica de scoring.
4. Conservar trazabilidad/auditoría de evaluaciones por conversación y versión de modelo.

---

## 4. Arquitectura objetivo (v2)

## 4.1 Servicios
- `inference-stack-v2/inference-core-v2`: orquestación + scoring engine configurable.
- `inference-stack-v2/semantic-adapter-v2`: opcionalmente reutilizable del actual en fase inicial.
- Bridges:
  - `realtor-bridge-v2` (si se mantiene ese frontend).
  - `generic-bridge-v2`.

## 4.2 Enrutamiento
- El bridge o gateway enviará `lead_type` y `business_domain`.
- `inference-core-v2` resolverá estrategia de prompt + scoring por configuración DB.

## 4.3 Feature flags
- `scoring_v2_enabled`
- `admin_dynamic_scoring_ui`
- `legacy_scoring_read_compat`

---

## 4.4 Requisitos no funcionales críticos (obligatorios)

### A) Caché de configuración de scoring
No se permite consultar tablas de configuración (`lead_scoring_models`, `lead_scoring_criteria`, `lead_scoring_bands`) en cada mensaje de chat.

Requisito:
- Implementar caché de configuración activa por llave lógica:
  - `(client_id, lead_type, business_domain)` o equivalente.
- Backend sugerido:
  - Redis compartido (preferido) o caché en memoria por proceso con invalidación.
- Definir:
  - TTL corto (ej. 60-300s) + invalidación explícita al publicar cambios de modelo.

Objetivo:
- Evitar presión innecesaria sobre Postgres y reducir latencia p95/p99 del chat.

### B) Versionado de prompts acoplado al modelo de scoring
Si cambian criterios/pesos/bandas, debe quedar trazabilidad del prompt usado para evaluar cada lead.

Requisito:
- Persistir versión de prompt asociada al modelo activo (por ejemplo en `lead_scoring_models` o tabla dedicada `lead_prompt_versions`).
- Guardar en cada `lead_scorecard` referencias inmutables al momento de evaluación:
  - `model_id`, `model_version`, `prompt_version` (o `prompt_id` versionado).

Objetivo:
- Auditoría reproducible: explicar \"con qué reglas y prompt\" fue evaluado un lead histórico.

### C) Transaccionalidad atómica de scorecards
La creación de `lead_scorecards` y `lead_score_items` debe ser una sola unidad atómica.

Requisito:
- En el flujo de persistencia, usar una transacción única para:
  1. insertar scorecard,
  2. insertar todos los items,
  3. actualizar `lead_leads.current_scorecard_id` (si aplica).
- Si falla cualquier paso: `ROLLBACK` completo.

Objetivo:
- Evitar estados corruptos (score total sin desglose de pilares).

---

## 5. Nuevo modelo de datos (desacoplado)

## 5.1 `lead_leads` (mantener como identidad base)
Mantener en esta tabla solo:
- identidad del lead
- tenant/client
- contacto
- ownership/status/workflow
- metadata de origen principal

Agregar:
- `lead_type VARCHAR(32) NOT NULL`
- `business_domain VARCHAR(64) NULL`
- `current_scorecard_id UUID NULL` (opcional para acceso rápido al score vigente)

## 5.2 Nuevas tablas de scoring

### `lead_scoring_models`
Define el modelo activo por tipo/tenant.
- `id`
- `client_id` (nullable para global)
- `lead_type`
- `name`
- `version`
- `is_active`
- `normalization_strategy`
- `created_at`, `updated_at`

### `lead_scoring_criteria`
Define pilares dinámicos.
- `id`
- `model_id`
- `criterion_key` (ej: `intent`, `urgency`, `data_quality`)
- `label`
- `weight`
- `min_score`, `max_score`
- `display_order`
- `is_active`

### `lead_scoring_bands`
Bandas visuales por criterio.
- `id`
- `criterion_id`
- `band_key`
- `label`
- `min_score`, `max_score`
- `icon`
- `color`

### `lead_scorecards`
Una evaluación completa de un lead en un instante.
- `id`
- `lead_id`
- `conversation_id` (nullable)
- `model_id`
- `score_total`
- `priority_label`
- `reasoning`
- `raw_payload JSONB`
- `created_at`

### `lead_score_items`
Detalle por pilar de una scorecard.
- `id`
- `scorecard_id`
- `criterion_key`
- `score`
- `band_id` (nullable)
- `explanation`
- `extracted_data JSONB`

## 5.3 Compatibilidad temporal (si se necesita)
- Mantener columnas legacy en `lead_leads` por un tiempo.
- Poblarlas desde `scorecards` con job/trigger de compatibilidad.
- Retirarlas al final de la migración de panel.

---

## 6. API objetivo v2

## 6.1 Chat
`POST /api/v2/chat`

Request:
- `queryText`
- `clientId`
- `conversationId` (optional)
- `leadType`
- `businessDomain` (optional)
- `userMetadata` (optional)

Response:
- `answer`
- `sources`
- `conversationId`
- `leadId`
- `scorecardId` (optional si scoring async)

## 6.2 Scorecards
- `GET /api/v2/leads/{lead_id}/scorecards/latest`
- `GET /api/v2/leads/{lead_id}/scorecards/{scorecard_id}`
- `GET /api/v2/scoring/models/active?lead_type=...`

## 6.3 Admin configuration
- CRUD de modelos de scoring
- CRUD de criterios
- CRUD de bandas

---

## 7. Impacto en Admin Console

## 7.1 Backend
Reemplazar consultas acopladas a `*_def_id` por:
- join a `lead_scorecards` (latest)
- join a `lead_score_items`
- resolver definición visual por `criterion_key` y banda

## 7.2 Frontend
- Grid de leads dinámico por `lead_type`.
- Columnas/pilares renderizados desde schema del backend.
- El detalle de lead deja de asumir 5 pilares fijos.

## 7.3 Contratos SDUI
Agregar estructura estándar para scoring dinámico:
- `scoring_schema` (columnas/pilares activos)
- `scoring_values` (scores por criterio)
- `score_total`
- `priority`

---

## 8. Plan por fases (completo hasta panel)

## Fase 0: Diseño y baseline (Master Architect)
Objetivo:
- Congelar contrato técnico y métricas base.

Tareas:
1. Congelar baseline de métricas actuales (latencia/error/calidad).
2. Definir contratos v2 (`/api/v2/*`).
3. Definir catálogo inicial de criterios por `lead_type`.
4. Definir contrato de handoff entre fases.

Entregables:
- RFC aprobado.
- Matriz de métricas baseline.
- Esquema de contratos API v2 firmado.

Gate:
- RFC aprobado + contrato API firmado.

## Fase 1: Base de datos v2 (Responsable: Qwen-2.5-Coder)
Objetivo:
- Crear el esquema v2 desacoplado sin romper lectura/escritura actual.

Tareas precisas:
1. Crear migraciones SQL versionadas para:
   - `lead_scoring_models`,
   - `lead_scoring_criteria`,
   - `lead_scoring_bands`,
   - `lead_scorecards`,
   - `lead_score_items`.
2. Alterar `lead_leads` agregando:
   - `lead_type`,
   - `business_domain`,
   - `current_scorecard_id`.
3. Crear constraints e índices de rendimiento.
4. Implementar scripts `up/down` + validación de integridad.
5. Preparar script de seed mínimo de modelos/criterios iniciales.

No permitido:
- Borrar columnas legacy en esta fase.
- Cambiar semántica de tablas fuera del RFC.

Entregables:
- Scripts SQL en carpeta de migraciones.
- Script de seed.
- Documento `docs/CHANGELOG_PHASE_1.md`.

Gate:
- Migraciones up/down validadas en staging.
- Integridad referencial validada.

## Fase 2: Inference Core v2 (Responsable: DeepSeek-V3)
Objetivo:
- Implementar motor de inferencia/scoring configurable, desacoplado de realtor hardcodeado.

Tareas precisas:
1. Crear servicio `services/inference-stack-v2/inference-core-v2`.
2. Implementar `POST /api/v2/chat` con:
   - `leadType` obligatorio,
   - `businessDomain` opcional.
3. Implementar resolución de modelo activo por `(client_id, lead_type, business_domain)`.
4. Implementar caché de configuración:
   - Redis preferido,
   - TTL + invalidación explícita.
5. Persistir scorecard + items en transacción atómica.
6. Persistir referencias de versionado:
   - `model_version`,
   - `prompt_version`.
7. Exponer endpoints:
   - `GET /api/v2/leads/{lead_id}/scorecards/latest`,
   - `GET /api/v2/leads/{lead_id}/scorecards/{scorecard_id}`.

No permitido:
- Consultar configuración en DB por cada mensaje sin caché.
- Persistir scorecard fuera de transacción.

Entregables:
- Servicio funcional `inference-core-v2`.
- Suite de unit/integration tests de engine y transacciones.
- Documento `docs/CHANGELOG_PHASE_2.md`.

Gate:
- Unit tests + integration tests verdes.
- Pruebas de caché y rollback transaccional verdes.

## Fase 3: Bridges v2 y rutas de chat (Responsable: DeepSeek-V3)
Objetivo:
- Conectar canales de chat hacia `api/v2` con payload tipificado.

Tareas precisas:
1. Crear `generic-bridge-v2`.
2. Adaptar/crear `realtor-bridge-v2` si aplica.
3. Garantizar envío de:
   - `lead_type`,
   - `business_domain`,
   - `client_id`.
4. Manejar errores de contrato v2 y observabilidad.
5. Validar tenant isolation extremo a extremo.

Entregables:
- Bridges v2 operativos.
- Pruebas E2E de chat para al menos 2 tipos de lead.
- Documento `docs/CHANGELOG_PHASE_3.md`.

Gate:
- E2E chat v2 funcionando para 2 tipos de lead.
- Contratos v2 respetados.

## Fase 4: Admin backend v2 (Responsable: Qwen-2.5-Coder)
Objetivo:
- Exponer backend de panel para scoring dinámico y configuración de modelos.

Tareas precisas:
1. Endpoint de leads con scoring dinámico (latest scorecard).
2. Endpoint de detalle de lead con desglose por `score_items`.
3. CRUD backend para:
   - modelos,
   - criterios,
   - bandas.
4. Política RBAC estricta para edición de configuración.
5. Contratos SDUI para `scoring_schema` y `scoring_values`.

Entregables:
- Rutas backend admin v2 funcionales.
- Contract tests y pruebas de seguridad.
- Documento `docs/CHANGELOG_PHASE_4.md`.

Gate:
- Contract tests SDUI y seguridad/RBAC verdes.

## Fase 5: Panel de control dinámico (Responsable: MiniMax M2.5)
Objetivo:
- Renderizar UI de scoring por esquema dinámico, sin supuestos realtor.

Tareas precisas:
1. Grid dinámico por `scoring_schema`.
2. Detalle de lead dinámico por criterios activos.
3. Soporte visual de bandas (`icon`, `color`, `label`) por criterio.
4. Fallback controlado si no existe scorecard.
5. Mantener performance de render y filtros.

Entregables:
- Frontend dinámico integrado al backend v2.
- E2E UI completos (grid/detalle/filtros).
- Documento `docs/CHANGELOG_PHASE_5.md`.

Gate:
- E2E UI + regresión UX aprobada.

## Fase 6: Migración de datos, cutover y limpieza (Responsable: MiniMax M2.5)
Objetivo:
- Activar v2 en operación controlada y desactivar dependencia legacy.

Tareas precisas:
1. Crear scripts de migración de datos legacy -> scorecards (si aplica).
2. Activar flags por tenant en rollout progresivo.
3. Monitorear estabilidad y errores por ventana definida.
4. Apagar lectura legacy del panel.
5. Proponer eliminación de compatibilidad legacy (sin ejecutar drop destructivo sin aprobación).

Entregables:
- Scripts de migración de datos validados.
- Plan de cutover ejecutado con evidencia.
- Documento `docs/CHANGELOG_PHASE_6.md`.

Gate:
- Operación estable durante ventana definida.
- Aprobación del Master Architect para cierre final.

---

## 9. Estrategia de pruebas por fase

## 9.1 DB
- tests de migración
- integridad referencial
- rendimiento de queries principales

## 9.2 Core v2
- unit tests del engine de scoring (criterios, bandas, pesos)
- integration tests de chat + persistencia de scorecards
- tenant isolation tests
- tests de caché de configuración (hit/miss/invalidation)
- tests de versionado de prompt en scorecard
- tests transaccionales (rollback total ante fallo en inserción de items)

## 9.3 API/Contract
- contratos de `/api/v2/chat`
- contratos de `/leads/*` para scoring dinámico

## 9.4 UI/E2E
- grid dinámico (render, sort, filtros)
- detalle de lead (pilares variables)
- flujos multi-tenant

---

## 10. Riesgos y mitigación

1. Complejidad de migración alta.
- Mitigar con fases, gates y flags.

2. Inconsistencia entre scorecard latest y lead.
- Mitigar con `current_scorecard_id` + transacciones claras.

3. Sobrecarga de queries dinámicas en panel.
- Mitigar con vistas/materialized views o caché selectiva.

4. Configuraciones inválidas de scoring.
- Mitigar con validaciones server-side antes de activar modelos.

---

## 11. Criterios de aceptación final

1. `inference-stack-v2` procesa chats por `lead_type` sin hardcode por vertical.
2. Scoring se persiste en `scorecards/items` para todos los leads nuevos.
3. Panel muestra scoring dinámico sin depender de columnas fijas legacy.
4. Configuración de pilares se puede cambiar en DB sin despliegue de código.
5. Seguridad y aislamiento tenant se mantienen.

---

## 12. Rollback

1. Flags para volver lectura/escritura al flujo legacy temporal.
2. Mantener servicio actual disponible durante transición.
3. No eliminar columnas legacy hasta estabilizar panel v2.

---

## 13. Checklist operativo para la siguiente IA

1. Crear carpeta de servicio `services/inference-stack-v2/inference-core-v2`.
2. Definir modelos y repositorios v2 desacoplados.
3. Implementar migraciones DB del nuevo esquema.
4. Implementar API `/api/v2/chat` y scorecards endpoints.
5. Implementar scoring engine configurable (models/criteria/bands).
6. Implementar bridges v2 con `lead_type` obligatorio.
7. Adaptar admin backend para scoring dinámico.
8. Adaptar renderer frontend para pilares variables.
9. Crear pruebas por fase + gates de salida.
10. Ejecutar rollout controlado con feature flags.

---

## 14. Nota
Este RFC reemplaza la estrategia incremental previa. El enfoque oficial pasa a ser **rediseño fuerte v2** por no existir tráfico productivo realtor.
