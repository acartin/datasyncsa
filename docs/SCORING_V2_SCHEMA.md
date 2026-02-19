# Scoring V2 Schema Reference

## Overview

El sistema de scoring v2 introduce un modelo dinámico y configurable por vertical, reemplazando los scores fijos (v1) almacenados directamente en `lead_leads`.

**Principio clave:** Los modelos de scoring se configuran por `vertical_id`, no por `client_id`. Esto permite reutilizar modelos entre clientes de la misma industria.

---

## Diagrama de Entidades

```
┌─────────────────────────┐
│ lead_client_verticals   │
├─────────────────────────
│ id (PK)                 │
│ name: "Healthcare"      │
│ slug: "healthcare"      │
└───────────┬─────────────┘
            │
            │ 1:N
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      lead_scoring_models                            │
├─────────────────────────────────────────────────────────────────────┤
│ id (PK)                                                             │
│ vertical_id (FK)                                                    │
│ business_domain: null | "premium" | "basic"                        │
│ name: "Medico Default v1"                                          │
│ version: 1                                                          │
│ prompt_version: 1                                                   │
│ is_active: true                                                     │
│ normalization_strategy: "weighted_average"                          │
└───────────┬─────────────────────────────────────────────────────────┘
            │
            ├──────────────────────────────┐
            │ 1:N (CASCADE DELETE)         │
            ▼                              ▼
┌───────────────────────────┐   ┌─────────────────────────────────────┐
│ lead_scoring_criteria     │   │       lead_scoring_prompts          │
├───────────────────────────┤   ├─────────────────────────────────────┤
│ id (PK)                   │   │ id (PK)                             │
│ model_id (FK)             │   │ model_id (FK)                       │
│ criterion_key: "intent"   │   │ version: 1                          │
│ label: "Intent"           │   │ prompt_template: TEXT               │
│ weight: 1.0               │   │ extraction_schema: JSONB            │
│ min_score: 0.0            │   │ is_active: true                     │
│ max_score: 10.0           │   │ created_by: uuid                    │
│ display_order: 1          │   └─────────────────────────────────────┘
│ is_active: true           │              │
└───────────┬───────────────┘              │ referencia
            │ 1:N (CASCADE)                │
            ▼                              │
┌───────────────────────────────────────┐  │
│         lead_scoring_bands            │  │
├───────────────────────────────────────┤  │
│ id (PK)                               │  │
│ criterion_id (FK)                     │  │
│ band_key: "low" | "medium" | "high"   │  │
│ label: "Low"                          │  │
│ min_score: 0.0                        │  │
│ max_score: 3.0                        │  │
│ icon: "thumb_down"                    │  │
│ color: "#ef4444"                      │  │
└───────────────────────────────────────┘  │
                                           │
┌──────────────────────────────────────────┼───────────────────────────┐
│                           lead_leads     │                           │
├──────────────────────────────────────────┼───────────────────────────┤
│ id (PK)                                  │                           │
│ client_id (FK)                           │                           │
│ full_name, email, phone, ...             │                           │
│ lead_type: "healthcare" (legacy)         │                           │
│ business_domain: null | "premium"        │                           │
│ current_scorecard_id (FK) ───────────────┼───────┐                   │
│                                          │       │                   │
│ ─── Columnas legacy (v1, deprecadas) ─── │       │                   │
│ score_engagement, score_finance, ...     │       │                   │
└──────────────────────────────────────────┼───────┼───────────────────┘
                                           │       │
            ┌──────────────────────────────┘       │
            │ 1:N (CASCADE DELETE)                  │
            ▼                                       │
┌───────────────────────────────────────────────────┴───────────────────┐
│                       lead_scorecards                                  │
├────────────────────────────────────────────────────────────────────────┤
│ id (PK)                                                                │
│ lead_id (FK)                                                           │
│ conversation_id (opcional)                                             │
│ model_id (FK)                                                          │
│ model_version: 1                         ← snapshot del modelo         │
│ prompt_version: 1                        ← snapshot numérico (legacy)  │
│ prompt_id (FK)                           ← referencia al prompt usado   │
│ prompt_snapshot: TEXT                    ← COPIA para reproducibilidad │
│ score_total: 3.75                                                      │
│ priority_label: "medium"                                               │
│ reasoning: "Lead analyzed using..."                                    │
│ extraction_result: JSONB                 ← datos extraídos             │
│ raw_payload: { metadata }                                              │
│ created_at                                                              │
└───────────┬─────────────────────────────────────────────────────────────┘
            │
            │ 1:N (CASCADE DELETE)
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      lead_score_items                               │
├─────────────────────────────────────────────────────────────────────┤
│ id (PK)                                                             │
│ scorecard_id (FK)                                                   │
│ criterion_key: "intent"                                             │
│ score: 4.0                                                          │
│ band_id (FK)                                                        │
│ explanation: "Score calculated based on..."                        │
│ extracted_data: { "confidence": 0.85 }                             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Tablas de Configuración (definidas una vez por vertical)

### `lead_client_verticals`

Define las verticales/industrias del sistema.

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | int | PK auto-incremental |
| `name` | varchar(100) | Nombre legible: "Healthcare", "Real Estate" |
| `slug` | varchar(100) | Identificador URL-safe: "healthcare" |

**Ejemplos:**
```sql
SELECT * FROM lead_client_verticals;

 id |     name      |    slug     
