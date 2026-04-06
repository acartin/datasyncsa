# AI Runtime Prompt Runtime

## Objetivo

Documentar la ruta real de carga y composicion de prompts en `ai-runtime` despues de la migracion de los prompts semanticos core a codigo por vertical.

Este documento no reemplaza leer los prompts activos. Para cambios en logica conversacional o phrasing final, hay que leer los builders vigentes en codigo y, cuando aplique, las trazas del turno.

## Resumen ejecutivo

El runtime actual separa prompts en tres grupos:

1. Prompts semanticos core locales por vertical
- `analyze_turn`
- `intent_detector`
- `synthesis_prompt`

2. Prompts tecnicos locales
- prompts compartidos bajo `services/ai_runtime/graph/_shared/prompts/*.py`
- prompts realtor especificos bajo `services/ai_runtime/graph/realtor/prompts/*.py`

3. Configuracion externa aun activa
- `lead_ai_prompts.slug = 'primary_chat'` para `tone_prompt`
- `lead_scoring_prompts.prompt_template`
- `lead_scoring_prompts.extraction_schema`
- `lead_scoring_criteria`

Importante:

- `planner_system` y `synthesizer_system` pueden seguir existiendo en BD como residuo historico, pero ya no forman parte del runtime activo.
- El runtime ya no carga `system_prompts` ni `ai_system_prompts` para planner/synthesizer.

## Fuente canonica por tipo de prompt

### 1. Prompts semanticos core

Codigo:

- `services/ai_runtime/config/prompt_composer.py`
- `services/ai_runtime/graph/realtor/prompts/*.py`
- `services/ai_runtime/graph/healthcare/prompts/*.py`
- `services/ai_runtime/graph/legal/prompts/*.py`
- `services/ai_runtime/graph/insurance/prompts/*.py`

Resolucion:

1. `compose("analyze_turn", ...)` llama `load_analyze_turn_prompt(vertical)`.
2. `compose("intent_detector", ...)` llama `load_intent_detector_prompt(vertical)`.
3. `compose("synthesis_prompt", ...)` llama `load_synthesis_prompt(vertical)`.
4. Cada vertical resuelve su propio builder local en codigo.

Resultado:

- la semantica core del runtime vive versionada en git
- ya no hay dependencia operativa de prompts planner/synthesizer en BD

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
- entra al prompt solo cuando el nodo llama `compose(..., include_tone=True)`

### 3. `lead_scoring`

Codigo:

- `services/data/repositories/tenant_repository.py`
- `services/ai_runtime/graph/_shared/scoring_hybrid.py`

Tablas usadas:

- `lead_scoring_models`
- `lead_scoring_criteria`
- `lead_scoring_prompts`

Resolucion:

1. `TenantRepository._load_scoring_profile()` resuelve el modelo activo por `vertical_id` + `scoring_model_id`.
2. Carga criterios activos y el prompt del modelo.
3. Inyecta el resultado en `TenantConfig.scoring_profile`.
4. `lead_advisor` ejecuta `score_turn` con ese prompt en memoria.

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
   - `scoring_profile`
   - metadata operativa del tenant
5. `TenantLoader` cachea ese `TenantConfig` por `client_id`.

Consecuencia operativa:

- un cambio en `lead_ai_prompts` o en scoring puede quedar cacheado hasta que expire `TenantCache`
- un cambio en prompts core del runtime requiere redeploy/rebuild del servicio, porque ahora viven en codigo

### Paso 2. Normalizacion del texto

Codigo:

- `services/data/repositories/tenant_repository.py`

Funcion:

- `_normalize_prompt_text(prompt_text)`

Que hace:

- si el valor viene como modulo Python del estilo `PROMPT = \"\"\"...\"\"\"`, extrae solo el cuerpo
- si viene como string triple quoted, extrae solo el cuerpo
- si viene como texto plano, lo deja tal cual

Esto hoy aplica a `tone_prompt` y a datos heredados compatibles.

## Composicion final del prompt

Codigo:

- `services/ai_runtime/config/prompt_composer.py`

Formula canonica:

`prompt_final = [tone_prompt si include_tone=True] + base_prompt_local + dynamic_context`

Donde:

- `tone_prompt` es opcional y sale de `lead_ai_prompts`
- `base_prompt_local` sale de builders en codigo segun `node_type` y `vertical`
- `dynamic_context` es un JSON serializado con estado/contexto del turno

## Mapa de nodos y su fuente

### Locales por vertical

- `analyze_turn`
- `intent_detector`
- `synthesis_prompt`

Fuente:

- `services/ai_runtime/graph/realtor/prompts/*.py`
- `services/ai_runtime/graph/healthcare/prompts/*.py`
- `services/ai_runtime/graph/legal/prompts/*.py`
- `services/ai_runtime/graph/insurance/prompts/*.py`

Importante:

- `analyze_turn`, `intent_detector` y `synthesis_prompt` son responsabilidad semantica del vertical
- `_shared` no debe contener prompts de negocio con semantica de dominio

### Locales compartidos

Se resuelven por ramas explicitas dentro de `services/ai_runtime/config/prompt_composer.py`:

- `lazy_condition_evaluator`
- `clarification`
- `lead_data_collector`
- `memory_entity_extractor`
- `appointment_data_collector`

Fuente:

- `services/ai_runtime/graph/_shared/prompts/*.py`
- `appointment_data_collector` entra via un shim en `services/ai_runtime/graph/realtor/prompts/appointment_data_collector_prompt.py`

### Locales realtor-specific

Se resuelven por ramas explicitas dentro de `services/ai_runtime/config/prompt_composer.py`:

- `text_to_sql`
- `search_filter_extractor`
- `comparison_synthesizer`
- `recommendation`

Fuente:

- `services/ai_runtime/graph/realtor/prompts/*.py`

## Reglas reales del runtime

1. `lead_ai_prompts` no define planner ni synthesizer operativos; hoy solo alimenta `tone_prompt`.
2. `planner_system` y `synthesizer_system` ya no participan en la composicion del runtime activo.
3. La semantica core conversacional vive en codigo por vertical.
4. La documentacion vieja en `docs/OLD/agent-core/` sirve solo como contexto historico.

## Phrasing de captura

Para preguntas de captura de lead, el runtime resuelve el wording con esta precedencia:

1. `slot_hints.question` devuelto por el prompt/scoring activo
2. `lead_scoring_prompts.extraction_schema.fields[].question`
3. fallback minimo en Python
