# AI Runtime Prompt Runtime

## Objetivo

Documentar la ruta real de carga y composicion de prompts en `ai-runtime` para evitar asumir tablas, fallbacks o carpetas que el codigo activo no usa.

Este documento no reemplaza leer los prompts activos. Para tareas que toquen logica conversacional, planner, synthesizer, lead capture o scoring, hay que leer los textos activos en BD o en la traza del turno. Saber la ruta de carga no alcanza.

## Resumen ejecutivo

El runtime actual separa los prompts en dos grupos:

1. Prompts DB-backed del sistema
- `planner_system`
- `synthesizer_system`

2. Prompts locales en codigo
- prompts compartidos bajo `services/ai_runtime/graph/_shared/prompts/*.py`
- prompts realtor especificos bajo `services/ai_runtime/graph/realtor/prompts/*.py`

3. Prompt de scoring por modelo (DB-backed, in-memory)
- `lead_scoring_prompts.prompt_template`
- `lead_scoring_prompts.extraction_schema`
- `lead_scoring_criteria` (criterios activos del modelo)

Ademas existe un overlay de tono por tenant:

- `lead_ai_prompts.slug = 'primary_chat'`

Ese overlay no reemplaza `planner_system` ni `synthesizer_system`; solo alimenta `tone_prompt`.

## Fuente canonica por tipo de prompt

### 1. `planner_system` y `synthesizer_system`

Codigo:

- `services/data/repositories/tenant_repository.py`
- `services/ai_runtime/config/prompt_composer.py`

Tabla usada:

- ruta soportada por codigo: `system_prompts` si existe
- fallback de compatibilidad: `ai_system_prompts`
- en la BD actual validada para este repo: existe `ai_system_prompts` y no existe `system_prompts`

Resolucion:

1. `TenantRepository._resolve_system_prompts_table()` detecta si existe `public.system_prompts`.
2. Si no existe, intenta `public.ai_system_prompts`.
3. Si no existe ninguna, deja ambos prompts vacios.
4. `load_tenant_config()` busca:
   - `node_slug = 'planner_system'`
   - `node_slug = 'synthesizer_system'`
5. La busqueda se hace por `vertical_slug = v.slug` del tenant.
6. Solo toma registros activos: `COALESCE(is_active, true) = true`.
7. Elige la version mas reciente con este orden:
   - `version DESC`
   - `updated_at DESC NULLS LAST`
   - `created_at DESC NULLS LAST`

Importante:

- No hay fallback global por `node_slug` sin `vertical_slug`.
- No hay lookup por `client_id`.
- Si la tabla existe pero no hay fila para ese `vertical_slug`, el prompt queda vacio.
- Cuando luego se intenta usar, `prompt_composer.load_vertical_prompt()` lanza error si el prompt sigue vacio.

### 2. `tone_prompt`

Codigo:

- `services/data/repositories/tenant_repository.py`

Tabla usada:

- `lead_ai_prompts`

Resolucion:

1. Se busca por `client_id = c.id`.
2. Se filtra `slug = 'primary_chat'`.
3. Solo toma registros activos:
   - `COALESCE(is_active, true) = true`
   - `deleted_at IS NULL`
4. Elige la version mas reciente con este orden:
   - `version DESC NULLS LAST`
   - `updated_at DESC NULLS LAST`
   - `created_at DESC NULLS LAST`

Resultado:

- ese valor se guarda como `TenantConfig.tone_prompt`
- no entra en `TenantConfig.system_prompts`
- no sustituye planner ni synthesizer

### 3. `lead_scoring` (evaluacion LLM en memoria)

Codigo:

- `services/data/repositories/tenant_repository.py`
- `services/ai_runtime/graph/_shared/scoring_hybrid.py`

Tablas usadas:

- `lead_scoring_models`
- `lead_scoring_criteria`
- `lead_scoring_prompts`

Resolucion:

1. `TenantRepository._load_scoring_profile()` resuelve modelo activo por `vertical_id` + `scoring_model_id`.
2. Carga criterios activos (`lead_scoring_criteria`).
3. Carga prompt activo del modelo (`prompt_template`, `extraction_schema`).
4. Se inyecta en `TenantConfig.scoring_profile`.
5. `lead_advisor` ejecuta `score_turn` con ese prompt en memoria (sin persistencia realtime).

