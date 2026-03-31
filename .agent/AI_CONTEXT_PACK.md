# AI Context Pack

- Generated UTC: `2026-03-30T17:01:54Z`
- Repo root: `/srv/datasyncsa`
- Git branch: `HETZNER-LOCAL-2026-03-28`
- Git commit: `e88b29f`
- Policy: high-signal only; enfocado en stack actual.

## Contexto Maestro

### `.agent/BRAIN_MAP.md`

```
# BRAIN_MAP

- Generated UTC: `2026-03-30T17:01:54Z`
- Repo root: `/srv/datasyncsa`
- Git branch: `HETZNER-LOCAL-2026-03-28`
- Git commit: `e88b29f`

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
- `realtor_flow` y `generic_flow` son selectores logicos internos.
- `scoring-core` permanece separado y no debe absorber decisiones conversacionales.
- `chat-web-renderer` es consumidor/canal, no autoridad de negocio.
- Toda operacion conversacional debe mantener scope por `client_id`.

## 4. SERVICIOS DOCKER ACTIVOS

```text
postgres
redis
ai-runtime
datasyncsa-web
etl-docs
portainer
scoring-core
scoring-core-worker
test-ui
admin-console-api
admin-console-web
chat-web-renderer-api
chat-web-renderer-ui
etl-docs-worker
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

## 7. ENTIDADES Y CAPAS CRITICAS

- Tenancy/runtime: `client_id`, `tenant_config`, `session_id`, `conversation_id`
- Estado conversacional: `services/ai_runtime/domain/state.py`
- Datos compartidos: `services/data/cache/**`, `services/data/repositories/**`
- Scoring: `lead_scorecards`, `lead_score_items`, `lead_scoring_models`, `lead_scoring_prompts`
- RAG: FAQ por tenant y documentos por tenant en Postgres/pgvector
```

## Compose y Variables

### Servicios activos del compose

```text
postgres
redis
ai-runtime
chat-web-renderer-api
chat-web-renderer-ui
datasyncsa-web
etl-docs
etl-docs-worker
portainer
admin-console-api
admin-console-web
scoring-core
scoring-core-worker
test-ui
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
      - LLM_MODEL=${LLM_MODEL}
      - AI_RUNTIME_API_PREFIX=/api/v1
      - PYTHONPATH=/app
    volumes:
      - ./schemas:/app/schemas:ro
      - ./log:/app/log
    depends_on:
      - postgres
      - redis
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
      - LLM_MODEL=${LLM_MODEL}
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
      - LLM_MODEL=${LLM_MODEL}
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
      - redis
    networks:
      - internal_network

  # ETL Docs Worker (RQ)
  etl-docs-worker:
