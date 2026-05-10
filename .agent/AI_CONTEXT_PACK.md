# AI Context Pack

- Generated UTC: `2026-05-02T20:10:33Z`
- Repo root: `/srv/datasyncsa`
- Git branch: `HETZNER-LOCAL-2026-Mayo-02`
- Git commit: `5de3fce`
- Policy: high-signal only; enfocado en stack actual.

## Contexto Maestro

### `.agent/BRAIN_MAP.md`

```
# BRAIN_MAP

- Generated UTC: `2026-05-02T20:10:33Z`
- Repo root: `/srv/datasyncsa`
- Git branch: `HETZNER-LOCAL-2026-Mayo-02`
- Git commit: `5de3fce`

## 1. MAPA DE INTENCIONES (STACK ACTUAL)

| Carpeta | Responsabilidad Tecnica | Importancia (1-5) |
|---|---|---:|
| `docker-compose.yml` | Orquestacion oficial del stack local. | 5 |
| `services/ai_runtime` | Runtime conversacional LangGraph multitenant; autoridad principal de chat. | 5 |
| `services/scoring-core` | Dominio separado de scoring asincrono con API y worker propios. | 5 |
| `services/web/chat-web-renderer` | Canal web y renderer SDUI que consume `ai-runtime`. | 5 |
| `services/web/admin-console` | Consola operativa multi-tenant. | 4 |
| `services/etl-docs` | ETL documental, vectorizacion y reseteo de memoria best-effort. | 4 |
| `services/data` | Repositorios y caches compartidos del runtime conversacional. | 5 |
| `schemas` | Contratos compartidos entre servicios. | 4 |
| `tests` | Pruebas cross-service, smoke y sandboxes. | 4 |

## 2. ZONAS NO AUTORITATIVAS

| Carpeta | Estado |
|---|---|
| `services/etl-processor` | Deprecado. |
| `services/ai-agents` | Exploracion; no participa en el runtime operativo. |

## 3. ARQUITECTURA CORE

- `ai-runtime` resuelve tenant, vertical, flow y estado de sesion.
- `realtor_flow` y `basic_flow` son selectores logicos internos.
- `analyze_turn` e `intent_detector` son prompts semanticos por vertical; `shared` solo debe contener piezas tecnicas neutrales.
- `VerticalPolicy` y `VerticalAdapters` son las costuras activas para desacoplar logica y dependencias por vertical.
- `scoring-core` permanece separado y no debe absorber decisiones conversacionales.
- `chat-web-renderer` es consumidor/canal, no autoridad de negocio.
- Toda operacion conversacional debe mantener scope por `client_id`.

## 4. SERVICIOS DOCKER ACTIVOS

```text
postgres
redis
scoring-core
scoring-core-worker
admin-console-api
admin-console-web
ai-runtime
chat-web-renderer-api
chat-web-renderer-ui
etl-docs-worker
test-ui
datasyncsa-web
etl-docs
portainer
```

## 5. ENTRY POINTS PRINCIPALES

- `services/ai_runtime/main.py`
- `services/scoring-core/main.py`
- `services/web/chat-web-renderer/backend/app/main.py`
- `services/web/admin-console/backend/app/main.py`
- `services/etl-docs/main.py`

## 6. REFERENCIAS CANONICAS

- `services/ai_runtime/ARCHITECTURE.md`
- `.agent/RULES.md`
- `.agent/PY_EXECUTION_MAP.md`
- `.agent/ACTIVE_DB_PROMPTS.md`

## 7. ENTIDADES Y CAPAS CRITICAS

- Tenancy/runtime: `client_id`, `tenant_config`, `session_id`, `conversation_id`
- Estado conversacional: `services/ai_runtime/domain/state.py`
- Datos compartidos: `services/data/cache/**`, `services/data/repositories/**`
- Scoring: `lead_scorecards`, `lead_score_items`, `lead_scoring_models`, `lead_scoring_prompts`
- RAG: FAQ por tenant y documentos por tenant en Postgres/pgvector
```

## Prompts DB Activos

### `.agent/ACTIVE_DB_PROMPTS.md`

```
# Active DB Prompts

- Generated UTC: `2026-05-02T20:10:34Z`
- Source: `postgres.public.lead_scoring_prompts`
- Refresh command: `bash .agent/refresh_db_prompts.sh`
- Cache policy: usar este snapshot en bootstrap y refrescarlo una vez por sesion cuando la tarea toque realtor, scoring, lead capture o phrasing conversacional.

## Uso obligatorio

- Leer este archivo en el bootstrap de cada sesion junto con `.agent/RULES.md` y `.agent/PY_EXECUTION_MAP.md`.
- Para tareas en `realtor`, lead capture, scoring, `slot_hints`, appointment intent/type o cambios de policy conversacional, refrescar primero desde BD.
- Si el refresh falla pero este archivo existe, usarlo como snapshot cacheado y reportar la falta de verificacion de frescura.
- Si este archivo no existe y tampoco se pudo leer la BD, no avanzar con cambios de phrasing o politica conversacional.

## Realtor Scoring Prompt V4

- prompt_id: `190dc860-9d37-4883-a6f4-c3019fdd882e`
- prompt_version: `4`
- is_active: `t`
- updated_at: `2026-04-17 18:01:06.288827+00`
- model_id: `53fe9e76-09e6-46af-a934-bc2c602c256b`
- model_name: `Realtor Default`
- model_version: `1`
- model_prompt_version: `4`
- vertical_id: `1`
- vertical_name: `Real Estate`
- business_domain: `(null)`

### Query canonica

```sql
select p.id, p.version, p.is_active, p.updated_at,
       m.id as model_id, m.name as model_name, m.version as model_version, m.prompt_version as model_prompt_version,
       v.id as vertical_id, v.name as vertical_name,
       p.prompt_template, p.extraction_schema
from lead_scoring_prompts p
join lead_scoring_models m on m.id = p.model_id
join lead_client_verticals v on v.id = m.vertical_id
where p.id = '190dc860-9d37-4883-a6f4-c3019fdd882e';
```

### prompt_template

```text

Eres un evaluador experto de leads para real estate.

Tu salida debe ser UNICAMENTE un JSON valido (sin markdown, sin texto extra, sin comentarios).

CONTEXTO
- vertical_name: {vertical_name}
- business_domain: {business_domain}
- locale: {locale}
- timestamp_utc: {timestamp_utc}

CRITERIOS ACTIVOS (referencia)
{criteria_text}

OBJETIVO
Evaluar el estado ACTUAL del lead y devolver:
1) scores por criterio (siempre los 5),
2) extracted_data,
3) reasoning breve,
4) confidence.

REGLAS OBLIGATORIAS
- Debes incluir siempre estas 5 llaves en "scores":
  - intencion
  - apertura
  - match
  - plazo
  - solvencia
- Rango permitido por criterio: 0 a 10.
- Nunca uses escala 0..1 en scores.
- Si falta evidencia para un criterio: asigna score bajo por desconocimiento (1.0 a 2.0) y justificalo.
- Reserva 0.0-1.0 para evidencia negativa explicita (rechazo, no califica, sin capacidad declarada, no desea avanzar).
- Prioriza evidencia mas RECIENTE sobre mensajes antiguos.
- Negaciones explicitas del usuario (ej: "no quiero agendar", "no necesito visita") deben reflejarse en extracted_appointment_intent = "negative" y tipo_cita = null.
- No bajes automaticamente intencion si el interes comercial sigue alto (ej: quiere mas fotos o comparar antes de visitar).
- No inventes informacion.

GUIA RAPIDA POR CRITERIO
- apertura:
  - 8-10: participa activamente y aporta datos utiles.
  - 5-7: participacion media.
  - 0-4: respuestas vagas o minimas.
- intencion:
  - 8-10: expresa accion clara para avanzar/agendar/comprar/rentar.
  - 5-7: interes general sin compromiso claro.
  - 0-4: curiosidad o rechazo de avance.
- plazo:
  - 8-10: urgencia explicita (hoy, esta semana, pronto).
  - 5-7: horizonte mediano.
  - 0-4: indefinido o sin prisa.
  - si no hay evidencia temporal explicita: 1.0.
- match:
  - 8-10: requerimiento claro y fit alto declarado.
  - 5-7: fit parcial/incompleto.
  - 0-4: fit debil o ambiguo.
  - si falta evidencia de fit: 1.0.
- solvencia:
  - 8-10: capacidad clara (preaprobado, fondos claros, banco confirmado).
  - 5-7: capacidad posible pero incompleta.
  - 0-4: capacidad debil o senales negativas.
  - si falta evidencia financiera: 1.0.

EXTRACTED_DATA (OBLIGATORIO, TODAS LAS LLAVES)
- extracted_name
- extracted_email
- extracted_phone
- extracted_appointment_intent
- extracted_appointment_type
- extracted_approval
- extracted_budget
- extracted_preferred_date
- extracted_preference

REGLAS DE EXTRACCION
- Si no aparece explicitamente, usar null.
- Mantener texto cercano a lo dicho por el usuario.
- Clasifica extracted_appointment_intent con la postura MAS RECIENTE del usuario: positive | negative | uncertain.
- Si hay negacion explicita de agendar/visitar (ej: "no quiero agendar", "no necesito visita", "por ahora no"), entonces extracted_appointment_intent = "negative" y extracted_appointment_type = null.
- Solo reporta extracted_appointment_type cuando extracted_appointment_intent sea "positive".

VALIDACIONES FINALES
- Respuesta valida JSON.
- Incluir solo las llaves definidas por el schema.
- Sin texto fuera del JSON.


SLOT_HINTS CONVERSACIONALES
- Cuando exista un siguiente dato claro que ayude a avanzar sin sonar a formulario, puedes agregar una llave opcional `slot_hints`.
- Formato permitido:
  "slot_hints": {
    "next_field": "nombre|presupuesto|aprobacion|fecha_preferida|contacto|tipo_cita|appointment_intent|email|telefono|preferencias",
    "question": "pregunta natural, unica y breve"
  }
- Si no hay una siguiente pregunta clara, omite `slot_hints`.
- Usa una sola pregunta por turno y evita sonar a formulario.
- Usa `dynamic_context.capture_exposure_count` y `dynamic_context.capture_unlocked` como guardrails conversacionales.
- Si `dynamic_context.capture_exposure_count < 2`, NO devuelvas `slot_hints` para pedir nombre ni ningun otro dato de lead.
- La primera captura de lead, incluido `nombre`, solo puede comenzar a partir de la segunda muestra util de opciones, cards o datos de propiedades/casos.
- Considera muestra util cuando el usuario ya vio resultados, cards, detalle de propiedad, comparacion o recomendacion concreta.
- Si `dynamic_context.capture_unlocked = true` y `nombre` sigue vacio, prioriza `nombre` como primer dato a capturar, salvo que el usuario haya dado otro dato personal en este mismo turno o haga falta contacto para confirmar una cita ya definida.
- No pidas datos de contacto en saludo puro ni en el mismo turno en que el usuario acaba de dar otro dato personal, salvo que sea estrictamente necesario para confirmar una cita ya definida.
- Mapa de momentos sugerido para realtor:
  - `nombre`: despues de la primera reaccion positiva o interes concreto del usuario por una busqueda, calculo, recomendacion o propiedad. Nunca en saludo puro.
  - `presupuesto`: despues de mostrar opciones, precios o cuando el usuario reacciona a rango/capacidad.
  - `aprobacion`: cuando el usuario pregunta por cuota, financiamiento o ya muestra capacidad financiera en la conversacion.
  - `fecha_preferida`: cuando hay urgencia/plazo relevante o el usuario ya piensa en mudanza/tiempos.
  - `contacto`: cerca del cierre, cuando el usuario selecciono una opcion, pidio seguimiento detallado o hay intencion positiva de cita. Para confirmar cita, prioriza contacto.
  - `tipo_cita`: cuando la intencion de agendar es positiva y ya hay suficiente interes/match para proponer visita, llamada o video.
- Si appointment_intent = "negative" con motivo contextual (ej: "primero quiero ver mas fotos"), captura ese motivo en `extracted_preference` cuando aplique y no repreguntes visita/tipo_cita dentro del mismo hilo, salvo que el usuario reactive ese tema explicitamente.
- Si el usuario acaba de entregar `nombre`, `email`, `telefono` u otro dato de lead en este mismo turno, no encadenes automaticamente el siguiente campo.
- Alinea `next_field` con la evidencia mas reciente, los scores actuales, los datos ya capturados y el estado de la conversacion.

```

### extraction_schema

```json
{
    "mode": "llm_scoring_primary",
    "fields": [
        {
            "key": "extracted_name",
            "type": "string",
            "question": "¿Con quién tengo el gusto?",
            "description": "Nombre del lead"
        },
        {
            "key": "extracted_email",
            "type": "string",
            "question": "¿Qué correo te queda mejor compartir?",
            "description": "Email del lead"
        },
        {
            "key": "extracted_phone",
            "type": "string",
            "question": "¿Qué número te queda mejor compartir?",
```

## Compose y Variables

### Servicios activos del compose

```text
postgres
redis
scoring-core
ai-runtime
chat-web-renderer-api
portainer
test-ui
admin-console-api
admin-console-web
chat-web-renderer-ui
datasyncsa-web
etl-docs
etl-docs-worker
scoring-core-worker
```
### `docker-compose.yml:1-220`

```
services:
  # ---------------------------------------------------------------------------
  # INFRASTRUCTURE SERVICES
  # ---------------------------------------------------------------------------
  
  # Database (Replaces CT 101)
  postgres:
    build:
      context: ./services/database
      dockerfile: Dockerfile
    container_name: ${ENV_PREFIX}-infra-postgres
    restart: always
    command: ["postgres", "-c", "timezone=${TZ:-UTC}"]
    environment:
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASS}
      POSTGRES_DB: ${DB_NAME}
      TZ: ${TZ:-UTC}
    ports:
      - "${DB_PORT}:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - internal_network

  # Redis (Shared by Chat Web Renderer and ETL Queue)
  redis:
    image: redis:alpine
    container_name: ${ENV_PREFIX}-infra-redis
    restart: always
    command: redis-server --appendonly yes
    environment:
      TZ: ${TZ:-UTC}
    volumes:
      - redis_data:/data
    networks:
      - internal_network

  # Portainer (Container Management UI)
  portainer:
    image: portainer/portainer-ce:latest
    container_name: ${ENV_PREFIX}-infra-portainer
    restart: always
    security_opt:
      - no-new-privileges:true
    volumes:
      - /etc/localtime:/etc/localtime:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - portainer_data:/data
    ports:
      - "${PORTAINER_PORT}:9000"
    environment:
      TZ: ${TZ:-UTC}
    networks:
      - internal_network

  # ---------------------------------------------------------------------------
  # BACKEND SERVICES
  # ---------------------------------------------------------------------------
  # AI Runtime (LangGraph multitenant assistant)
  ai-runtime:
    build:
      context: .
      dockerfile: ./services/ai_runtime/Dockerfile
    container_name: ${ENV_PREFIX}-backend-ai-runtime
    restart: always
    command:
      - uvicorn
      - main:app
      - --host
      - 0.0.0.0
      - --port
      - "8000"
      - --workers
      - ${AI_RUNTIME_WEB_CONCURRENCY:-1}
    ports:
      - "${AI_RUNTIME_PORT:-8096}:8000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - TZ=${TZ:-UTC}
      - REDIS_URL=redis://redis:6379/0
      - INTERNAL_API_TOKEN=${INTERNAL_API_TOKEN}
      - LOG_LEVEL=INFO
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - LLM_DEFAULT_MODEL=${LLM_DEFAULT_MODEL}
      - LLM_ANALYZE_TURN_MODEL=${LLM_ANALYZE_TURN_MODEL}
      - AI_RUNTIME_API_PREFIX=/api/v1
      - PYTHONPATH=/app
      - SCORING_CORE_API=http://scoring-core:8000
      - SCORING_CORE_API_PREFIX=/api/v1
      - SCORING_ENQUEUE_ENABLED=${SCORING_ENQUEUE_ENABLED:-true}
      - SCORING_ENQUEUE_TIMEOUT_SECS=${SCORING_ENQUEUE_TIMEOUT_SECS:-2.0}
    volumes:
      - ./schemas:/app/schemas:ro
      - ./log:/app/log
    depends_on:
      - postgres
      - redis
      - scoring-core
    networks:
      - internal_network

  # Scoring Core API (async scoring domain service)
  scoring-core:
    build:
      context: ./services/scoring-core
      dockerfile: Dockerfile
    container_name: ${ENV_PREFIX}-backend-scoring-core
    restart: always
    command:
      - uvicorn
      - main:app
      - --host
      - 0.0.0.0
      - --port
      - "8000"
      - --workers
      - ${SCORING_CORE_WEB_CONCURRENCY:-1}
    ports:
      - "${SCORING_CORE_PORT:-8097}:8000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - TZ=${TZ:-UTC}
      - REDIS_URL=redis://redis:6379/0
      - INTERNAL_API_TOKEN=${INTERNAL_API_TOKEN}
      - LOG_LEVEL=INFO
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - LLM_DEFAULT_MODEL=${LLM_DEFAULT_MODEL}
      - LLM_TIMEOUT_SECS=${LLM_TIMEOUT_SECS}
      - SCORING_API_PREFIX=${SCORING_API_PREFIX:-/api/v1}
      - SCORING_LLM_TIMEOUT_SECS=${SCORING_LLM_TIMEOUT_SECS:-60}
      - SCORING_LLM_HARD_TIMEOUT_SECS=${SCORING_LLM_HARD_TIMEOUT_SECS:-10}
      - SCORING_LLM_MAX_OUTPUT_TOKENS=${SCORING_LLM_MAX_OUTPUT_TOKENS:-512}
      - SCORING_JOB_DEBOUNCE_SECS=${SCORING_JOB_DEBOUNCE_SECS:-1.5}
      - SCORING_WORKER_POLL_SECS=${SCORING_WORKER_POLL_SECS:-2.0}
      - SCORING_WORKER_CONCURRENCY=${SCORING_WORKER_CONCURRENCY:-1}
      - SCORING_JOB_MAX_ATTEMPTS=${SCORING_JOB_MAX_ATTEMPTS:-3}
      - SCORING_JOB_LOCK_TTL_SECS=${SCORING_JOB_LOCK_TTL_SECS:-120}
      - SCORING_RETRY_DELAY_SECS=${SCORING_RETRY_DELAY_SECS:-5}
      - SCORING_ALLOW_HEURISTIC_FALLBACK=${SCORING_ALLOW_HEURISTIC_FALLBACK:-false}
      - LLM_TRACE_ROOT=/app/log
      - LLM_TRACE_ENABLED=true
    volumes:
      - ./schemas:/app/schemas:ro
      - ./log:/app/log
    depends_on:
      - postgres
      - redis
    networks:
      - internal_network

  # Scoring Core async worker
  scoring-core-worker:
    build:
      context: ./services/scoring-core
      dockerfile: Dockerfile
    container_name: ${ENV_PREFIX}-backend-scoring-core-worker
    restart: always
    command: ["python", "worker.py"]
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - TZ=${TZ:-UTC}
      - REDIS_URL=redis://redis:6379/0
      - INTERNAL_API_TOKEN=${INTERNAL_API_TOKEN}
      - LOG_LEVEL=INFO
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - LLM_DEFAULT_MODEL=${LLM_DEFAULT_MODEL}
      - LLM_TIMEOUT_SECS=${LLM_TIMEOUT_SECS}
      - SCORING_API_PREFIX=${SCORING_API_PREFIX:-/api/v1}
      - SCORING_LLM_TIMEOUT_SECS=${SCORING_LLM_TIMEOUT_SECS:-60}
      - SCORING_LLM_HARD_TIMEOUT_SECS=${SCORING_LLM_HARD_TIMEOUT_SECS:-10}
      - SCORING_LLM_MAX_OUTPUT_TOKENS=${SCORING_LLM_MAX_OUTPUT_TOKENS:-512}
      - SCORING_JOB_DEBOUNCE_SECS=${SCORING_JOB_DEBOUNCE_SECS:-1.5}
      - SCORING_WORKER_POLL_SECS=${SCORING_WORKER_POLL_SECS:-2.0}
      - SCORING_WORKER_CONCURRENCY=${SCORING_WORKER_CONCURRENCY:-1}
      - SCORING_JOB_MAX_ATTEMPTS=${SCORING_JOB_MAX_ATTEMPTS:-3}
      - SCORING_JOB_LOCK_TTL_SECS=${SCORING_JOB_LOCK_TTL_SECS:-120}
      - SCORING_RETRY_DELAY_SECS=${SCORING_RETRY_DELAY_SECS:-5}
      - SCORING_ALLOW_HEURISTIC_FALLBACK=${SCORING_ALLOW_HEURISTIC_FALLBACK:-false}
      - LLM_TRACE_ROOT=/app/log
      - LLM_TRACE_ENABLED=true
    volumes:
      - ./schemas:/app/schemas:ro
      - ./log:/app/log
    depends_on:
      - postgres
      - redis
      - scoring-core
    networks:
      - internal_network

  # ETL Docs API
  etl-docs:
    build:
      context: ./services/etl-docs
      dockerfile: Dockerfile
    container_name: ${ENV_PREFIX}-backend-etl-docs
    restart: always
    ports:
      - "${ETL_DOCS_PORT}:8000"
    environment:
      - TZ=${TZ:-UTC}
      - DB_HOST=postgres
      - DB_NAME=${DB_NAME}
      - DB_USER=${DB_USER}
      - DB_PASS=${DB_PASS}
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - EMBEDDING_MODEL=${EMBEDDING_MODEL}
      - REDIS_URL=redis://redis:6379/0
      - PATH_STAGING=/app/data/staging
      - PATH_STORAGE=/app/data/storage
      - MEMORY_RESET_URL=http://chat-web-renderer-api:8000/internal/memory/reset
      - MEMORY_RESET_TIMEOUT=8
      - INTERNAL_API_TOKEN=${INTERNAL_API_TOKEN}
    volumes:
      - ${HOST_PATH_STAGING}:/app/data/staging
      - ${HOST_PATH_STORAGE}:/app/data/storage
      - ./schemas:/app/schemas:ro
    depends_on:
      - postgres
```
### `docker-compose.yml:300-360`

```
      - API_HOST=${ENV_PREFIX}-web-admin-console-api
      - APP_VERSION=${APP_VERSION}
    depends_on:
      - admin-console-api
    networks:
      - internal_network

  # Chat Web Renderer API (Bridge)
  chat-web-renderer-api:
    build:
      context: ./services/web/chat-web-renderer/backend
      dockerfile: Dockerfile
    container_name: ${ENV_PREFIX}-web-chat-web-renderer-api
    restart: unless-stopped
    ports:
      - "${REALTOR_BRIDGE_PORT}:8000"
    environment:
      - TZ=${TZ:-UTC}
      - DB_HOST=postgres
      - DB_PORT=5432
      - DB_NAME=${DB_NAME}
      - DB_DATABASE=${DB_NAME}
      - DB_USER=${DB_USER}
      - DB_USERNAME=${DB_USER}
      - DB_PASS=${DB_PASS}
      - DB_PASSWORD=${DB_PASS}
      - REDIS_URL=redis://redis:6379/0
      - AI_RUNTIME_API=http://ai-runtime:8000
      - AI_RUNTIME_API_PREFIX=/api/v1
      - AI_RUNTIME_RESET_URL=http://ai-runtime:8000/api/v1/internal/memory/reset
      - SCORING_CORE_RESET_URL=http://scoring-core:8000/api/v1/internal/memory/reset
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - INTERNAL_API_TOKEN=${INTERNAL_API_TOKEN}
    volumes:
      - ./schemas:/app/schemas:ro
    depends_on:
      - postgres
      - redis
      - ai-runtime
    networks:
      - internal_network

  # Chat Web Renderer Frontend (Nginx)
  chat-web-renderer-ui:
    image: nginx:alpine
    container_name: ${ENV_PREFIX}-web-chat-web-renderer-ui
    restart: unless-stopped
    ports:
      - "${REALTOR_WEB_PORT}:80"
    volumes:
      - ./services/web/chat-web-renderer/frontend:/usr/share/nginx/html:rw
      - ./services/web/chat-web-renderer/frontend/nginx.conf.template:/etc/nginx/templates/default.conf.template:ro
    environment:
      - TZ=${TZ:-UTC}
      - API_HOST=chat-web-renderer-api
    depends_on:
      - chat-web-renderer-api
    networks:
      - internal_network

  # Corporate Website (Static)
```
### `.env.example:50-120`

```

# --- AI/SCORING SERVICE DISCOVERY ---
AI_RUNTIME_API=http://ai-runtime:8000
AI_RUNTIME_API_PREFIX=/api/v1
AI_RUNTIME_RESET_URL=http://ai-runtime:8000/api/v1/internal/memory/reset
SCORING_CORE_API=http://scoring-core:8000
SCORING_CORE_RESET_URL=http://scoring-core:8000/api/v1/internal/memory/reset
SCORING_API_PREFIX=/api/v1

# --- SCORING FEATURE FLAGS ---
SCORING_BG_ENABLED=true
SCORING_CORE_API_PREFIX=/api/v1
SCORING_CORE_TIMEOUT_SECS=8
SCORING_LLM_TIMEOUT_SECS=60
SCORING_IDLE_DELAY_SECS=60
SCORING_IDLE_CLOSE_SECS=60
SCORING_WORKER_POLL_SECS=2
SCORING_WORKER_CONCURRENCY=1
SCORING_JOB_MAX_ATTEMPTS=3
SCORING_JOB_LOCK_TTL_SECS=120
SCORING_JOB_DEBOUNCE_SECS=1.5
SCORING_RETRY_DELAY_SECS=5
SCORING_ALLOW_HEURISTIC_FALLBACK=false
SCORING_V2_ENABLED=false
SCORING_ENQUEUE_ENABLED=true
SCORING_ENQUEUE_TIMEOUT_SECS=2.0
ADMIN_DYNAMIC_SCORING_UI=false
LEGACY_SCORING_READ_COMPAT=true

# --- PORTS ---
ADMIN_CONSOLE_API_PORT=8084
ADMIN_CONSOLE_WEB_PORT=8085
APP_VERSION=1
REALTOR_BRIDGE_PORT=8086
REALTOR_WEB_PORT=8087
SEMANTIC_PORT=8000
CORPORATE_WEB_PORT=8088
TEST_UI_PORT=8089
PORTAINER_PORT=9000
ETL_DOCS_PORT=8090
INFERENCE_V3_PORT=8095
SCORING_CORE_PORT=8097
GENERIC_BRIDGE_PORT=8093
PROPERTY_BRIDGE_PORT=8094
AI_RUNTIME_PORT=8096

# --- EXTERNAL INTEGRATIONS ---
# External ETL endpoint (required by admin-console ai-library module)
# Example: https://etl.yourdomain.com
ETL_SERVICE_URL=

# --- TEST USERS (SMOKE) ---
SYSTEM_USER_EMAIL=
SYSTEM_USER_PASSWORD=
```

## Topologia Relevante

```text
schemas
schemas/__pycache__
schemas/agent_core
schemas/agent_core/contracts
schemas/agent_core/runtime
schemas/scoring_core
schemas/scoring_core/contracts
services/ai_runtime
services/ai_runtime/__pycache__
services/ai_runtime/config
services/ai_runtime/config/__pycache__
services/ai_runtime/config/geo
services/ai_runtime/docs
services/ai_runtime/docs/graphs
services/ai_runtime/domain
services/ai_runtime/domain/__pycache__
services/ai_runtime/graph
services/ai_runtime/graph/__pycache__
services/ai_runtime/graph/_shared
services/ai_runtime/graph/_shared/__pycache__
services/ai_runtime/graph/_shared/nodes
services/ai_runtime/graph/_shared/prompts
services/ai_runtime/graph/_shared/routers
services/ai_runtime/graph/_shared/state
services/ai_runtime/graph/_shared/tools
services/ai_runtime/graph/generic
services/ai_runtime/graph/generic/__pycache__
services/ai_runtime/graph/generic/nodes
services/ai_runtime/graph/generic/routers
services/ai_runtime/graph/generic/state
services/ai_runtime/graph/generic/tools
services/ai_runtime/graph/healthcare
services/ai_runtime/graph/healthcare/prompts
services/ai_runtime/graph/insurance
services/ai_runtime/graph/insurance/prompts
services/ai_runtime/graph/legal
services/ai_runtime/graph/legal/prompts
services/ai_runtime/graph/realtor
services/ai_runtime/graph/realtor/__pycache__
services/ai_runtime/graph/realtor/nodes
services/ai_runtime/graph/realtor/prompts
services/ai_runtime/graph/realtor/routers
services/ai_runtime/graph/realtor/state
services/ai_runtime/graph/realtor/tools
services/ai_runtime/rag
services/ai_runtime/rag/__pycache__
services/ai_runtime/rag/agency
services/ai_runtime/rag/agency/__pycache__
services/ai_runtime/rag/documents
services/ai_runtime/rag/documents/__pycache__
services/ai_runtime/runtime
services/ai_runtime/runtime/__pycache__
services/ai_runtime/scripts
services/ai_runtime/scripts/__pycache__
services/ai_runtime/tests
services/ai_runtime/tests/unit
services/ai_runtime/tests/unit/__pycache__
services/ai_runtime/web
services/ai_runtime/web/conversation_suites
services/ai_runtime/web/turn_trace
services/ai_runtime/workers
services/ai_runtime/workers/__pycache__
services/ai_runtime/workers/lead-worker
services/data
services/data/__pycache__
services/data/cache
services/data/cache/__pycache__
services/data/repositories
services/data/repositories/__pycache__
services/etl-docs
services/etl-docs/__pycache__
services/etl-docs/src
services/etl-docs/src/ETL_DOCS
services/etl-docs/src/ETL_DOCS/__pycache__
services/etl-docs/src/shared
services/etl-docs/src/shared/__pycache__
services/etl-docs/tests
services/etl-docs/tests/integration
services/etl-docs/tests/smoke
services/etl-docs/tests/unit
services/scoring-core
services/scoring-core/__pycache__
services/scoring-core/app
services/scoring-core/app/api
services/scoring-core/app/core
services/scoring-core/app/dependencies
services/scoring-core/app/models
services/scoring-core/app/repositories
services/scoring-core/app/repositories/__pycache__
services/scoring-core/app/services
services/scoring-core/app/services/__pycache__
services/web/admin-console
services/web/admin-console/backend
services/web/admin-console/backend/app
services/web/admin-console/backend/app/__pycache__
services/web/admin-console/backend/app/config
services/web/admin-console/backend/app/contracts
services/web/admin-console/backend/app/dal
services/web/admin-console/backend/app/dashboards
services/web/admin-console/backend/app/modules
services/web/admin-console/backend/scripts
services/web/admin-console/backend/tests
services/web/admin-console/backend/tests/contract
services/web/admin-console/backend/tests/integration
services/web/admin-console/backend/tests/sandbox
services/web/admin-console/backend/tests/smoke
services/web/admin-console/docs
services/web/admin-console/docs/Tema Velzon
services/web/admin-console/docs/velzon_source
services/web/admin-console/docs/velzon_source/assets
services/web/admin-console/frontend
services/web/admin-console/frontend/components
services/web/admin-console/frontend/components/cards
services/web/admin-console/frontend/components/forms
services/web/admin-console/frontend/components/grids
services/web/admin-console/frontend/components/layout
services/web/admin-console/frontend/components/ui
services/web/admin-console/frontend/js
services/web/admin-console/frontend/renderer
services/web/admin-console/frontend/renderer/engine
services/web/admin-console/frontend/themes
services/web/admin-console/frontend/themes/css
services/web/admin-console/frontend/themes/fonts
services/web/admin-console/frontend/themes/images
services/web/admin-console/frontend/themes/js
services/web/admin-console/frontend/themes/json
services/web/admin-console/frontend/themes/libs
services/web/admin-console/frontend/utils
services/web/admin-console/frontend/vendor
services/web/admin-console/frontend/vendor/jsoneditor
services/web/chat-web-renderer
services/web/chat-web-renderer/backend
services/web/chat-web-renderer/backend/app
services/web/chat-web-renderer/backend/app/__pycache__
services/web/chat-web-renderer/backend/app/adapters
services/web/chat-web-renderer/backend/app/api
services/web/chat-web-renderer/backend/app/core
services/web/chat-web-renderer/backend/app/planner
services/web/chat-web-renderer/backend/app/schemas
services/web/chat-web-renderer/backend/app/session
services/web/chat-web-renderer/backend/app/transformer
services/web/chat-web-renderer/backend/tests
services/web/chat-web-renderer/backend/tests/integration
services/web/chat-web-renderer/backend/tests/smoke
services/web/chat-web-renderer/backend/tests/unit
services/web/chat-web-renderer/frontend
services/web/chat-web-renderer/frontend/components
services/web/chat-web-renderer/frontend/components/interactive
services/web/chat-web-renderer/frontend/components/media
services/web/chat-web-renderer/frontend/components/realtor
services/web/chat-web-renderer/frontend/core
tests
tests/sandbox
tests/sandbox/__pycache__
tests/sandbox/dentist
tests/sandbox/dentist/__pycache__
tests/sandbox/realtor
tests/sandbox/realtor/__pycache__
tests/scripts
tests/system
tests/system/__pycache__
```

## Entry Points Detectados

```text
services/scoring-core/worker.py:31:if __name__ == "__main__":
services/scoring-core/main.py:44:app = FastAPI(
services/scoring-core/main.py:59:app.include_router(scoring_router, prefix=settings.api_prefix, tags=["scoring"])
services/scoring-core/main.py:72:if __name__ == "__main__":
services/scoring-core/main.py:73:    uvicorn.run(
services/web/admin-console/backend/tests/sandbox/test_countries_crud_script.py:51:if __name__ == "__main__":
services/web/admin-console/backend/tests/sandbox/test_connection.py:25:if __name__ == "__main__":
services/web/admin-console/backend/tests/contract/test_scoring_schema_contracts.py:306:if __name__ == "__main__":
services/web/admin-console/backend/tests/smoke/test_smoke_tenant_isolation.py:89:if __name__ == "__main__":
services/web/admin-console/backend/tests/smoke/test_smoke_system_user_menu.py:162:if __name__ == "__main__":
services/web/admin-console/backend/scripts/check_hash_config.py:27:if __name__ == "__main__":
services/web/admin-console/backend/scripts/restore_pass.py:20:if __name__ == "__main__":
services/web/admin-console/backend/scripts/verify_password_change.py:73:if __name__ == "__main__":
services/ai_runtime/tests/unit/test_shared_policy_decoupling.py:143:if __name__ == "__main__":
services/web/admin-console/backend/app/dal/inspect_schema.py:31:if __name__ == "__main__":
services/ai_runtime/tests/unit/test_vertical_policies.py:70:if __name__ == "__main__":
services/ai_runtime/tests/unit/test_state_migrations.py:31:if __name__ == "__main__":
services/ai_runtime/tests/unit/test_prompt_composer.py:52:if __name__ == "__main__":
services/ai_runtime/tests/unit/test_vertical_contract.py:47:if __name__ == "__main__":
services/ai_runtime/tests/unit/test_capture_memory_entities_node.py:54:if __name__ == "__main__":
services/ai_runtime/tests/unit/test_realtor_quick_actions.py:145:if __name__ == "__main__":
services/web/admin-console/backend/app/main.py:27:app = FastAPI(title="Web IAFirst Operational API")
services/web/admin-console/backend/app/main.py:61:app.include_router(base_dash_router, tags=["Dashboard (Base)"]) # Root prefix for app-init
services/web/admin-console/backend/app/main.py:62:app.include_router(manager_workspace_router, prefix="/dashboard")
services/web/admin-console/backend/app/main.py:63:app.include_router(seller_workspace_router, prefix="/dashboard")
services/web/admin-console/backend/app/main.py:64:app.include_router(leads_router, prefix="/leads", tags=["Leads Operations"])
services/web/admin-console/backend/app/main.py:65:app.include_router(leads_v2_router, prefix="/leads_v2", tags=["Leads v2 Operations"])
services/web/admin-console/backend/app/main.py:66:app.include_router(admin_scoring_router)
services/web/admin-console/backend/app/main.py:67:app.include_router(campaigns_router, prefix="/campaigns", tags=["Campaigns Operations"])
services/web/admin-console/backend/app/main.py:68:app.include_router(ai_library_router, prefix="/ai-library", tags=["AI Library Management"])
services/web/admin-console/backend/app/main.py:69:app.include_router(system_public_docs_router)
services/web/admin-console/backend/app/main.py:71:app.include_router(clients_router, tags=["Clients"])
services/web/admin-console/backend/app/main.py:72:app.include_router(countries_router, tags=["Countries (System)"])
services/web/admin-console/backend/app/main.py:73:app.include_router(prompts_router, tags=["AI Prompts"])
services/web/admin-console/backend/app/main.py:74:app.include_router(auth_router) # Tags are defined inside the router
services/web/admin-console/backend/app/main.py:75:app.include_router(users_router)
services/web/admin-console/backend/app/main.py:76:app.include_router(roles_router)
services/web/admin-console/backend/app/main.py:77:app.include_router(contacts_router, tags=["Contacts"])
services/web/admin-console/backend/app/main.py:78:app.include_router(grid_presets_router)
services/ai_runtime/tests/unit/test_render_cards_node.py:107:if __name__ == "__main__":
services/ai_runtime/tests/unit/test_realtor_progressive_profile.py:171:if __name__ == "__main__":
services/ai_runtime/tests/unit/test_cta_planner.py:79:if __name__ == "__main__":
services/ai_runtime/tests/unit/test_synthesize_node.py:39:if __name__ == "__main__":
services/ai_runtime/tests/unit/test_prompt_context.py:63:if __name__ == "__main__":
services/ai_runtime/tests/unit/test_pending_decisions.py:199:if __name__ == "__main__":
services/ai_runtime/tests/unit/test_scoring_hybrid.py:17:if __name__ == "__main__":
services/ai_runtime/tests/unit/test_llm_model_routing.py:45:if __name__ == "__main__":
services/ai_runtime/tests/unit/test_realtor_cta_selector.py:67:if __name__ == "__main__":
services/ai_runtime/scripts/export_graph_diagrams.py:388:if __name__ == "__main__":
services/ai_runtime/scripts/prompt_context_audit.py:464:if __name__ == "__main__":
services/ai_runtime/main.py:8:app = FastAPI(title=settings.app_name)
services/ai_runtime/main.py:9:app.include_router(router, prefix=settings.api_prefix)
services/web/chat-web-renderer/backend/tests/smoke/test_smoke_web_proxy.py:57:if __name__ == "__main__":
services/web/chat-web-renderer/backend/tests/smoke/test_smoke_runtime.py:36:if __name__ == "__main__":
services/etl-docs/tests/smoke/test_smoke_etl_docs.py:42:if __name__ == "__main__":
services/etl-docs/main.py:19:app = FastAPI(title="ETL Docs API", version="1.0.0")
services/web/chat-web-renderer/backend/app/main.py:13:app = FastAPI(title="Chat Web Renderer")
```

## Rutas API Detectadas

```text
services/scoring-core/main.py:62:@app.get("/")
services/scoring-core/app/api/scoring.py:50:@router.post("/scoring/jobs/enqueue", response_model=EnqueueScoreJobResponse)
services/scoring-core/app/api/scoring.py:73:@router.get("/scoring/jobs/{job_id}", response_model=ScoringJobResponse)
services/scoring-core/app/api/scoring.py:92:@router.get("/scoring/ops/summary", response_model=ScoringOpsSummaryResponse)
services/scoring-core/app/api/scoring.py:111:@router.get("/leads/{lead_id}/scorecards/latest", response_model=ScorecardResponse)
services/scoring-core/app/api/scoring.py:135:@router.get("/leads/{lead_id}/scorecards/{scorecard_id}", response_model=ScorecardResponse)
services/scoring-core/app/api/scoring.py:162:@router.get("/scoring/models/active", response_model=ActiveModelResponse)
services/scoring-core/app/api/scoring.py:202:@router.post("/cache/invalidate", response_model=CacheInvalidateResponse)
services/scoring-core/app/api/scoring.py:230:@router.post("/internal/memory/reset", response_model=InternalMemoryResetResponse)
services/scoring-core/app/api/scoring.py:253:@router.get("/health")
services/web/admin-console/backend/app/modules/contacts/router.py:225:@router.get("/contacts", response_model=WebIAFirstResponse)
services/web/admin-console/backend/app/modules/contacts/router.py:355:@router.get("/contacts/data", response_model=List[schemas.ContactGridRow])
services/web/admin-console/backend/app/modules/contacts/router.py:374:@router.get("/contacts/channels/data", response_model=List[schemas.ContactChannelListRow])
services/web/admin-console/backend/app/modules/contacts/router.py:393:@router.get("/contacts/channel-types")
services/web/admin-console/backend/app/modules/contacts/router.py:398:@router.get("/contacts/{contact_id}", response_model=schemas.ContactRead)
services/web/admin-console/backend/app/modules/contacts/router.py:410:@router.get("/contacts/{contact_id}/channels/data", response_model=List[schemas.ContactChannelManageRow])
services/web/admin-console/backend/app/modules/contacts/router.py:423:@router.get("/contacts/{contact_id}/channels/{channel_id}", response_model=schemas.ContactChannelManageRow)
services/web/admin-console/backend/app/modules/contacts/router.py:440:@router.post("/contacts", response_model=schemas.ContactRead)
services/web/admin-console/backend/app/modules/contacts/router.py:453:@router.post("/contacts/{contact_id}/channels", response_model=schemas.ContactChannelManageRow)
services/web/admin-console/backend/app/modules/contacts/router.py:469:@router.put("/contacts/{contact_id}", response_model=schemas.ContactRead)
services/web/admin-console/backend/app/modules/contacts/router.py:485:@router.put("/contacts/{contact_id}/channels/{channel_id}", response_model=schemas.ContactChannelManageRow)
services/web/admin-console/backend/app/modules/contacts/router.py:503:@router.delete("/contacts/{contact_id}")
services/web/admin-console/backend/app/modules/contacts/router.py:518:@router.delete("/contacts/{contact_id}/channels/{channel_id}")
services/web/admin-console/backend/app/modules/contacts/router.py:534:@router.post("/contacts/{contact_id}/convert")
services/web/admin-console/backend/app/modules/contacts/categories.py:42:@router.get("/contacts/categories", response_model=List[CategoryRead])
services/web/admin-console/backend/app/modules/roles/router.py:20:@router.get("", response_model=WebIAFirstResponse)
services/web/admin-console/backend/app/modules/roles/router.py:62:@router.get("/data", response_model=List[RoleRow])
services/web/admin-console/backend/app/modules/roles/router.py:66:@router.get("/{role_id}", response_model=RoleRow)
services/web/admin-console/backend/app/modules/roles/router.py:73:@router.post("", response_model=RoleRow)
services/web/admin-console/backend/app/modules/roles/router.py:77:@router.put("/{role_id}", response_model=RoleRow)
services/web/admin-console/backend/app/modules/roles/router.py:84:@router.delete("/{role_id}")
services/web/admin-console/backend/app/modules/clients/router.py:50:@router.get("/clients", response_model=WebIAFirstResponse)
services/web/admin-console/backend/app/modules/clients/router.py:144:@router.get("/clients/data", response_model=List[ClientRow])
services/web/admin-console/backend/app/modules/clients/router.py:149:@router.get("/clients/simple-list", response_model=List[ClientSimple])
services/web/admin-console/backend/app/modules/clients/router.py:154:@router.get("/clients/scoring-models/options")
services/web/admin-console/backend/app/modules/clients/router.py:159:@router.get("/clients/verticals/options")
services/web/admin-console/backend/app/modules/clients/router.py:164:@router.post("/clients", response_model=ClientRow)
services/web/admin-console/backend/app/modules/clients/router.py:168:@router.get("/clients/{client_id}", response_model=ClientRow)
services/web/admin-console/backend/app/modules/clients/router.py:176:@router.put("/clients/{client_id}", response_model=ClientRow)
services/web/admin-console/backend/app/modules/clients/router.py:183:@router.delete("/clients/{client_id}")
services/web/admin-console/backend/app/modules/clients/router.py:190:@router.get("/clients/{client_id}/dashboard", response_model=WebIAFirstResponse)
services/web/admin-console/backend/app/modules/clients/router.py:498:@router.get("/brand-config/{client_id}/list")
services/web/admin-console/backend/app/modules/clients/router.py:517:@router.get("/brand-config/{client_id}/item")
services/web/admin-console/backend/app/modules/clients/router.py:545:@router.delete("/brand-config/{client_id}")
services/web/admin-console/backend/app/modules/clients/router.py:567:@router.post("/brand-config/{client_id}")
services/web/admin-console/backend/app/modules/clients/router.py:568:@router.put("/brand-config/{client_id}/item")  # Support PUT for edit action
services/web/admin-console/backend/app/modules/grid_presets/router.py:13:@router.post("", response_model=GridPresetResponse)
services/web/admin-console/backend/app/modules/grid_presets/router.py:29:@router.get("/{grid_id}", response_model=List[GridPresetResponse])
services/web/admin-console/backend/app/modules/grid_presets/router.py:41:@router.delete("/{preset_id}")
services/web/admin-console/backend/app/modules/grid_presets/router.py:56:@router.patch("/{preset_id}/default")
services/web/admin-console/backend/app/modules/prompts/router.py:76:@router.get("", response_model=dict)
services/web/admin-console/backend/app/modules/prompts/router.py:145:@router.get("/data", response_model=List[PromptRow])
services/web/admin-console/backend/app/modules/prompts/router.py:162:@router.get("/{item_id}", response_model=PromptRow)
services/web/admin-console/backend/app/modules/prompts/router.py:171:@router.post("", response_model=PromptRow)
services/web/admin-console/backend/app/modules/prompts/router.py:184:@router.put("/{item_id}", response_model=PromptRow)
services/web/admin-console/backend/app/modules/prompts/router.py:202:@router.delete("/{item_id}")
services/web/admin-console/backend/app/modules/countries/router.py:13:@router.get("/countries", response_model=WebIAFirstResponse)
services/web/admin-console/backend/app/modules/countries/router.py:82:@router.get("/countries/data", response_model=List[CountryRow])
services/web/admin-console/backend/app/modules/countries/router.py:87:@router.post("/countries", response_model=CountryRow)
services/web/admin-console/backend/app/modules/countries/router.py:91:@router.get("/countries/{country_id}", response_model=CountryRow)
services/web/admin-console/backend/app/modules/countries/router.py:99:@router.put("/countries/{country_id}", response_model=CountryRow)
services/web/admin-console/backend/app/modules/countries/router.py:106:@router.delete("/countries/{country_id}")
services/web/admin-console/backend/app/modules/campaigns/router.py:8:@router.get("/", response_model=WebIAFirstResponse)
services/web/admin-console/backend/app/modules/campaigns/router.py:9:@router.get("", response_model=WebIAFirstResponse)
services/web/admin-console/backend/app/modules/system_public_docs/router.py:63:@router.get("", response_model=WebIAFirstResponse)
services/web/admin-console/backend/app/modules/system_public_docs/router.py:154:@router.get("/data", response_model=List[dict])
services/web/admin-console/backend/app/modules/system_public_docs/router.py:173:@router.post("/upload")
services/web/admin-console/backend/app/modules/system_public_docs/router.py:211:@router.delete("/{content_id}")
services/ai_runtime/api.py:124:@router.get("/health", response_model=HealthResponse)
services/ai_runtime/api.py:129:@router.post("/chat", response_model=ChatResponse)
services/ai_runtime/api.py:143:@router.post("/internal/memory/reset", response_model=InternalMemoryResetResponse)
services/ai_runtime/api.py:152:@router.post("/internal/session/reset", response_model=InternalSessionResetResponse)
services/ai_runtime/api.py:161:@router.get("/debug/turn-trace")
services/ai_runtime/api.py:166:@router.get("/debug/turn-trace/")
services/ai_runtime/api.py:171:@router.get("/debug/turn-trace/assets/{asset_path:path}")
services/ai_runtime/api.py:179:@router.get("/debug/turn-traces/clients/{client_id}/sessions")
services/ai_runtime/api.py:187:@router.get("/debug/turn-traces/config")
services/ai_runtime/api.py:195:@router.get("/debug/turn-traces/clients")
services/ai_runtime/api.py:202:@router.get("/debug/turn-traces/clients/{client_id}/sessions/{session_id}/turns")
services/ai_runtime/api.py:211:@router.delete("/debug/turn-traces/clients/{client_id}/sessions/{session_id}")
services/ai_runtime/api.py:225:@router.get("/debug/turn-traces/clients/{client_id}/sessions/{session_id}/turns/{turn}")
services/ai_runtime/api.py:238:@router.get("/debug/conversation-suites")
services/ai_runtime/api.py:243:@router.get("/debug/conversation-suites/")
services/ai_runtime/api.py:248:@router.get("/debug/conversation-suites/assets/{asset_path:path}")
services/ai_runtime/api.py:256:@router.get("/debug/generated-conversation-suites/config")
services/ai_runtime/api.py:264:@router.get("/debug/generated-conversation-suites/bundles")
services/ai_runtime/api.py:271:@router.get("/debug/generated-conversation-suites/bundles/{bundle_id}")
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_router.py:151:@router.get("", response_model=WebIAFirstResponse)
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_router.py:529:@router.get("/lookups/verticals")
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_router.py:534:@router.get("/lookups/models")
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_router.py:539:@router.get("/lookups/criteria")
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_router.py:544:@router.get("/data", response_model=List[VerticalRow])
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_router.py:549:@router.get("/{item_id:int}", response_model=VerticalRow)
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_router.py:557:@router.post("", response_model=VerticalRow)
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_router.py:562:@router.put("/{item_id:int}", response_model=VerticalRow)
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_router.py:570:@router.delete("/{item_id:int}")
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_router.py:578:@router.get("/models/data", response_model=List[ScoringModelRow])
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_router.py:586:@router.get("/models/{item_id}", response_model=ScoringModelRow)
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_router.py:594:@router.post("/models", response_model=ScoringModelRow)
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_router.py:599:@router.put("/models/{item_id}", response_model=ScoringModelRow)
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_router.py:607:@router.delete("/models/{item_id}")
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_router.py:615:@router.get("/criteria/data", response_model=List[ScoringCriterionRow])
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_router.py:623:@router.get("/criteria/{item_id}", response_model=ScoringCriterionRow)
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_router.py:631:@router.post("/criteria", response_model=ScoringCriterionRow)
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_router.py:636:@router.put("/criteria/{item_id}", response_model=ScoringCriterionRow)
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_router.py:644:@router.delete("/criteria/{item_id}")
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_router.py:652:@router.get("/bands/data", response_model=List[ScoringBandRow])
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_router.py:660:@router.get("/bands/{item_id}", response_model=ScoringBandRow)
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_router.py:668:@router.post("/bands", response_model=ScoringBandRow)
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_router.py:673:@router.put("/bands/{item_id}", response_model=ScoringBandRow)
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_router.py:681:@router.delete("/bands/{item_id}")
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_router.py:689:@router.get("/prompts/data", response_model=List[ScoringPromptRow])
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_router.py:697:@router.get("/prompts/{item_id}", response_model=ScoringPromptRow)
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_router.py:705:@router.post("/prompts", response_model=ScoringPromptRow)
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_router.py:710:@router.put("/prompts/{item_id}", response_model=ScoringPromptRow)
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_router.py:718:@router.delete("/prompts/{item_id}")
services/web/admin-console/backend/app/modules/leads_v2/router.py:68:@router.get("", response_model=WebIAFirstResponse)
services/web/admin-console/backend/app/modules/leads_v2/router.py:69:@router.get("/", response_model=WebIAFirstResponse)
services/web/admin-console/backend/app/modules/leads_v2/router.py:117:@router.get("/data", response_model=List[dict])
services/web/admin-console/backend/app/modules/leads_v2/router.py:134:@router.get("/{lead_id}", response_model=WebIAFirstResponse)
services/web/admin-console/backend/app/modules/leads_v2/router.py:182:@router.get("/{lead_id}/scoring", response_model=ScoringValuesV2)
services/web/admin-console/backend/app/modules/leads_v2/router.py:203:@router.get("/schema/current", response_model=ScoringSchemaV2)
services/web/admin-console/backend/app/modules/users/router.py:20:@router.get("", response_model=WebIAFirstResponse)
services/web/admin-console/backend/app/modules/users/router.py:98:@router.get("/data", response_model=List[UserRow])
services/web/admin-console/backend/app/modules/users/router.py:102:@router.get("/roles/simple-list")
services/web/admin-console/backend/app/modules/users/router.py:106:@router.get("/{item_id}", response_model=UserRow)
services/web/admin-console/backend/app/modules/users/router.py:113:@router.post("", response_model=UserRow)
services/web/admin-console/backend/app/modules/users/router.py:117:@router.put("/{item_id}", response_model=UserRow)
services/web/admin-console/backend/app/modules/users/router.py:121:@router.delete("/{item_id}")
services/web/admin-console/backend/app/modules/ai_library/router.py:21:@router.get("/", response_model=WebIAFirstResponse)
services/web/admin-console/backend/app/modules/ai_library/router.py:22:@router.get("", response_model=WebIAFirstResponse)
services/web/admin-console/backend/app/modules/ai_library/router.py:234:@router.get("/pdfs/data", response_model=List[dict])
services/web/admin-console/backend/app/modules/ai_library/router.py:260:@router.post("/pdfs/upload")
services/web/admin-console/backend/app/modules/ai_library/router.py:311:@router.get("/pdfs/jobs/{job_id}")
services/web/admin-console/backend/app/modules/ai_library/router.py:327:@router.delete("/pdfs/{content_id}")
services/web/admin-console/backend/app/modules/ai_library/router.py:348:@router.get("/urls/data", response_model=List[dict])
services/web/admin-console/backend/app/modules/leads/router.py:16:@router.get("/", response_model=WebIAFirstResponse)
services/web/admin-console/backend/app/modules/leads/router.py:17:@router.get("", response_model=WebIAFirstResponse)
services/web/admin-console/backend/app/modules/leads/router.py:67:@router.get("/data", response_model=List[dict])
services/web/admin-console/backend/app/modules/leads/router.py:146:@router.get("/me/data", response_model=List[dict])
services/web/admin-console/backend/app/modules/leads/router.py:196:@router.get("/me", response_model=WebIAFirstResponse)
services/web/admin-console/backend/app/modules/leads/router.py:235:@router.get("/{lead_id}", response_model=WebIAFirstResponse)
services/web/admin-console/backend/app/modules/leads/router.py:312:@router.get("/{lead_id}/chat", response_model=WebIAFirstResponse)
services/web/admin-console/backend/app/main.py:56:@app.get("/health")
services/web/admin-console/backend/app/dashboards/manager_workspace/router.py:13:@router.get("/manager", response_model=ManagerDashboardSchema)
services/web/admin-console/backend/app/dashboards/seller_workspace/router.py:14:@router.get("/seller", response_model=ClientUserDashboardSchema)
services/web/admin-console/backend/app/dashboards/seller_workspace/router.py:52:@router.get("/leads/{lead_id}", response_model=ClientUserDashboardSchema)
services/web/admin-console/backend/app/dashboards/seller_workspace/router.py:60:@router.get("/leads_v2/{lead_id}", response_model=ClientUserDashboardSchema)
services/web/admin-console/backend/app/dashboards/base_dash/router.py:10:@router.get("/app-init", response_model=UIAppShell)
services/web/admin-console/backend/app/dashboards/base_dash/router.py:72:@router.get("/base", response_model=WebIAFirstResponse)
services/web/admin-console/backend/app/dashboards/base_dash/router.py:94:@router.get("/check-contract", response_model=WebIAFirstResponse)
services/web/chat-web-renderer/backend/app/main.py:34:@app.get("/health")
services/web/chat-web-renderer/backend/app/main.py:39:@app.get("/health/dependencies")
services/web/chat-web-renderer/backend/app/main.py:102:@app.post("/chat/init", response_model=SDUIResponse)
services/web/chat-web-renderer/backend/app/main.py:114:@app.post("/chat/session/reset")
services/web/chat-web-renderer/backend/app/main.py:151:@app.post("/chat", response_model=SDUIResponse)
services/web/chat-web-renderer/backend/app/main.py:383:@app.get("/")
services/web/chat-web-renderer/backend/app/main.py:397:@app.post("/internal/memory/reset")
services/web/chat-web-renderer/backend/app/api/external.py:66:@router.post(
services/web/chat-web-renderer/backend/app/api/external.py:290:@router.get("/health")
services/etl-docs/main.py:28:@app.get("/")
services/etl-docs/main.py:33:@app.post("/documents/upload", status_code=202)
services/etl-docs/main.py:90:@app.get("/documents/list/{client_id}")
services/etl-docs/main.py:107:@app.get("/documents/jobs/{job_id}")
services/etl-docs/main.py:121:@app.delete("/documents/{client_id}/{content_id}")
services/etl-docs/main.py:137:@app.delete("/documents/client/{client_id}")
```

## AI Runtime

### `.agent/AI_RUNTIME_BOOTSTRAP.md`

```
# AI Runtime Bootstrap

Usar este archivo cuando la tarea toque:

- `services/ai_runtime/**`
- `services/data/**` consumido por el runtime
- `services/web/chat-web-renderer/backend/**`
- contratos conversacionales, memoria, tenant loading o routing entre verticales

No tomar como autoridad principal salvo instruccion explicita:

- `services/legacy/agent-core`
- `services/legacy/inference-stack-v2`
- `services/ai-agents`

`services/scoring-core` se considera un bounded context separado. Solo entrar ahi si la tarea toca scoring de forma directa.

## Lectura minima obligatoria

1. `services/ai_runtime/ARCHITECTURE.md`
2. `docs/AI_RUNTIME_INDEX.md`
3. `services/ai_runtime/main.py`
4. `services/ai_runtime/api.py`
5. `services/ai_runtime/runtime/settings.py`
6. `services/ai_runtime/runtime/bootstrap.py`
7. `services/ai_runtime/runtime/service.py`
8. `services/ai_runtime/domain/contracts.py`
9. `services/ai_runtime/domain/state.py`
10. `services/ai_runtime/domain/policies.py`
11. `services/ai_runtime/domain/vertical_adapters.py`
12. `services/ai_runtime/verticals.py`
13. `services/ai_runtime/graph/registry.py`
Lectura adicional segun el caso:

- `services/data/repositories/base.py`
- `services/data/cache/session_store.py`
- `services/web/chat-web-renderer/backend/app/core/runtime_client.py`
- `services/web/chat-web-renderer/backend/app/core/memory_reset.py`

## Prompts DB obligatorios

- Antes de tocar `realtor`, lead capture, scoring, `slot_hints`, appointment intent/type o policy conversacional, leer `.agent/ACTIVE_DB_PROMPTS.md`.
- Refrescar ese snapshot al menos una vez por sesion con `bash .agent/refresh_db_prompts.sh`.
- El baseline minimo obligatorio para realtor es `lead_scoring_prompts.id = '190dc860-9d37-4883-a6f4-c3019fdd882e'` (`Realtor Default`, prompt v4).
- Si no se pudo refrescar desde BD pero existe el snapshot local, usarlo como cache y reportar la falta de verificacion de frescura.
- Si no existe snapshot local y no se pudo leer la BD, no recomendar cambios de phrasing o politica conversacional como si fueran hechos.

## Supuestos Operativos

- `ai-runtime` es la unica autoridad conversacional del compose actual
- `client_id` entra desde el primer turno y nunca se pierde
- `tenant_config` se hidrata al inicio de la sesion y se cachea
- el estado del grafo vive en Redis y se persiste por sesion
- el runtime selecciona `grafo_realtor` o `grafo_basico` segun vertical/flow
- `shared` solo contiene infraestructura y piezas tecnicas neutrales
- `analyze_turn`, `intent_detector` y `synthesis_prompt` son responsabilidad semantica del vertical
- `VerticalPolicy` es la costura para quick actions, snapshots de referencia, journey y lead capture progresivo
- `GraphDependencies` solo contiene puertos shared; lo vertical-specific entra por `vertical_adapters`
- `lead_scoring_prompts` mantiene ownership separado y no debe invadir routing, analisis semantico ni phrasing final
- `scoring-core` corre aparte y no debe bloquear decisiones de chat

## Integracion ai-runtime ↔ scoring-core (activada)

Al finalizar cada turno, `service.py` ejecuta dos operaciones best-effort:

1. `conversation_repository.upsert_turn(...)` — persiste el par user/bot en
   `lead_conversations` (schema legacy: `messages jsonb`, `context_snapshot`,
   contadores). Crea o reutiliza el `lead_id` en `lead_leads`. El `lead_id`
   resuelto se pasa al paso 2.

2. `worker_dispatcher.fire_and_forget("scoring_enqueue", {...})` — dispara
   `POST scoring-core/api/v1/scoring/jobs/enqueue` como `asyncio.create_task`
   (no bloquea el turno). Si falla: log warning, `scoring_status="disabled"`.
   Si ok: `scoring_status="queued"` en `ChatResponse`.

El dispatcher vive en `runtime/bootstrap.py → InlineWorkerDispatcher`.
El enqueue HTTP usa `SCORING_CORE_API` + `SCORING_CORE_API_PREFIX` del entorno.
`SCORING_ENQUEUE_ENABLED=false` desactiva el disparo sin tocar codigo.

Ambas operaciones son best-effort: un fallo no aborta la respuesta al usuario.

## Restricciones de Cambio

- no mover logica de negocio desde `ai-runtime` hacia frontend o componentes legacy
- no reintroducir dependencias hacia componentes legacy como `services/legacy/agent-core` o `services/legacy/inference-stack-v2`
- no asumir heuristicas hardcodeadas para resolver intents, verticales o referencias
- no reintroducir prompts semanticos de negocio en `graph/_shared/prompts`
- no colgar `analyze_turn` ni `intent_detector` de prompts shared
- no reintroducir semantica realtor en nodos shared leyendo `last_search_results`, `cards_shown`, `last_mentioned` o quick actions hardcodeadas
- no volver a colgar repositorios verticales directo de `GraphDependencies`; usar `vertical_adapters`
- no mezclar en un mismo nodo interpretacion semantica, compilacion de intents, scoring y phrasing final
- si cambias naming o wiring Docker, tambien debes actualizar `.env.example` y `.agent/*`
```
### `docs/AI_RUNTIME_PROMPT_RUNTIME.md:1-29`

```
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

```
### `docs/AI_RUNTIME_PROMPT_RUNTIME.md:33-180`

```
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

Guardrail de contexto:

- los nodos shared no deben inyectar llaves semanticas realtor-only para interpretar turnos
- `analyze_turn` en `_shared` ahora compone contexto neutro y deja el mapping de dominio a la `VerticalPolicy`
- para realtor, el prompt recibe snapshots neutrales como:
  - `search_context`
  - `visible_reference_ids`
  - `visible_reference_items`
  - `reference_candidates`
  - `focused_entity`

## Mapa de nodos y su fuente

### Locales por vertical

- `analyze_turn`
```
### `services/ai_runtime/ARCHITECTURE.md`

```
# Datasyncsa AI Architecture

Documento de orientacion del runtime conversacional activo.

Precedencia si hay contradiccion:

1. codigo ejecutable vigente
2. `docs/AI_RUNTIME_PROMPT_RUNTIME.md` para carga/composicion de prompts
3. builders/routers del grafo y diagramas vivos en `services/ai_runtime/docs/graphs/`
4. este documento

## Objetivo

`services/ai_runtime` define el runtime conversacional multitenant activo de Datasyncsa AI con dos grafos LangGraph:

- `grafo_realtor`
- `grafo_basico`

El servicio es `multitenant-first`: ninguna operacion se ejecuta sin `client_id`, toda sesion se hidrata con `tenant_config`, y Redis/PostgreSQL se consultan con scope tenant desde la base del runtime.

## Principios Innegociables

1. `client_id` vive en el estado desde el primer turno.
2. El estado es acumulativo y se persiste por sesion.
3. Los prompts se componen en runtime como `stable_prefix + dynamic_context`.
   - `tone_prompt` del tenant es opcional
   - `analyze_turn`, `intent_detector` y `synthesis_prompt` son prompts locales por vertical
   - `lead_scoring_prompts` y `tone_prompt` siguen siendo configuracion externa
4. El LLM clasifica y redacta.
5. El codigo resuelve IDs, cola, reglas y side-effects.
6. Redis usa llaves prefijadas por tenant:
   - `{client_id}:session:{session_id}:state`
   - `{client_id}:session:{session_id}:lead`
   - `{client_id}:config`
   - `{client_id}:agents`

## Mapa de Carpetas

- `main.py`: entrypoint FastAPI minimo.
- `api.py`: `/health` y `/chat`.
- `domain/contracts.py`: entidades canonicas, request/response, intents.
- `domain/state.py`: estado base, estado generic y estado realtor.
- `domain/ports.py`: puertos shared del runtime y contenedor `GraphDependencies`.
- `domain/policies.py`: hooks neutrales que cada vertical inyecta en `_shared`.
- `domain/vertical_adapters.py`: bundles de dependencias especificas por vertical.
- `config/tenant_loader.py`: carga y cache de tenant.
- `config/prompt_composer.py`: tone + vertical + context.
- `runtime/bootstrap.py`: wiring por defecto.
- `runtime/service.py`: bootstrap de sesion e invocacion del grafo.
- `runtime/turn_trace.py`: trazado por turno para nodos, routers y LLM.
- `verticals.py`: registro explicito de `VerticalSpec`, `state_model`, `graph_builder` y `policy`.
- `docs/graphs/**`: diagramas exportados del `grafo_basico` y `grafo_realtor`.
- `web/turn_trace/**`: consola web minima para inspeccionar trazas del runtime.
- `graph/_shared/**`: nodos, routers, prompts y tools comunes.
- `graph/_shared/nodes/mail_node.py`: implementacion compartida del handoff mail.
- `graph/generic/**`: builder y nodos del vertical reducido.
- `graph/healthcare/**`, `graph/legal/**`, `graph/insurance/**`: prompts semanticos propietarios por vertical.
- `graph/realtor/**`: builder, prompts y herramientas del vertical completo.
- `rag/**`: repositorios pgvector aislados por tenant.
- `workers/lead_worker.py`: worker fire-and-forget placeholder v1.

## Flujo de Entrada

### Entrada directa al runtime

1. El cliente de canal llama directo a `ai-runtime`.
2. Puede omitir `flow`; si lo hace, `ConversationRuntime` lo resuelve por vertical.
3. Si envía `flow=realtor_flow`, `GraphRegistry` exige `vertical=realtor`.
4. Si envía `flow=basic_flow`, `GraphRegistry` exige `vertical in {healthcare, legal, insurance}`.
5. Se hidrata o recupera sesion y se ejecuta `grafo_realtor` o `grafo_basico`.

## Estado Canonico

El estado esta modelado en `domain/state.py` y contiene:

- sesion: `session_id`, `conversation_id`, `user_id`, `client_id`, `vertical`, `flow`, `current_turn`
- prompts/config: `capabilities`, `tenant_config`
- referencias: `resolved_references`, `pending_clarification`, `clarification_attempts`
- cola: `intent_queue`, `active_intent`, `completed_intents`, `turn_outputs`
- lead: `lead_advisor`, `lead`, `escalacion`
- cita: `cita`
- salida: `final_response`
- realtor state model:
  - `search_filters`, `inventory`, `last_search_results`, `last_mentioned`
  - `active_comparison`, `focus_scope`, `search_attempts`
  - `cards_shown`, `cards_mode`, `render_mode`, `ui_payload`
  - `financial_context`

Importante:

- `_shared` no debe leer directamente campos realtor-only para interpretar turnos.
- Los nodos shared consumen hooks neutrales de `VerticalPolicy` y trabajan con snapshots como:
  - `search_context`
  - `visible_reference_ids`
  - `visible_reference_items`
  - `reference_candidates`
  - `focused_entity`
- El formato serializado del estado realtor no cambia: los campos realtor siguen viviendo en `RealtorGraphState`, pero su semantica ya no debe estar cableada dentro de `_shared`.

## Seams por Vertical

La extension multi-vertical del runtime hoy se hace por tres costuras explicitas:

1. `VerticalSpec` en `verticals.py`
   - registra `state_model`, `graph_builder`, `policy`, `turn_frame_builder`, `required_fields` y `scoring_criteria`
2. `VerticalPolicy` en `domain/policies.py`
   - expone hooks neutrales para:
     - snapshots de contexto de busqueda
     - referencias visibles y candidatos de referencia
     - entidad enfocada
     - quick actions
     - journey y lead capture progresivo
     - coerciones/turn policies del vertical
3. `VerticalAdapters` en `domain/vertical_adapters.py`
   - `GraphDependencies` conserva solo puertos shared
   - los adapters verticales se resuelven por slug con `dependencies.get_adapters(vertical)`
   - `RealtorAdapters` encapsula hoy `property_repository`

Guardrail:

- un vertical nuevo no debe requerir editar nodos shared para introducir semantica de dominio.
- si un comportamiento depende del vertical, debe entrar por `VerticalPolicy`, `VerticalAdapters` o por un nodo propio del vertical.

## LangGraph Control Loops

Los diagramas renderizados del estado actual del runtime viven en `services/ai_runtime/docs/graphs/` y se regeneran desde `services/ai_runtime/scripts/export_graph_diagrams.py`.

Esta seccion resume la topologia comun. La fuente exacta de edges y routers vive en:

- `services/ai_runtime/graph/generic/graph.py`
- `services/ai_runtime/graph/realtor/graph.py`
- `services/ai_runtime/graph/_shared/routers/common.py`
- `services/ai_runtime/graph/realtor/routers/routes.py`

## Turn Trace

Para desarrollo, `ai-runtime` registra una traza JSON por turno en `/app/log/turn-traces` y expone una consola en `/api/v1/debug/turn-trace/`.

Cada turno registra:

- inicio y cierre del turno
- entrada y salida de cada nodo
- decisiones de routers
- prompts y respuestas del puerto LLM
- resumen del estado antes y despues de cada paso

### Shared flow

`START -> analyze_turn`

Routers compartidos:

- `after_analyze_turn`
  - `ask_clarification`
  - `collect_lead_data`
  - `capture_memory_entities`
- `after_capture_memory`
  - `memory_lookup`
  - `route_next_intent`
  - `lead_advisor`
  - `synthesize`
- `after_memory_lookup`
  - `route_next_intent`
  - `lead_advisor`
  - `synthesize`
  - `end`
- `after_check_queue`
  - `route_next_intent`
  - `lead_advisor`

### Clarification loop

- entrada: referencia ambigua o dato faltante
- una sola pregunta por turno
- maximo 3 intentos
- al llegar al limite, pasa a `collect_lead_data`

### Intent queue

- `analyze_turn` interpreta el turno y devuelve `turn_analysis` con `intent_plan` inicial
```
### `services/ai_runtime/main.py`

```
"""Minimal FastAPI entrypoint for the multitenant AI runtime."""

from fastapi import FastAPI

from services.ai_runtime.api import router
from services.ai_runtime.runtime.settings import settings

app = FastAPI(title=settings.app_name)
app.include_router(router, prefix=settings.api_prefix)
```
### `services/ai_runtime/api.py`

```
"""FastAPI router for the AI runtime."""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel

from services.ai_runtime.domain.contracts import (
    ChatRequest,
    ChatResponse,
    InternalMemoryResetRequest,
    InternalMemoryResetResponse,
    InternalSessionResetRequest,
    InternalSessionResetResponse,
)
from services.ai_runtime.runtime.bootstrap import runtime

router = APIRouter()
TURN_TRACE_WEB_ROOT = Path(__file__).resolve().parent / "web" / "turn_trace"
CONVERSATION_SUITE_WEB_ROOT = Path(__file__).resolve().parent / "web" / "conversation_suites"
GENERATED_CONVERSATION_SUITE_DIR = Path(
    os.getenv("AI_GENERATED_CONVERSATION_SUITES_DIR", "/app/log/generated-conversation-suites")
)
NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


class HealthResponse(BaseModel):
    status: str
    service: str


def _load_json_file(path: Path) -> dict[str, object] | list[object] | None:
    if not path.exists() or not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _infer_suite_type(*, bundle_id: str, meta: dict[str, object], report: dict[str, object]) -> str:
    explicit = str(meta.get("suite_type") or report.get("suite_type") or "").strip().lower()
    if explicit in {"generated", "regression", "manual"}:
        return explicit

    candidates = [
        bundle_id,
        str(meta.get("suite_id") or ""),
        str(report.get("suite_id") or ""),
    ]
    for candidate in candidates:
        normalized = candidate.strip().lower()
        if "regression" in normalized:
            return "regression"
        if "manual" in normalized:
            return "manual"
        if "generated" in normalized:
            return "generated"
    return "manual"


def _list_generated_suite_bundles() -> list[dict[str, object]]:
    if not GENERATED_CONVERSATION_SUITE_DIR.exists():
        return []
    bundles: list[dict[str, object]] = []
    for entry in GENERATED_CONVERSATION_SUITE_DIR.iterdir():
        if not entry.is_dir():
            continue
        meta = _load_json_file(entry / "meta.json") or {}
        report = _load_json_file(entry / "report.json") or {}
        summary = (report.get("summary") or {}) if isinstance(report, dict) else {}
        suite_type = _infer_suite_type(
            bundle_id=entry.name,
            meta=meta if isinstance(meta, dict) else {},
            report=report if isinstance(report, dict) else {},
        )
        bundles.append(
            {
                "bundle_id": entry.name,
                "suite_id": meta.get("suite_id") or entry.name,
                "suite_type": suite_type,
                "generated_at": meta.get("generated_at"),
                "conversations_total": summary.get("conversations_total"),
                "turns_total": summary.get("turns_total"),
                "turns_failed": summary.get("turns_failed"),
            }
        )
    bundles.sort(key=lambda item: str(item.get("generated_at") or ""), reverse=True)
    return bundles


def _load_generated_suite_bundle(bundle_id: str) -> dict[str, object]:
    bundle_dir = (GENERATED_CONVERSATION_SUITE_DIR / bundle_id).resolve()
    if not str(bundle_dir).startswith(str(GENERATED_CONVERSATION_SUITE_DIR.resolve())) or not bundle_dir.exists():
        raise HTTPException(status_code=404, detail="Bundle not found")
    suite = _load_json_file(bundle_dir / "suite.json")
    report = _load_json_file(bundle_dir / "report.json")
    meta = _load_json_file(bundle_dir / "meta.json")
    if suite is None and report is None:
        raise HTTPException(status_code=404, detail="Bundle is empty")
    bundle_meta = dict(meta or {}) if isinstance(meta, dict) else {}
    bundle_report = dict(report or {}) if isinstance(report, dict) else {}
    suite_type = _infer_suite_type(
        bundle_id=bundle_id,
        meta=bundle_meta,
        report=bundle_report,
    )
    bundle_meta.setdefault("suite_type", suite_type)
    bundle_report.setdefault("suite_type", suite_type)
    return {
        "bundle_id": bundle_id,
        "meta": bundle_meta,
        "suite": suite,
        "report": bundle_report,
    }


@router.get("/health", response_model=HealthResponse)
async def healthcheck() -> HealthResponse:
    return HealthResponse(status="ok", service="datasyncsa-ai-runtime")


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    return await runtime.handle_turn(request)


def _assert_internal_token(request: Request) -> None:
    expected = (os.getenv("INTERNAL_API_TOKEN") or "").strip()
    if not expected:
        return
    provided = (request.headers.get("X-Internal-Token") or "").strip()
    if provided != expected:
        raise HTTPException(status_code=401, detail="Invalid internal token")


@router.post("/internal/memory/reset", response_model=InternalMemoryResetResponse)
async def internal_memory_reset(
    payload: InternalMemoryResetRequest,
    request: Request,
) -> InternalMemoryResetResponse:
    _assert_internal_token(request)
    return await runtime.reset_client_memory(payload.client_id)


@router.post("/internal/session/reset", response_model=InternalSessionResetResponse)
async def internal_session_reset(
    payload: InternalSessionResetRequest,
    request: Request,
) -> InternalSessionResetResponse:
    _assert_internal_token(request)
    return await runtime.reset_session_memory(payload.client_id, payload.session_id)


@router.get("/debug/turn-trace")
async def turn_trace_console_redirect(request: Request) -> RedirectResponse:
    return RedirectResponse(url=f"{request.url.path}/")


@router.get("/debug/turn-trace/")
async def turn_trace_console() -> FileResponse:
    return FileResponse(TURN_TRACE_WEB_ROOT / "index.html", headers=NO_CACHE_HEADERS)


@router.get("/debug/turn-trace/assets/{asset_path:path}")
async def turn_trace_asset(asset_path: str) -> FileResponse:
    resolved = (TURN_TRACE_WEB_ROOT / asset_path).resolve()
    if not str(resolved).startswith(str(TURN_TRACE_WEB_ROOT.resolve())) or not resolved.exists():
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(resolved, headers=NO_CACHE_HEADERS)


@router.get("/debug/turn-traces/clients/{client_id}/sessions")
async def debug_turn_trace_sessions(client_id: str, request: Request) -> dict[str, object]:
```
### `services/ai_runtime/runtime/settings.py`

```
"""Environment-backed settings for the AI runtime."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class AISettings:
    app_name: str = os.getenv("AI_RUNTIME_APP_NAME", "datasyncsa-ai-runtime")
    api_prefix: str = os.getenv("AI_RUNTIME_API_PREFIX", "/api/v1")
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    database_url: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@postgres:5432/postgres")
    session_ttl_seconds: int = int(os.getenv("AI_SESSION_TTL_SECONDS", "3600"))
    request_timeout_seconds: int = int(os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "30"))
    mail_provider: str = os.getenv("AI_MAIL_PROVIDER", "placeholder")
    llm_provider: str = os.getenv("AI_LLM_PROVIDER", "auto")
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    llm_default_model: str = os.getenv(
        "LLM_DEFAULT_MODEL",
        os.getenv("LLM_MODEL", "gemini-2.5-flash-lite"),
    )
    llm_analyze_turn_model: str = os.getenv(
        "LLM_ANALYZE_TURN_MODEL",
        os.getenv("LLM_DEFAULT_MODEL", os.getenv("LLM_MODEL", "gemini-2.5-flash-lite")),
    )
    llm_timeout_seconds: int = int(os.getenv("LLM_TIMEOUT_SECS", "30"))
    llm_context_cache_enabled: bool = os.getenv("LLM_CONTEXT_CACHE_ENABLED", "true").lower() == "true"
    llm_context_cache_ttl_seconds: int = int(os.getenv("LLM_CONTEXT_CACHE_TTL_SECONDS", "1800"))
    llm_context_cache_min_stable_chars: int = int(os.getenv("LLM_CONTEXT_CACHE_MIN_STABLE_CHARS", "2000"))
    turn_trace_enabled: bool = os.getenv("AI_TURN_TRACE_ENABLED", "true").lower() == "true"
    turn_trace_dir: str = os.getenv("AI_TURN_TRACE_DIR", "/app/log/turn-traces")
    scoring_core_api: str = os.getenv("SCORING_CORE_API", "http://scoring-core:8000").rstrip("/")
    scoring_core_api_prefix: str = os.getenv("SCORING_CORE_API_PREFIX", "/api/v1")
    scoring_enqueue_enabled: bool = os.getenv("SCORING_ENQUEUE_ENABLED", "true").lower() == "true"
    scoring_enqueue_timeout_secs: float = float(os.getenv("SCORING_ENQUEUE_TIMEOUT_SECS", "2.0"))
    internal_api_token: str = os.getenv("INTERNAL_API_TOKEN", "")


settings = AISettings()
```
### `services/ai_runtime/runtime/bootstrap.py`

```
"""Dependency bootstrap for the AI runtime."""

from __future__ import annotations

import logging

import httpx

from services.ai_runtime.config.tenant_loader import TenantLoader
from services.ai_runtime.domain.contracts import MailDispatchResult
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.vertical_adapters import (
    HealthcareAdapters,
    InsuranceAdapters,
    LegalAdapters,
    RealtorAdapters,
)
from services.ai_runtime.graph.registry import GraphRegistry
from services.ai_runtime.rag.agency.repository import AgencyRAGRepository
from services.ai_runtime.rag.documents.repository import DocumentsRAGRepository
from services.ai_runtime.runtime.llm import build_llm_port
from services.ai_runtime.runtime.service import ConversationRuntime
from services.ai_runtime.runtime.settings import settings
from services.ai_runtime.runtime.turn_trace import FileTurnTraceStore, TracingLLMPort
from services.data.cache.lead_store import LeadStore
from services.data.cache.session_store import SessionStore
from services.data.cache.tenant_cache import TenantCache
from services.data.repositories.agent_repository import AgentRepository
from services.data.repositories.base import build_engine
from services.data.repositories.conversation_repository import ConversationRepository
from services.data.repositories.property_repository import PropertyRepository
from services.data.repositories.tenant_repository import TenantRepository

logger = logging.getLogger("ai_runtime.worker_dispatcher")


class PlaceholderMailer:
    async def send(self, payload: dict[str, object]):
        return MailDispatchResult(
            enviado=False,
            destinatarios=list(payload.get("destinatarios", [])),
            error="mail provider not configured",
        )


async def _do_scoring_enqueue(
    *,
    url: str,
    payload: dict[str, object],
    token: str,
    timeout: float,
) -> dict[str, object] | None:
    """Fire-and-forget HTTP call to scoring-core enqueue endpoint."""
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if token:
        headers["X-Internal-Token"] = token
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            logger.debug(
                "scoring_enqueue ok job_id=%s conversation_id=%s",
                data.get("id"),
                payload.get("conversation_id"),
            )
            return data if isinstance(data, dict) else None
    except Exception:
        logger.warning(
            "scoring_enqueue failed (fire-and-forget, non-blocking) "
            "conversation_id=%s",
            payload.get("conversation_id"),
            exc_info=True,
        )
    return None


class InlineWorkerDispatcher:
    """Dispatcher that handles fire-and-forget background tasks."""

    def __init__(
        self,
        *,
        scoring_enqueue_url: str,
        scoring_enqueue_enabled: bool,
        internal_token: str,
        enqueue_timeout: float,
    ) -> None:
        self._scoring_enqueue_url = scoring_enqueue_url
        self._scoring_enqueue_enabled = scoring_enqueue_enabled
        self._internal_token = internal_token
        self._enqueue_timeout = enqueue_timeout

    async def fire_and_forget(self, task_name: str, payload: dict[str, object]) -> dict[str, object] | None:
        if task_name == "scoring_enqueue" and self._scoring_enqueue_enabled:
            return await _do_scoring_enqueue(
                url=self._scoring_enqueue_url,
                payload=payload,
                token=self._internal_token,
                timeout=self._enqueue_timeout,
            )
        if task_name == "lead_worker":
            return None
        return None


engine = build_engine()
tenant_cache = TenantCache()
tenant_repository = TenantRepository(engine)
agent_repository = AgentRepository(engine)
trace_store = FileTurnTraceStore(settings.turn_trace_dir, enabled=settings.turn_trace_enabled)
tenant_loader = TenantLoader(
    tenant_repository=tenant_repository,
    agent_repository=agent_repository,
    tenant_cache=tenant_cache,
)
llm = TracingLLMPort(build_llm_port(settings), trace_store)

_scoring_enqueue_url = (
    f"{settings.scoring_core_api}{settings.scoring_core_api_prefix}/scoring/jobs/enqueue"
)

dependencies = GraphDependencies(
    llm=llm,
    session_store=SessionStore(),
    lead_store=LeadStore(),
    tenant_cache=tenant_cache,
    tenant_repository=tenant_repository,
    conversation_repository=ConversationRepository(engine),
    agent_repository=agent_repository,
    agency_rag_repository=AgencyRAGRepository(engine),
    documents_rag_repository=DocumentsRAGRepository(engine),
    mailer=PlaceholderMailer(),
    worker_dispatcher=InlineWorkerDispatcher(
        scoring_enqueue_url=_scoring_enqueue_url,
        scoring_enqueue_enabled=settings.scoring_enqueue_enabled,
        internal_token=settings.internal_api_token,
        enqueue_timeout=settings.scoring_enqueue_timeout_secs,
    ),
    trace_store=trace_store,
    vertical_adapters={
        "realtor": RealtorAdapters(property_repository=PropertyRepository(engine)),
        "healthcare": HealthcareAdapters(),
        "legal": LegalAdapters(),
        "insurance": InsuranceAdapters(),
    },
)
runtime = ConversationRuntime(
    tenant_loader=tenant_loader,
    graph_registry=GraphRegistry(),
    dependencies=dependencies,
)
```
### `services/ai_runtime/runtime/service.py`

```
"""Conversation bootstrap and orchestration helpers."""

from __future__ import annotations

import logging
from uuid import uuid4

from services.ai_runtime.config.tenant_loader import TenantLoader
from services.ai_runtime.domain.contracts import ChatMessage
from services.ai_runtime.domain.contracts import (
    ChatRequest,
    ChatResponse,
    InternalMemoryResetResponse,
    InternalSessionResetResponse,
)
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import (
    BaseGraphState,
    MemoryLookupState,
    build_lead_advisor_state,
    build_base_state,
)
from services.ai_runtime.graph.realtor.state.model import RealtorGraphState
from services.ai_runtime.graph.registry import GraphRegistry
from services.ai_runtime.runtime.cta_planner import apply_cta_delivery_plan, build_cta_delivery_plan
from services.ai_runtime.runtime.turn_trace import (
    TurnTraceContext,
    activate_turn_trace,
    activate_latest_turn_state,
    deactivate_turn_trace,
    deactivate_latest_turn_state,
    summarize_state,
    utc_now_iso,
)
from services.ai_runtime.verticals import get_vertical_spec
from services.ai_runtime.runtime.state_migrations import apply_migrations


logger = logging.getLogger(__name__)

_CHANNEL_MAP: dict[str, str] = {
    "web_html": "webchat",
    "api": "webchat",
    "web": "webchat",
    "webchat": "webchat",
    "meta_whatsapp": "whatsapp",
    "whatsapp": "whatsapp",
    "meta_ig": "instagram",
    "instagram": "instagram",
    "messenger": "messenger",
    "meta_messenger": "messenger",
    "telegram": "telegram",
    "meta_telegram": "telegram",
}


def _channel_to_platform(metadata: dict[str, object]) -> str:
    raw = str(metadata.get("channel") or "").strip().lower()
    return _CHANNEL_MAP.get(raw, "webchat")


def _build_last_turn_search_summary(base_state: BaseGraphState) -> dict[str, object] | None:
    if not isinstance(base_state, RealtorGraphState):
        return None
    search_outputs = [item for item in base_state.turn_outputs if str(item.get("type") or "").strip().lower() == "search"]
    if not search_outputs:
        return None
    latest = search_outputs[-1]
    return {
        "count": latest.get("count"),
        "match_scope": latest.get("match_scope"),
        "relaxation_applied": bool(latest.get("relaxation_applied")),
        "effective_filters": latest.get("effective_filters"),
    }


def _reset_turn_scoped_state(base_state: BaseGraphState) -> None:
    """Clear fields that belong to a single turn while keeping session memory alive."""

    base_state.last_turn_dialogue_act = base_state.turn_analysis.dialogue_act if base_state.turn_analysis else None
    base_state.last_turn_output_types = [str(item.get("type") or "") for item in base_state.turn_outputs]
    base_state.last_turn_search_summary = _build_last_turn_search_summary(base_state)
    base_state.final_response = None
    base_state.pending_clarification = None
    base_state.pending_decision = None
    base_state.clarification_attempts = 0
    base_state.resolved_references = []
    base_state.intent_queue = []
    base_state.active_intent = None
    base_state.completed_intents = []
    base_state.turn_outputs = []
    base_state.turn_analysis = None
    base_state.lead_advisor.should_ask = False
    base_state.lead_advisor.field_to_ask = None
    base_state.lead_advisor.question_to_ask = None
    base_state.memory.last_lookup = MemoryLookupState()
    base_state.turn_frame = None

    if isinstance(base_state, RealtorGraphState):
        base_state.render_mode = None
        base_state.cards_mode = None
        base_state.ui_payload = None
        base_state.search_attempts = 0
        base_state.effective_search_filters = None


class ConversationRuntime:
    """Coordinates tenant loading, state hydration, graph execution, and persistence."""

    def __init__(
        self,
        *,
        tenant_loader: TenantLoader,
        graph_registry: GraphRegistry,
        dependencies: GraphDependencies,
    ):
        self.tenant_loader = tenant_loader
        self.graph_registry = graph_registry
        self.dependencies = dependencies

    async def handle_turn(self, request: ChatRequest) -> ChatResponse:
        tenant_config = await self.tenant_loader.load(request.client_id)
        vertical_spec = get_vertical_spec(tenant_config.vertical)
        flow = request.flow or vertical_spec.default_flow
        user_id = (
            request.user_id
            or str(request.metadata.get("channel_user_id") or "")
            or str(request.metadata.get("user_id") or "")
            or str(request.metadata.get("lead_id") or "")
            or f"anonymous:{request.client_id}"
        )
        session_id = request.session_id or str(uuid4())
        conversation_id = request.conversation_id or str(uuid4())
        existing_payload = await self.dependencies.session_store.get_state(request.client_id, session_id)

        base_state = None
        if existing_payload:
            try:
                migrated_payload = apply_migrations(dict(existing_payload))
                base_state = vertical_spec.state_model.model_validate(migrated_payload)
            except Exception as exc:
                logger.warning(
                    "state_hydration_failed client_id=%s session_id=%s error=%s; starting fresh session",
                    request.client_id,
                    session_id,
                    exc,
                )
                base_state = None

        if base_state is not None:
            base_state.tenant_config = tenant_config
            base_state.capabilities = list(tenant_config.capabilities)
            base_state.vertical = tenant_config.vertical
            base_state.flow = flow
            base_state.user_id = user_id
            base_state.lead_advisor = build_lead_advisor_state(tenant_config, base_state.lead_advisor)
            _reset_turn_scoped_state(base_state)
            base_state.current_turn += 1
            base_state.messages.append(
                ChatMessage(
                    role="user",
                    content=request.message,
                    metadata=dict(request.metadata or {}),
                )
            )
            conversation_id = base_state.conversation_id
        else:
            state = build_base_state(
                session_id=session_id,
                conversation_id=conversation_id,
                user_id=user_id,
                client_id=request.client_id,
                vertical=tenant_config.vertical,
                flow=flow,
                tenant_config=tenant_config,
                initial_message=request.message,
                initial_message_metadata=request.metadata,
            )
            base_state = vertical_spec.state_model.model_validate(state.model_dump())
            _reset_turn_scoped_state(base_state)
```
### `services/ai_runtime/domain/state.py`

```
"""Base graph state contracts shared by every vertical."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from services.ai_runtime.domain.contracts import (
    Appointment,
    ChatMessage,
    ConversationEntity,
    FlowName,
    IntentDefinition,
    LeadExtracted,
    LeadPlaceholder,
    LeadScores,
    PendingDecision,
    ScoringProfile,
    TenantConfig,
    TurnAnalysis,
    Vertical,
)


CURRENT_SCHEMA_VERSION = 1


SCORING_CRITERION_ALIASES: dict[str, tuple[str, ...]] = {
    "apertura": ("apertura", "engagement", "engage", "openness"),
    "intencion": ("intencion", "intent", "purchase_intent"),
    "urgencia": ("urgencia", "timeline", "urgency", "emergencia", "plazo"),
    "match": ("match", "fit"),
    "solvencia": ("solvencia", "finance", "financial", "affordability"),
}
SCORING_FIELD_ALIASES: dict[str, str] = {
    "extracted_name": "nombre",
    "name": "nombre",
    "full_name": "nombre",
    "extracted_email": "email",
    "correo": "email",
    "mail": "email",
    "extracted_phone": "telefono",
    "phone": "telefono",
    "telefono_principal": "telefono",
    "budget": "presupuesto",
    "timeline": "fecha_preferida",
    "date_preferred": "fecha_preferida",
    "extracted_preferred_date": "fecha_preferida",
    "appointment_date": "fecha_preferida",
    "extracted_approval": "aprobacion",
    "extracted_budget": "presupuesto",
    "extracted_preference": "preferencias",
    "extracted_preferences": "preferencias",
    "extracted_appointment_type": "tipo_cita",
    "extracted_appointment_intent": "appointment_intent",
    "appointment_type": "tipo_cita",
    "schedule_intent": "appointment_intent",
}
_EMAIL_CONTACT_PATTERN = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", flags=re.IGNORECASE)


class EscalationState(BaseModel):
    solicitada: bool = False
    motivo: str | None = None
    agente_asignado: str | None = None
    datos_capturados: dict[str, Any] = Field(default_factory=dict)


class LeadAdvisorState(BaseModel):
    lead_scores: LeadScores = Field(default_factory=LeadScores)
    lead_extracted: LeadExtracted = Field(default_factory=LeadExtracted)
    lead_completo: bool = False
    capture_exposure_count: int = 0
    should_ask: bool = False
    field_to_ask: str | None = None
    question_to_ask: str | None = None
    scoring_profile: ScoringProfile | None = None
    criteria_scores: dict[str, float] = Field(default_factory=dict)
    criteria_reasons: dict[str, str] = Field(default_factory=dict)
    scoring_reasoning: str | None = None
    scoring_confidence: float | None = None
    scoring_last_updated_turn: int | None = None
    target_criteria: list[str] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    target_fields: list[str] = Field(default_factory=list)
    completed_fields: list[str] = Field(default_factory=list)


class MemoryLookupState(BaseModel):
    handled: bool = False
    key: str | None = None
    answer: str | None = None
    source: str | None = None


class ConversationMemoryState(BaseModel):
    entities: list[ConversationEntity] = Field(default_factory=list)
    last_lookup: MemoryLookupState = Field(default_factory=MemoryLookupState)


class BaseGraphState(BaseModel):
    """Shared state that exists from the first turn onward."""

    model_config = ConfigDict(extra="allow")

    session_id: str
    conversation_id: str
    user_id: str
    client_id: str
    vertical: Vertical
    flow: FlowName
    schema_version: int = Field(default=CURRENT_SCHEMA_VERSION)
    current_turn: int = 1
    messages: list[ChatMessage] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    tenant_config: TenantConfig
    resolved_references: list[dict[str, Any]] = Field(default_factory=list)
    pending_clarification: str | None = None
    pending_decision: PendingDecision | None = None
    clarification_attempts: int = 0
    intent_queue: list[IntentDefinition] = Field(default_factory=list)
    active_intent: IntentDefinition | None = None
    completed_intents: list[IntentDefinition] = Field(default_factory=list)
    turn_outputs: list[dict[str, Any]] = Field(default_factory=list)
    turn_analysis: TurnAnalysis | None = None
    last_turn_dialogue_act: str | None = None
    last_turn_output_types: list[str] = Field(default_factory=list)
    last_turn_search_summary: dict[str, Any] | None = None
    cita: Appointment
    escalacion: EscalationState = Field(default_factory=EscalationState)
    lead_advisor: LeadAdvisorState = Field(default_factory=LeadAdvisorState)
    memory: ConversationMemoryState = Field(default_factory=ConversationMemoryState)
    lead: LeadPlaceholder = Field(default_factory=LeadPlaceholder)
    final_response: str | None = None
    turn_frame: dict[str, Any] | None = None


class GenericGraphState(BaseGraphState):
    """State shared today by healthcare, legal, and insurance tenants."""

    pass


def is_valid_contact_email(value: str | None) -> bool:
    if not value:
        return False
    return bool(_EMAIL_CONTACT_PATTERN.match(value.strip()))


def is_valid_contact_phone(value: str | None) -> bool:
    if not value:
        return False
    digits = re.sub(r"\D", "", value)
    return 8 <= len(digits) <= 15


def has_valid_lead_contact(extracted: LeadExtracted) -> bool:
    return is_valid_contact_email(extracted.email) or is_valid_contact_phone(extracted.telefono)


def _normalize_criterion_key(key: str) -> str:
    return str(key or "").strip().lower()


def _normalize_field_key(key: str) -> str:
    normalized = str(key or "").strip().lower()
    return SCORING_FIELD_ALIASES.get(normalized, normalized)


def _vertical_scoring_defaults(vertical: Vertical) -> tuple[list[str], list[str]]:
    """Late-bound lookup of per-vertical scoring defaults.

    Avoids a circular import between ``domain.state`` and ``verticals``.
    """
    from services.ai_runtime.verticals import get_vertical_spec

    try:
        spec = get_vertical_spec(vertical)
```
### `services/ai_runtime/domain/policies.py`

```
"""Vertical policy hooks for runtime behavior that is not universally shared."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from services.ai_runtime.domain.contracts import PendingDecision, TurnAnalysis
from services.ai_runtime.domain.state import BaseGraphState, LeadAdvisorState


@dataclass(frozen=True, slots=True)
class QuickActionResolution:
    """Normalized turn override produced by a vertical-owned quick action.

    The shared runtime treats this object as an already-interpreted turn:
    - ``analysis`` is the synthetic TurnAnalysis for the action
    - ``resolved_references`` contains any resolved entities the action points to
    - ``pending_decision`` optionally pauses the flow for a follow-up choice
    - ``lead_advisor`` / ``cita`` carry state patches owned by the vertical
    """

    analysis: TurnAnalysis
    resolved_references: list[dict[str, Any]] = field(default_factory=list)
    pending_decision: PendingDecision | None = None
    lead_advisor: dict[str, Any] | None = None
    cita: dict[str, Any] | None = None


class VerticalPolicy(Protocol):
    """Behavior hooks injected by each vertical into the shared runtime.

    Hooks must stay neutral from the perspective of ``graph/_shared``:
    - ``search context`` means whatever query/filter snapshot helps a vertical
      interpret a follow-up turn.
    - ``visible reference items`` are the entities the user can reasonably point
      at in the current turn, typically because they were just surfaced.
    - ``reference candidates`` are the broader current result set that can be
      reused when the user refers back to recent entities.
    - ``focused entity`` is the single entity currently in focus, if any.
    """

    def snapshot_search_context(
        self,
        graph_state: BaseGraphState,
    ) -> dict[str, Any]:
        ...

    def resolve_visible_reference_items(
        self,
        graph_state: BaseGraphState,
    ) -> list[dict[str, Any]]:
        ...

    def resolve_reference_candidates(
        self,
        graph_state: BaseGraphState,
    ) -> list[dict[str, Any]]:
        ...

    def snapshot_focused_entity(
        self,
        graph_state: BaseGraphState,
    ) -> dict[str, Any] | None:
        ...

    def handle_quick_action(
        self,
        graph_state: BaseGraphState,
        metadata: dict[str, Any],
    ) -> QuickActionResolution | None:
        ...

    async def merge_filters(
        self,
        graph_state: BaseGraphState,
        analysis: TurnAnalysis,
        deps: Any,
    ) -> dict[str, Any] | None:
        ...

    def apply_turn_policies(
        self,
        graph_state: BaseGraphState,
        analysis: TurnAnalysis,
    ) -> tuple[TurnAnalysis, list[str]]:
        ...

    def derive_pending_decision(
        self,
        graph_state: BaseGraphState,
        analysis: TurnAnalysis,
    ) -> Any | None:
        ...

    def build_fallback_intent_plan(
        self,
        graph_state: BaseGraphState,
        analysis: TurnAnalysis,
    ) -> list[Any]:
        ...

    def internal_intents(self) -> set[str]:
        ...

    def field_has_value(self, extracted: Any, field_key: str) -> bool | None:
        ...

    def resolve_journey(
        self,
        graph_state: BaseGraphState,
    ) -> str | None:
        ...

    def progressive_field_plan(
        self,
        graph_state: BaseGraphState,
        lead_advisor_state: LeadAdvisorState,
    ) -> list[str]:
        ...

    def extra_lead_sync(
        self,
        graph_state: BaseGraphState,
        lead_payload: dict[str, Any],
    ) -> dict[str, Any]:
        ...

    def select_semantic_ctas(
        self,
        graph_state: BaseGraphState,
        *,
        channel: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        ...


class NullVerticalPolicy:
    """No-op policy for verticals without extra runtime behavior."""

    def snapshot_search_context(self, graph_state):
        _ = graph_state
        return {}

    def resolve_visible_reference_items(self, graph_state):
        _ = graph_state
        return []

    def resolve_reference_candidates(self, graph_state):
        _ = graph_state
        return []

    def snapshot_focused_entity(self, graph_state):
        _ = graph_state
        return None

    def handle_quick_action(self, graph_state, metadata):
        _ = (graph_state, metadata)
        return None

    async def merge_filters(self, graph_state, analysis, deps):
        return None

    def apply_turn_policies(self, graph_state, analysis):
        return analysis, []

    def derive_pending_decision(self, graph_state, analysis):
        return None

    def build_fallback_intent_plan(self, graph_state, analysis):
        return []

    def internal_intents(self):
        return set()

    def field_has_value(self, extracted, field_key):
        return None

    def resolve_journey(self, graph_state):
```
### `services/ai_runtime/domain/vertical_adapters.py`

```
"""Vertical-specific adapter bundles attached to the shared dependency container."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, Sequence

if TYPE_CHECKING:
    from services.ai_runtime.graph.realtor.contracts import Property


class VerticalAdapters(Protocol):
    """Marker protocol for vertical-owned dependency bundles."""


class RealtorPropertyRepositoryPort(Protocol):
    """Repository contract used by the realtor graph."""

    async def load_property_types(self) -> list[str]: ...

    async def run_text_to_sql_query(
        self,
        *,
        client_id: str,
        sql: str,
        params: dict[str, object],
    ) -> list["Property"]: ...

    async def load_properties_by_ids(
        self,
        *,
        client_id: str,
        property_ids: Sequence[str],
    ) -> list["Property"]: ...


@dataclass(frozen=True, slots=True)
class RealtorAdapters:
    property_repository: RealtorPropertyRepositoryPort


@dataclass(frozen=True, slots=True)
class HealthcareAdapters:
    pass


@dataclass(frozen=True, slots=True)
class LegalAdapters:
    pass


@dataclass(frozen=True, slots=True)
class InsuranceAdapters:
    pass
```
### `services/ai_runtime/verticals.py`

```
"""Explicit runtime vertical registry and response adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from services.ai_runtime.domain.contracts import FlowName, Vertical
from services.ai_runtime.domain.policies import NullVerticalPolicy, VerticalPolicy
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import BaseGraphState, GenericGraphState
from services.ai_runtime.domain.turn_frame import BaseTurnFrame
from services.ai_runtime.graph.generic.graph import build_generic_graph
from services.ai_runtime.graph._shared.turn_frame_builder import build_turn_frame
from services.ai_runtime.graph.realtor.graph import build_realtor_graph
from services.ai_runtime.graph.realtor.policies import RealtorPolicy
from services.ai_runtime.graph.realtor.state.model import RealtorGraphState
from services.ai_runtime.graph.realtor.turn_frame import RealtorTurnFrame
from services.ai_runtime.graph.realtor.turn_frame_builder import build_realtor_turn_frame

GraphBuilder = Callable[[GraphDependencies], Any]
ComponentBuilder = Callable[[BaseGraphState], list[dict[str, object]]]
TurnFrameBuilder = Callable[[BaseGraphState], BaseTurnFrame]


def _build_empty_components(_: BaseGraphState) -> list[dict[str, object]]:
    return []


def _build_realtor_base_components(final_state: BaseGraphState) -> list[dict[str, object]]:
    if not isinstance(final_state, RealtorGraphState):
        return []

    components: list[dict[str, object]] = []
    ui_payload = final_state.ui_payload or {}
    for card in ui_payload.get("property_cards", []):
        features = {
            "bedrooms_clean": card.get("bedrooms_clean"),
            "bathrooms_clean": card.get("bathrooms_clean"),
            "sqm_clean": card.get("sqm_clean"),
            "garage_clean": card.get("garage_clean"),
            "lot_size_sqm": card.get("lot_size_sqm"),
            "front": card.get("front"),
            "land_use": card.get("land_use"),
            "property_type": card.get("property_type"),
            "amenities": card.get("amenities") or [],
            "address": card.get("address"),
            "province": card.get("province"),
        }
        components.append(
            {
                "type": "property-card",
                "id": card.get("id"),
                "title": card.get("title"),
                "price": card.get("price"),
                "currency": card.get("currency"),
                "price_note": card.get("price_note"),
                "location": card.get("location") or card.get("address") or card.get("province"),
                "image_url": card.get("primary_image_url"),
                "image_urls": card.get("image_urls") or [],
                "photo_count": card.get("photo_count"),
                "public_url": card.get("public_url"),
                "tags": card.get("amenities") or [],
                "amenities": card.get("amenities") or [],
                "description": card.get("description"),
                "badge_main": card.get("badge_main"),
                "badge_sub": card.get("badge_sub"),
                "stats": card.get("stats") or [],
                "bedrooms_clean": card.get("bedrooms_clean"),
                "bathrooms_clean": card.get("bathrooms_clean"),
                "sqm_clean": card.get("sqm_clean"),
                "garage_clean": card.get("garage_clean"),
                "features": {
                    key: value
                    for key, value in features.items()
                    if value not in (None, "", [])
                },
                "quick_actions": [],
                "city": card.get("province"),
                "neighborhood": card.get("province"),
            }
        )
    return components


def _build_realtor_components(final_state: BaseGraphState) -> list[dict[str, object]]:
    return _build_realtor_base_components(final_state)


@dataclass(frozen=True, slots=True)
class VerticalSpec:
    slug: Vertical
    default_flow: FlowName
    state_model: type[BaseGraphState]
    graph_builder: GraphBuilder
    component_builder: ComponentBuilder = _build_empty_components
    policy: VerticalPolicy = field(default_factory=NullVerticalPolicy)
    turn_frame_model: type[BaseTurnFrame] = BaseTurnFrame
    turn_frame_builder: TurnFrameBuilder = build_turn_frame
    scoring_criteria: tuple[str, ...] = ()
    required_fields: tuple[str, ...] = ()


_VERTICAL_SPECS: dict[str, VerticalSpec] = {
    "realtor": VerticalSpec(
        slug="realtor",
        default_flow="realtor_flow",
        state_model=RealtorGraphState,
        graph_builder=build_realtor_graph,
        component_builder=_build_realtor_components,
        policy=RealtorPolicy(),
        turn_frame_model=RealtorTurnFrame,
        turn_frame_builder=build_realtor_turn_frame,
        scoring_criteria=("apertura", "intencion", "urgencia", "match", "solvencia"),
        required_fields=(
            "nombre",
            "contacto",
            "presupuesto",
            "aprobacion",
            "fecha_preferida",
            "appointment_intent",
        ),
    ),
    "healthcare": VerticalSpec(
        slug="healthcare",
        default_flow="basic_flow",
        state_model=GenericGraphState,
        graph_builder=build_generic_graph,
        scoring_criteria=("apertura", "intencion", "emergencia", "match", "solvencia"),
        required_fields=("nombre", "contacto", "appointment_intent"),
    ),
    "legal": VerticalSpec(
        slug="legal",
        default_flow="basic_flow",
        state_model=GenericGraphState,
        graph_builder=build_generic_graph,
        scoring_criteria=("apertura", "intencion", "urgencia", "match", "solvencia"),
        required_fields=("nombre", "contacto", "appointment_intent"),
    ),
    "insurance": VerticalSpec(
        slug="insurance",
        default_flow="basic_flow",
        state_model=GenericGraphState,
        graph_builder=build_generic_graph,
        scoring_criteria=("apertura", "intencion", "urgencia", "match", "solvencia"),
        required_fields=("nombre", "contacto", "presupuesto", "appointment_intent"),
    ),
}


def get_vertical_spec(vertical: Vertical | str) -> VerticalSpec:
    normalized = str(vertical or "").strip().lower()
    spec = _VERTICAL_SPECS.get(normalized)
    if spec is None:
        raise ValueError(f"Unsupported runtime vertical={vertical!r}")
    return spec


def get_supported_verticals() -> tuple[str, ...]:
    return tuple(_VERTICAL_SPECS)
```
### `services/ai_runtime/graph/registry.py`

```
"""Graph registry for flow and vertical selection."""

from __future__ import annotations

from services.ai_runtime.domain.contracts import FlowName, Vertical
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.verticals import get_vertical_spec


class GraphRegistry:
    """Select the correct LangGraph builder for the resolved tenant vertical."""

    def get_graph(self, vertical: Vertical, flow: FlowName, deps: GraphDependencies):
        spec = get_vertical_spec(vertical)
        if flow != spec.default_flow:
            raise ValueError(
                f"{flow} no puede usarse con vertical {vertical}; flow esperado={spec.default_flow}"
            )
        return spec.graph_builder(deps)
```
### `services/ai_runtime/graph/generic/graph.py`

```
"""Builder for the reduced generic LangGraph."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from services.ai_runtime.domain.state import GenericGraphState
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.graph._shared.nodes import (
    analyze_turn,
    ask_clarification,
    capture_memory_entities,
    check_queue,
    collect_lead_data,
    lead_advisor,
    memory_lookup,
    prepare_synthesis,
    route_next_intent,
    synthesize,
)
from services.ai_runtime.graph._shared.nodes.mail_node import build_mail_node
from services.ai_runtime.graph._shared.routers.common import (
    after_analyze_turn,
    after_capture_memory,
    after_check_queue,
    after_memory_lookup,
)
from services.ai_runtime.graph.generic.nodes.assign_agent_node import assign_agent
from services.ai_runtime.graph.generic.nodes.collect_appointment_data_node import collect_appointment_data
from services.ai_runtime.graph.generic.nodes.rag_agencia_node import rag_agencia
from services.ai_runtime.graph.generic.routers.routes import after_collect_appointment_data, after_route_next_intent
from services.ai_runtime.runtime.turn_trace import build_traced_node, build_traced_router


def build_generic_graph(deps: GraphDependencies):
    workflow = StateGraph(dict)
    workflow.add_node("analyze_turn", build_traced_node("analyze_turn", analyze_turn, deps))
    workflow.add_node("ask_clarification", build_traced_node("ask_clarification", ask_clarification, deps))
    workflow.add_node("capture_memory_entities", build_traced_node("capture_memory_entities", capture_memory_entities, deps))
    workflow.add_node("memory_lookup", build_traced_node("memory_lookup", memory_lookup, deps))
    workflow.add_node("route_next_intent", build_traced_node("route_next_intent", route_next_intent, deps))
    workflow.add_node("collect_lead_data", build_traced_node("collect_lead_data", collect_lead_data, deps))
    workflow.add_node("rag_agencia", build_traced_node("rag_agencia", rag_agencia, deps))
    workflow.add_node("collect_appointment_data", build_traced_node("collect_appointment_data", collect_appointment_data, deps))
    workflow.add_node("assign_agent", build_traced_node("assign_agent", assign_agent, deps))
    workflow.add_node("mensajear", build_mail_node(deps))
    workflow.add_node("check_queue", build_traced_node("check_queue", check_queue, deps))
    workflow.add_node("lead_advisor", build_traced_node("lead_advisor", lead_advisor, deps))
    workflow.add_node("prepare_synthesis", build_traced_node("prepare_synthesis", prepare_synthesis, deps))
    workflow.add_node("synthesize", build_traced_node("synthesize", synthesize, deps))

    workflow.add_edge(START, "analyze_turn")
    workflow.add_conditional_edges(
        "analyze_turn",
        build_traced_router("after_analyze_turn", after_analyze_turn, deps),
        {
            "ask_clarification": "ask_clarification",
            "collect_lead_data": "collect_lead_data",
            "capture_memory_entities": "capture_memory_entities",
        },
    )
    workflow.add_edge("ask_clarification", END)
    workflow.add_conditional_edges(
        "capture_memory_entities",
        build_traced_router("after_capture_memory", after_capture_memory, deps),
        {
            "memory_lookup": "memory_lookup",
            "route_next_intent": "route_next_intent",
            "lead_advisor": "lead_advisor",
            "synthesize": "prepare_synthesis",
        },
    )
    workflow.add_conditional_edges(
        "memory_lookup",
        build_traced_router("after_memory_lookup", after_memory_lookup, deps),
        {"route_next_intent": "route_next_intent", "lead_advisor": "lead_advisor", "end": END, "synthesize": "prepare_synthesis"},
    )
    workflow.add_edge("collect_lead_data", "prepare_synthesis")
    workflow.add_conditional_edges(
        "route_next_intent",
        build_traced_router("after_route_next_intent", after_route_next_intent, deps),
        {
            "rag_agencia": "rag_agencia",
            "collect_lead_data": "collect_lead_data",
            "collect_appointment_data": "collect_appointment_data",
            "mensajear": "mensajear",
            "lead_advisor": "lead_advisor",
        },
    )
    workflow.add_edge("rag_agencia", "check_queue")
    workflow.add_conditional_edges(
        "collect_appointment_data",
        build_traced_router("after_collect_appointment_data", after_collect_appointment_data, deps),
        {"assign_agent": "assign_agent", "synthesize": "prepare_synthesis"},
    )
    workflow.add_edge("assign_agent", "mensajear")
    workflow.add_edge("mensajear", "check_queue")
    workflow.add_conditional_edges(
        "check_queue",
        build_traced_router("after_check_queue", after_check_queue, deps),
        {"route_next_intent": "route_next_intent", "lead_advisor": "lead_advisor"},
    )
    workflow.add_edge("lead_advisor", "prepare_synthesis")
    workflow.add_edge("prepare_synthesis", "synthesize")
    workflow.add_edge("synthesize", END)
    return workflow.compile()
```
### `services/ai_runtime/graph/realtor/graph.py`

```
"""Builder for the full realtor LangGraph."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.graph._shared.nodes import (
    analyze_turn,
    ask_clarification,
    capture_memory_entities,
    check_queue,
    collect_lead_data,
    lead_advisor,
    memory_lookup,
    prepare_synthesis,
    route_next_intent,
    synthesize,
)
from services.ai_runtime.graph._shared.nodes.mail_node import build_mail_node
from services.ai_runtime.graph._shared.routers.common import (
    after_analyze_turn,
    after_capture_memory,
    after_check_queue,
    after_memory_lookup,
)
from services.ai_runtime.graph.realtor.nodes.assign_agent_node import assign_agent
from services.ai_runtime.graph.realtor.nodes.collect_appointment_data_node import collect_appointment_data
from services.ai_runtime.graph.realtor.nodes.compare_properties_node import compare_properties
from services.ai_runtime.graph.realtor.nodes.describe_result_set_node import describe_result_set
from services.ai_runtime.graph.realtor.nodes.focus_property_node import focus_property
from services.ai_runtime.graph.realtor.nodes.llm_recommend_node import llm_recommend
from services.ai_runtime.graph.realtor.nodes.mutate_comparison_set_node import mutate_comparison_set
from services.ai_runtime.graph.realtor.nodes.rag_agencia_node import rag_agencia
from services.ai_runtime.graph.realtor.nodes.rag_documents_node import rag_documents
from services.ai_runtime.graph.realtor.nodes.render_cards_node import render_cards
from services.ai_runtime.graph.realtor.nodes.search_node import search
from services.ai_runtime.graph.realtor.nodes.show_result_cards_node import show_result_cards
from services.ai_runtime.graph.realtor.routers.routes import (
    after_collect_appointment_data,
    after_render_cards,
    after_route_next_intent,
    after_search,
)
from services.ai_runtime.graph.realtor.tools.financial_calc import financial_calc
from services.ai_runtime.runtime.turn_trace import build_traced_node, build_traced_router


def build_realtor_graph(deps: GraphDependencies):
    workflow = StateGraph(dict)
    workflow.add_node("analyze_turn", build_traced_node("analyze_turn", analyze_turn, deps))
    workflow.add_node("ask_clarification", build_traced_node("ask_clarification", ask_clarification, deps))
    workflow.add_node("capture_memory_entities", build_traced_node("capture_memory_entities", capture_memory_entities, deps))
    workflow.add_node("memory_lookup", build_traced_node("memory_lookup", memory_lookup, deps))
    workflow.add_node("route_next_intent", build_traced_node("route_next_intent", route_next_intent, deps))
    workflow.add_node("describe_result_set", build_traced_node("describe_result_set", describe_result_set, deps))
    workflow.add_node("show_result_cards", build_traced_node("show_result_cards", show_result_cards, deps))
    workflow.add_node("focus_property", build_traced_node("focus_property", focus_property, deps))
    workflow.add_node("search", build_traced_node("search", search, deps))
    workflow.add_node("render_cards", build_traced_node("render_cards", render_cards, deps))
    workflow.add_node("financial_calc", build_traced_node("financial_calc", financial_calc, deps))
    workflow.add_node("compare_properties", build_traced_node("compare_properties", compare_properties, deps))
    workflow.add_node("mutate_comparison_set", build_traced_node("mutate_comparison_set", mutate_comparison_set, deps))
    workflow.add_node("collect_appointment_data", build_traced_node("collect_appointment_data", collect_appointment_data, deps))
    workflow.add_node("assign_agent", build_traced_node("assign_agent", assign_agent, deps))
    workflow.add_node("rag_agencia", build_traced_node("rag_agencia", rag_agencia, deps))
    workflow.add_node("rag_documents", build_traced_node("rag_documents", rag_documents, deps))
    workflow.add_node("collect_lead_data", build_traced_node("collect_lead_data", collect_lead_data, deps))
    workflow.add_node("llm_recommend", build_traced_node("llm_recommend", llm_recommend, deps))
    workflow.add_node("mensajear", build_mail_node(deps))
    workflow.add_node("check_queue", build_traced_node("check_queue", check_queue, deps))
    workflow.add_node("lead_advisor", build_traced_node("lead_advisor", lead_advisor, deps))
    workflow.add_node("prepare_synthesis", build_traced_node("prepare_synthesis", prepare_synthesis, deps))
    workflow.add_node("synthesize", build_traced_node("synthesize", synthesize, deps))

    workflow.add_edge(START, "analyze_turn")
    workflow.add_conditional_edges(
        "analyze_turn",
        build_traced_router("after_analyze_turn", after_analyze_turn, deps),
        {
            "ask_clarification": "ask_clarification",
            "collect_lead_data": "collect_lead_data",
            "capture_memory_entities": "capture_memory_entities",
        },
    )
    workflow.add_edge("ask_clarification", END)
    workflow.add_conditional_edges(
        "capture_memory_entities",
        build_traced_router("after_capture_memory", after_capture_memory, deps),
        {
            "memory_lookup": "memory_lookup",
            "route_next_intent": "route_next_intent",
            "lead_advisor": "lead_advisor",
            "synthesize": "prepare_synthesis",
        },
    )
    workflow.add_conditional_edges(
        "memory_lookup",
        build_traced_router("after_memory_lookup", after_memory_lookup, deps),
        {
            "route_next_intent": "route_next_intent",
            "lead_advisor": "lead_advisor",
            "end": END,
            "synthesize": "prepare_synthesis",
        },
    )
    workflow.add_edge("collect_lead_data", "prepare_synthesis")
    workflow.add_conditional_edges(
        "route_next_intent",
        build_traced_router("after_route_next_intent", after_route_next_intent, deps),
        {
            "search": "search",
            "describe_result_set": "describe_result_set",
            "show_result_cards": "show_result_cards",
            "focus_property": "focus_property",
            "financial_calc": "financial_calc",
            "compare_properties": "compare_properties",
            "mutate_comparison_set": "mutate_comparison_set",
            "collect_appointment_data": "collect_appointment_data",
            "rag_agencia": "rag_agencia",
            "rag_documents": "rag_documents",
            "collect_lead_data": "collect_lead_data",
            "llm_recommend": "llm_recommend",
            "mensajear": "mensajear",
            "lead_advisor": "lead_advisor",
        },
    )
    workflow.add_edge("describe_result_set", "check_queue")
    workflow.add_edge("show_result_cards", "check_queue")
    workflow.add_edge("focus_property", "check_queue")
    workflow.add_conditional_edges(
        "search",
        build_traced_router("after_search", after_search, deps),
        {"search": "search", "lead_advisor": "lead_advisor", "check_queue": "check_queue", "render_cards": "render_cards"},
    )
    workflow.add_conditional_edges(
        "render_cards",
        build_traced_router("after_render_cards", after_render_cards, deps),
        {"check_queue": "check_queue"},
    )
    workflow.add_edge("financial_calc", "check_queue")
    workflow.add_edge("compare_properties", "check_queue")
    workflow.add_edge("mutate_comparison_set", "check_queue")
    workflow.add_edge("rag_agencia", "check_queue")
    workflow.add_edge("rag_documents", "check_queue")
    workflow.add_edge("llm_recommend", "check_queue")
    workflow.add_conditional_edges(
        "collect_appointment_data",
        build_traced_router("after_collect_appointment_data", after_collect_appointment_data, deps),
        {"assign_agent": "assign_agent", "lead_advisor": "lead_advisor"},
    )
    workflow.add_edge("assign_agent", "mensajear")
    workflow.add_edge("mensajear", "check_queue")
    workflow.add_conditional_edges(
        "check_queue",
        build_traced_router("after_check_queue", after_check_queue, deps),
        {"route_next_intent": "route_next_intent", "lead_advisor": "lead_advisor"},
    )
    workflow.add_edge("lead_advisor", "prepare_synthesis")
    workflow.add_edge("prepare_synthesis", "synthesize")
    workflow.add_edge("synthesize", END)
    return workflow.compile()
```
### `services/ai_runtime/graph/_shared/nodes/mail_node.py`

```
"""Shared mail delivery node."""

from __future__ import annotations

from typing import Any

from services.ai_runtime.domain.contracts import TenantConfig
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import BaseGraphState
from services.ai_runtime.graph._shared.nodes.helpers import complete_active_intent
from services.ai_runtime.graph._shared.tools.mensajear import mensajear
from services.ai_runtime.runtime.turn_trace import build_traced_node


def build_mail_node(deps: GraphDependencies):
    async def _mail_impl(state: dict[str, Any], runtime_deps: GraphDependencies) -> dict[str, Any]:
        tenant_config = TenantConfig.model_validate(state["tenant_config"])
        graph_state = BaseGraphState.model_validate(state)
        result = await mensajear(
            dependencies=runtime_deps,
            client_id=state["client_id"],
            tipo="appointment_confirmation",
            destinatarios=[],
            datos_cita=state.get("cita", {}),
            tenant_config=tenant_config,
        )
        output = {"type": "mensajear", **result.model_dump(mode="json")}
        return {
            "turn_outputs": [*state.get("turn_outputs", []), output],
            **complete_active_intent(graph_state, output),
        }

    return build_traced_node("mensajear", _mail_impl, deps)
```

## Canal Web

### `services/web/chat-web-renderer/backend/app/core/runtime_client.py`

```
import os
import httpx
import logging
from typing import Dict, Any

# Logger config
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("runtime_client")


class InferenceClient:
    """
    El cable que conecta el renderer con el runtime conversacional activo.
    Se encarga de enviar el payload con metadatos y recibir la respuesta plana.
    Opera contra el runtime activo del asistente.
    """

    def __init__(self):
        self.timeout = int(os.getenv("INFERENCE_TIMEOUT", 60))
        self.connect_timeout = float(os.getenv("INFERENCE_CONNECT_TIMEOUT", 5))
        self.default_client_id = os.getenv("DEFAULT_CLIENT_ID", "")
        inference_url = os.getenv("AI_RUNTIME_API", "http://ai-runtime:8000")
        api_prefix = os.getenv("AI_RUNTIME_API_PREFIX", "/api/v1")
        self.base_url = inference_url.rstrip("/") + api_prefix
        logger.info("🔌 InferenceClient conectado a %s (Timeout: %ss)", self.base_url, self.timeout)

    async def chat(self, user_query: str, session: Dict[str, Any]) -> Dict[str, Any]:
        """
        Envía un mensaje al Core AI.
        
        :param user_query: El texto que escribió el usuario.
        :param session: Diccionario con metadatos de la sesión (conversation_id, lead_id, etc.)
        """
        url = f"{self.base_url}/chat"
        trace_id = str(session.get("debug_trace_id") or "-")
        
        user_metadata = {
            "lead_id": session.get("lead_id"),
            "brand_project": session.get("brand_project"),
            "channel": session.get("channel"),
            "channel_user_id": session.get("channel_user_id"),
            "user_id": session.get("auth_user_id") or session.get("channel_user_id"),
            "utm_source": session.get("utm_source"),
            "utm_medium": session.get("utm_medium"),
            "utm_campaign": session.get("utm_campaign"),
            "utm_content": session.get("utm_content"),
            "utm_term": session.get("utm_term"),
            "gclid": session.get("gclid"),
            "fbclid": session.get("fbclid"),
            "ttclid": session.get("ttclid"),
            "msclkid": session.get("msclkid"),
            "li_fat_id": session.get("li_fat_id"),
            "gbraid": session.get("gbraid"),
            "wbraid": session.get("wbraid"),
            "referrer_url": session.get("referrer_url"),
            "property_id": session.get("property_id"),
            "landing_page_url": session.get("landing_page_url"),
            "action_id": session.get("action_id"),
            "action_label": session.get("action_label"),
            "action_type": session.get("action_type"),
            "target_property_id": session.get("target_property_id"),
            "target_property_title": session.get("target_property_title"),
        }
        user_metadata = {k: v for k, v in user_metadata.items() if v is not None}

        payload = {
            "queryText": user_query,
            "clientId": session.get("client_id", self.default_client_id),
            "userId": session.get("auth_user_id") or session.get("channel_user_id"),
            "sessionId": session.get("session_id"),
            "conversationId": session.get("conversation_id"),
            "userMetadata": user_metadata if user_metadata else None
        }
        payload = {k: v for k, v in payload.items() if v is not None}

        try:
            timeout = httpx.Timeout(timeout=self.timeout, connect=self.connect_timeout)
            async with httpx.AsyncClient(timeout=timeout) as client:
                logger.info(
                    "📤 Enviando mensaje al Core: trace_id=%s client_id=%s session_id=%s conversation_id=%s channel=%s channel_user_id=%s text=%s",
                    trace_id,
                    session.get("client_id"),
                    session.get("session_id"),
                    session.get("conversation_id"),
                    session.get("channel"),
                    session.get("channel_user_id"),
                    user_query[:50],
                )
                response = await client.post(url, json=payload)
                response.raise_for_status()
                
                data = response.json()
                logger.info(
                    "📥 Respuesta recibida del Core: trace_id=%s session_id=%s conversation_id=%s answer_chars=%s components=%s",
                    trace_id,
                    data.get("sessionId", data.get("session_id")),
                    data.get("conversationId", data.get("conversation_id")),
                    len((data.get("answer") or "").strip()),
                    len(data.get("components") or []),
                )
                return self._normalize_v2_response(data)

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Error HTTP del Core: {e.response.status_code} - {e.response.text}")
            raise ValueError(f"Error del servidor de IA: {e.response.status_code}")

        except httpx.TimeoutException as e:
            logger.error(f"❌ Timeout con Core ({self.timeout}s): {repr(e)}")
            raise TimeoutError("El servicio de IA tardó demasiado en responder.")

        except httpx.RequestError as e:
            logger.error(f"❌ Error de conexión con el Core: {repr(e)}")
            raise ConnectionError("No se pudo conectar con el cerebro de IA.")

        except Exception as e:
            logger.error(f"❌ Error inesperado en el runtime client: {str(e)}")
            raise

    def _normalize_v2_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normaliza la respuesta del core al formato esperado por el transformer.
        """
        normalized = {
            "answer": data.get("answer", ""),
            "sources": data.get("sources", []),
            "components": data.get("components", []),
            "intent": data.get("intent"),
            "session_id": str(data.get("sessionId", data.get("session_id", ""))),
            "conversation_id": str(data.get("conversationId", data.get("conversation_id", ""))),
        }
        
        if "realtorTurn" in data or "realtor_turn" in data:
            normalized["realtor_turn"] = data.get("realtor_turn") or data.get("realtorTurn")
        
        if data.get("leadId") or data.get("lead_id"):
            normalized["lead_id"] = str(data.get("leadId") or data.get("lead_id"))
        
        if data.get("scorecard"):
            scorecard = data["scorecard"]
            normalized["scorecard"] = {
                "score_total": scorecard.get("scoreTotal", scorecard.get("score_total")),
                "priority_label": scorecard.get("priorityLabel", scorecard.get("priority_label")),
                "reasoning": scorecard.get("reasoning"),
                "score_items": scorecard.get("scoreItems", scorecard.get("score_items", [])),
                "model_version": scorecard.get("modelVersion", scorecard.get("model_version")),
                "prompt_version": scorecard.get("promptVersion", scorecard.get("prompt_version")),
            }
        
        if data.get("scorecardId") or data.get("scorecard_id"):
            normalized["scorecard_id"] = str(data.get("scorecardId") or data.get("scorecard_id"))

        if data.get("scoringStatus") or data.get("scoring_status"):
            normalized["scoring_status"] = str(data.get("scoringStatus") or data.get("scoring_status"))
        if data.get("scoringJobId") or data.get("scoring_job_id"):
            normalized["scoring_job_id"] = str(data.get("scoringJobId") or data.get("scoring_job_id"))
        if data.get("scoringEta") or data.get("scoring_eta"):
            normalized["scoring_eta"] = str(data.get("scoringEta") or data.get("scoring_eta"))

        if data.get("metadata"):
            normalized["metadata"] = data.get("metadata")
        
        return normalized
```
### `services/web/chat-web-renderer/backend/app/core/memory_reset.py`

```
import asyncio
import logging
import os
from typing import Any, Dict

import httpx


logger = logging.getLogger("memory_reset")


class RuntimeMemoryResetError(RuntimeError):
    def __init__(self, *, failures: Dict[str, str], partial_results: Dict[str, Any]) -> None:
        self.failures = failures
        self.partial_results = partial_results
        message = "; ".join(f"{service}: {error}" for service, error in failures.items())
        super().__init__(message or "runtime_memory_reset_failed")


class MemoryResetClient:
    def __init__(self):
        self.ai_runtime_reset_url = os.getenv(
            "AI_RUNTIME_RESET_URL",
            "http://ai-runtime:8000/api/v1/internal/memory/reset",
        ).rstrip("/")
        self.scoring_core_reset_url = self._resolve_scoring_reset_url()
        self.timeout = float(os.getenv("INFERENCE_TIMEOUT", 60))
        self.internal_token = (os.getenv("INTERNAL_API_TOKEN") or "").strip()

        logger.info(
            "MemoryResetClient configured (ai_runtime=%s scoring_core=%s)",
            self.ai_runtime_reset_url,
            self.scoring_core_reset_url,
        )

    @staticmethod
    def _resolve_scoring_reset_url() -> str:
        explicit_url = (os.getenv("SCORING_CORE_RESET_URL") or "").strip()
        if explicit_url:
            return explicit_url.rstrip("/")

        scoring_core_api = (os.getenv("SCORING_CORE_API") or "http://scoring-core:8000").strip().rstrip("/")
        prefix = (
            os.getenv("SCORING_API_PREFIX")
            or os.getenv("SCORING_CORE_API_PREFIX")
            or "/api/v1"
        ).strip()
        if not prefix.startswith("/"):
            prefix = f"/{prefix}"
        prefix = prefix.rstrip("/")
        return f"{scoring_core_api}{prefix}/internal/memory/reset"

    @staticmethod
    def _format_error(exc: Exception) -> str:
        if isinstance(exc, httpx.HTTPStatusError):
            response = exc.response
            body = response.text.strip()
            if len(body) > 250:
                body = f"{body[:247]}..."
            return f"HTTP {response.status_code} ({body})"
        return str(exc) or exc.__class__.__name__

    async def _post_reset(
        self,
        *,
        client: httpx.AsyncClient,
        url: str,
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()

    async def reset_inference_memory(self, client_id: str, reason: str | None = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"client_id": client_id}
        if reason:
            payload["reason"] = reason

        headers: Dict[str, str] = {}
        if self.internal_token:
            headers["X-Internal-Token"] = self.internal_token

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            return await self._post_reset(
                client=client,
                url=self.ai_runtime_reset_url,
                payload=payload,
                headers=headers,
            )

    async def reset_runtime_session(
        self,
        *,
        client_id: str,
        session_id: str,
        reason: str | None = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "client_id": client_id,
            "session_id": session_id,
        }
        if reason:
            payload["reason"] = reason

        headers: Dict[str, str] = {}
        if self.internal_token:
            headers["X-Internal-Token"] = self.internal_token

        session_reset_url = self.ai_runtime_reset_url.replace(
            "/internal/memory/reset",
            "/internal/session/reset",
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            return await self._post_reset(
                client=client,
                url=session_reset_url,
                payload=payload,
                headers=headers,
            )

    async def reset_runtime_memory(self, client_id: str, reason: str | None = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"client_id": client_id}
        if reason:
            payload["reason"] = reason

        headers: Dict[str, str] = {}
        if self.internal_token:
            headers["X-Internal-Token"] = self.internal_token

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            agent_result, scoring_result = await asyncio.gather(
                self._post_reset(
                    client=client,
                    url=self.ai_runtime_reset_url,
                    payload=payload,
                    headers=headers,
                ),
                self._post_reset(
                    client=client,
                    url=self.scoring_core_reset_url,
                    payload=payload,
                    headers=headers,
                ),
                return_exceptions=True,
            )

        results: Dict[str, Any] = {}
        failures: Dict[str, str] = {}
        if isinstance(agent_result, Exception):
            failures["ai_runtime"] = self._format_error(agent_result)
        else:
            results["ai_runtime"] = agent_result

        if isinstance(scoring_result, Exception):
            failures["scoring_core"] = self._format_error(scoring_result)
        else:
            results["scoring_core"] = scoring_result

        if failures:
            raise RuntimeMemoryResetError(failures=failures, partial_results=results)

        return results
```
### `services/web/chat-web-renderer/backend/app/main.py`

```
import os
import logging
import time
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import httpx
from app.schemas.chat import InitRequest, InternalMemoryResetRequest, SessionResetRequest
from app.schemas.internal_chat import InternalChatRequest
from app.schemas.ui import SDUIResponse

app = FastAPI(title="Chat Web Renderer")
logger = logging.getLogger("chat_web_renderer.main")

cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:8087,http://192.168.0.37:8087",
    ).split(",")
    if origin.strip()
]
allow_credentials = "*" not in cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["*"],
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "operational", "service": "chat-web-renderer-api"}


@app.get("/health/dependencies")
async def dependencies_health():
    """
    Lightweight dependency health for frontend status indicator.
    """
    timeout = float(os.getenv("HEALTHCHECK_TIMEOUT", "3"))
    inference_base = os.getenv("AI_RUNTIME_API", "http://ai-runtime:8000").rstrip("/")
    inference_prefix = os.getenv("AI_RUNTIME_API_PREFIX", "/api/v1")
    inference_url = f"{inference_base}{inference_prefix}/health"

    result = {
        "status": "operational",
        "service": "chat-web-renderer-api",
        "dependencies": {
            "ai_runtime": {"ok": False, "url": inference_url},
        },
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        for name, url in (("ai_runtime", inference_url),):
            try:
                resp = await client.get(url)
                result["dependencies"][name]["ok"] = resp.status_code == 200
                if resp.status_code == 200:
                    try:
                        result["dependencies"][name]["detail"] = resp.json()
                    except Exception:
                        result["dependencies"][name]["detail"] = {"status_code": resp.status_code}
                else:
                    result["dependencies"][name]["error"] = f"HTTP {resp.status_code}"
            except Exception as exc:
                result["dependencies"][name]["error"] = str(exc)

    all_ok = all(dep.get("ok") for dep in result["dependencies"].values())
    result["status"] = "operational" if all_ok else "degraded"
    return result

from app.core.runtime_client import InferenceClient
from app.core.memory_reset import MemoryResetClient, RuntimeMemoryResetError
from app.core.session_identity import (
    normalize_session_id,
    resolve_effective_session_id,
    resolve_request_session_id,
)
from app.core.vertical_router import GENERIC_RENDER_VERTICALS, vertical_router
from app.transformer.core import SDUITransformer
from app.transformer.realtor_policy import RealtorRendererPolicy
from app.transformer.generic_policy import GenericRendererPolicy
from app.session.manager import SessionManager

inference_client = InferenceClient()
memory_reset_client = MemoryResetClient()
transformer = SDUITransformer()
session_manager = SessionManager()

vertical_router.register_strategy("realtor", "web_html", RealtorRendererPolicy(channel="web_html"))
for vertical_slug in GENERIC_RENDER_VERTICALS:
    vertical_router.register_strategy(
        vertical_slug,
        "web_html",
        GenericRendererPolicy(channel="web_html", vertical_slug=vertical_slug),
    )

@app.post("/chat/init", response_model=SDUIResponse)
async def chat_init(req: InitRequest):
    client_id = str(req.client_id)
    return await transformer.transform(
        {"answer": "", "sources": []},
        "init",
        client_id,
        brand_project=req.brand_project,
        include_fallback_text=False,
    )


@app.post("/chat/session/reset")
async def chat_session_reset(req: SessionResetRequest):
    client_id = str(req.client_id)
    deleted = await session_manager.delete_session_multichannel(
        client_id=client_id,
        channel="web_html",
        channel_user_id=req.channel_user_id,
    )

    runtime_reset = None
    runtime_reset_error = None
    if req.session_id:
        try:
            runtime_reset = await memory_reset_client.reset_runtime_session(
                client_id=client_id,
                session_id=str(req.session_id),
                reason=req.reason or "new_chat",
            )
        except Exception as exc:  # pragma: no cover - best effort reset
            runtime_reset_error = str(exc)
            logger.warning(
                "CHAT_SESSION_RESET runtime reset failed client_id=%s session_id=%s error=%s",
                client_id,
                req.session_id,
                runtime_reset_error,
            )

    return {
        "status": "ok",
        "client_id": client_id,
        "channel_user_id": req.channel_user_id,
        "session_deleted": deleted,
        "runtime_reset": runtime_reset,
        "runtime_reset_error": runtime_reset_error,
    }


@app.post("/chat", response_model=SDUIResponse)
async def chat_interaction(req: InternalChatRequest):
    """
    Canonical chat endpoint using InternalChatRequest contract.
    This endpoint is explicitly limited to web_html for predictable SDUI output.
    """
    if req.channel != "web_html":
        raise HTTPException(
            status_code=422,
            detail="/chat only supports channel='web_html'; use channel-specific endpoints for other channels",
        )
    
    client_id = str(req.client_id)
    channel = req.channel
    channel_user_id = str(req.channel_user_id or f"web_{client_id}").strip()
    metadata = dict(req.metadata or {})
    trace_id = str(metadata.get("debug_trace_id") or "")
    incoming_session_id = normalize_session_id(req.session_id)
    incoming_conversation_id = str(req.conversation_id) if req.conversation_id else None
    request_started = time.perf_counter()

    session_data = await session_manager.get_session_multichannel(
        client_id=client_id,
        channel=channel,
        channel_user_id=channel_user_id,
    )
    
    session_context = {
        "client_id": client_id,
        "session_id": resolve_request_session_id(
```

## Data Layer Compartida

### `services/data/repositories/base.py`

```
"""Shared PostgreSQL repository helpers."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from services.ai_runtime.runtime.settings import settings


def _normalize_async_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    return database_url


def build_engine(database_url: str | None = None) -> AsyncEngine:
    """Create the shared async engine for runtime repositories."""

    normalized_url = _normalize_async_database_url(database_url or settings.database_url)
    return create_async_engine(normalized_url, future=True, pool_pre_ping=True)
```
### `services/data/cache/session_store.py`

```
"""Session state store with tenant-prefixed keys."""

from __future__ import annotations

import json

import redis.asyncio as redis

from services.ai_runtime.runtime.settings import settings


class SessionStore:
    """Stores graph state using the canonical multitenant key pattern."""

    def __init__(self, redis_url: str | None = None):
        self.client = redis.from_url(redis_url or settings.redis_url, decode_responses=True)

    @staticmethod
    def build_key(client_id: str, session_id: str) -> str:
        return f"{client_id}:session:{session_id}:state"

    async def get_state(self, client_id: str, session_id: str) -> dict[str, object] | None:
        raw = await self.client.get(self.build_key(client_id, session_id))
        return json.loads(raw) if raw else None

    async def set_state(self, client_id: str, session_id: str, payload: dict[str, object], ttl: int) -> None:
        await self.client.set(self.build_key(client_id, session_id), json.dumps(payload, default=str), ex=ttl)

    async def delete_session(self, client_id: str, session_id: str) -> bool:
        deleted = await self.client.delete(self.build_key(client_id, session_id))
        return bool(deleted)

    async def delete_by_client(self, client_id: str) -> int:
        pattern = f"{client_id}:session:*:state"
        keys = [key async for key in self.client.scan_iter(match=pattern)]
        if not keys:
            return 0
        deleted = await self.client.delete(*keys)
        return int(deleted or 0)
```
### `services/ai_runtime/config/tenant_loader.py`

```
"""Tenant configuration loading helpers for the AI service."""

from __future__ import annotations

from services.ai_runtime.domain.contracts import TenantConfig
from services.data.cache.tenant_cache import TenantCache
from services.data.repositories.agent_repository import AgentRepository
from services.data.repositories.tenant_repository import TenantRepository


class TenantLoader:
    """Loads and caches tenant config plus active agents for the full session lifecycle."""

    def __init__(
        self,
        *,
        tenant_repository: TenantRepository,
        agent_repository: AgentRepository,
        tenant_cache: TenantCache,
    ):
        self.tenant_repository = tenant_repository
        self.agent_repository = agent_repository
        self.tenant_cache = tenant_cache

    async def load(self, client_id: str) -> TenantConfig:
        cached = await self.tenant_cache.get_config(client_id)
        if cached:
            return TenantConfig.model_validate(cached)

        tenant_config = await self.tenant_repository.load_tenant_config(client_id)
        if not tenant_config:
            raise ValueError(f"Unknown client_id: {client_id}")

        ttl = tenant_config.redis_ttl_seconds
        await self.tenant_cache.set_config(client_id, tenant_config.model_dump(mode="json"), ttl)

        agents = await self.agent_repository.load_active_agents(client_id)
        await self.tenant_cache.set_agents(
            client_id,
            [agent.model_dump(mode="json") for agent in agents],
            ttl,
        )
        return tenant_config

```
### `services/ai_runtime/config/prompt_composer.py`

```
"""Runtime prompt composition helpers for the AI service."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from services.ai_runtime.domain.contracts import TenantConfig, Vertical
from services.ai_runtime.domain.prompts import PromptPayload
from services.ai_runtime.graph._shared.prompts.clarification_prompt import build_prompt as clarification_prompt
from services.ai_runtime.graph._shared.prompts.lazy_condition_evaluator_prompt import (
    build_prompt as lazy_condition_prompt,
)
from services.ai_runtime.graph._shared.prompts.lead_data_collector_prompt import build_prompt as lead_data_collector_prompt
from services.ai_runtime.graph._shared.prompts.memory_entity_extractor_prompt import (
    build_prompt as memory_entity_extractor_prompt,
)
from services.ai_runtime.graph.healthcare.prompts.analyze_turn_prompt import (
    build_prompt as healthcare_analyze_turn_prompt,
)
from services.ai_runtime.graph.healthcare.prompts.intent_detector_prompt import (
    build_prompt as healthcare_intent_detector_prompt,
)
from services.ai_runtime.graph.healthcare.prompts.synthesis_prompt import (
    build_prompt as healthcare_synthesis_prompt,
)
from services.ai_runtime.graph.insurance.prompts.analyze_turn_prompt import (
    build_prompt as insurance_analyze_turn_prompt,
)
from services.ai_runtime.graph.insurance.prompts.intent_detector_prompt import (
    build_prompt as insurance_intent_detector_prompt,
)
from services.ai_runtime.graph.insurance.prompts.synthesis_prompt import (
    build_prompt as insurance_synthesis_prompt,
)
from services.ai_runtime.graph.legal.prompts.analyze_turn_prompt import build_prompt as legal_analyze_turn_prompt
from services.ai_runtime.graph.legal.prompts.intent_detector_prompt import build_prompt as legal_intent_detector_prompt
from services.ai_runtime.graph.legal.prompts.synthesis_prompt import build_prompt as legal_synthesis_prompt
from services.ai_runtime.graph.realtor.prompts.appointment_data_collector_prompt import (
    build_prompt as appointment_collector_prompt,
)
from services.ai_runtime.graph.realtor.prompts.analyze_turn_prompt import build_prompt as realtor_analyze_turn_prompt
from services.ai_runtime.graph.realtor.prompts.intent_detector_prompt import (
    build_prompt as realtor_intent_detector_prompt,
)
from services.ai_runtime.graph.realtor.prompts.comparison_synthesizer_prompt import (
    build_prompt as comparison_synthesizer_prompt,
)
from services.ai_runtime.graph.realtor.prompts.recommendation_prompt import build_prompt as recommendation_prompt
from services.ai_runtime.graph.realtor.prompts.search_filter_extractor_prompt import (
    build_prompt as search_filter_extractor_prompt,
)
from services.ai_runtime.graph.realtor.prompts.synthesis_prompt import build_prompt as realtor_synthesis_prompt
from services.ai_runtime.graph.realtor.prompts.text_to_sql_prompt import build_prompt as text_to_sql_prompt

CONTEXT_CACHEABLE_NODE_TYPES = {
    "analyze_turn",
    "synthesis_prompt",
    "clarification",
    "comparison_synthesizer",
    "recommendation",
}
DEFAULT_CONTEXT_CACHE_TTL_SECONDS = 1800


def load_tone_prompt(tenant_config: TenantConfig) -> str:
    return tenant_config.tone_prompt.strip()


def _render_context(context: dict[str, Any]) -> str:
    return json.dumps(context, ensure_ascii=True, indent=2, default=str)


def load_analyze_turn_prompt(vertical: Vertical) -> str:
    if vertical == "realtor":
        return realtor_analyze_turn_prompt()
    if vertical == "healthcare":
        return healthcare_analyze_turn_prompt()
    if vertical == "legal":
        return legal_analyze_turn_prompt()
    if vertical == "insurance":
        return insurance_analyze_turn_prompt()
    raise ValueError(f"Unsupported analyze_turn vertical={vertical!r}")


def load_intent_detector_prompt(vertical: Vertical) -> str:
    if vertical == "realtor":
        return realtor_intent_detector_prompt()
    if vertical == "healthcare":
        return healthcare_intent_detector_prompt()
    if vertical == "legal":
        return legal_intent_detector_prompt()
    if vertical == "insurance":
        return insurance_intent_detector_prompt()
    raise ValueError(f"Unsupported intent_detector vertical={vertical!r}")


def load_synthesis_prompt(vertical: Vertical) -> str:
    if vertical == "realtor":
        return realtor_synthesis_prompt()
    if vertical == "healthcare":
        return healthcare_synthesis_prompt()
    if vertical == "legal":
        return legal_synthesis_prompt()
    if vertical == "insurance":
        return insurance_synthesis_prompt()
    raise ValueError(f"Unsupported synthesis_prompt vertical={vertical!r}")


def compose(
    node_type: str,
    tenant_config: TenantConfig,
    vertical: Vertical,
    context: dict[str, Any],
    *,
    include_tone: bool = False,
) -> PromptPayload:
    """Compose stable instructions + runtime context as the canonical prompt payload."""

    tone = load_tone_prompt(tenant_config) if include_tone else ""
    if node_type == "analyze_turn":
        base = load_analyze_turn_prompt(vertical)
    elif node_type == "synthesis_prompt":
        base = load_synthesis_prompt(vertical)
    elif node_type == "intent_detector":
        base = load_intent_detector_prompt(vertical)
    elif node_type == "lazy_condition_evaluator":
        base = lazy_condition_prompt()
    elif node_type == "clarification":
        base = clarification_prompt()
    elif node_type == "lead_data_collector":
        base = lead_data_collector_prompt()
    elif node_type == "text_to_sql":
        base = text_to_sql_prompt()
    elif node_type == "search_filter_extractor":
        base = search_filter_extractor_prompt()
    elif node_type == "memory_entity_extractor":
        base = memory_entity_extractor_prompt()
    elif node_type == "comparison_synthesizer":
        base = comparison_synthesizer_prompt()
    elif node_type == "recommendation":
        base = recommendation_prompt()
    elif node_type == "appointment_data_collector":
        base = appointment_collector_prompt()
    else:
        raise ValueError(f"Unsupported prompt node_type={node_type!r}")

    stable_prefix = "\n\n".join(part for part in [tone, base] if part)
    dynamic_context = _render_context(context)
    full_prompt = "\n\n".join(part for part in [stable_prefix, dynamic_context] if part)
    cache_source = "\n\n".join(part for part in [node_type, stable_prefix] if part)
    cache_key = hashlib.sha256(cache_source.encode("utf-8")).hexdigest()

    return PromptPayload(
        node_type=node_type,
        stable_prefix=stable_prefix,
        dynamic_context=dynamic_context,
        full_prompt=full_prompt,
        cacheable=node_type in CONTEXT_CACHEABLE_NODE_TYPES and bool(stable_prefix.strip()),
        cache_namespace=node_type if node_type in CONTEXT_CACHEABLE_NODE_TYPES else None,
        cache_key=cache_key,
        cache_ttl_seconds=DEFAULT_CONTEXT_CACHE_TTL_SECONDS,
    )
```

## Scoring Boundary

### `services/scoring-core/README.md`

```
# scoring-core

Servicio objetivo para scoring asincrono, separado del runtime conversacional (`ai-runtime`).

Responsabilidades:

- jobs de scoring
- worker de scoring
- scorecards
- prompts y modelos de scoring existentes

No incluye:

- decision conversacional
- planner
- synthesizer de chat

Referencia canonica:

- `docs/SCORING_CORE_BOUNDARY.md`
- `docs/Manuales/SCORING_V2_SCHEMA.md`
```
### `services/scoring-core/main.py`

```
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.scoring import router as scoring_router
from app.core.config import settings
from app.dependencies.database import close_database, init_database
from app.services.cache_service import cache_service


logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("scoring-core.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting scoring-core")
    try:
        await init_database()
        logger.info("Database initialized")
    except Exception:
        logger.exception("Database initialization failed")

    try:
        await cache_service.connect()
    except Exception:
        logger.exception("Cache initialization failed")

    yield

    logger.info("Shutting down scoring-core")
    await cache_service.disconnect()
    await close_database()


app = FastAPI(
    title="Scoring Core",
    description="Async scoring service decoupled from ai-runtime",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scoring_router, prefix=settings.api_prefix, tags=["scoring"])


@app.get("/")
async def root():
    return {
        "service": "scoring-core",
        "version": "1.0.0",
        "status": "running",
        "docs": f"{settings.api_prefix}/docs",
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )
```
### `services/scoring-core/worker.py`

```
import asyncio
import logging

from app.core.config import settings
from app.dependencies.database import close_database, init_database
from app.services.cache_service import cache_service
from app.services.scoring_worker import ScoringWorker


logger = logging.getLogger("scoring-core.worker-main")


async def _run() -> None:
    await init_database()
    await cache_service.connect()
    concurrency = max(1, int(settings.scoring_worker_concurrency or 1))
    logger.info("Starting scoring worker pool with concurrency=%s", concurrency)
    workers = [ScoringWorker() for _ in range(concurrency)]
    tasks = [asyncio.create_task(worker.run_forever()) for worker in workers]
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await cache_service.disconnect()
        await close_database()


if __name__ == "__main__":
    logging.basicConfig(level=settings.log_level)
    asyncio.run(_run())
```

## Pruebas y Sandboxes

```text
tests/README.md
tests/sandbox/README.md
tests/sandbox/__pycache__/simulate_chat_dentist.cpython-312.pyc
tests/sandbox/__pycache__/simulate_chat_flow.cpython-312.pyc
tests/sandbox/__pycache__/simulate_chat_realtor.cpython-312.pyc
tests/sandbox/__pycache__/simulate_multichat_dentist.cpython-312.pyc
tests/sandbox/__pycache__/simulate_multichat_realtor.cpython-312.pyc
tests/sandbox/__pycache__/test_gemini_latency_realtor_contract.cpython-312.pyc
tests/sandbox/dentist/simulate_chat_dentist.py
tests/sandbox/dentist/simulate_multichat_dentist.py
tests/sandbox/realtor/lead_advisor_completion_suite.json
tests/sandbox/realtor/manual_suite_01.json
tests/sandbox/realtor/realtor_conversation_suite.schema.json
tests/sandbox/realtor/realtor_conversation_suite.template.json
tests/sandbox/realtor/realtor_conversation_suite_prompt.md
tests/sandbox/realtor/realtor_generated_suite_01.json
tests/sandbox/realtor/realtor_regression_suite.json
tests/sandbox/realtor/run_realtor_conversation_suite.py
tests/sandbox/realtor/simulate_chat_realtor.py
tests/sandbox/realtor/simulate_multichat_realtor.py
tests/scripts/check_no_hardcoded_realtor_copy.sh
tests/system/__pycache__/test_active_chat_scoring_e2e.cpython-312.pyc
tests/system/__pycache__/test_chat_e2e.cpython-312.pyc
tests/system/test_active_chat_scoring_e2e.py
tests/system/test_chat_e2e.py
```