----+---------------+-------------
  1 | Real Estate   | real_estate
  2 | Automotive    | automotive
  8 | Healthcare    | healthcare
```

---

### `lead_scoring_models`

Define un modelo de scoring completo para una vertical.

| Columna | Tipo | Nullable | Descripción |
|---------|------|----------|-------------|
| `id` | uuid | NO | PK |
| `vertical_id` | int | NO | FK a `lead_client_verticals.id` |
| `business_domain` | varchar(64) | YES | Sub-ámbito opcional (ej: "premium") |
| `name` | varchar(128) | NO | Nombre del modelo |
| `version` | int | NO | Versión del modelo (default: 1) |
| `prompt_version` | int | NO | Versión del prompt LLM usado |
| `is_active` | boolean | NO | Solo UN activo por (vertical + domain) |
| `normalization_strategy` | varchar(64) | YES | "weighted_average", "sum" |

**Constraints importantes:**
- `uq_lead_scoring_models_active_scope`: Solo un modelo activo por `(vertical_id, COALESCE(business_domain, ''))`

**Ejemplo:**
```sql
SELECT id, vertical_id, name, version, is_active 
FROM lead_scoring_models;

                  id                  | vertical_id |        name         | version | is_active 
--------------------------------------+-------------+---------------------+---------+-----------
 53fe9e76-09e6-46af-a934-bc2c602c256b |           1 | Realtor Default v1  |       1 | t
 23dbbd82-8ab6-4122-8d38-0528c0fa3cb5 |           8 | Dentista1 Medico v1 |       1 | t
```

---

### `lead_scoring_criteria`

Define los criterios individuales de scoring dentro de un modelo.

| Columna | Tipo | Nullable | Descripción |
|---------|------|----------|-------------|
| `id` | uuid | NO | PK |
| `model_id` | uuid | NO | FK a `lead_scoring_models.id` (CASCADE) |
| `criterion_key` | varchar(64) | NO | Key técnica: "intent", "urgency" |
| `label` | varchar(128) | NO | Label para UI: "Intent" |
| `weight` | numeric(5,2) | NO | Peso para promedio ponderado (default: 1.0) |
| `min_score` | numeric(5,2) | NO | Score mínimo (default: 0.0) |
| `max_score` | numeric(5,2) | NO | Score máximo (default: 10.0) |
| `display_order` | int | NO | Orden visual |
| `is_active` | boolean | NO | Criterio activo |

**Constraint:** `(model_id, criterion_key)` es único.

**Ejemplo:**
```sql
SELECT criterion_key, label, weight, min_score, max_score, display_order
FROM lead_scoring_criteria
WHERE model_id = '23dbbd82-8ab6-4122-8d38-0528c0fa3cb5'
ORDER BY display_order;

 criterion_key |    label     | weight | min_score | max_score | display_order 
---------------+--------------+--------+-----------+-----------+---------------
 intent        | Intent       |   1.00 |      0.00 |     10.00 |             1
 urgency       | Urgency      |   1.00 |      0.00 |     10.00 |             2
 data_quality  | Data Quality |   1.00 |      0.00 |     10.00 |             3
 engagement    | Engagement   |   1.00 |      0.00 |     10.00 |             4