```
### `docker-compose.yml:300-360`

```

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
      - ./services/web/chat-web-renderer/frontend:/usr/share/nginx/html:ro
      - ./services/web/chat-web-renderer/frontend/nginx.conf.template:/etc/nginx/templates/default.conf.template:ro
    environment:
      - TZ=${TZ:-UTC}
      - API_HOST=chat-web-renderer-api
    depends_on:
      - chat-web-renderer-api
    networks:
      - internal_network

  # Corporate Website (Static)
  datasyncsa-web:
    image: nginx:alpine
    container_name: ${ENV_PREFIX}-web-corporate
    restart: unless-stopped
    ports:
      - "${CORPORATE_WEB_PORT}:80"
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
services/ai_runtime/scripts/export_graph_diagrams.py:388:if __name__ == "__main__":
services/ai_runtime/main.py:8:app = FastAPI(title=settings.app_name)
services/ai_runtime/main.py:9:app.include_router(router, prefix=settings.api_prefix)
services/web/admin-console/backend/app/dal/inspect_schema.py:31:if __name__ == "__main__":
services/web/chat-web-renderer/backend/tests/smoke/test_smoke_web_proxy.py:57:if __name__ == "__main__":
services/web/chat-web-renderer/backend/tests/smoke/test_smoke_runtime.py:36:if __name__ == "__main__":
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
services/web/chat-web-renderer/backend/app/main.py:13:app = FastAPI(title="Chat Web Renderer")
services/etl-docs/tests/smoke/test_smoke_etl_docs.py:42:if __name__ == "__main__":
services/etl-docs/main.py:19:app = FastAPI(title="ETL Docs API", version="1.0.0")
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
services/web/chat-web-renderer/backend/app/api/external.py:56:@router.post(
services/web/chat-web-renderer/backend/app/api/external.py:263:@router.get("/health")
services/etl-docs/main.py:28:@app.get("/")
services/etl-docs/main.py:33:@app.post("/documents/upload", status_code=202)
services/etl-docs/main.py:90:@app.get("/documents/list/{client_id}")
services/etl-docs/main.py:107:@app.get("/documents/jobs/{job_id}")
services/etl-docs/main.py:121:@app.delete("/documents/{client_id}/{content_id}")
services/etl-docs/main.py:137:@app.delete("/documents/client/{client_id}")
services/web/chat-web-renderer/backend/app/main.py:34:@app.get("/health")
services/web/chat-web-renderer/backend/app/main.py:39:@app.get("/health/dependencies")
services/web/chat-web-renderer/backend/app/main.py:92:@app.post("/chat/init", response_model=SDUIResponse)
services/web/chat-web-renderer/backend/app/main.py:104:@app.post("/chat/session/reset")
services/web/chat-web-renderer/backend/app/main.py:141:@app.post("/chat", response_model=SDUIResponse)
services/web/chat-web-renderer/backend/app/main.py:357:@app.get("/")
services/web/chat-web-renderer/backend/app/main.py:371:@app.post("/internal/memory/reset")
```

## AI Runtime

### `services/ai_runtime/ARCHITECTURE.md`

```
# Datasyncsa AI Architecture

## Objetivo

`services/ai_runtime` define el runtime conversacional multitenant nuevo de Datasyncsa AI con dos grafos LangGraph:

- `grafo_realtor`
- `grafo_generico`

El servicio es `multitenant-first`: ninguna operacion se ejecuta sin `client_id`, toda sesion se hidrata con `tenant_config`, y Redis/PostgreSQL se consultan con scope tenant desde la base del runtime.

## Principios Innegociables

1. `client_id` vive en el estado desde el primer turno.
2. El estado es acumulativo y se persiste por sesion.
3. Prompts se componen en runtime con tres capas:
   - `tone_prompt` del tenant
   - prompt base del vertical
   - contexto del turno
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
- `domain/ports.py`: puertos abstractos para LLM, Redis, PG, RAG, mail y workers.
- `config/tenant_loader.py`: carga y cache de tenant.
- `config/prompt_composer.py`: tone + vertical + context.
- `runtime/bootstrap.py`: wiring por defecto.
- `runtime/service.py`: bootstrap de sesion e invocacion del grafo.
- `runtime/turn_trace.py`: trazado por turno para nodos, routers y LLM.
- `docs/graphs/**`: diagramas exportados del `grafo_generico` y `grafo_realtor`.
- `web/turn_trace/**`: consola web minima para inspeccionar trazas del runtime.
- `graph/_shared/**`: nodos, routers, prompts y tools comunes.
- `graph/generic/**`: builder y nodos del vertical reducido.
- `graph/realtor/**`: builder, prompts y herramientas del vertical completo.
- `rag/**`: repositorios pgvector aislados por tenant.
- `workers/lead_worker.py`: worker fire-and-forget placeholder v1.

## Flujo de Entrada

### Entrada directa al runtime

1. El cliente de canal llama directo a `ai-runtime`.
2. Puede omitir `flow`; si lo hace, `ConversationRuntime` lo resuelve por vertical.
3. Si envía `flow=realtor_flow`, `GraphRegistry` exige `vertical=realtor`.
4. Si envía `flow=generic_flow`, `GraphRegistry` exige `vertical in {healthcare, legal}`.
5. Se hidrata o recupera sesion y se ejecuta `grafo_realtor` o `grafo_generico`.

## Estado Canonico

El estado esta modelado en `domain/state.py` y contiene:

- sesion: `session_id`, `conversation_id`, `user_id`, `client_id`, `vertical`, `flow`, `current_turn`
- prompts/config: `capabilities`, `tenant_config`
- referencias: `resolved_references`, `pending_clarification`, `clarification_attempts`
- cola: `intent_queue`, `active_intent`, `completed_intents`, `turn_outputs`
- lead: `lead_advisor`, `lead`, `escalacion`
- cita: `cita`
- salida: `final_response`
- realtor only:
  - `search_filters`, `inventory`, `last_search_results`, `last_mentioned`
  - `active_comparison`, `focus_scope`, `search_attempts`
  - `cards_shown`, `cards_mode`, `render_mode`, `ui_payload`
  - `financial_context`

## LangGraph Control Loops

Los diagramas renderizados del estado actual del runtime viven en `services/ai_runtime/docs/graphs/` y se regeneran desde `services/ai_runtime/scripts/export_graph_diagrams.py`.

## Turn Trace

Para desarrollo, `ai-runtime` registra una traza JSON por turno en `/app/log/turn-traces` y expone una consola en `/api/v1/debug/turn-trace/`.

Cada turno registra:

- inicio y cierre del turno
- entrada y salida de cada nodo
- decisiones de routers
- prompts y respuestas del puerto LLM
- resumen del estado antes y despues de cada paso

### Shared flow

`START -> resolve_references -> classify_intent -> route_next_intent`

Routers compartidos:

- `after_resolve_references`
  - `ask_clarification`
  - `collect_lead_data`
  - `classify_intent`
- `after_classify_intent`
  - `route_next_intent`
  - `lead_advisor`
- `after_check_queue`
  - `route_next_intent`
  - `lead_advisor`

### Clarification loop

- entrada: referencia ambigua o dato faltante
- una sola pregunta por turno
- maximo 3 intentos
- al llegar al limite, pasa a `collect_lead_data`

### Intent queue

- `classify_intent` genera hasta 4 intents
- `route_next_intent` elige el siguiente intent ejecutable
- cada nodo de capacidad cierra explicitamente `running -> done`
- `check_queue` decide si quedan intents pendientes

### Realtor enrich/reanalyze loop

- `search`
- si `0 resultados` y `attempts < 3` -> `search` otra vez con filtros relajados
- si `0 < resultados < 4` -> `render_mode=text`
- si `>= 4` -> `render_cards`

## Separacion de Responsabilidades

### LLM

- `resolve_references`: clasifica tipo de referencia
- `classify_intent`: detecta intenciones
- `route_next_intent`: solo condiciones lazy
- `synthesize`: respuesta final
- `compare_properties`: solo redaccion
- `llm_recommend`: solo redaccion
- `text_to_sql`: traduccion controlada a SQL
- `collect_lead_data` y `collect_appointment_data`: extraccion conversacional

### Codigo deterministico

- resolver referencias a IDs
- filtrar capabilities por tenant
- manejar la cola y dependencias
- reglas `lead_advisor`
- `render_cards`
- `financial_calc`
- `assign_agent`
- aislamiento `client_id` en Redis y PostgreSQL

## Prompt Runtime

`prompt_composer.compose(node_type, tenant_config, vertical, context)` aplica:

1. `tone_prompt` del tenant
2. prompt del vertical o prompt base segun `node_type`
3. contexto JSON serializado del turno

Prompts incluidos:

- base:
  - `reference_classifier_prompt.py`
  - `intent_detector_prompt.py`
  - `lazy_condition_evaluator_prompt.py`
  - `clarification_prompt.py`
  - `lead_data_collector_prompt.py`
- vertical:
  - `vertical/realtor/{plan,synthesis}_prompt.py`
  - `vertical/healthcare/{plan,synthesis}_prompt.py`
  - `vertical/legal/{plan,synthesis}_prompt.py`
- realtor:
  - `text_to_sql_prompt.py`
  - `comparison_synthesizer_prompt.py`
  - `recommendation_prompt.py`
  - `appointment_data_collector_prompt.py`

## Persistencia y Caches

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
    llm_model: str = os.getenv("LLM_MODEL", "gemini-2.5-flash-lite")
    llm_timeout_seconds: int = int(os.getenv("LLM_TIMEOUT_SECS", "30"))
    llm_context_cache_enabled: bool = os.getenv("LLM_CONTEXT_CACHE_ENABLED", "true").lower() == "true"
    llm_context_cache_ttl_seconds: int = int(os.getenv("LLM_CONTEXT_CACHE_TTL_SECONDS", "1800"))
    llm_context_cache_min_stable_chars: int = int(os.getenv("LLM_CONTEXT_CACHE_MIN_STABLE_CHARS", "2000"))
    turn_trace_enabled: bool = os.getenv("AI_TURN_TRACE_ENABLED", "true").lower() == "true"
    turn_trace_dir: str = os.getenv("AI_TURN_TRACE_DIR", "/app/log/turn-traces")


settings = AISettings()
```
### `services/ai_runtime/runtime/bootstrap.py`

```
"""Dependency bootstrap for the AI runtime."""

from __future__ import annotations

from services.ai_runtime.config.tenant_loader import TenantLoader
from services.ai_runtime.domain.contracts import MailDispatchResult
from services.ai_runtime.domain.ports import GraphDependencies
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


class PlaceholderMailer:
    async def send(self, payload: dict[str, object]):
        return MailDispatchResult(
            enviado=False,
            destinatarios=list(payload.get("destinatarios", [])),
            error="mail provider not configured",
        )


class InlineWorkerDispatcher:
    async def fire_and_forget(self, task_name: str, payload: dict[str, object]) -> None:
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
dependencies = GraphDependencies(
    llm=llm,
    session_store=SessionStore(),
    lead_store=LeadStore(),
    tenant_cache=tenant_cache,
    tenant_repository=tenant_repository,
    conversation_repository=ConversationRepository(engine),
    property_repository=PropertyRepository(engine),
    agent_repository=agent_repository,
    agency_rag_repository=AgencyRAGRepository(engine),
    documents_rag_repository=DocumentsRAGRepository(engine),
    mailer=PlaceholderMailer(),
    worker_dispatcher=InlineWorkerDispatcher(),
    trace_store=trace_store,
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
    GenericGraphState,
    MemoryLookupState,
    RealtorGraphState,
    build_base_state,
)
from services.ai_runtime.graph.registry import GraphRegistry
from services.ai_runtime.runtime.turn_trace import (
    TurnTraceContext,
    activate_turn_trace,
    activate_latest_turn_state,
    deactivate_turn_trace,
    deactivate_latest_turn_state,
    summarize_state,
    utc_now_iso,
)


def _resolve_flow(vertical: str, flow: str | None) -> str:
    if flow:
        return flow
    return "realtor_flow" if vertical == "realtor" else "generic_flow"


def _build_components(final_state: BaseGraphState) -> list[dict[str, object]]:
    components: list[dict[str, object]] = []
    ui_payload = getattr(final_state, "ui_payload", None) or {}
    for card in ui_payload.get("property_cards", []):
        components.append(
            {
                "type": "property-card",
                "listing_id": card.get("property_id_internal"),
                "title": card.get("title"),
                "price": card.get("price"),
                "image_url": card.get("primary_image_url"),
                "public_url": card.get("public_url"),
                "city": card.get("province"),
                "neighborhood": card.get("province"),
            }
        )
    return components


def _reset_turn_scoped_state(base_state: BaseGraphState) -> None:
    """Clear fields that belong to a single turn while keeping session memory alive."""

    base_state.final_response = None
    base_state.pending_clarification = None
    base_state.clarification_attempts = 0
    base_state.resolved_references = []
    base_state.intent_queue = []
    base_state.active_intent = None
    base_state.completed_intents = []
    base_state.turn_outputs = []
    base_state.turn_analysis = None
    base_state.lead_advisor.should_ask = False
    base_state.lead_advisor.field_to_ask = None
    base_state.memory.last_lookup = MemoryLookupState()

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
        flow = _resolve_flow(tenant_config.vertical, request.flow)
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

        if existing_payload:
            state_cls = RealtorGraphState if tenant_config.vertical == "realtor" else GenericGraphState
            base_state = state_cls.model_validate(existing_payload)
            base_state.tenant_config = tenant_config
            base_state.capabilities = list(tenant_config.capabilities)
            base_state.vertical = tenant_config.vertical
            base_state.flow = flow
            base_state.user_id = user_id
            _reset_turn_scoped_state(base_state)
            base_state.current_turn += 1
            base_state.messages.append(ChatMessage(role="user", content=request.message))
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
            )
            if tenant_config.vertical == "realtor":
                base_state = RealtorGraphState.model_validate(state.model_dump())
            else:
                base_state = GenericGraphState.model_validate(state.model_dump())
            _reset_turn_scoped_state(base_state)
            conversation_id = base_state.conversation_id

        trace_context = TurnTraceContext(
            trace_id=str(uuid4()),
            client_id=request.client_id,
            session_id=session_id,
            conversation_id=conversation_id,
            vertical=tenant_config.vertical,
            flow=flow,
            turn=base_state.current_turn,
            user_id=user_id,
            user_message=request.message,
            started_at=utc_now_iso(),
        )
        token = activate_turn_trace(trace_context)
        state_token = activate_latest_turn_state(base_state.model_dump(mode="json"))
        self.dependencies.trace_store.start_turn(
            trace_context,
            request_metadata=request.metadata,
            state_summary=summarize_state(base_state.model_dump(mode="json")),
        )
        graph = self.graph_registry.get_graph(tenant_config.vertical, flow, self.dependencies)
        try:
            final_payload = await graph.ainvoke(base_state.model_dump(mode="json"))
            final_state = (
                RealtorGraphState.model_validate(final_payload)
                if tenant_config.vertical == "realtor"
                else GenericGraphState.model_validate(final_payload)
            )
            components = _build_components(final_state)
            rag_outputs = [
                item
                for item in final_state.turn_outputs
                if item.get("type") in {"rag_agencia", "rag_docs"}
            ]
            sources = [chunk for output in rag_outputs for chunk in output.get("chunks", [])]
            await self.dependencies.session_store.set_state(
                request.client_id,
                session_id,
                final_state.model_dump(mode="json"),
                tenant_config.redis_ttl_seconds,
```
### `services/ai_runtime/domain/state.py`

```
"""Graph state contracts for generic and realtor assistants."""

from __future__ import annotations

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
    Property,
    TenantConfig,
    TurnAnalysis,
    Vertical,
)