## Cadena real de carga

### Paso 1. Carga del tenant

Codigo:

- `services/ai_runtime/runtime/service.py`
- `services/ai_runtime/config/tenant_loader.py`
- `services/data/repositories/tenant_repository.py`

Flujo:

1. `ConversationRuntime.handle_turn()` llama `tenant_loader.load(client_id)`.
2. `TenantLoader` intenta primero cache en `TenantCache`.
3. Si no existe cache, llama `TenantRepository.load_tenant_config(client_id)`.
4. `TenantRepository` devuelve un `TenantConfig` con:
   - `vertical`
   - `tone_prompt`
   - `system_prompts['planner_system']`
   - `system_prompts['synthesizer_system']`
5. `TenantLoader` cachea ese `TenantConfig` por `client_id` en `TenantCache`.

Consecuencia operativa:

- si se cambia el prompt en DB, el runtime puede seguir usando la version cacheada para ese tenant hasta que expire el TTL o se limpie `TenantCache`

### Paso 2. Normalizacion del texto

Codigo:

- `services/data/repositories/tenant_repository.py`

Funcion:

- `_normalize_prompt_text(prompt_text)`

Que hace:

- si el valor viene como modulo Python del estilo `PROMPT = \"\"\"...\"\"\"`, extrae solo el cuerpo
- si viene como string triple quoted, extrae solo el cuerpo
- si viene como texto plano, lo deja tal cual

Esto existe para tolerar datos heredados en DB que fueron guardados con wrapper tipo archivo Python.

## Composicion final del prompt

Codigo:

- `services/ai_runtime/config/prompt_composer.py`

Formula canonica:

`prompt_final = [tone_prompt si include_tone=True] + base_prompt + dynamic_context`

Donde:

- `tone_prompt` es opcional, sale de `lead_ai_prompts` y solo entra cuando el nodo llama `compose(..., include_tone=True)`
- `base_prompt` sale de DB o de builders locales segun el nodo
- `dynamic_context` es un JSON serializado con estado/contexto del turno

## Mapa de nodos y su fuente

### DB-backed directos

- `plan_prompt` -> `planner_system`
- `synthesis_prompt` -> `synthesizer_system`

### DB-backed indirectos

- ninguno activo en el runtime actual para nodos de analisis semantico

### Locales por vertical

- `analyze_turn` ya no sale de `_shared`.
- `intent_detector` ya no sale de `_shared`.
- Cada vertical resuelve su propio prompt:
  - `realtor` -> `graph/realtor/prompts/analyze_turn_prompt.py`
  - `healthcare` -> `graph/healthcare/prompts/analyze_turn_prompt.py`
  - `legal` -> `graph/legal/prompts/analyze_turn_prompt.py`
  - `insurance` -> `graph/insurance/prompts/analyze_turn_prompt.py`
  - `realtor` -> `graph/realtor/prompts/intent_detector_prompt.py`
  - `healthcare` -> `graph/healthcare/prompts/intent_detector_prompt.py`
  - `legal` -> `graph/legal/prompts/intent_detector_prompt.py`
  - `insurance` -> `graph/insurance/prompts/intent_detector_prompt.py`

Importante:

- cambios en `planner_system` ya no alteran directamente `analyze_turn`
- cambios en `planner_system` ya no alteran directamente `intent_detector`
- `analyze_turn` queda como responsabilidad semantica por vertical
- `intent_detector` queda como responsabilidad semantica por vertical
- `_shared` no debe contener prompts de analisis de turno con semantica de dominio

### Locales compartidos

Se resuelven por ramas explicitas dentro de `services/ai_runtime/config/prompt_composer.py`:

- `reference_classifier`
- `lazy_condition_evaluator`
- `clarification`
- `lead_data_collector`
- `memory_entity_extractor`
- `appointment_data_collector`

Fuente:

- `services/ai_runtime/graph/_shared/prompts/*.py`
- `appointment_data_collector` entra al composer via un shim en `services/ai_runtime/graph/realtor/prompts/appointment_data_collector_prompt.py` que reexporta el builder compartido

### Locales realtor-specific

Se resuelven por ramas explicitas dentro de `services/ai_runtime/config/prompt_composer.py`:

- `text_to_sql`
- `search_filter_extractor`
- `comparison_synthesizer`
- `recommendation`

Fuente:

- `services/ai_runtime/graph/realtor/prompts/*.py`

Importante:

- hoy no existen carpetas equivalentes activas para `healthcare`, `legal` o `insurance`
- esos verticales dependen del `basic_flow` y de prompts compartidos + system prompts DB-backed

## Reglas reales del runtime

1. `lead_ai_prompts` no define `planner_system` ni `synthesizer_system`.
2. `lead_ai_prompts` hoy solo alimenta `tone_prompt` con `slug = 'primary_chat'`.
3. `planner_system` y `synthesizer_system` vienen de `system_prompts` o `ai_system_prompts`; en la BD actual de este entorno, la tabla viva es `ai_system_prompts`.
4. La seleccion de planner/synthesizer es por `vertical_slug`, no por `client_id`.
5. No existe fallback global por vertical ausente en la implementacion actual.
6. Si falta `planner_system` o `synthesizer_system` para el vertical activo, el runtime falla al componer ese nodo.
7. La documentacion vieja en `docs/OLD/agent-core/` puede servir como contexto historico, pero la autoridad es el codigo activo.

## Phrasing de Captura

Para preguntas de captura de lead, el runtime resuelve el wording con esta precedencia:

1. `slot_hints.question` devuelto por el prompt/scoring activo
2. `lead_scoring_prompts.extraction_schema.fields[].question`
3. fallback minimo en Python (`FIELD_QUESTIONS` u otro guardrail equivalente)

Importante:

- `fields[].question` no define por si solo el momento conversacional.
- `fields[].question` es wording base configurable por tenant/modelo.
- La decision de si conviene preguntar y cual campo sigue debe venir del prompt activo (`slot_hints.next_field`) o de guardrails duros del runtime.
- Hoy `fields[].question` se usa como fallback del runtime y no se inyecta automaticamente al prompt LLM de scoring.

## Prompt Preload Obligatorio

Antes de recomendar cambios de logica conversacional o scoring en `ai-runtime`, hay que leer y tener presentes en el contexto los prompts activos del tenant:

1. `lead_ai_prompts.slug = 'primary_chat'`
2. `planner_system`
3. `synthesizer_system`
4. Si la tarea toca scoring o lead capture:
   - `lead_scoring_prompts.prompt_template`
   - `lead_scoring_prompts.extraction_schema`
   - `lead_scoring_criteria`

Si no se pueden leer desde BD, la alternativa valida es inspeccionar una traza del turno que exponga `stable_prefix` o el prompt compuesto real. Si no hay ni BD ni traza, no se debe cambiar politica conversacional como si el prompt activo ya fuera conocido.

## Checklist de debug

Si hay dudas sobre que prompt uso un tenant:

1. Verificar el `vertical` resuelto para el tenant en `lead_client_verticals`.
2. Verificar si existe `system_prompts` o si el runtime esta cayendo a `ai_system_prompts`.
3. Buscar filas activas para:
   - `node_slug = 'planner_system'`
   - `node_slug = 'synthesizer_system'`
   - `vertical_slug = <vertical_del_tenant>`
4. Verificar si existe `lead_ai_prompts.slug = 'primary_chat'` para ese `client_id`.
5. Recordar que el runtime puede estar sirviendo config cacheada por `TenantLoader` y `TenantCache`.

### Consulta sugerida para preload real

Usar el wrapper de entorno del repo:

`set -a; source .env; set +a; <comando>`

Luego leer, como minimo:

1. `lead_ai_prompts` por `client_id` y `slug = 'primary_chat'`
2. `ai_system_prompts` o `system_prompts` por:
   - `node_slug = 'planner_system'`
   - `node_slug = 'synthesizer_system'`
   - `vertical_slug = <vertical_del_tenant>`
3. `lead_scoring_prompts`, `lead_scoring_models` y `lead_scoring_criteria` si la tarea toca scoring

## Archivos clave

- `services/ai_runtime/runtime/service.py`
- `services/ai_runtime/config/tenant_loader.py`
- `services/data/repositories/tenant_repository.py`
- `services/ai_runtime/config/prompt_composer.py`