```

---

### `lead_scoring_bands`

Define las bandas/rangos visuales para cada criterio.

| Columna | Tipo | Nullable | Descripción |
|---------|------|----------|-------------|
| `id` | uuid | NO | PK |
| `criterion_id` | uuid | NO | FK a `lead_scoring_criteria.id` (CASCADE) |
| `band_key` | varchar(32) | NO | Key: "low", "medium", "high" |
| `label` | varchar(64) | NO | Label UI: "Low", "Medium", "High" |
| `min_score` | numeric(5,2) | NO | Límite inferior |
| `max_score` | numeric(5,2) | NO | Límite superior |
| `icon` | varchar(128) | YES | Icono Material Icons |
| `color` | varchar(32) | YES | Color hexadecimal |

**Constraint:** `(criterion_id, band_key)` es único.

**Ejemplo:**
```sql
SELECT c.criterion_key, b.band_key, b.label, b.min_score, b.max_score, b.icon, b.color
FROM lead_scoring_bands b
JOIN lead_scoring_criteria c ON c.id = b.criterion_id
WHERE c.model_id = '23dbbd82-8ab6-4122-8d38-0528c0fa3cb5'
ORDER BY c.display_order, b.min_score;

 criterion_key | band_key | label  | min_score | max_score | icon                     | color    
---------------+----------+--------+-----------+-----------+--------------------------+---------
 intent        | low      | Low    |      0.00 |      3.00 | thumb_down               | #ef4444
 intent        | medium   | Medium |      3.00 |      7.00 | thumb_up                 | #f59e0b
 intent        | high     | High   |      7.00 |     10.00 | star                     | #22c55e
 urgency       | low      | Low    |      0.00 |      3.00 | schedule                 | #ef4444
 urgency       | medium   | Medium |      3.00 |      7.00 | event                    | #f59e0b
 urgency       | high     | High   |      7.00 |     10.00 | bolt                     | #22c55e
 ...
```

---

### `lead_scoring_prompts`

Define los prompts versionados para cada modelo de scoring. Permite auditoría reproducible.

| Columna | Tipo | Nullable | Descripción |
|---------|------|----------|-------------|
| `id` | uuid | NO | PK |
| `model_id` | uuid | NO | FK a `lead_scoring_models.id` (CASCADE) |
| `version` | int | NO | Versión del prompt (incremental) |
| `prompt_template` | text | NO | Template con placeholders: `{criteria}`, `{bands}`, `{vertical}` |
| `extraction_schema` | jsonb | YES | Schema de campos a extraer por vertical |
| `is_active` | boolean | NO | Solo UN prompt activo por modelo |
| `created_at` | timestamptz | NO | Timestamp de creación |
| `updated_at` | timestamptz | NO | Timestamp de actualización |
| `created_by` | uuid | YES | Usuario que creó el prompt (auditoría) |

**Constraint:** `(model_id, version)` es único.

**Ejemplo de `extraction_schema`:**
```json
{
  "fields": [
    {"key": "extracted_name", "type": "string", "description": "Nombre completo del usuario"},
    {"key": "extracted_email", "type": "string", "description": "Email del usuario"},
    {"key": "extracted_phone", "type": "string", "description": "Teléfono del usuario"},
    {"key": "extracted_insurance", "type": "string", "description": "Seguro médico (solo healthcare)"},
    {"key": "extracted_appointment_type", "type": "string", "description": "Tipo de cita (solo healthcare)"}
  ]
}
```

**Ejemplo:**
```sql
SELECT id, model_id, version, is_active, created_at
FROM lead_scoring_prompts
WHERE model_id = '23dbbd82-8ab6-4122-8d38-0528c0fa3cb5'
ORDER BY version DESC;

                  id                  |              model_id               | version | is_active |          created_at           
--------------------------------------+--------------------------------------+---------+-----------+-------------------------------
 a1b2c3d4-5678-90ab-cdef-1234567890ab | 23dbbd82-8ab6-4122-8d38-0528c0fa3cb5 |       2 | t         | 2026-02-18 22:00:00+00
 b2c3d4e5-6789-01bc-def0-2345678901bc | 23dbbd82-8ab6-4122-8d38-0528c0fa3cb5 |       1 | f         | 2026-02-15 10:00:00+00