class SearchFilters(BaseModel):
    ubicacion: str | None = None
    habitaciones: int | None = None
    banos: float | None = None
    garage: int | None = None
    precio_max: float | None = None
    precio_min: float | None = None
    currency: str | None = None
    provincia: str | None = None
    amenidades: list[str] = Field(default_factory=list)
    tipo: str | None = None
    operacion: str | None = None


class FinancialContext(BaseModel):
    property_id: str | None = None
    price: float | None = None
    currency: str | None = None
    prima: float | None = None
    plazo: int | None = None
    banco: str | None = None
    resultado: dict[str, Any] | None = None


class EscalationState(BaseModel):
    solicitada: bool = False
    motivo: str | None = None
    agente_asignado: str | None = None
    datos_capturados: dict[str, Any] = Field(default_factory=dict)


class LeadAdvisorState(BaseModel):
    lead_scores: LeadScores = Field(default_factory=LeadScores)
    lead_extracted: LeadExtracted = Field(default_factory=LeadExtracted)
    lead_completo: bool = False
    should_ask: bool = False
    field_to_ask: str | None = None


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
    current_turn: int = 1
    messages: list[ChatMessage] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    tenant_config: TenantConfig
    resolved_references: list[dict[str, Any]] = Field(default_factory=list)
    pending_clarification: str | None = None
    clarification_attempts: int = 0
    intent_queue: list[IntentDefinition] = Field(default_factory=list)
    active_intent: IntentDefinition | None = None
    completed_intents: list[IntentDefinition] = Field(default_factory=list)
    turn_outputs: list[dict[str, Any]] = Field(default_factory=list)
    turn_analysis: TurnAnalysis | None = None
    cita: Appointment
    escalacion: EscalationState = Field(default_factory=EscalationState)
    lead_advisor: LeadAdvisorState = Field(default_factory=LeadAdvisorState)
    memory: ConversationMemoryState = Field(default_factory=ConversationMemoryState)
    lead: LeadPlaceholder = Field(default_factory=LeadPlaceholder)
    final_response: str | None = None


class GenericGraphState(BaseGraphState):
    """State for healthcare and legal tenants."""

    pass


class RealtorGraphState(BaseGraphState):
    """State for the full realtor graph."""

    search_filters: SearchFilters = Field(default_factory=SearchFilters)
    effective_search_filters: SearchFilters | None = None
    inventory: list[Property] = Field(default_factory=list)
    last_search_results: list[Property] = Field(default_factory=list)
    last_mentioned: Property | None = None
    active_comparison: list[str] = Field(default_factory=list)
    focus_scope: str | None = None
    search_attempts: int = 0
    cards_shown: list[str] = Field(default_factory=list)
    cards_mode: str | None = None
    render_mode: str | None = None
    ui_payload: dict[str, Any] | None = None
    financial_context: FinancialContext = Field(default_factory=FinancialContext)


def build_base_state(
    *,
    session_id: str,
    conversation_id: str,
    user_id: str,
    client_id: str,
    vertical: Vertical,
    flow: FlowName,
    tenant_config: TenantConfig,
    initial_message: str,
) -> BaseGraphState:
    """Bootstrap the canonical base state for a new session."""

    return BaseGraphState(
        session_id=session_id,
        conversation_id=conversation_id,
        user_id=user_id,
        client_id=client_id,
        vertical=vertical,
        flow=flow,
        capabilities=list(tenant_config.capabilities),
        tenant_config=tenant_config,
        messages=[ChatMessage(role="user", content=initial_message)],
        cita=Appointment(client_id=client_id),
    )