```

---

## Tablas de Runtime (se poblan con cada interacción)

### `lead_leads`

Tabla principal de leads. Ver nota sobre columnas legacy.

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | uuid | PK |
| `client_id` | uuid | FK a `lead_clients.id` |
| `full_name` | varchar(255) | Nombre del lead |
| `lead_type` | varchar(32) | **Legacy v1.** Derivado de vertical_slug. Ignorado en v2. |
| `business_domain` | varchar(64) | Sub-ámbito opcional |
| `current_scorecard_id` | uuid | FK al scorecard más reciente |

**Columnas legacy (v1, deprecadas):**
- `lead_type`: Redundante con `vertical_id`. Se deriva automáticamente del vertical pero no se usa en scoring v2.
- `score_engagement`, `score_finance`, `score_timeline`, `score_match`, `score_info`, `score_total`
- Mantener para backwards compatibility, pero no usar en v2.

**Nota:** En v2, el scoring se resuelve exclusivamente por `client_id` → `lead_clients.vertical_id` → `lead_scoring_models.vertical_id`.

---

### `lead_scorecards`

Almacena el resultado de scoring de un lead en un momento dado.

| Columna | Tipo | Nullable | Descripción |
|---------|------|----------|-------------|
| `id` | uuid | NO | PK |
| `lead_id` | uuid | NO | FK a `lead_leads.id` (CASCADE) |
| `conversation_id` | uuid | YES | Referencia a la conversación |
| `model_id` | uuid | NO | FK a `lead_scoring_models.id` |
| `model_version` | int | NO | Snapshot de versión del modelo |
| `prompt_version` | int | NO | Snapshot de versión del prompt (numérico, legacy) |
| `prompt_id` | uuid | YES | FK a `lead_scoring_prompts.id` (referencia exacta) |
| `prompt_snapshot` | text | YES | **Copia del prompt** para reproducibilidad |
| `score_total` | numeric(5,2) | NO | Score total calculado |
| `priority_label` | varchar(32) | YES | "low", "medium", "high" |
| `reasoning` | text | YES | Explicación general del LLM |
| `extraction_result` | jsonb | YES | Datos extraídos de la conversación |
| `raw_payload` | jsonb | YES | Metadatos adicionales |
| `created_at` | timestamptz | NO | Timestamp de creación |

**Importante:** 
- Un lead puede tener múltiples scorecards (historial). El más reciente está referenciado en `lead_leads.current_scorecard_id`.
- `prompt_snapshot` contiene una **copia exacta** del prompt usado, permitiendo reproducir el scoring históricamente aunque el prompt haya cambiado.

---

### `lead_score_items`

Desglose individual de cada criterio dentro de un scorecard.

| Columna | Tipo | Nullable | Descripción |
|---------|------|----------|-------------|
| `id` | uuid | NO | PK |
| `scorecard_id` | uuid | NO | FK a `lead_scorecards.id` (CASCADE) |
| `criterion_key` | varchar(64) | NO | Criterio evaluado |
| `score` | numeric(5,2) | NO | Score asignado |
| `band_id` | uuid | YES | FK a `lead_scoring_bands.id` |
| `explanation` | text | YES | Explicación del LLM |
| `extracted_data` | jsonb | YES | Datos extraídos relacionados |

**Constraint:** `(scorecard_id, criterion_key)` es único.

---

## Flujo de Datos

### 1. Configuración (una vez por vertical)

```
lead_client_verticals
     ↓ crear
lead_scoring_models (activo)
     ↓ definir
lead_scoring_criteria (4-5 criterios)
     ↓ configurar
lead_scoring_bands (3 bandas por criterio)
```

### Requerimiento No Funcional: Scoring Invisible para el Usuario Final

El usuario que está chateando **no debe percibir** el proceso de scoring.

Directrices obligatorias:
- `POST /api/v2/chat` responde inmediatamente con la respuesta conversacional.
- El scoring se ejecuta **siempre en background** (cola/worker), sin bloquear la respuesta del chat.
- El frontend de chat no espera `scorecard_id` ni estado de scoring.
- Errores de scoring no se propagan al usuario final de chat; se manejan por observabilidad interna.

Requisitos técnicos derivados:
- Usar procesamiento asíncrono con reintentos controlados y DLQ.
- Garantizar idempotencia para evitar scorecards duplicados (por ejemplo con llave lógica por conversación/modelo).
- Persistir trazabilidad técnica en logs y métricas para diagnóstico.
- Exponer resultados de scoring únicamente a backoffice/admin.

### 2. Runtime (por cada mensaje de chat)

```
POST /api/v2/chat { queryText, clientId }
     ↓