```
### `services/ai_runtime/graph/registry.py`

```
"""Graph registry for flow and vertical selection."""

from __future__ import annotations

from services.ai_runtime.domain.contracts import FlowName, Vertical
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.graph.generic.graph import build_generic_graph
from services.ai_runtime.graph.realtor.graph import build_realtor_graph


class GraphRegistry:
    """Select the correct LangGraph builder for the resolved tenant vertical."""

    def get_graph(self, vertical: Vertical, flow: FlowName, deps: GraphDependencies):
        if flow == "realtor_flow" and vertical != "realtor":
            raise ValueError("realtor_flow solo puede usarse con vertical realtor")
        if flow == "generic_flow" and vertical == "realtor":
            raise ValueError("generic_flow no puede usarse con vertical realtor")
        if vertical == "realtor":
            return build_realtor_graph(deps)
        return build_generic_graph(deps)
```
### `services/ai_runtime/graph/generic/graph.py`

```
"""Builder for the reduced generic LangGraph."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from services.ai_runtime.domain.state import GenericGraphState
from services.ai_runtime.domain.contracts import TenantConfig
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.graph._shared.nodes import (
    analyze_turn,
    ask_clarification,
    capture_memory_entities,
    check_queue,
    collect_lead_data,
    lead_advisor,
    memory_lookup,
    route_next_intent,
    synthesize,
)
from services.ai_runtime.graph._shared.nodes.helpers import complete_active_intent
from services.ai_runtime.graph._shared.routers.common import (
    after_analyze_turn,
    after_capture_memory,
    after_check_queue,
    after_memory_lookup,
)
from services.ai_runtime.graph._shared.tools.mensajear import mensajear
from services.ai_runtime.graph.generic.nodes.assign_agent_node import assign_agent
from services.ai_runtime.graph.generic.nodes.collect_appointment_data_node import collect_appointment_data
from services.ai_runtime.graph.generic.nodes.rag_agencia_node import rag_agencia
from services.ai_runtime.graph.generic.routers.routes import after_collect_appointment_data, after_route_next_intent
from services.ai_runtime.runtime.turn_trace import build_traced_node, build_traced_router


def _mail_node(deps: GraphDependencies):
    async def _mail_impl(state: dict, runtime_deps: GraphDependencies):
        tenant_config = TenantConfig.model_validate(state["tenant_config"])
        graph_state = GenericGraphState.model_validate(state)
        output = (
            await mensajear(
                dependencies=runtime_deps,
                client_id=state["client_id"],
                tipo="appointment_confirmation",
                destinatarios=[],
                datos_cita=state.get("cita", {}),
                tenant_config=tenant_config,
            )
        ).model_dump(mode="json")
        return {
            "turn_outputs": [*state.get("turn_outputs", []), {"type": "mensajear", **output}],
            **complete_active_intent(graph_state, {"type": "mensajear", **output}),
        }

    return build_traced_node("mensajear", _mail_impl, deps)


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
    workflow.add_node("mensajear", _mail_node(deps))
    workflow.add_node("check_queue", build_traced_node("check_queue", check_queue, deps))
    workflow.add_node("lead_advisor", build_traced_node("lead_advisor", lead_advisor, deps))
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
            "synthesize": "synthesize",
        },
    )
    workflow.add_conditional_edges(
        "memory_lookup",
        build_traced_router("after_memory_lookup", after_memory_lookup, deps),
        {"route_next_intent": "route_next_intent", "lead_advisor": "lead_advisor", "end": END, "synthesize": "synthesize"},
    )
    workflow.add_edge("collect_lead_data", "synthesize")
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
        {"assign_agent": "assign_agent", "synthesize": "synthesize"},
    )
    workflow.add_edge("assign_agent", "mensajear")
    workflow.add_edge("mensajear", "check_queue")
    workflow.add_conditional_edges(
        "check_queue",
        build_traced_router("after_check_queue", after_check_queue, deps),
        {"route_next_intent": "route_next_intent", "lead_advisor": "lead_advisor"},
    )
    workflow.add_edge("lead_advisor", "synthesize")
    workflow.add_edge("synthesize", END)
    return workflow.compile()
```
### `services/ai_runtime/graph/realtor/graph.py`

```
"""Builder for the full realtor LangGraph."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from services.ai_runtime.domain.contracts import TenantConfig
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import RealtorGraphState
from services.ai_runtime.graph._shared.nodes import (
    analyze_turn,
    ask_clarification,
    capture_memory_entities,
    check_queue,
    collect_lead_data,
    lead_advisor,
    memory_lookup,
    route_next_intent,
    synthesize,
)
from services.ai_runtime.graph._shared.nodes.helpers import complete_active_intent
from services.ai_runtime.graph._shared.routers.common import (
    after_analyze_turn,
    after_capture_memory,
    after_check_queue,
    after_memory_lookup,
)
from services.ai_runtime.graph._shared.tools.mensajear import mensajear
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


def _mail_node(deps: GraphDependencies):
    async def _mail_impl(state: dict, runtime_deps: GraphDependencies):
        tenant_config = TenantConfig.model_validate(state["tenant_config"])
        graph_state = RealtorGraphState.model_validate(state)
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
    workflow.add_node("mensajear", _mail_node(deps))
    workflow.add_node("check_queue", build_traced_node("check_queue", check_queue, deps))
    workflow.add_node("lead_advisor", build_traced_node("lead_advisor", lead_advisor, deps))
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
            "synthesize": "synthesize",
        },
    )
    workflow.add_conditional_edges(
        "memory_lookup",
        build_traced_router("after_memory_lookup", after_memory_lookup, deps),
        {
            "route_next_intent": "route_next_intent",
            "lead_advisor": "lead_advisor",
            "end": END,
            "synthesize": "synthesize",
        },
    )
    workflow.add_edge("collect_lead_data", "synthesize")
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
        {"assign_agent": "assign_agent", "synthesize": "synthesize"},
    )
    workflow.add_edge("assign_agent", "mensajear")
    workflow.add_edge("mensajear", "check_queue")
    workflow.add_conditional_edges(
        "check_queue",
        build_traced_router("after_check_queue", after_check_queue, deps),
        {"route_next_intent": "route_next_intent", "lead_advisor": "lead_advisor"},
    )
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
            "source_property_ref": session.get("source_property_ref"),
            "landing_page_url": session.get("landing_page_url")
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
from app.core.vertical_router import vertical_router
from app.transformer.core import SDUITransformer
from app.transformer.realtor_policy import RealtorRendererPolicy
from app.transformer.generic_policy import GenericRendererPolicy
from app.session.manager import SessionManager