1. Resolver vertical desde client_id
   SELECT vertical_id FROM lead_clients WHERE id = :client_id
     ↓
2. Buscar modelo activo
   SELECT * FROM lead_scoring_models 
   WHERE vertical_id = :vertical_id AND is_active = true
     ↓
3. Crear/actualizar lead
   INSERT/UPDATE lead_leads
     ↓
4. Calcular scores con modelo + LLM
     ↓
5. Persistir resultados
   INSERT lead_scorecards
   INSERT lead_score_items (por cada criterio)
     ↓
6. Actualizar referencia
   UPDATE lead_leads SET current_scorecard_id = :new_id
```

---

## Queries Útiles

### Ver scorecard completo de un lead

```sql
SELECT 
    l.full_name,
    l.lead_type,
    sc.score_total,
    sc.priority_label,
    sc.model_version,
    si.criterion_key,
    si.score,
    b.band_key,
    b.label as band_label,
    b.color
FROM lead_leads l
JOIN lead_scorecards sc ON sc.lead_id = l.id
JOIN lead_score_items si ON si.scorecard_id = sc.id
LEFT JOIN lead_scoring_bands b ON b.id = si.band_id
WHERE l.id = 'lead-uuid-here'
ORDER BY sc.created_at DESC, si.criterion_key;
```

### Ver historial de scorecards de un lead

```sql
SELECT 
    sc.id,
    sc.score_total,
    sc.priority_label,
    sc.created_at,
    json_agg(json_build_object(
        'criterion', si.criterion_key,
        'score', si.score,
        'band', b.band_key
    )) as items
FROM lead_scorecards sc
JOIN lead_score_items si ON si.scorecard_id = sc.id
LEFT JOIN lead_scoring_bands b ON b.id = si.band_id
WHERE sc.lead_id = 'lead-uuid-here'
GROUP BY sc.id
ORDER BY sc.created_at DESC;
```

### Ver configuración completa de un modelo

```sql
SELECT 
    m.name as model_name,
    m.version as model_version,
    c.criterion_key,
    c.label as criterion_label,
    c.weight,
    json_agg(json_build_object(
        'band', b.band_key,
        'label', b.label,
        'range', concat(b.min_score, '-', b.max_score),
        'color', b.color
    ) ORDER BY b.min_score) as bands
FROM lead_scoring_models m
JOIN lead_scoring_criteria c ON c.model_id = m.id
LEFT JOIN lead_scoring_bands b ON b.criterion_id = c.id
WHERE m.id = 'model-uuid-here'
GROUP BY m.id, c.id
ORDER BY c.display_order;
```

---

## Migración de v1 a v2

| Concepto v1 | Concepto v2 |
|-------------|-------------|
| `lead_leads.score_engagement` | `lead_score_items` con `criterion_key='engagement'` |
| `lead_leads.score_finance` | `lead_score_items` con criterio configurable |
| Scores fijos en columnas | Scores dinámicos por modelo |
| Un scoring para todos | Scoring configurable por vertical |

---

## APIs Relacionadas

| Endpoint | Descripción |
|----------|-------------|
| `POST /api/v2/chat` | Procesa mensaje, crea lead y scorecard |
| `GET /api/v2/leads/{lead_id}/scorecards/latest` | Obtiene último scorecard |
| `GET /api/v2/scoring/models/active?client_id=...` | Obtiene modelo activo para un cliente |
| `POST /api/v2/cache/invalidate` | Invalida caché de modelos |

---

## Referencias

- RFC original: `docs/LEAD_FLOW_SPLIT_RFC.md`
- Código del repositorio: `services/inference-stack-v2/inference-core-v2/app/repositories/scoring_repository.py`
- Simulador de pruebas: `tests/sandbox/simulate_chat_flow.py`