inference_client = InferenceClient()
memory_reset_client = MemoryResetClient()
transformer = SDUITransformer()
session_manager = SessionManager()

vertical_router.register_strategy("realtor", "web_html", RealtorRendererPolicy(channel="web_html"))
vertical_router.register_strategy("generic", "web_html", GenericRendererPolicy(channel="web_html"))

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
    channel_user_id = req.channel_user_id
    metadata = dict(req.metadata or {})
    trace_id = str(metadata.get("debug_trace_id") or "")
    incoming_session_id = str(req.session_id).strip() if req.session_id else None
    incoming_conversation_id = str(req.conversation_id) if req.conversation_id else None
    request_started = time.perf_counter()

    session_data = await session_manager.get_session_multichannel(
        client_id=client_id,
        channel=channel,
        channel_user_id=channel_user_id,
    )
    
    session_context = {
        "client_id": client_id,
        "session_id": incoming_session_id or session_data.get("session_id"),
        "conversation_id": incoming_conversation_id or session_data.get("conversation_id"),
        "lead_id": session_data.get("lead_id"),
        "brand_project": req.brand_project or session_data.get("brand_project"),
        "channel": channel,
        "channel_user_id": channel_user_id,
        "auth_user_id": req.auth_user_id or session_data.get("auth_user_id"),
    }
    
    if metadata:
        session_context.update(metadata)
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
from services.ai_runtime.graph._shared.prompts.analyze_turn_prompt import build_prompt as analyze_turn_prompt
from services.ai_runtime.graph._shared.prompts.clarification_prompt import build_prompt as clarification_prompt
from services.ai_runtime.graph._shared.prompts.intent_detector_prompt import build_prompt as intent_detector_prompt
from services.ai_runtime.graph._shared.prompts.lazy_condition_evaluator_prompt import (
    build_prompt as lazy_condition_prompt,
)
from services.ai_runtime.graph._shared.prompts.lead_data_collector_prompt import build_prompt as lead_data_collector_prompt
from services.ai_runtime.graph._shared.prompts.memory_entity_extractor_prompt import (
    build_prompt as memory_entity_extractor_prompt,
)
from services.ai_runtime.graph._shared.prompts.reference_classifier_prompt import build_prompt as reference_classifier_prompt
from services.ai_runtime.graph.realtor.prompts.appointment_data_collector_prompt import (
    build_prompt as appointment_collector_prompt,
)
from services.ai_runtime.graph.realtor.prompts.comparison_synthesizer_prompt import (
    build_prompt as comparison_synthesizer_prompt,
)
from services.ai_runtime.graph.realtor.prompts.recommendation_prompt import build_prompt as recommendation_prompt
from services.ai_runtime.graph.realtor.prompts.search_filter_extractor_prompt import (
    build_prompt as search_filter_extractor_prompt,
)
from services.ai_runtime.graph.realtor.prompts.text_to_sql_prompt import build_prompt as text_to_sql_prompt

SYSTEM_NODE_SLUG_BY_TYPE = {
    "plan_prompt": "planner_system",
    "synthesis_prompt": "synthesizer_system",
}

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


def load_vertical_prompt(tenant_config: TenantConfig, vertical: Vertical, node_type: str) -> str:
    system_node_slug = SYSTEM_NODE_SLUG_BY_TYPE.get(node_type)
    if not system_node_slug:
        raise ValueError(f"Unsupported vertical prompt node_type={node_type!r} for vertical={vertical!r}")
    runtime_prompt = (tenant_config.system_prompts.get(system_node_slug) or "").strip()
    if runtime_prompt:
        return runtime_prompt
    raise ValueError(
        f"Missing system prompt slug={system_node_slug!r} for vertical={vertical!r} and client_id={tenant_config.client_id!r}"
    )


def _render_context(context: dict[str, Any]) -> str:
    return json.dumps(context, ensure_ascii=True, indent=2, default=str)


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
    if node_type in {"plan_prompt", "synthesis_prompt"}:
        base = load_vertical_prompt(tenant_config, vertical, node_type)
    elif node_type == "analyze_turn":
        base = "\n\n".join(
            [
                load_vertical_prompt(tenant_config, vertical, "plan_prompt"),
                analyze_turn_prompt(),
            ]
        )
    elif node_type == "reference_classifier":
        base = reference_classifier_prompt()
    elif node_type == "intent_detector":
        base = "\n\n".join(
            [
                load_vertical_prompt(tenant_config, vertical, "plan_prompt"),
                intent_detector_prompt(),
            ]
        )
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
tests/sandbox/realtor/generated_conversation_suite.schema.json
tests/sandbox/realtor/generated_conversation_suite.template.json
tests/sandbox/realtor/generated_conversation_suite_prompt.md
tests/sandbox/realtor/generated_suite_01.json
tests/sandbox/realtor/manual_suite_01.json
tests/sandbox/realtor/realtor_v3_regression_battery.py
tests/sandbox/realtor/regression_suite_01.json
tests/sandbox/realtor/run_generated_conversation_suite.py
tests/sandbox/realtor/simulate_chat_realtor.py
tests/sandbox/realtor/simulate_multichat_realtor.py
tests/sandbox/realtor/test_gemini_latency_realtor_contract.py
tests/scripts/check_no_hardcoded_realtor_copy.sh
tests/system/__pycache__/test_active_chat_scoring_e2e.cpython-312.pyc
tests/system/__pycache__/test_chat_e2e.cpython-312.pyc
tests/system/test_active_chat_scoring_e2e.py
tests/system/test_chat_e2e.py
```
