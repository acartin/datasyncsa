# AI Context Pack

- Generated UTC: `2026-03-07T05:15:16Z`
- Repo root: `/srv/datasyncsa`
- Git branch: `HETZNER-LOCAL-2026-03-6`
- Git commit: `a802100`
- Policy: High-signal only; assets/binarios excluidos.

## Contexto Maestro

- Fuente principal: `.agent/BRAIN_MAP.md`
### `.agent/BRAIN_MAP.md`

```
# BRAIN_MAP

- Generated UTC: `2026-03-07T05:15:16Z`
- Repo root: `/srv/datasyncsa`
- Git branch: `HETZNER-LOCAL-2026-03-6`
- Git commit: `a802100`

## 1. MAPA DE INTENCIONES (DIRECTORIO)

| Carpeta | Responsabilidad Técnica | Importancia (1-5) |
|---|---|---:|
| `docker-compose.yml` | Orquestación de servicios (DB, Redis, APIs, bridges, UI, ETL). | 5 |
| `services/web/admin-console` | BFF FastAPI + renderer SDUI para consola operativa multi-tenant. | 5 |
| `services/web/chat-web-renderer` | Canal web y renderer SDUI del chat. | 5 |
| `services/inference-stack-v2/inference-core-v2` | Motor v2 de chat/scoring por vertical/modelo/prompt. | 5 |
| `services/inference-stack-v2/semantic-adapter-v2` | Recuperación semántica v2 (RAG retriever). | 5 |
| `services/etl-docs` | Ingesta documental, colas RQ y vectorización. | 5 |
| `services/generic-bridge-v2` | Wrapper liviano para integraciones genéricas hacia inference-core-v2. | 4 |
| `services/property-bridge-v2` | Wrapper de compatibilidad del vertical inmobiliario hacia inference-core-v2. | 4 |
| `schemas` | Contratos canónicos compartidos entre servicios. | 4 |
| `tests` | Pruebas de integración y sistema cross-service. | 4 |
| `volumes/r2_storage` | Storage documental montado (Cloudflare R2 vía rclone). | 5 |
| `volumes/staging` | Buffer de staging para pipelines ETL. | 4 |
| `services/etl-processor` | Servicio deprecado (no usar para features nuevas). | 1 |
| `services/legacy-ETL_DOCS` | Código ETL legacy/deprecado. | 1 |

## 2. ARQUITECTURA CORE (SDUI/SUID)

- Backend soberano: frontend renderiza contratos SDUI, no decide negocio.
- Multi-tenant estricto: toda consulta operativa debe tener scope por `client_id`.
- Contratos UI validados con Pydantic y consistentes con renderer.

## 3. ENTRY POINTS PRINCIPALES

- `services/web/admin-console/backend/app/main.py`
- `services/web/chat-web-renderer/backend/app/main.py`
- `services/inference-stack-v2/inference-core-v2/main.py`
- `services/inference-stack-v2/semantic-adapter-v2/main.py`
- `services/etl-docs/main.py`

## Referencia Canónica

- Documento operativo detallado: `docs/CHAT_SYSTEM_REFERENCE.md`

## 4. ENTIDADES CRÍTICAS (DB)

- Tenancy/seguridad: `lead_clients`, `auth_users`, `auth_roles`, `auth_client_user`
- Leads/conversación: `lead_leads`, `lead_conversations`, `lead_statuses`, `lead_sources`
- Scoring v2: `lead_scorecards`, `lead_score_items`, `lead_scoring_models`, `lead_scoring_criteria`, `lead_scoring_bands`, `lead_scoring_prompts`
- RAG/documentos: `ai_knowledge_documents`, `ai_vectors`
```

## Infraestructura y Entradas

### `docker-compose.yml`

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
  # Inference Core V2
  inference-core-v2:
    build:
      context: ./services/inference-stack-v2/inference-core-v2
      dockerfile: Dockerfile
    container_name: ${ENV_PREFIX}-backend-inference-v2
    restart: always
    command:
      - uvicorn
      - main:app
      - --host
      - 0.0.0.0
      - --port
      - "8000"
      - --workers
      - ${INFERENCE_WEB_CONCURRENCY:-3}
    ports:
      - "${INFERENCE_V2_PORT}:8000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - TZ=${TZ:-UTC}
      - REDIS_URL=redis://redis:6379/0
      - INTERNAL_API_TOKEN=${INTERNAL_API_TOKEN}
      - LOG_LEVEL=INFO
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - LLM_MODEL=${LLM_MODEL}
      - LLM_TIMEOUT_SECS=${LLM_TIMEOUT_SECS}
      - CHAT_LLM_MAX_OUTPUT_TOKENS=${CHAT_LLM_MAX_OUTPUT_TOKENS:-320}
      - CHAT_HISTORY_CONTEXT_MAX_CHARS=${CHAT_HISTORY_CONTEXT_MAX_CHARS:-1800}
      - SCORING_LLM_TIMEOUT_SECS=${SCORING_LLM_TIMEOUT_SECS:-60}
      - SCORING_LLM_HARD_TIMEOUT_SECS=${SCORING_LLM_HARD_TIMEOUT_SECS:-10}
      - SCORING_LLM_MAX_OUTPUT_TOKENS=${SCORING_LLM_MAX_OUTPUT_TOKENS:-512}
      - SCORING_JOB_DEBOUNCE_SECS=${SCORING_JOB_DEBOUNCE_SECS:-1.5}
      - SCORING_IDLE_DELAY_SECS=${SCORING_IDLE_DELAY_SECS}
      - RAG_RETRIEVER_V2_URL=http://semantic-adapter-v2:8000
      - RAG_RETRIEVER_V2_SEARCH_PATH=/api/v2/search
    volumes:
      - ./schemas:/app/schemas:ro
    depends_on:
      - postgres
      - redis
    networks:
      - internal_network

  # Inference Core V2 async scoring worker (persistent jobs)
  inference-core-v2-worker:
    build:
      context: ./services/inference-stack-v2/inference-core-v2
      dockerfile: Dockerfile
    container_name: ${ENV_PREFIX}-backend-inference-v2-worker
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
      - SCORING_LLM_TIMEOUT_SECS=${SCORING_LLM_TIMEOUT_SECS:-60}
      - SCORING_LLM_HARD_TIMEOUT_SECS=${SCORING_LLM_HARD_TIMEOUT_SECS:-10}
      - SCORING_LLM_MAX_OUTPUT_TOKENS=${SCORING_LLM_MAX_OUTPUT_TOKENS:-512}
      - SCORING_JOB_DEBOUNCE_SECS=${SCORING_JOB_DEBOUNCE_SECS:-1.5}
      - SCORING_IDLE_DELAY_SECS=${SCORING_IDLE_DELAY_SECS}
      - SCORING_IDLE_CLOSE_SECS=${SCORING_IDLE_CLOSE_SECS:-15.0}
      - SCORING_WORKER_POLL_SECS=${SCORING_WORKER_POLL_SECS:-2.0}
      - SCORING_WORKER_CONCURRENCY=${SCORING_WORKER_CONCURRENCY:-1}
      - SCORING_JOB_MAX_ATTEMPTS=${SCORING_JOB_MAX_ATTEMPTS:-3}
      - SCORING_ALLOW_HEURISTIC_FALLBACK=${SCORING_ALLOW_HEURISTIC_FALLBACK:-false}
    volumes:
      - ./schemas:/app/schemas:ro
    depends_on:
      - postgres
      - redis
      - inference-core-v2
    networks:
      - internal_network

  # Semantic Adapter V2 (isolated runtime for v2 rollout)
  semantic-adapter-v2:
    build:
      context: ./services/inference-stack-v2/semantic-adapter-v2
      dockerfile: Dockerfile
    container_name: ${ENV_PREFIX}-backend-semantic-v2
    restart: always
    ports:
      - "${SEMANTIC_V2_PORT}:8000"
    env_file:
      - .env
    environment:
      - TZ=${TZ:-UTC}
      - INFERENCE_CORE_URL=http://inference-core-v2:8000
      - DATABASE_URL=${DATABASE_URL}
      - TABLE_VECTORS=${TABLE_VECTORS}
    volumes:
      - ./schemas:/app/schemas:ro
    depends_on:
      - postgres
      - inference-core-v2
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
    build:
      context: ./services/etl-docs
      dockerfile: Dockerfile
    container_name: ${ENV_PREFIX}-backend-etl-docs-worker
    restart: always
    command: ["rq", "worker", "docs", "--url", "redis://redis:6379/0"]
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
```
### `.env.example`

```
# --- INFRASTRUCTURE ---
ENV_PREFIX=ds-dev
TZ=UTC

# DB Credentials
DB_USER=postgres
DB_PASS=change-me
DB_NAME=agentic
DB_PORT=5432

# Full Connection String (Internal Docker Network)
DATABASE_URL=postgresql://${DB_USER}:${DB_PASS}@postgres:${DB_PORT}/${DB_NAME}
TABLE_VECTORS=ai_vectors
TABLE_PROPERTIES=lead_properties
TABLE_IMAGES=lead_property_images
TABLE_CLIENTS=lead_clients
TABLE_BRANDING=lead_brand_configs
TABLE_APPOINTMENTS=lead_appointments
TABLE_LEADS=lead_leads

# --- STORAGE PATHS (CRITICAL) ---
# Dev & Prod: Standardized to /srv/datasyncsa/volumes
HOST_PATH_STAGING=/srv/datasyncsa/volumes/staging
HOST_PATH_STORAGE=/srv/datasyncsa/volumes/r2_storage

# --- API KEYS ---
GOOGLE_API_KEY=replace-with-real-key

# --- SECURITY ---
SECRET_KEY=replace-with-long-random-secret
INTERNAL_API_TOKEN=replace-with-internal-service-token
ALLOWED_ORIGINS=http://admin-console.local:8085,http://admin-console-web:80,http://localhost:8085,http://127.0.0.1:8085

# --- AI CONFIGURATION ---
EMBEDDING_MODEL=models/gemini-embedding-001
VISION_MODEL=gemini-2.0-flash
LLM_MODEL=gemini-2.5-flash-lite
LLM_TIMEOUT_SECS=30
RAG_RETRIEVER_V2_URL=http://semantic-adapter-v2:8000
RAG_RETRIEVER_V2_SEARCH_PATH=/api/v2/search
RAG_RETRIEVER_V2_TIMEOUT_SECS=10
RAG_RETRIEVER_V2_RETRIES=2
RAG_TOP_K=3
CHAT_HISTORY_MAX_MESSAGES=20
SESSION_TTL_SECONDS=86400
VERTICAL_CACHE_TTL_SECONDS=300

# --- CHAT MULTI-CHANNEL FEATURE FLAGS ---
CHANNEL_GATEWAY_ENABLED=true
VERTICAL_ROUTING_ENABLED=true
META_ADAPTER_ENABLED=false

# --- SCORING FEATURE FLAGS ---
SCORING_LLM_TIMEOUT_SECS=60
SCORING_IDLE_DELAY_SECS=60
SCORING_IDLE_CLOSE_SECS=60
SCORING_WORKER_POLL_SECS=2
SCORING_JOB_MAX_ATTEMPTS=3
SCORING_JOB_LOCK_TTL_SECS=120
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
INFERENCE_V2_PORT=8091
SEMANTIC_V2_PORT=8092
GENERIC_BRIDGE_V2_PORT=8093
PROPERTY_BRIDGE_V2_PORT=8094

# --- EXTERNAL INTEGRATIONS ---
# External ETL endpoint (required by admin-console ai-library module)
# Example: https://etl.yourdomain.com
ETL_SERVICE_URL=

# --- TEST USERS (SMOKE) ---
SYSTEM_USER_EMAIL=
SYSTEM_USER_PASSWORD=
```
### `rclone-mount.service`

```
[Unit]
Description=Rclone Mount for R2 Storage (Dev)
After=network-online.target
Wants=network-online.target

[Service]
Type=notify
User=acartin
Group=acartin
ExecStart=/usr/bin/rclone mount datasync-dev: /srv/datasyncsa/volumes/r2_storage \
    --allow-other \
    --vfs-cache-mode full \
    --vfs-cache-max-size 10G \
    --log-file /var/log/rclone-storage.log \
    --log-level INFO
ExecStop=/bin/fusermount -u /srv/datasyncsa/volumes/r2_storage
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## Topología Técnica (directorios clave)

```text
docs
docs/OLD
schemas
schemas/__pycache__
services
services/database
services/etl-docs
services/etl-docs/__pycache__
services/etl-docs/src
services/etl-docs/src/ETL_DOCS
services/etl-docs/src/shared
services/etl-docs/tests
services/etl-docs/tests/integration
services/etl-docs/tests/smoke
services/etl-docs/tests/unit
services/etl-processor
services/generic-bridge-v2
services/generic-bridge-v2/__pycache__
services/inference-stack-v2
services/inference-stack-v2/inference-core-v2
services/inference-stack-v2/inference-core-v2/__pycache__
services/inference-stack-v2/inference-core-v2/app
services/inference-stack-v2/inference-core-v2/migrations
services/inference-stack-v2/inference-core-v2/scripts
services/inference-stack-v2/inference-core-v2/tests
services/inference-stack-v2/semantic-adapter-v2
services/inference-stack-v2/semantic-adapter-v2/app
services/property-bridge-v2
services/property-bridge-v2/__pycache__
services/web
services/web/admin-console
services/web/admin-console/backend
services/web/admin-console/docs
services/web/admin-console/frontend
services/web/chat-web-renderer
services/web/chat-web-renderer/backend
services/web/chat-web-renderer/frontend
services/web/datasyncsa
services/web/datasyncsa/css
services/web/datasyncsa/img
services/web/datasyncsa/js
services/web/tests
services/web/tests/assets
tests
tests/fixtures-shared
tests/sandbox
tests/sandbox/__pycache__
tests/sandbox/dentist
tests/sandbox/dentist/__pycache__
tests/sandbox/realtor
tests/sandbox/realtor/__pycache__
tests/scripts
tests/smoke-stack
tests/system
tests/system/__pycache__
```

## Entry Points Detectados

```text
services/generic-bridge-v2/main.py:28:app = FastAPI(
services/generic-bridge-v2/main.py:287:if __name__ == "__main__":
services/generic-bridge-v2/main.py:293:    uvicorn.run(
services/etl-processor/main.py:3:app = FastAPI()
services/property-bridge-v2/main.py:29:app = FastAPI(
services/property-bridge-v2/main.py:348:if __name__ == "__main__":
services/property-bridge-v2/main.py:354:    uvicorn.run(
services/web/chat-web-renderer/backend/tests/smoke/test_smoke_web_proxy.py:57:if __name__ == "__main__":
services/web/chat-web-renderer/backend/tests/smoke/test_smoke_bridge.py:36:if __name__ == "__main__":
services/web/chat-web-renderer/backend/app/main.py:11:app = FastAPI(title="Chat Web Renderer")
services/web/admin-console/backend/tests/sandbox/test_countries_crud_script.py:51:if __name__ == "__main__":
services/web/admin-console/backend/tests/sandbox/test_connection.py:25:if __name__ == "__main__":
services/web/admin-console/backend/tests/contract/test_scoring_schema_contracts.py:306:if __name__ == "__main__":
services/web/admin-console/backend/tests/smoke/test_smoke_tenant_isolation.py:89:if __name__ == "__main__":
services/web/admin-console/backend/tests/smoke/test_smoke_system_user_menu.py:162:if __name__ == "__main__":
services/web/admin-console/backend/scripts/check_hash_config.py:27:if __name__ == "__main__":
services/web/admin-console/backend/scripts/restore_pass.py:20:if __name__ == "__main__":
services/web/admin-console/backend/scripts/verify_password_change.py:73:if __name__ == "__main__":
services/web/admin-console/backend/app/dal/inspect_schema.py:31:if __name__ == "__main__":
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
services/inference-stack-v2/inference-core-v2/worker.py:31:if __name__ == "__main__":
services/inference-stack-v2/inference-core-v2/main.py:53:app = FastAPI(
services/inference-stack-v2/inference-core-v2/main.py:70:app.include_router(chat_v2_router, prefix=settings.api_prefix, tags=["chat-v2"])
services/inference-stack-v2/inference-core-v2/main.py:84:if __name__ == "__main__":
services/inference-stack-v2/inference-core-v2/main.py:85:    uvicorn.run(
services/inference-stack-v2/semantic-adapter-v2/main.py:21:app = FastAPI(
services/inference-stack-v2/semantic-adapter-v2/main.py:46:app.include_router(router, prefix="/api/v2")
services/inference-stack-v2/semantic-adapter-v2/main.py:52:if __name__ == "__main__":
services/inference-stack-v2/semantic-adapter-v2/main.py:54:    uvicorn.run(app, host="0.0.0.0", port=8000)
services/etl-docs/tests/smoke/test_smoke_etl_docs.py:42:if __name__ == "__main__":
services/etl-docs/main.py:19:app = FastAPI(title="ETL Docs API", version="1.0.0")
```

## Rutas API Detectadas

```text
services/web/chat-web-renderer/backend/app/api/external.py:56:@router.post(
services/web/chat-web-renderer/backend/app/api/external.py:267:@router.get("/health")
services/inference-stack-v2/inference-core-v2/app/api/chat_v2.py:35:@router.post("/chat", response_model=ChatV2Response)
services/inference-stack-v2/inference-core-v2/app/api/chat_v2.py:77:@router.get("/leads/{lead_id}/scorecards/latest", response_model=ScorecardResponse)
services/inference-stack-v2/inference-core-v2/app/api/chat_v2.py:99:@router.get("/leads/{lead_id}/scorecards/{scorecard_id}", response_model=ScorecardResponse)
services/inference-stack-v2/inference-core-v2/app/api/chat_v2.py:126:@router.get("/scoring/jobs/{job_id}", response_model=ScoringJobResponse)
services/inference-stack-v2/inference-core-v2/app/api/chat_v2.py:145:@router.get("/scoring/ops/summary", response_model=ScoringOpsSummaryResponse)
services/inference-stack-v2/inference-core-v2/app/api/chat_v2.py:163:@router.get("/scoring/models/active", response_model=ActiveModelResponse)
services/inference-stack-v2/inference-core-v2/app/api/chat_v2.py:210:@router.post("/cache/invalidate")
services/inference-stack-v2/inference-core-v2/app/api/chat_v2.py:241:@router.get("/health")
services/inference-stack-v2/inference-core-v2/app/api/chat_v2.py:261:@router.post("/internal/memory/reset", response_model=InternalMemoryResetResponse)
services/inference-stack-v2/semantic-adapter-v2/app/api.py:45:@router.get("/health")
services/inference-stack-v2/semantic-adapter-v2/app/api.py:66:@router.post("/search", response_model=SearchResponse)
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
services/web/admin-console/backend/app/dashboards/base_dash/router.py:10:@router.get("/app-init", response_model=UIAppShell)
services/web/admin-console/backend/app/dashboards/base_dash/router.py:72:@router.get("/base", response_model=WebIAFirstResponse)
services/web/admin-console/backend/app/dashboards/base_dash/router.py:94:@router.get("/check-contract", response_model=WebIAFirstResponse)
services/web/admin-console/backend/app/dashboards/seller_workspace/router.py:14:@router.get("/seller", response_model=ClientUserDashboardSchema)
services/web/admin-console/backend/app/dashboards/seller_workspace/router.py:52:@router.get("/leads/{lead_id}", response_model=ClientUserDashboardSchema)
services/web/admin-console/backend/app/dashboards/seller_workspace/router.py:60:@router.get("/leads_v2/{lead_id}", response_model=ClientUserDashboardSchema)
services/web/admin-console/backend/app/dashboards/manager_workspace/router.py:13:@router.get("/manager", response_model=ManagerDashboardSchema)
```

## Contratos/Modelos Críticos

```text
services/web/chat-web-renderer/backend/app/schemas/ui.py:4:class BaseComponent(BaseModel):
services/web/chat-web-renderer/backend/app/schemas/ui.py:51:class BrandingConfig(BaseModel):
services/web/chat-web-renderer/backend/app/schemas/ui.py:76:class SDUIResponse(BaseModel):
services/web/chat-web-renderer/backend/app/schemas/chat.py:7:class InitRequest(BaseModel):
services/web/chat-web-renderer/backend/app/schemas/chat.py:17:class ChatRequest(BaseModel):
services/web/chat-web-renderer/backend/app/schemas/chat.py:50:class InternalMemoryResetRequest(BaseModel):
services/web/chat-web-renderer/backend/app/schemas/internal_chat.py:10:class InternalChatRequest(BaseModel):
services/web/chat-web-renderer/backend/app/schemas/internal_chat.py:45:class InternalChatResponse(BaseModel):
services/etl-docs/src/shared/memory_reset.py:11:def reset_client_memory(client_id: str, reason: Optional[str] = None) -> bool:
services/etl-docs/src/shared/schemas.py:27:class DocumentUploadMetadata(BaseModel):
services/etl-docs/src/shared/schemas.py:34:class CanonicalMetadata(BaseModel):
services/etl-docs/src/shared/schemas.py:44:class CanonicalDocument(BaseModel):
services/etl-docs/src/shared/schemas.py:73:class SemanticItem(BaseModel):
services/etl-docs/src/shared/schemas.py:88:class RAGFilters(BaseModel):
services/etl-docs/src/shared/schemas.py:92:class RAGQuery(BaseModel):
services/etl-docs/src/shared/schemas.py:98:class RAGResult(BaseModel):
services/etl-docs/src/shared/schemas.py:105:class RAGResponse(BaseModel):
services/etl-docs/src/shared/schemas.py:113:class PropertyBase(BaseModel):
services/inference-stack-v2/inference-core-v2/app/models/chat_v2.py:7:class ChatV2Request(BaseModel):
services/inference-stack-v2/inference-core-v2/app/models/chat_v2.py:38:class ScoreItemV2(BaseModel):
services/inference-stack-v2/inference-core-v2/app/models/chat_v2.py:47:class ScorecardV2(BaseModel):
services/inference-stack-v2/inference-core-v2/app/models/chat_v2.py:57:class ChatV2Response(BaseModel):
services/inference-stack-v2/inference-core-v2/app/models/chat_v2.py:86:class ScoringJobResponse(BaseModel):
services/inference-stack-v2/inference-core-v2/app/models/chat_v2.py:114:class ScoringOpsSummaryResponse(BaseModel):
services/inference-stack-v2/inference-core-v2/app/models/chat_v2.py:137:class ScorecardResponse(BaseModel):
services/inference-stack-v2/inference-core-v2/app/models/chat_v2.py:159:class ActiveModelResponse(BaseModel):
services/inference-stack-v2/inference-core-v2/app/models/chat_v2.py:172:class InternalMemoryResetRequest(BaseModel):
services/inference-stack-v2/inference-core-v2/app/models/chat_v2.py:177:class InternalMemoryResetResponse(BaseModel):
services/web/admin-console/backend/app/contracts/ui_schema.py:4:class UIComponent(BaseModel):
services/web/admin-console/backend/app/contracts/ui_schema.py:23:class UIMenuItem(BaseModel):
services/web/admin-console/backend/app/contracts/ui_schema.py:30:class UISidebar(BaseModel):
services/web/admin-console/backend/app/contracts/ui_schema.py:34:class UIAppShell(BaseModel):
services/web/admin-console/backend/app/contracts/ui_schema.py:39:class WebIAFirstResponse(BaseModel):
services/web/admin-console/backend/app/contracts/scoring_schema.py:5:class ScoringBandV2(BaseModel):
services/web/admin-console/backend/app/contracts/scoring_schema.py:15:class ScoringCriterionV2(BaseModel):
services/web/admin-console/backend/app/contracts/scoring_schema.py:27:class ScoringSchemaV2(BaseModel):
services/web/admin-console/backend/app/contracts/scoring_schema.py:39:class ScoreItemValueV2(BaseModel):
services/web/admin-console/backend/app/contracts/scoring_schema.py:51:class ScoringValuesV2(BaseModel):
services/web/admin-console/backend/app/contracts/scoring_schema.py:63:class DynamicLeadGridColumn(BaseModel):
services/web/admin-console/backend/app/contracts/scoring_schema.py:74:class DynamicGridConfig(BaseModel):
```

## Tablas/SQL Referenciadas (DB Map)

```text
services/etl-docs/src/ETL_DOCS/processor.py -> ai_vectors
services/etl-docs/src/shared/vector_store.py -> ai_knowledge_documents
services/etl-docs/src/shared/vector_store.py -> ai_vectors
services/generic-bridge-v2/main.py -> lead_id
services/inference-stack-v2/inference-core-v2/app/api/chat_v2.py -> lead_id
services/inference-stack-v2/inference-core-v2/app/dependencies/database.py -> lead_id
services/inference-stack-v2/inference-core-v2/app/dependencies/database.py -> lead_leads
services/inference-stack-v2/inference-core-v2/app/dependencies/database.py -> lead_messages
services/inference-stack-v2/inference-core-v2/app/dependencies/database.py -> lead_scoring_jobs
services/inference-stack-v2/inference-core-v2/app/dependencies/database.py -> lead_scoring_jobs_conversation
services/inference-stack-v2/inference-core-v2/app/dependencies/database.py -> lead_scoring_jobs_lead_created
services/inference-stack-v2/inference-core-v2/app/dependencies/database.py -> lead_scoring_jobs_status
services/inference-stack-v2/inference-core-v2/app/dependencies/database.py -> lead_scoring_jobs_status_scheduled
services/inference-stack-v2/inference-core-v2/app/models/chat_v2.py -> lead_id
services/inference-stack-v2/inference-core-v2/app/models/chat_v2.py -> lead_messages
services/inference-stack-v2/inference-core-v2/app/repositories/scoring_repository.py -> lead_ai_prompts
services/inference-stack-v2/inference-core-v2/app/repositories/scoring_repository.py -> lead_by_conversation_id
services/inference-stack-v2/inference-core-v2/app/repositories/scoring_repository.py -> lead_client_verticals
services/inference-stack-v2/inference-core-v2/app/repositories/scoring_repository.py -> lead_clients
services/inference-stack-v2/inference-core-v2/app/repositories/scoring_repository.py -> lead_conversation
services/inference-stack-v2/inference-core-v2/app/repositories/scoring_repository.py -> lead_conversations
services/inference-stack-v2/inference-core-v2/app/repositories/scoring_repository.py -> lead_count
services/inference-stack-v2/inference-core-v2/app/repositories/scoring_repository.py -> lead_current_scorecard
services/inference-stack-v2/inference-core-v2/app/repositories/scoring_repository.py -> lead_from_extraction
services/inference-stack-v2/inference-core-v2/app/repositories/scoring_repository.py -> lead_id
services/inference-stack-v2/inference-core-v2/app/repositories/scoring_repository.py -> lead_leads
services/inference-stack-v2/inference-core-v2/app/repositories/scoring_repository.py -> lead_lock_stmt
services/inference-stack-v2/inference-core-v2/app/repositories/scoring_repository.py -> lead_messages
services/inference-stack-v2/inference-core-v2/app/repositories/scoring_repository.py -> lead_row
services/inference-stack-v2/inference-core-v2/app/repositories/scoring_repository.py -> lead_score_items
services/inference-stack-v2/inference-core-v2/app/repositories/scoring_repository.py -> lead_scorecards
services/inference-stack-v2/inference-core-v2/app/repositories/scoring_repository.py -> lead_scoring_bands
services/inference-stack-v2/inference-core-v2/app/repositories/scoring_repository.py -> lead_scoring_criteria
services/inference-stack-v2/inference-core-v2/app/repositories/scoring_repository.py -> lead_scoring_jobs
services/inference-stack-v2/inference-core-v2/app/repositories/scoring_repository.py -> lead_scoring_models
services/inference-stack-v2/inference-core-v2/app/repositories/scoring_repository.py -> lead_scoring_prompts
services/inference-stack-v2/inference-core-v2/app/repositories/scoring_repository.py -> lead_snapshot
services/inference-stack-v2/inference-core-v2/app/services/prompt_builder.py -> lead_scoring_bands
services/inference-stack-v2/inference-core-v2/app/services/prompt_builder.py -> lead_scoring_criteria
services/inference-stack-v2/inference-core-v2/app/services/prompt_linter.py -> lead_type
services/inference-stack-v2/inference-core-v2/app/services/realtor_turn_resolver.py -> lead_leads
services/inference-stack-v2/inference-core-v2/app/services/realtor_turn_resolver.py -> lead_properties
services/inference-stack-v2/inference-core-v2/app/services/realtor_turn_resolver.py -> lead_property_images
services/inference-stack-v2/inference-core-v2/app/services/realtor_turn_resolver.py -> lead_propierties
services/inference-stack-v2/inference-core-v2/app/services/scoring_job_service.py -> lead_id
services/inference-stack-v2/inference-core-v2/app/services/scoring_job_service.py -> lead_messages
services/inference-stack-v2/inference-core-v2/app/services/scoring_orchestrator.py -> lead_ai_prompts
services/inference-stack-v2/inference-core-v2/app/services/scoring_orchestrator.py -> lead_by_conversation_id
services/inference-stack-v2/inference-core-v2/app/services/scoring_orchestrator.py -> lead_current_scorecard
services/inference-stack-v2/inference-core-v2/app/services/scoring_orchestrator.py -> lead_from_extraction
services/inference-stack-v2/inference-core-v2/app/services/scoring_orchestrator.py -> lead_id
services/inference-stack-v2/inference-core-v2/app/services/scoring_orchestrator.py -> lead_messages
services/inference-stack-v2/inference-core-v2/app/services/scoring_orchestrator.py -> lead_properties
services/inference-stack-v2/inference-core-v2/app/services/scoring_orchestrator.py -> lead_snapshot
services/inference-stack-v2/inference-core-v2/app/services/scoring_worker.py -> lead_id
services/inference-stack-v2/inference-core-v2/app/services/scoring_worker.py -> lead_messages
services/inference-stack-v2/inference-core-v2/tests/integration/test_api_chat_v2.py -> lead_id
services/inference-stack-v2/inference-core-v2/tests/unit/test_hybrid_chat_context.py -> lead_snapshot
services/inference-stack-v2/inference-core-v2/tests/unit/test_scoring_job_service.py -> lead_id
services/inference-stack-v2/inference-core-v2/tests/unit/test_scoring_job_service.py -> lead_messages
services/inference-stack-v2/inference-core-v2/tests/unit/test_scoring_orchestrator.py -> lead_id
services/inference-stack-v2/inference-core-v2/tests/unit/test_scoring_worker_generation.py -> lead_id
services/inference-stack-v2/inference-core-v2/tests/unit/test_scoring_worker_generation.py -> lead_messages
services/inference-stack-v2/semantic-adapter-v2/app/vector_repo.py -> ai_vectors
services/property-bridge-v2/main.py -> lead_scoring
services/web/admin-console/backend/app/dashboards/seller_workspace/router.py -> lead_detail_dashboard
services/web/admin-console/backend/app/dashboards/seller_workspace/router.py -> lead_detail_dashboard_v2_clone
services/web/admin-console/backend/app/dashboards/seller_workspace/router.py -> lead_detail_schema_v2_clone
services/web/admin-console/backend/app/dashboards/seller_workspace/router.py -> lead_detail_with_scoring_v2
services/web/admin-console/backend/app/dashboards/seller_workspace/router.py -> lead_id
services/web/admin-console/backend/app/dashboards/seller_workspace/router.py -> lead_v2_service
services/web/admin-console/backend/app/dashboards/seller_workspace/schema.py -> lead_detail_schema_v2_clone
services/web/admin-console/backend/app/dashboards/seller_workspace/schema.py -> lead_id
services/web/admin-console/backend/app/dashboards/seller_workspace/schema.py -> lead_messages
services/web/admin-console/backend/app/main.py -> ai_library
services/web/admin-console/backend/app/main.py -> ai_library_router
services/web/admin-console/backend/app/main.py -> auth_router
services/web/admin-console/backend/app/modules/ai_library/router.py -> ai_library
services/web/admin-console/backend/app/modules/ai_library/router.py -> ai_library_view
services/web/admin-console/backend/app/modules/auth/config.py -> auth_backend
services/web/admin-console/backend/app/modules/auth/models.py -> auth_client_user
services/web/admin-console/backend/app/modules/auth/models.py -> auth_roles
services/web/admin-console/backend/app/modules/auth/models.py -> auth_users
services/web/admin-console/backend/app/modules/auth/models.py -> lead_clients
services/web/admin-console/backend/app/modules/auth/models.py -> lead_contacts
services/web/admin-console/backend/app/modules/auth/router.py -> auth_backend
services/web/admin-console/backend/app/modules/auth/router.py -> auth_router
services/web/admin-console/backend/app/modules/clients/router.py -> lead_brand_configs
services/web/admin-console/backend/app/modules/clients/service.py -> lead_client_verticals
services/web/admin-console/backend/app/modules/clients/service.py -> lead_clients
services/web/admin-console/backend/app/modules/clients/service.py -> lead_countries
services/web/admin-console/backend/app/modules/clients/service.py -> lead_knowledge_documents
services/web/admin-console/backend/app/modules/clients/service.py -> lead_leads
services/web/admin-console/backend/app/modules/clients/service.py -> lead_properties
services/web/admin-console/backend/app/modules/clients/service.py -> lead_scoring_models
services/web/admin-console/backend/app/modules/contacts/categories.py -> lead_channel_categories
services/web/admin-console/backend/app/modules/contacts/models.py -> lead_client_channels
services/web/admin-console/backend/app/modules/contacts/models.py -> lead_clients
services/web/admin-console/backend/app/modules/contacts/models.py -> lead_contact_channels
services/web/admin-console/backend/app/modules/contacts/models.py -> lead_contacts
services/web/admin-console/backend/app/modules/contacts/service.py -> lead_channel_categories
services/web/admin-console/backend/app/modules/contacts/service.py -> lead_contact_channels
services/web/admin-console/backend/app/modules/contacts/service.py -> lead_contacts
services/web/admin-console/backend/app/modules/countries/service.py -> lead_countries
services/web/admin-console/backend/app/modules/grid_presets/service.py -> lead_grid_presets
services/web/admin-console/backend/app/modules/leads/router.py -> lead_by_id
services/web/admin-console/backend/app/modules/leads/router.py -> lead_chat
services/web/admin-console/backend/app/modules/leads/router.py -> lead_detail
services/web/admin-console/backend/app/modules/leads/router.py -> lead_id
services/web/admin-console/backend/app/modules/leads/router.py -> lead_service
services/web/admin-console/backend/app/modules/leads/service.py -> lead_appointments
services/web/admin-console/backend/app/modules/leads/service.py -> lead_by_id
services/web/admin-console/backend/app/modules/leads/service.py -> lead_contact_preferences
services/web/admin-console/backend/app/modules/leads/service.py -> lead_id
services/web/admin-console/backend/app/modules/leads/service.py -> lead_leads
services/web/admin-console/backend/app/modules/leads/service.py -> lead_name
services/web/admin-console/backend/app/modules/leads/service.py -> lead_scoring_definitions
services/web/admin-console/backend/app/modules/leads/service.py -> lead_sources
services/web/admin-console/backend/app/modules/leads/service.py -> lead_statuses
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_service.py -> lead_client_verticals
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_service.py -> lead_scoring_bands
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_service.py -> lead_scoring_criteria
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_service.py -> lead_scoring_models
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_service.py -> lead_scoring_prompts
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_service.py -> lead_scoring_prompts_active_model
services/web/admin-console/backend/app/modules/leads_v2/admin_scoring_service.py -> lead_scoring_prompts_model_id_version_key
services/web/admin-console/backend/app/modules/leads_v2/router.py -> lead_detail_components
services/web/admin-console/backend/app/modules/leads_v2/router.py -> lead_detail_v2
services/web/admin-console/backend/app/modules/leads_v2/router.py -> lead_detail_with_scoring_v2
services/web/admin-console/backend/app/modules/leads_v2/router.py -> lead_id
services/web/admin-console/backend/app/modules/leads_v2/router.py -> lead_scoring_values
services/web/admin-console/backend/app/modules/leads_v2/router.py -> lead_v2_service
services/web/admin-console/backend/app/modules/leads_v2/service.py -> lead_by_id
services/web/admin-console/backend/app/modules/leads_v2/service.py -> lead_client_verticals
services/web/admin-console/backend/app/modules/leads_v2/service.py -> lead_clients
services/web/admin-console/backend/app/modules/leads_v2/service.py -> lead_contact_preferences
services/web/admin-console/backend/app/modules/leads_v2/service.py -> lead_conversations
services/web/admin-console/backend/app/modules/leads_v2/service.py -> lead_data
services/web/admin-console/backend/app/modules/leads_v2/service.py -> lead_detail_with_scoring_v2
services/web/admin-console/backend/app/modules/leads_v2/service.py -> lead_id
services/web/admin-console/backend/app/modules/leads_v2/service.py -> lead_leads
services/web/admin-console/backend/app/modules/leads_v2/service.py -> lead_messages
services/web/admin-console/backend/app/modules/leads_v2/service.py -> lead_score_items
services/web/admin-console/backend/app/modules/leads_v2/service.py -> lead_scorecards
services/web/admin-console/backend/app/modules/leads_v2/service.py -> lead_scoring_bands
services/web/admin-console/backend/app/modules/leads_v2/service.py -> lead_scoring_criteria
services/web/admin-console/backend/app/modules/leads_v2/service.py -> lead_scoring_models
services/web/admin-console/backend/app/modules/leads_v2/service.py -> lead_sources
services/web/admin-console/backend/app/modules/leads_v2/service.py -> lead_statuses
services/web/admin-console/backend/app/modules/prompts/service.py -> lead_ai_prompts
services/web/admin-console/backend/app/modules/prompts/service.py -> lead_clients
services/web/admin-console/backend/app/modules/roles/service.py -> auth_roles
services/web/admin-console/backend/app/modules/system_public_docs/router.py -> ai_library
services/web/admin-console/backend/app/modules/system_public_docs/router.py -> lead_clients
services/web/admin-console/backend/app/modules/users/service.py -> auth_client_user
services/web/admin-console/backend/app/modules/users/service.py -> auth_roles
services/web/admin-console/backend/app/modules/users/service.py -> auth_users
services/web/admin-console/backend/app/modules/users/service.py -> lead_clients
services/web/admin-console/backend/scripts/restore_pass.py -> auth_users
services/web/admin-console/backend/scripts/verify_password_change.py -> auth_users
services/web/admin-console/backend/tests/conftest.py -> auth_override
services/web/admin-console/backend/tests/contract/test_leads_ai_library_contracts.py -> ai_library
services/web/admin-console/backend/tests/contract/test_leads_ai_library_contracts.py -> ai_library_pdfs_data_maps_sync_status
services/web/admin-console/backend/tests/contract/test_leads_ai_library_contracts.py -> ai_library_router_module
services/web/admin-console/backend/tests/contract/test_leads_ai_library_contracts.py -> ai_library_view_contract
services/web/admin-console/backend/tests/contract/test_leads_ai_library_contracts.py -> ai_library_view_hides_public_access_level_for_regular_tenant
services/web/admin-console/backend/tests/contract/test_leads_ai_library_contracts.py -> auth_override
services/web/admin-console/backend/tests/contract/test_leads_ai_library_contracts.py -> lead_by_id
services/web/admin-console/backend/tests/contract/test_leads_ai_library_contracts.py -> lead_detail_contract_includes_chat_navigation
services/web/admin-console/backend/tests/contract/test_leads_ai_library_contracts.py -> lead_id
services/web/admin-console/backend/tests/contract/test_leads_ai_library_contracts.py -> lead_service
services/web/admin-console/backend/tests/contract/test_sdui_router_contracts.py -> auth_override
services/web/admin-console/backend/tests/integration/test_security_and_scoping.py -> auth_override
services/web/admin-console/backend/tests/integration/test_security_and_scoping.py -> auth_returns_ok
services/web/admin-console/backend/tests/integration/test_security_and_scoping.py -> lead_by_id
services/web/admin-console/backend/tests/integration/test_security_and_scoping.py -> lead_detail_passes_user_scope
services/web/admin-console/backend/tests/integration/test_security_and_scoping.py -> lead_id
services/web/admin-console/backend/tests/integration/test_security_and_scoping.py -> lead_service
services/web/chat-web-renderer/backend/app/api/external.py -> ai_response
services/web/chat-web-renderer/backend/app/api/external.py -> ai_text
services/web/chat-web-renderer/backend/app/api/external.py -> auth_not_configured
services/web/chat-web-renderer/backend/app/api/external.py -> auth_user_id
services/web/chat-web-renderer/backend/app/api/external.py -> lead_id
services/web/chat-web-renderer/backend/app/api/schemas.py -> auth_user_id
services/web/chat-web-renderer/backend/app/core/database.py -> lead_brand_configs
services/web/chat-web-renderer/backend/app/core/database.py -> lead_client_verticals
services/web/chat-web-renderer/backend/app/core/database.py -> lead_clients
services/web/chat-web-renderer/backend/app/core/database.py -> lead_properties
services/web/chat-web-renderer/backend/app/core/database.py -> lead_property_images
services/web/chat-web-renderer/backend/app/core/inference_bridge.py -> lead_id
services/web/chat-web-renderer/backend/app/main.py -> ai_response
services/web/chat-web-renderer/backend/app/main.py -> ai_text
services/web/chat-web-renderer/backend/app/main.py -> lead_id
services/web/chat-web-renderer/backend/app/planner/sql_planner.py -> lead_ai_prompts
services/web/chat-web-renderer/backend/app/planner/sql_planner.py -> lead_leads
services/web/chat-web-renderer/backend/app/planner/sql_planner.py -> lead_properties
services/web/chat-web-renderer/backend/app/planner/sql_planner.py -> lead_property_images
services/web/chat-web-renderer/backend/app/planner/sql_planner.py -> lead_propierties
services/web/chat-web-renderer/backend/app/schemas/internal_chat.py -> auth_user_id
services/web/chat-web-renderer/backend/app/transformer/core.py -> ai_response
services/web/chat-web-renderer/backend/app/transformer/core.py -> ai_text
services/web/chat-web-renderer/backend/app/transformer/core.py -> lead_brand_configs
services/web/chat-web-renderer/backend/app/transformer/generic_policy.py -> ai_response
services/web/chat-web-renderer/backend/app/transformer/generic_policy.py -> ai_text
services/web/chat-web-renderer/backend/app/transformer/realtor_policy.py -> ai_response
services/web/chat-web-renderer/backend/app/transformer/realtor_policy.py -> ai_text
services/web/chat-web-renderer/backend/tests/integration/test_api.py -> ai_text
services/web/chat-web-renderer/backend/tests/integration/test_tenant_isolation.py -> ai_text
services/web/chat-web-renderer/backend/tests/unit/test_chat_runtime.py -> ai_text
services/web/chat-web-renderer/backend/tests/unit/test_external_api_security.py -> ai_text
services/web/chat-web-renderer/backend/tests/unit/test_generic_policy.py -> ai_text
services/web/chat-web-renderer/backend/tests/unit/test_internal_chat_schema.py -> auth_user_id
services/web/chat-web-renderer/backend/tests/unit/test_realtor_policy.py -> ai_text
services/web/chat-web-renderer/backend/tests/unit/test_sql_planner.py -> lead_leads
```

## Motor SUID/SDUI (archivos núcleo)

### `services/web/admin-console/backend/app/contracts/ui_schema.py`

```
from pydantic import BaseModel
from typing import List, Optional, Literal

class UIComponent(BaseModel):
    type: str
    label: Optional[str] = None
    color: Optional[str] = "primary" # Relaxed literal for now or keep it strict? Keeping strict might break valid Velzon tokens if not listed. Let's make it optional string for flexibility.
    
    # Generic fields for various components
    components: Optional[List['UIComponent']] = None # Recursive for Grid
    text: Optional[str] = None # For Typography
    tag: Optional[str] = None # For Typography
    buttons: Optional[List[dict]] = None # For Button Group
    class_: Optional[str] = None # For custom classes (using class_ alias for 'class')

    properties: dict = {}

    model_config = {
        "extra": "allow", # Allow arbitrary fields like 'icon', 'metric', etc.
        "populate_by_name": True
    }

class UIMenuItem(BaseModel):
    id: str
    label: str
    icon: Optional[str] = None
    link: Optional[str] = None # For navigation
    subItems: Optional[List['UIMenuItem']] = None # Recursive submenu

class UISidebar(BaseModel):
    brand: str
    items: List[UIMenuItem]

class UIAppShell(BaseModel):
    layout: Literal["dashboard-shell"] = "dashboard-shell"
    sidebar: UISidebar
    content: List['UIComponent'] # Initial content to load

class WebIAFirstResponse(BaseModel):
    # This might be deprecated or used for partial updates, but for app-init we'll use UIAppShell
    layout: str
    components: Optional[List[UIComponent]] = None
    properties: Optional[dict] = None
    tabs: Optional[List[dict]] = None
```
### `services/web/admin-console/backend/app/modules/shared/sdui.py`

```
import base64
import json
from typing import Any, Dict


def encode_schema_b64(schema: list[dict]) -> str:
    return base64.b64encode(json.dumps(schema).encode()).decode()


def edit_action(action_url: str, schema_b64: str, label: str = "Editar") -> Dict[str, Any]:
    return {
        "label": label,
        "icon": "ri-pencil-line",
        "action": "edit",
        "action_url": action_url,
        "schema": schema_b64,
    }


def delete_action(action_url: str, label: str = "Eliminar") -> Dict[str, Any]:
    return {
        "label": label,
        "icon": "ri-delete-bin-line",
        "action": "delete",
        "action_url": action_url,
        "color": "danger",
    }


def create_modal_action(
    action_url: str,
    schema_b64: str,
    modal_title: str,
    label: str,
    icon: str = "ri-add-line",
) -> Dict[str, Any]:
    return {
        "label": label,
        "action": "modal-form",
        "action_url": action_url,
        "modal_title": modal_title,
        "color": "success",
        "icon": icon,
        "schema": schema_b64,
    }
```
### `services/web/admin-console/frontend/renderer/main.js`

```
/**
 * AI-First SDUI Renderer Engine (Modular Version)
 * Strictly follows 'visual_dictionary.json' and 'catalog_context.json'
 */

import { renderContent, renderComponent } from './engine/registry.js';
export { renderContent, renderComponent };
import { hydrateGrids } from './engine/hydration.js';
import './engine/actions.js'; // Attaches handlers to window
const RUNTIME_VERSION = (window.AppConfig && window.AppConfig.APP_VERSION) ? window.AppConfig.APP_VERSION : '1';

import { LinkAppShell } from '../components/layout/AppShell.js';
import { LinkSidebar } from '../components/layout/Sidebar.js';
import { LinkNavbar } from '../components/layout/Navbar.js';
import { LinkProjectBanner } from '../components/layout/ProjectBanner.js';

const API_BASE_URL = window.AppConfig.API_BASE_URL;
const RENDERER_VERSION = RUNTIME_VERSION;
console.log(`[Renderer] v${RENDERER_VERSION} Modular Initializing... (REGISTRY FIX)`);

window.appState = { currentPath: null };
window.navigateTo = navigateTo; // Expose for inline clicks
window.hydrateGrids = hydrateGrids;

async function init() {
    const appRoot = document.getElementById('app-root');
    try {
        const token = localStorage.getItem('access_token');
        const headers = {
            'Accept': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        };
        if (token) headers['Authorization'] = `Bearer ${token}`;

        // Timeout Promise
        const timeout = new Promise((_, reject) =>
            setTimeout(() => reject(new Error('Connection timed out. Backend is unresponsive.')), 5000)
        );

        // Race fetch against timeout
        const requestAppInit = (url) => fetch(url, { headers, cache: 'no-store' });
        let response = await Promise.race([
            requestAppInit(`${API_BASE_URL}/app-init`),
            timeout
        ]);

        // Defensive retry to avoid intermittent stale/unauthorized responses on hard reload.
        if (response.status === 401 && token) {
            response = await Promise.race([
                requestAppInit(`${API_BASE_URL}/app-init?_ts=${Date.now()}`),
                timeout
            ]);
        }

        if (response.status === 401) {
            window.location.href = '/login.html';
            return;
        }
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

        const appData = await response.json();

        // Normal Boot Process...
        if (appData.layout === 'dashboard-shell') {
            if (appData.content) appData.contentHtml = renderContent(appData.content);
            const shellHtml = LinkAppShell(appData);

            const existingWrapper = document.getElementById('layout-wrapper');
            if (existingWrapper) existingWrapper.outerHTML = shellHtml;
            else document.body.insertAdjacentHTML('afterbegin', shellHtml);

            setupThemeSwitcher();
            updateHeaderProfile();
            setupNavigation();

            const currentPath = `${window.location.pathname}${window.location.search || ''}`;
            if (currentPath && currentPath !== '/' && currentPath !== '/index.html') {
                navigateTo(currentPath);
            } else {
                hydrateGrids();
            }
        }
    } catch (error) {
        console.error('Render Error:', error);
        // EMERGENCY MODE UI
        document.body.innerHTML = `
            <div class="ac-emergency-screen">
                <h1 class="ac-emergency-title">⚠️ EMERGENCY MODE</h1>
                <p>The Application failed to initialize.</p>
                <div class="ac-emergency-box">
                    <textarea readonly class="ac-emergency-textarea">${(error.stack || error.message || JSON.stringify(error) || "Unknown Error")}</textarea>
                    <button type="button" class="ac-emergency-copy-btn" onclick="navigator.clipboard.writeText(this.previousElementSibling.value); this.innerText='COPIED!'">COPY ERROR TO CLIPBOARD</button>
                </div>
                <button class="ac-emergency-retry-btn" onclick="window.location.reload()">
                    Retry Connection
                </button>
            </div>
        `;
    }
}

export async function navigateTo(href, pushState = true) {
    if (!href || href === '#' || href.startsWith('#')) return;

    // PERSISTENCE LOGIC START
    // If we are leaving a grid view (e.g. /leads/me) to go to a detail view, save the grid URL.
    const isDetailView = /\/leads(?:_v2)?\/[0-9a-fA-F-]{36}/.test(href);
    if (isDetailView && window.location.pathname !== href) {
        localStorage.setItem('last_active_grid_url', window.location.pathname);
    }
    // PERSISTENCE LOGIC END
    // PERSISTENCE LOGIC END

    window.appState.currentPath = href;
    const pageRoot = document.getElementById('page-root');
    if (!pageRoot) return;

    pageRoot.innerHTML = `<div class="text-center mt-5"><div class="spinner-border text-primary" role="status"></div></div>`;

    try {
        const token = localStorage.getItem('access_token');
        const headers = {
            'Accept': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        };
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        const toggleTrailingSlash = (path) => {
            const [pathname, query = ''] = String(path).split('?');
            if (!pathname || pathname === '/') return path;
            const toggled = pathname.endsWith('/') ? pathname.slice(0, -1) : `${pathname}/`;
            return query ? `${toggled}?${query}` : toggled;
        };

        let resolvedHref = href;
        let response = await fetch(`${API_BASE_URL}${resolvedHref}`, { headers, cache: 'no-store' });
        if (!response.ok) throw new Error(`View not found (${response.status})`);

        let contentType = response.headers.get('content-type') || '';
        if (!contentType.toLowerCase().includes('application/json')) {
            const altHref = toggleTrailingSlash(resolvedHref);
            if (altHref !== resolvedHref) {
                const altResponse = await fetch(`${API_BASE_URL}${altHref}`, { headers, cache: 'no-store' });
                const altContentType = altResponse.headers.get('content-type') || '';
                if (altResponse.ok && altContentType.toLowerCase().includes('application/json')) {
                    resolvedHref = altHref;
                    response = altResponse;
                    contentType = altContentType;
                }
            }
        }

        if (!contentType.toLowerCase().includes('application/json')) {
            throw new Error(`Invalid view payload (expected JSON). status=${response.status} content-type=${contentType} url=${response.url}`);
        }

        const viewData = await response.json();
        if (viewData.debug_data) {
            console.log("[Lead Detail Data]:", viewData.debug_data);
        }
        if (viewData.layout === 'dashboard-project-overview') {
            const bannerHtml = LinkProjectBanner(viewData);
            let tabsContentHtml = '';
            if (viewData.tabs) {
                tabsContentHtml = viewData.tabs.map(tab => {
                    const activeClass = tab.active ? 'show active' : '';
                    return `<div class="tab-pane fade ${activeClass}" id="${tab.id}" role="tabpanel">${renderContent(tab.components)}</div>`;
                }).join('');
            } else {
                tabsContentHtml = `<div class="tab-pane fade show active" id="project-overview" role="tabpanel">${renderContent(viewData.components)}</div>`;
            }
            pageRoot.innerHTML = `${bannerHtml}<div class="tab-content text-muted mt-3">${tabsContentHtml}</div>`;
        } else if (viewData.components) {
            pageRoot.innerHTML = renderContent(viewData.components);
        }

        hydrateGrids();

        if (pushState) history.pushState(null, '', resolvedHref);
        document.body.classList.remove('vertical-sidebar-enable');
    } catch (error) {
        console.error('Navigation Error:', error);
        pageRoot.innerHTML = `<div class="alert alert-danger">${error.message}</div>`;
    }
}

function setupThemeSwitcher() {
    const btn = document.querySelector('.light-dark-mode');
    if (!btn) return;
    btn.addEventListener('click', () => {
        const html = document.documentElement;
        const currentMode = html.getAttribute('data-bs-theme') || 'light';
        const newMode = currentMode === 'light' ? 'dark' : 'light';
        html.setAttribute('data-bs-theme', newMode);
        html.setAttribute('data-layout-mode', newMode);
        localStorage.setItem('theme-mode', newMode);
    });
    const savedMode = localStorage.getItem('theme-mode');
    if (savedMode) {
        document.documentElement.setAttribute('data-bs-theme', savedMode);
        document.documentElement.setAttribute('data-layout-mode', savedMode);
    }
}

function setupNavigation() {
    document.addEventListener('click', (e) => {
        const link = e.target.closest('a.nav-link') || e.target.closest('.js-navigate');
        if (!link) return;
        const href = link.getAttribute('href') || link.dataset.url;
        if (!href || href === '#' || href.startsWith('#')) return;
        e.preventDefault();
        navigateTo(href, true);
    });
    window.addEventListener('popstate', () => {
        const path = window.location.pathname;
        if (path) navigateTo(path, false);
    });
}

```
### `services/web/admin-console/frontend/renderer/engine/registry.js`

```
/**
 * Component Registry for SDUI Renderer
 * Maps component types to their respective Link functions.
 */

import { LinkMetricCard } from '../../components/cards/MetricCard.js';
import { LinkGridContainer } from '../../components/grids/Grid.js';
import { LinkTypography } from '../../components/ui/Typography.js';
import { LinkButtonGroup } from '../../components/ui/ButtonGroup.js';

import { LinkLeadControlGrid } from '../../components/grids/LeadControlGrid.js';
import { LinkTabs } from '../../components/ui/Tabs.js';
import { LinkModalForm } from '../../components/forms/ModalForm.js';
import { LinkFormContainer } from '../../components/forms/FormContainer.js';
import { LinkRow, LinkCol } from '../../components/layout/Layout.js';
import { LinkProjectBanner } from '../../components/layout/ProjectBanner.js';
import { LinkCard } from '../../components/ui/Card.js';
import { LinkGauge } from '../../components/ui/Gauge.js';
import { LinkMemberListCard, LinkGenericCard, LinkFileGrid, LinkContactListDetailed } from '../../components/cards/DashboardWidgets.js';
import { LinkScoreRow } from '../../components/ui/ScoreRow.js';
import { LinkInfoRow } from '../../components/ui/InfoRow.js';
import { LinkProfileHeader } from '../../components/ui/ProfileHeader.js';
import { LinkBackLink } from '../../components/ui/BackLink.js';
import { LinkEmptyState } from '../../components/ui/EmptyState.js';
import { LinkAuditSplitView } from '../../components/ui/AuditSplitView.js';
import { LinkLeadSourceView } from '../../components/ui/LeadSourceView.js';

// Simple Wrapper for Custom Grid Container
import { LinkCustomGridContainer } from '../../components/grids/CustomGridContainer.js';

import { LinkGridVisual } from '../../components/grids/GridVisual.js';

const registry = {
    'custom-leads-grid': LinkCustomGridContainer, // Beta Engine
    'card': LinkCard,
    'card-metric': LinkMetricCard,
    'grid': LinkGridContainer,
    'typography': LinkTypography,
    'button-group': LinkButtonGroup,
    'grid-visual': LinkGridVisual,
    'grid-leads-control': LinkLeadControlGrid,
    'tabs': LinkTabs,
    'modal-form': LinkModalForm,
    'row': LinkRow,
    'col': LinkCol,
    'layout-row': LinkRow,
    'layout-col': LinkCol,
    'form-container': LinkFormContainer,
    'project-banner': LinkProjectBanner,
    'member-list': LinkMemberListCard,
    'member-list-card': LinkMemberListCard,
    'generic-card': LinkGenericCard,
    'gauge': LinkGauge,
    'file-grid': LinkFileGrid,
    'contact-list-detailed': LinkContactListDetailed,
    'score-row': LinkScoreRow,
    'info-row': LinkInfoRow,
    'profile-header': LinkProfileHeader,
    'back-link': LinkBackLink,
    'empty-state': LinkEmptyState,
    'audit-split-view': LinkAuditSplitView,
    'lead-source-view': LinkLeadSourceView
};

// --- GLOBAL FORM HANDLERS (Moved from FormContainer to ensure execution) ---

if (!window.validateFileSize) {
    window.validateFileSize = (input, helpId) => {
        const file = input.files[0];
        const helpText = document.getElementById(helpId);
        if (!file) {
            helpText.innerText = 'Max: 100MB';
            helpText.classList.remove('text-danger', 'text-success');
            helpText.classList.add('text-muted');
            return;
        }

        const sizeMB = file.size / (1024 * 1024);
        if (sizeMB > 100) {
            input.value = ''; // Clear input
            helpText.innerText = `Error: Archivo demasiado grande (${sizeMB.toFixed(2)} MB). Límite: 100MB`;
            helpText.classList.remove('text-muted', 'text-success');
            helpText.classList.add('text-danger');
        } else {
            helpText.innerText = `Tamaño: ${sizeMB.toFixed(2)} MB (OK)`;
            helpText.classList.remove('text-muted', 'text-danger');
            helpText.classList.add('text-success');
        }
    };
}

if (!window.handleFormSubmit) {
    window.handleFormSubmit = async (event, formId) => {
        event.preventDefault();
        console.log('--- Handle Form Submit Triggered ---');

        const form = document.getElementById(formId);
        const formData = new FormData(form);
        const action = form.getAttribute('action');
        const method = form.getAttribute('method');
        const btn = form.querySelector('button[type="submit"]');
        const originalText = btn.innerText;

        try {
            btn.disabled = true;
            btn.innerText = 'Guardando...';

            // Get auth token if available
            const token = localStorage.getItem('access_token');
            const headers = {};
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const fullUrl = window.AppConfig.API_BASE_URL + action;
            console.log('Sending to:', fullUrl);
            console.log('Token exists:', !!token);

            const response = await fetch(fullUrl, {
                method: method,
                headers: headers,
                body: formData
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || `Error ${response.status}`);
            }

            const result = await response.json();

            // Success Feedback
            btn.classList.replace('btn-primary', 'btn-success');
            btn.innerText = '¡Guardado!';
            setTimeout(() => {
                btn.classList.replace('btn-success', 'btn-primary');
                btn.innerText = originalText;
                btn.disabled = false;
            }, 2000);

        } catch (error) {
            console.error('Form Submit Error:', error);
            btn.classList.replace('btn-primary', 'btn-danger');
            btn.innerText = 'Error';
            setTimeout(() => {
                btn.classList.replace('btn-danger', 'btn-primary');
                btn.innerText = originalText;
                btn.disabled = false;
            }, 2000);
        }
    };
}


export function renderComponent(component) {
    if (!component || !component.type) return '';

    const LinkFn = registry[component.type];
    if (LinkFn) {
        return LinkFn(component);
    }

    // console.warn(`[Renderer] Missing component type: ${ component.type } `);
    return `< div class= "alert alert-warning" > Unknown component: ${component.type}</div > `;
}

export function renderContent(components) {
    if (!components) return '';
    if (!Array.isArray(components)) return renderComponent(components);
    return components.map(c => renderComponent(c)).join('');
}
```
### `services/web/chat-web-renderer/backend/app/schemas/ui.py`

```
from typing import List, Optional, Union, Dict
from pydantic import BaseModel, Field

class BaseComponent(BaseModel):
    type: str
    id: Optional[str] = None

class ChatMessage(BaseComponent):
    type: str = "chat"
    text: str
    sender: str  # "bot" or "user"

class PropertyCard(BaseComponent):
    type: str = "property-card"
    title: str
    price: float
    location: Optional[str] = None
    image_url: Optional[str] = None
    features: Dict[str, Union[int, float, str]] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)

class MortgageCalculator(BaseComponent):
    type: str = "mortgage-calculator"
    property_price: float
    default_interest: float = 8.5
    allow_custom_input: bool = True

class PropertyGrid(BaseComponent):
    type: str = "property-grid"
    title: str
    properties: List[PropertyCard]
    layout: str = "horizontal"

class PropertyMap(BaseComponent):
    type: str = "property-map"
    center: Dict[str, float]  # {"lat": ..., "lng": ...}
    zoom: int = 15
    pois: List[Dict[str, Union[float, str]]] = Field(default_factory=list)
    interactive: bool = True

class ActionMenu(BaseComponent):
    type: str = "action-menu"
    title: Optional[str] = None
    options: List[Dict[str, str]]  # [{"label": "Ver Más", "payload": "HOUSE_123"}]

class PhotoCarousel(BaseComponent):
    type: str = "photo-carousel"
    images: List[str]
    show_thumbnails: bool = False

class BrandingConfig(BaseModel):
    primary_color: str = "#4b38b3"
    secondary_color: str = "#6366f1"
    surface_color: Optional[str] = None
    text_on_primary: Optional[str] = "#ffffff"
    text_on_secondary: Optional[str] = "#ffffff"
    text_on_surface: Optional[str] = "#f8fafc"
    
    # Fuentes
    font_heading_name: Optional[str] = "Outfit"
    font_heading_url: Optional[str] = None
    font_body_name: Optional[str] = "Inter"
    font_body_url: Optional[str] = None
    
    # Estética
    border_radius: Optional[str] = "18px"
    box_shadow_style: Optional[str] = "0 10px 25px rgba(0,0,0,0.1)"
    
    # Logos (Base64)
    favicon_base64: Optional[str] = None
    logo_header_base64: Optional[str] = None
    brand_wordmark_base64: Optional[str] = None
    
    agent_name: str = "Hommie AI"

class SDUIResponse(BaseModel):
    session_id: str
    branding: Optional[BrandingConfig] = None
    components: List[Union[ChatMessage, PropertyCard, MortgageCalculator, PropertyGrid, PropertyMap, ActionMenu, PhotoCarousel]]
```
### `services/web/chat-web-renderer/backend/app/transformer/core.py`

```
import logging
import asyncio
from typing import Dict, Any, List, Union
from app.schemas.ui import (
    SDUIResponse, ChatMessage, PropertyCard, PropertyGrid, 
    ActionMenu, MortgageCalculator, BaseComponent, BrandingConfig
)
from app.core.database import db_manager

# Logger config
logger = logging.getLogger("transformer")

class SDUITransformer:
    """
    El 'Transformer' es el corazón polimórfico del Bridge.
    Toma la respuesta cruda de la IA (texto + sources) y decide qué 
    componentes visuales (Cards, Grids, Mapas) se deben renderizar.
    """

    async def transform(
        self,
        ai_response: Dict[str, Any],
        session_id: str,
        client_id: str = "default",
        brand_project: Union[str, None] = None,
        include_fallback_text: bool = True,
    ) -> SDUIResponse:
        """
        Convierte el payload del Inference Core en una respuesta SDUI estructurada.
        """
        components: List[BaseComponent] = []
        
        # 1. Extraer el Texto Base (Siempre hay un mensaje de chat)
        ai_text = (ai_response.get("answer", "") or "").strip()
        if ai_text:
            components.append(ChatMessage(text=ai_text, sender="bot"))
        elif include_fallback_text:
            components.append(ChatMessage(text="Lo siento, no pude generar una respuesta.", sender="bot"))

        # 2. Procesar Fuentes (Sources) - Aquí ocurre la magia de "Grounding"
        # Si la IA cita propiedades, las convertimos en Cards visuales.
        sources = ai_response.get("sources", [])
        property_cards = await self._extract_properties_from_sources(sources)

        if property_cards:
            if len(property_cards) == 1:
                # Si es una sola, la mostramos directa
                components.append(property_cards[0])
                # Y quizás una calculadora para esa propiedad
                components.append(MortgageCalculator(property_price=property_cards[0].price))
            else:
                # Si son varias, usamos un Grid/Carrusel
                components.append(PropertyGrid(
                    title="Propiedades Relacionadas",
                    properties=property_cards
                ))

        # 3. Detectar Intenciones de Acción (Heurística simple por ahora)
        if ai_text and ("cita" in ai_text.lower() or "visita" in ai_text.lower()):
            components.append(ActionMenu(
                options=[
                    {"label": "📅 Agendar Visita", "payload": "SCHEDULE_VISIT"},
                    {"label": "📞 Hablar con Asesor", "payload": "CALL_AGENT"}
                ]
            ))

        # 4. Configuración de Branding (Multi-tenant Real)
        branding = await self._get_branding_for_client(client_id, brand_project)

        return SDUIResponse(
            session_id=session_id,
            branding=branding,
            components=components
        )

    async def _get_branding_for_client(self, client_id: str, brand_project: Union[str, None]) -> BrandingConfig:
        """
        Retorna la configuración visual adaptada al cliente desde la DB.
        """
        db_brand = await asyncio.to_thread(db_manager.get_branding, client_id, brand_project)
        if not db_brand:
            return BrandingConfig()

        # Si tenemos branding en DB, mapeamos campos
        # lead_brand_configs: primary_color, secondary_color, project (como agent_name)
        return BrandingConfig(
            primary_color=db_brand.get("primary_color", "#4b38b3"),
            secondary_color=db_brand.get("secondary_color", "#6366f1"),
            surface_color=db_brand.get("surface_color"),
            text_on_primary=db_brand.get("text_on_primary", "#ffffff"),
            text_on_secondary=db_brand.get("text_on_secondary", "#ffffff"),
            text_on_surface=db_brand.get("text_on_surface", "#f8fafc"),
            
            # Fuentes
            font_heading_name=db_brand.get("font_heading_name", "Outfit"),
            font_heading_url=db_brand.get("font_heading_url"),
            font_body_name=db_brand.get("font_body_name", "Inter"),
            font_body_url=db_brand.get("font_body_url"),
            
            # Estética
            border_radius=db_brand.get("border_radius", "18px"),
            box_shadow_style=db_brand.get("box_shadow_style", "0 10px 25px rgba(0,0,0,0.1)"),
            
            # Logos (Base64)
            favicon_base64=db_brand.get("favicon_base64"),
            logo_header_base64=db_brand.get("logo_header_base64"),
            brand_wordmark_base64=db_brand.get("brand_wordmark_base64"),
            
            agent_name=db_brand.get("project", db_brand.get("agent_name", "Hommie AI"))
        )

    async def _extract_properties_from_sources(self, sources: List[Dict[str, Any]]) -> List[PropertyCard]:
        """
        Analiza los sources devueltos por RAG. Si encuentra metadatos de propiedades,
        crea los objetos PropertyCard correspondientes consultando la base de datos real.
        """
        cards = []
        prop_ids: List[Any] = []
        seen_ids = set()

        for source in sources:
            metadata = source.get("metadata", {})
            
            # Buscamos el ID de la propiedad (puede venir como 'id' o 'external_prop_id')
            prop_id = metadata.get("id") or metadata.get("id_propiedad")
            if prop_id and prop_id not in seen_ids:
                seen_ids.add(prop_id)
                prop_ids.append(prop_id)

        if not prop_ids:
            return cards

        # Ejecuta consultas de propiedades fuera del event loop principal
        prop_results = await asyncio.gather(
            *(asyncio.to_thread(db_manager.get_property, prop_id) for prop_id in prop_ids),
            return_exceptions=True,
        )

        for prop_data in prop_results:
            if isinstance(prop_data, Exception) or not prop_data:
                continue
            card = self._map_property_data_to_card(prop_data)
            if card:
                cards.append(card)
        
        return cards

    async def search_properties_for_query(
        self,
        client_id: str,
        query_text: str,
        limit: int = 4,
        include_terms: bool = True,
    ) -> List[PropertyCard]:
        properties = await asyncio.to_thread(
            db_manager.search_properties,
            client_id,
            query_text,
            limit,
            include_terms,
        )
        cards: List[PropertyCard] = []
        for prop_data in properties or []:
            card = self._map_property_data_to_card(prop_data)
            if card:
                cards.append(card)
        return cards

    async def count_properties_for_query(self, client_id: str, query_text: str, include_terms: bool = True) -> int:
        return await asyncio.to_thread(db_manager.count_properties, client_id, query_text, include_terms)

    async def get_property_price_stats_for_query(self, client_id: str, query_text: str, include_terms: bool = False) -> Dict[str, Any]:
        return await asyncio.to_thread(db_manager.get_property_price_stats, client_id, query_text, include_terms)

    async def extract_property_filters_for_query(self, query_text: str) -> Dict[str, Any]:
        return await asyncio.to_thread(db_manager.extract_property_filters, query_text)

    def _map_property_data_to_card(self, prop_data: Dict[str, Any]) -> Union[PropertyCard, None]:
        try:
            title = (prop_data.get("title") or "Propiedad Sugerida").replace("&#8211;", "-")
            location = f"{prop_data.get('address_city', '')}, {prop_data.get('address_state', '')}".strip(", ")
            features = prop_data.get("features") if isinstance(prop_data.get("features"), dict) else {}
            tags = features.get("highlights", []) if isinstance(features, dict) else []
            return PropertyCard(
                id=str(prop_data.get("id")),
                title=title,
                price=float(prop_data.get("price", 0) or 0),
                location=location,
                image_url=prop_data["images"][0] if prop_data.get("images") else None,
                tags=tags if isinstance(tags, list) else [],
            )
        except Exception as e:
            logger.warning(f"Error mapeando data de DB a PropertyCard: {e}")
            return None
```
### `services/web/chat-web-renderer/frontend/core/renderer.js`

```
/**
 * REALTOR CHAT: POLYMORPHIC RENDERER CORE
 * Este es el cerebro del frontend. Recibe un JSON del Bridge y decide qué dibujar.
 */

export class ChatRenderer {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.botName = "Hommie AI";
    }

    setBotName(name) {
        if (name) this.botName = name;
    }

    scrollToBottom() {
        this.container.scrollTop = this.container.scrollHeight;
    }

    renderResponse(sduiResponse) {
        const components = Array.isArray(sduiResponse?.components) ? sduiResponse.components : [];

        // Limpiamos mensajes de "Cargando..." si existen
        if (this.container.querySelector('.text-muted')) {
            this.container.innerHTML = '';
        }

        components.forEach((comp) => {
            const element = this.createComponent(comp);
            if (element) {
                const bubble = this.wrapInBubble(element, comp.sender || 'bot');
                this.container.appendChild(bubble);
            }
        });

        // Scroll automático al final
        this.container.scrollTop = this.container.scrollHeight;
    }

    createComponent(config) {
        let el = null;

        switch (config.type) {
            case 'chat':
                el = document.createElement('div');
                el.innerText = config.text;
                break;

            case 'property-card':
                el = document.createElement('property-card');
                el.title = config.title;
                el.price = config.price;
                el.location = config.location;
                el.imageUrl = config.image_url;
                break;

            case 'property-grid':
                el = document.createElement('property-grid');
                el.title = config.title;
                el.properties = config.properties;
                break;

            case 'action-menu':
                el = document.createElement('action-menu');
                el.options = config.options;
                break;

            case 'mortgage-calculator':
                el = document.createElement('mortgage-calculator');
                el.propertyPrice = config.property_price;
                el.defaultInterest = config.default_interest;
                break;

            case 'property-map':
                el = document.createElement('property-map');
                el.center = config.center;
                el.zoom = config.zoom;
                el.pois = config.pois;
                break;

            case 'photo-carousel':
                el = document.createElement('photo-carousel');
                el.images = config.images;
                el.showThumbnails = config.show_thumbnails;
                break;

            default:
                console.warn(`Componente desconocido: ${config.type}`);
        }

        return el;
    }

    showTyping() {
        const indicator = document.createElement('div');
        indicator.id = 'typing-indicator';
        indicator.className = 'typing-indicator';
        indicator.innerHTML = '<span></span><span></span><span></span>';
        this.container.appendChild(indicator);
        this.container.scrollTop = this.container.scrollHeight;
    }

    hideTyping() {
        const indicator = document.getElementById('typing-indicator');
        if (indicator) indicator.remove();
    }

    wrapInBubble(element, sender) {
        const wrapper = document.createElement('div');
        wrapper.className = `message-wrapper ${sender}`;

        const name = document.createElement('div');
        name.className = 'sender-name';
        name.innerText = sender === 'user' ? 'Tú' : this.botName;

        wrapper.appendChild(name);

        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';
        bubble.appendChild(element);
        wrapper.appendChild(bubble);

        return wrapper;
    }
}
```
### `services/web/chat-web-renderer/backend/app/main.py`

```
import os
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import httpx
from app.schemas.chat import InitRequest, InternalMemoryResetRequest
from app.schemas.internal_chat import InternalChatRequest
from app.schemas.ui import SDUIResponse

app = FastAPI(title="Chat Web Renderer")

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
    inference_url = os.getenv("INFERENCE_V2_URL", "http://inference-core-v2:8000").rstrip("/") + "/api/v2/health"
    retriever_url = os.getenv("RAG_RETRIEVER_V2_URL", "http://semantic-adapter-v2:8000").rstrip("/") + "/api/v2/health"

    result = {
        "status": "operational",
        "service": "chat-web-renderer-api",
        "dependencies": {
            "inference_core_v2": {"ok": False, "url": inference_url},
            "semantic_adapter_v2": {"ok": False, "url": retriever_url},
        },
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        for name, url in (
            ("inference_core_v2", inference_url),
            ("semantic_adapter_v2", retriever_url),
        ):
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

from app.core.inference_bridge import InferenceClient
from app.core.memory_reset import MemoryResetClient
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

    session_data = await session_manager.get_session_multichannel(
        client_id=client_id,
        channel=channel,
        channel_user_id=channel_user_id,
    )
    
    session_context = {
        "client_id": client_id,
        "conversation_id": str(req.conversation_id) if req.conversation_id else session_data.get("conversation_id"),
        "lead_id": session_data.get("lead_id"),
        "brand_project": req.brand_project or session_data.get("brand_project"),
        "channel": channel,
        "channel_user_id": channel_user_id,
    }
    
    if req.metadata:
        session_context.update(req.metadata)
    
    try:
        ai_response = await inference_client.chat(user_query=req.message_text, session=session_context)
        
        new_conversation_id = ai_response.get("conversation_id") or session_context.get("conversation_id")
        if new_conversation_id:
            await session_manager.upsert_session(
                client_id=client_id,
                channel=channel,
                channel_user_id=channel_user_id,
                data={
                    "conversation_id": new_conversation_id,
                    "brand_project": session_context.get("brand_project"),
                    "last_interaction": datetime.now(timezone.utc).isoformat(),
                },
            )
        
        vertical = await vertical_router.resolve_vertical_for_client_async(client_id)
        policy_handler = await vertical_router.get_handler_async(client_id, channel)
        if not policy_handler:
            raise HTTPException(status_code=500, detail="No renderer policy available for resolved vertical/channel")
        
        ai_text = ai_response.get("answer")
        if isinstance(ai_text, dict):
            ai_text = str(ai_text.get("text", str(ai_text)))
        elif not isinstance(ai_text, str):
            ai_text = str(ai_text) if ai_text is not None else ""
        ai_text = (ai_text or "").strip()
        extracted_components = []
        canonical_components = ai_response.get("components") or []
        if canonical_components:
            for component_payload in canonical_components:
                comp_type = component_payload.get("type")
                if comp_type == "property-card":
                    from app.schemas.ui import PropertyCard
                    extracted_components.append(PropertyCard(**component_payload))
                elif comp_type == "property-grid":
                    from app.schemas.ui import PropertyGrid
                    extracted_components.append(PropertyGrid(**component_payload))
                elif comp_type == "chat":
                    from app.schemas.ui import ChatMessage
                    extracted_components.append(ChatMessage(**component_payload))
        else:
            sources = ai_response.get("sources", [])
            if sources:
                property_cards = await transformer._extract_properties_from_sources(sources)
                if property_cards:
                    if len(property_cards) == 1:
                        extracted_components.append(property_cards[0])
                    else:
                        from app.schemas.ui import PropertyGrid
                        extracted_components.append(PropertyGrid(
                            title="Propiedades Relacionadas",
                            properties=property_cards
                        ))
        
        if "cita" in ai_text.lower() or "visita" in ai_text.lower():
            from app.schemas.ui import ActionMenu
            extracted_components.append(ActionMenu(
                options=[
                    {"label": "📅 Agendar Visita", "payload": "SCHEDULE_VISIT"},
                    {"label": "📞 Hablar con Asesor", "payload": "CALL_AGENT"}
                ]
            ))
        
        branding = await transformer._get_branding_for_client(
            client_id, 
            session_context.get("brand_project")
        )
        
        policy_response = policy_handler.build_response(
            ai_text=ai_text,
            components=extracted_components,
            session_id=str(new_conversation_id or "init"),
        )
        
        from app.schemas.ui import BaseComponent
        final_components = []
        for comp_data in policy_response.get("components", []):
            comp_type = comp_data.get("type")
            if comp_type == "chat":
                from app.schemas.ui import ChatMessage
                final_components.append(ChatMessage(**comp_data))
            elif comp_type == "property-card":
```
### `services/web/admin-console/backend/app/main.py`

```
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config.settings import settings
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.responses import JSONResponse
import logging

# Import Feature Modules
from app.dashboards.base_dash.router import router as base_dash_router
from app.dashboards.manager_workspace.router import router as manager_workspace_router
from app.dashboards.seller_workspace.router import router as seller_workspace_router
from app.modules.clients.router import router as clients_router
from app.modules.countries.router import router as countries_router
from app.modules.prompts.router import router as prompts_router
from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router
from app.modules.roles.router import router as roles_router
from app.modules.contacts.router import router as contacts_router
from app.modules.leads.router import router as leads_router
from app.modules.leads_v2.router import router as leads_v2_router
from app.modules.leads_v2.admin_scoring_router import router as admin_scoring_router
from app.modules.campaigns.router import router as campaigns_router
from app.modules.ai_library.router import router as ai_library_router
from app.modules.system_public_docs.router import router as system_public_docs_router
from app.modules.grid_presets.router import router as grid_presets_router

app = FastAPI(title="Web IAFirst Operational API")
logger = logging.getLogger(__name__)

cors_origins = settings.cors_allow_origins or ["*"]
allow_credentials = "*" not in cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={"detail": "Request Validation Error"},
    )

@app.exception_handler(ResponseValidationError)
async def response_validation_exception_handler(request, exc):
    logger.exception("Response contract validation failed", exc_info=exc)
    return JSONResponse(
        status_code=500, 
        content={"detail": "Response Contract Violation"},
    )

@app.get("/health")
async def health_check():
    return {"status": "operational", "version": "1.0"}

# Include Feature Routers
app.include_router(base_dash_router, tags=["Dashboard (Base)"]) # Root prefix for app-init
app.include_router(manager_workspace_router, prefix="/dashboard")
app.include_router(seller_workspace_router, prefix="/dashboard")
app.include_router(leads_router, prefix="/leads", tags=["Leads Operations"])
app.include_router(leads_v2_router, prefix="/leads_v2", tags=["Leads v2 Operations"])
app.include_router(admin_scoring_router)
app.include_router(campaigns_router, prefix="/campaigns", tags=["Campaigns Operations"])
app.include_router(ai_library_router, prefix="/ai-library", tags=["AI Library Management"])
app.include_router(system_public_docs_router)

app.include_router(clients_router, tags=["Clients"])
app.include_router(countries_router, tags=["Countries (System)"])
app.include_router(prompts_router, tags=["AI Prompts"])
app.include_router(auth_router) # Tags are defined inside the router
app.include_router(users_router)
app.include_router(roles_router)
app.include_router(contacts_router, tags=["Contacts"])
app.include_router(grid_presets_router)
```

## Inyección IA / Orquestadores

### `services/inference-stack-v2/inference-core-v2/app/services/scoring_orchestrator.py`

```
import logging
import asyncio
import re
import json
import time
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from decimal import Decimal
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_v2 import ChatV2Request, ChatV2Response, ScoreItemV2, ScorecardV2
from app.repositories.scoring_repository import ScoringRepository
from app.services.cache_service import cache_service
from app.services.hybrid_retriever import HybridRetriever
from app.services.scoring_job_service import ScoringJobService
from app.services.prompt_selector import prompt_selector
from app.services.realtor_turn_resolver import RealtorTurnResolver
from app.core.config import settings

logger = logging.getLogger("inference-core-v2.orchestrator")

MISCONFIGURED_CHAT_MESSAGE = "Lo siento, no puedo conversar, estoy desconfigurado."


class ScoringOrchestrator:
    """Orchestrator for v2 chat and scoring"""
    _PROPERTY_SEARCH_LIMIT = 4
    _conversation_locks: Dict[str, asyncio.Lock] = {}
    _scheduled_scoring_tasks: Dict[str, asyncio.Task] = {}
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.repo = ScoringRepository(db_session)
        self.job_service = ScoringJobService(self.repo)
        self.hybrid_retriever = HybridRetriever()
        self.realtor_turn_resolver = RealtorTurnResolver(
            db_session,
            search_limit=self._PROPERTY_SEARCH_LIMIT,
        )
        self._scoring_engine = None
        self._llm_client = None
        self._planner_prompt_cache: Dict[str, str] = {}
        self._property_intents = {
            "PROPERTY_SEARCH",
            "PROPERTY_INVENTORY",
            "PROPERTY_PRICE_RANGE",
            "RAG",
            "CLARIFICATION",
            "NONE",
        }

    _PROPERTY_PLANNER_GUARDRAILS = """
MANDATORY EXECUTION RULES (append as hard constraint, after any prompt text from DB):
- You must return only JSON. Do not include markdown, surrounding quotes, or explanatory text.
- If intent is PROPERTY_SEARCH / PROPERTY_INVENTORY / PROPERTY_PRICE_RANGE, SQL must be a single SELECT over lead_properties.
- Always include hard tenant scoping: client_id = '{client_id}'.
- Always include published price constraint: COALESCE(price, 0) > 0.
- For direct user location requests (includes "en X", "zona X", "en el"), generate a new SQL from scratch using current message and do not inherit prior filters.
- Use previous search only when user explicitly references prior results (examples: "de esas", "más baratas de esas", "las mismas").
- Prefer title, description, features->>'address' for textual filtering.
""".strip()
    
    @property
    def llm_client(self):
        """Lazy initialization of LLM client for chat"""
        if self._llm_client is None and settings.google_api_key:
            try:
                from google import genai
                self._llm_client = genai.Client(api_key=settings.google_api_key)
            except ImportError:
                logger.warning("google-genai not installed")
        return self._llm_client
    
    @property
    def scoring_engine(self):
        """Lazy initialization of scoring engine"""
        if self._scoring_engine is None and settings.google_api_key:
            try:
                from app.services.scoring_engine import scoring_engine
                self._scoring_engine = scoring_engine
            except ImportError:
                logger.warning("ScoringEngine not available - google-genai not installed")
        return self._scoring_engine
    
    async def get_active_scoring_model(
        self,
        client_id: UUID,
        vertical_id: int,
        scoring_model_id: Optional[UUID] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get active scoring model with caching"""
        cached = await cache_service.get_active_model(client_id)
        if cached:
            logger.debug(f"Cache hit for active model: client_id={client_id}")
            return cached
        
        model_data = await self.repo.get_active_scoring_model(
            vertical_id=vertical_id,
            scoring_model_id=scoring_model_id,
        )
        if not model_data:
            logger.warning(
                "No active model found: vertical=%s, scoring_model_id=%s",
                vertical_id,
                scoring_model_id,
            )
            return None
        
        await cache_service.set_active_model(client_id, model_data)
        return model_data

    async def resolve_vertical_for_client(self, client_id: UUID) -> Dict[str, Any]:
        """Resolve vertical context from tenant configuration."""
        vertical_ctx = await self.repo.get_client_vertical_context(client_id)
        if not vertical_ctx or not vertical_ctx.get("client_exists"):
            raise ValueError("CLIENT_NOT_FOUND")
        if vertical_ctx.get("vertical_id") is None:
            raise ValueError("TENANT_VERTICAL_NOT_CONFIGURED")
        if vertical_ctx.get("scoring_model_id") is None:
            raise ValueError("TENANT_SCORING_MODEL_NOT_CONFIGURED")
        return vertical_ctx

    async def get_or_create_prompt(
        self,
        model_data: Dict[str, Any],
        vertical_ctx: Dict[str, Any],
        client_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """Get active prompt - must be configured in database"""
        model_id = UUID(model_data["id"])
        if client_id:
            cached_prompt = await cache_service.get_scoring_prompt(client_id=client_id, model_id=model_id)
            if cached_prompt:
                return cached_prompt

        prompt_config = await self.repo.get_active_prompt(model_id)
        
        if not prompt_config:
            raise ValueError(f"No active prompt found for model {model_id} - please configure prompt in database")
        if client_id:
            await cache_service.set_scoring_prompt(client_id=client_id, model_id=model_id, prompt_data=prompt_config)
        return prompt_config

    @staticmethod
    def _resolve_channel_from_metadata(user_metadata: Optional[Dict[str, Any]]) -> str:
        if not isinstance(user_metadata, dict):
            return "web_html"
        raw = (
            user_metadata.get("channel")
            or user_metadata.get("channel_slug")
            or user_metadata.get("channel_type")
        )
        if not isinstance(raw, str):
            return "web_html"
        normalized = raw.strip().lower()
        return normalized if normalized in {"web_html", "meta_whatsapp", "meta_ig", "api"} else "web_html"

    def _select_chat_prompt_slug(
        self,
        vertical_ctx: Dict[str, Any],
        user_metadata: Optional[Dict[str, Any]],
    ) -> str:
        vertical = (vertical_ctx.get("vertical_slug") or "generic").strip().lower()
        channel = self._resolve_channel_from_metadata(user_metadata)
        return prompt_selector.get_prompt_slug(vertical=vertical, channel=channel)

    async def _resolve_client_chat_prompt(
        self,
        client_id: UUID,
        preferred_slug: str,
    ) -> tuple[str, Optional[str]]:
        slug = (preferred_slug or "primary_chat").strip() or "primary_chat"
        cached_prompt = await cache_service.get_client_chat_prompt(client_id=client_id, slug=slug)
        if cached_prompt:
            return slug, cached_prompt

        prompt_text = await self.repo.get_client_system_prompt(client_id, slug=slug)
        if prompt_text:
            await cache_service.set_client_chat_prompt(client_id=client_id, slug=slug, prompt_text=prompt_text)
            return slug, prompt_text
        if slug != "primary_chat":
            cached_fallback = await cache_service.get_client_chat_prompt(client_id=client_id, slug="primary_chat")
            if cached_fallback:
                logger.warning(
                    "Prompt slug '%s' not found for client_id=%s; using cached fallback slug 'primary_chat'",
                    slug,
                    client_id,
                )
                return "primary_chat", cached_fallback
            fallback_prompt = await self.repo.get_client_system_prompt(client_id, slug="primary_chat")
            if fallback_prompt:
                await cache_service.set_client_chat_prompt(
                    client_id=client_id,
                    slug="primary_chat",
                    prompt_text=fallback_prompt,
                )
                logger.warning(
                    "Prompt slug '%s' not found for client_id=%s; using fallback slug 'primary_chat'",
                    slug,
                    client_id,
                )
                return "primary_chat", fallback_prompt
        return slug, None

    async def _resolve_property_planner_prompt(self, client_id: UUID) -> Optional[str]:
        """
        Resolve the property-routing planner prompt (planner/system prompt) for a client.
        """
        primary_slug = "sql_planner_system"
        secondary_slug = "sql_planner"

        cached_prompt = await cache_service.get_client_chat_prompt(
            client_id=client_id,
            slug=primary_slug,
        )
        if cached_prompt:
            resolved = cached_prompt.replace("{search_limit}", str(self._PROPERTY_SEARCH_LIMIT)).replace(
                "{client_id}", str(client_id)
            )
```
### `services/inference-stack-v2/inference-core-v2/app/services/scoring_engine.py`

```
"""
Scoring Engine with Gemini LLM Integration

Implements real scoring using Gemini LLM with dynamic prompts from database.
"""

import logging
import json
import asyncio
import re
import time
from typing import Dict, Any, List, Optional, Tuple

from app.core.config import settings
from app.services.prompt_builder import PromptBuilder
from app.services.prompt_linter import PromptLinter

logger = logging.getLogger("inference-core-v2.scoring_engine")

DEFAULT_EXTRACTION_FIELDS = [
    # Intentionally empty: extraction field contract must come from DB prompt config.
]


class ScoringEngine:
    """
    Scoring engine that uses Gemini LLM for lead analysis.
    
    Features:
    - Dynamic prompts from database configuration
    - Structured JSON output
    - Retry logic with exponential backoff
    - Timeout handling
    """
    
    def __init__(self):
        self._client = None
        self._model_id = settings.llm_model
        self._temperature = settings.llm_temperature
        self._max_retries = max(1, int(settings.scoring_llm_max_retries or 1))
        configured_timeout = max(1, int(settings.scoring_llm_timeout_secs or 1))
        hard_timeout_cap = max(1, int(settings.scoring_llm_hard_timeout_secs or configured_timeout))
        self._timeout = min(configured_timeout, hard_timeout_cap)
        self._max_output_tokens = max(128, int(settings.scoring_llm_max_output_tokens or 512))
        if configured_timeout > self._timeout:
            logger.warning(
                "SCORING_LLM_TIMEOUT_CAPPED configured_timeout_secs=%s hard_cap_secs=%s effective_timeout_secs=%s",
                configured_timeout,
                hard_timeout_cap,
                self._timeout,
            )
    
    @property
    def client(self):
        """Lazy initialization of Gemini client"""
        if self._client is None:
            if not settings.google_api_key:
                raise ValueError("GOOGLE_API_KEY not configured")
            
            try:
                from google import genai
                self._client = genai.Client(api_key=settings.google_api_key)
            except ImportError:
                raise ImportError("google-genai package not installed. Run: pip install google-genai")
        
        return self._client
    
    async def analyze_conversation(
        self,
        conversation_text: str,
        model_config: Dict[str, Any],
        prompt_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Analyze a conversation and return scoring results.
        
        Args:
            conversation_text: Full conversation text to analyze
            model_config: Model configuration with criteria and bands
            prompt_config: Prompt configuration with template and extraction_schema
        
        Returns:
            Dict with:
            - scores: Dict[criterion_key, score]
            - explanations: Dict[criterion_key, explanation]
            - extraction_result: Dict with extracted data
            - reasoning: str
            - prompt_snapshot: str (the actual prompt used)
        """
        analysis_start = time.perf_counter()
        vertical_name = model_config.get("vertical_name", "leads")
        vertical_slug = model_config.get("vertical_slug", "")
        criteria = model_config.get("criteria", [])
        bands = self._extract_bands_from_criteria(criteria)
        
        prompt_template = prompt_config.get("prompt_template")
        if not prompt_template:
            raise ValueError("No prompt_template found in prompt_config - prompt must be configured in database")
        lint = PromptLinter().validate_template(prompt_template)
        prompt_template = lint["normalized_template"]
        
        builder = PromptBuilder(custom_template=prompt_template)
        schema_config = self._parse_extraction_schema_config(prompt_config.get("extraction_schema"))
        extraction_fields = self._merge_extraction_fields(
            builder.get_extraction_fields_from_prompt(),
            schema_config["extraction_fields"],
        )
        extraction_fields = self._merge_extraction_fields(
            extraction_fields,
            DEFAULT_EXTRACTION_FIELDS,
        )
        
        system_prompt = builder.build_prompt(
            vertical_name=vertical_name,
            criteria=criteria,
            bands=bands,
            extraction_fields=extraction_fields,
            business_domain=model_config.get("business_domain"),
            locale=model_config.get("locale"),
            timestamp_utc=model_config.get("timestamp_utc")
        )
        
        response_schema = builder.build_response_schema(
            criteria,
            extraction_fields,
            slot_hints_schema=schema_config["slot_hints_schema"],
            response_schema_override=schema_config["response_schema_override"],
        )
        try:
            schema_chars = len(json.dumps(response_schema, ensure_ascii=False, default=str))
        except Exception:
            schema_chars = 0
        logger.info(
            "SCORING_INPUT model=%s criteria=%s conversation_chars=%s conversation_lines=%s prompt_chars=%s schema_chars=%s timeout_secs=%s max_output_tokens=%s",
            self._model_id,
            len(criteria),
            len(conversation_text or ""),
            len((conversation_text or "").splitlines()),
            len(system_prompt or ""),
            schema_chars,
            self._timeout,
            self._max_output_tokens,
        )

        used_fallback = False
        llm_meta = {
            "json_valid": False,
            "response_chars": 0,
            "llm_latency_ms": None,
        }
        result: Dict[str, Any] = {}
        try:
            llm_response = await self._call_gemini(
                system_prompt=system_prompt,
                conversation_text=conversation_text,
                response_schema=response_schema
            )
            result = llm_response.get("payload", {}) if isinstance(llm_response, dict) else {}
            llm_meta = llm_response.get("meta", llm_meta) if isinstance(llm_response, dict) else llm_meta
        except Exception as exc:
            logger.error("LLM scoring unavailable, using conservative fallback: %s", exc)
            used_fallback = True
        
        extraction_result: Dict[str, Any] = {}
        slot_state: Dict[str, Any] = {}
        confidence = None
        if isinstance(result.get("slot_hints"), dict):
            slot_state = result.get("slot_hints") or {}
        
        extracted_data_container = result.get("extracted_data", {})
        if not isinstance(extracted_data_container, dict):
            extracted_data_container = {}

        for field in extraction_fields:
            key = field.get("key")
            if not key or key not in extracted_data_container:
                continue
            value = extracted_data_container[key]
            if self._is_meaningful_value(value):
                extraction_result[key] = value

        extraction_result = self._enrich_extraction_from_text(conversation_text, extraction_result)
        scores, explanations, missing_score_keys = self._extract_scores_and_explanations(
            criteria=criteria,
            payload=result,
            missing_score_policy=schema_config.get("missing_score_policy"),
        )
        if missing_score_keys:
            used_fallback = True
            logger.warning(
                "LLM payload missing/invalid scores for criteria=%s; conservative defaults applied",
                ",".join(missing_score_keys),
            )
        
        if "confidence" in result and result["confidence"] is not None:
            parsed_conf = self._coerce_float(result["confidence"])
            if parsed_conf is not None:
                confidence = max(0.0, min(1.0, parsed_conf))

        reasoning_parts = []
        llm_reasoning = (result.get("reasoning") or "").strip() if isinstance(result, dict) else ""
        if llm_reasoning:
            reasoning_parts.append(llm_reasoning)
        elif used_fallback:
            reasoning_parts.append("Scoring conservador por ausencia de salida valida del LLM.")
        if missing_score_keys:
            reasoning_parts.append(
                f"Criteria con default conservador: {', '.join(missing_score_keys)}."
            )
        final_reasoning = " | ".join(reasoning_parts)

        total_ms = (time.perf_counter() - analysis_start) * 1000.0
        logger.info(
            "SCORING_OUTPUT duration_ms=%.1f fallback=%s scores=%s extraction_fields=%s slots=%s json_valid=%s response_chars=%s",
            total_ms,
            used_fallback,
            len(scores),
            len(extraction_result),
            len(slot_state),
            llm_meta.get("json_valid"),
```
### `services/inference-stack-v2/inference-core-v2/app/services/prompt_builder.py`

```
"""
Prompt Builder for Dynamic Scoring

Builds prompts dynamically from database configuration (criteria, bands, extraction schema).
"""

import logging
from typing import Dict, Any, List, Optional

from app.services.prompt_linter import PromptLinter

logger = logging.getLogger("inference-core-v2.prompt_builder")


class PromptBuilder:
    """Builds dynamic prompts for scoring based on model configuration"""
    
    def __init__(self, custom_template: str):
        self.system_template = PromptLinter.normalize_template(custom_template)
    
    def build_prompt(
        self,
        vertical_name: str,
        criteria: List[Dict[str, Any]],
        bands: List[Dict[str, Any]],
        extraction_fields: Optional[List[Dict[str, Any]]] = None,
        business_domain: Optional[str] = None,
        locale: Optional[str] = None,
        timestamp_utc: Optional[str] = None
    ) -> str:
        """
        Build the complete system prompt for scoring.
        
        Args:
            vertical_name: Name of the vertical (e.g., "Healthcare", "Real Estate")
            criteria: List of criteria from lead_scoring_criteria
            bands: List of bands from lead_scoring_bands (grouped by criterion)
            extraction_fields: Optional list of fields to extract from extraction_schema
            business_domain: Optional business domain for context
            locale: Optional locale
            timestamp_utc: Optional timestamp
        
        Returns:
            Complete system prompt string
        """
        criteria_text = self._format_criteria(criteria, bands)
        extraction_text = self._format_extraction_fields(extraction_fields)
        
        format_kwargs = {
            "vertical_name": vertical_name,
            "criteria_text": criteria_text,
            "extraction_text": extraction_text,
        }
        
        if business_domain is not None:
            format_kwargs["business_domain"] = business_domain
        else:
            format_kwargs["business_domain"] = "null"
            
        if locale is not None:
            format_kwargs["locale"] = locale
        else:
            format_kwargs["locale"] = "null"
            
        if timestamp_utc is not None:
            format_kwargs["timestamp_utc"] = timestamp_utc
        else:
            format_kwargs["timestamp_utc"] = "null"
        
        try:
            prompt = self.system_template.format(**format_kwargs)
        except KeyError as e:
            missing_key = str(e).strip("'")
            # The template has literal { and } that are not placeholders
            # Escape them by doubling: { -> {{, } -> }}
            escaped_template = self.system_template.replace("{", "{{").replace("}", "}}")
            # Now unescape the placeholders we want to keep
            for key in format_kwargs:
                escaped_template = escaped_template.replace("{{" + key + "}}", "{" + key + "}")
            prompt = escaped_template.format(**format_kwargs)
        
        return prompt
    
    def _format_criteria(
        self,
        criteria: List[Dict[str, Any]],
        bands: List[Dict[str, Any]]
    ) -> str:
        """Format criteria with their bands for the prompt"""
        lines = []
        
        for i, criterion in enumerate(criteria, 1):
            criterion_key = criterion.get("criterion_key", "unknown")
            label = criterion.get("label", criterion_key)
            min_score = float(criterion.get("min_score", 0))
            max_score = float(criterion.get("max_score", 10))
            weight = float(criterion.get("weight", 1.0))
            
            lines.append(f"\n{i}. {criterion_key} ({min_score:.0f}-{max_score:.0f}): {label}")
            lines.append(f"   Peso: {weight:.1f}")
            
            criterion_bands = [
                b for b in bands 
                if b.get("criterion_id") == criterion.get("id") or b.get("criterion_id") == str(criterion.get("id"))
            ]
            
            if criterion_bands:
                lines.append("   Bandas:")
                for band in sorted(criterion_bands, key=lambda x: float(x.get("min_score", 0))):
                    band_key = band.get("band_key", "unknown")
                    band_label = band.get("label", band_key)
                    band_min = float(band.get("min_score", 0))
                    band_max = float(band.get("max_score", 10))
                    lines.append(f"   - {band_key} ({band_min:.0f}-{band_max:.0f}): {band_label}")
        
        return "\n".join(lines)
    
    def get_extraction_fields_from_prompt(self) -> List[Dict[str, Any]]:
        """Extract field names from JSON schema in prompt template"""
        import re
        
        fields = []
        
        extracted_data_match = re.search(
            r'"extracted_data"\s*:\s*\{(.+?)\n\s*\}',
            self.system_template,
            re.DOTALL
        )
        
        if extracted_data_match:
            extracted_data_block = extracted_data_match.group(1)
            field_matches = re.findall(r'"(\w+)"\s*:', extracted_data_block)
            
            for field_name in field_matches:
                fields.append({"key": field_name, "type": "string"})
        
        logger.info(f"Extracted fields from prompt: {fields}")
        return fields
    
    def _format_extraction_fields(
        self,
        extraction_fields: Optional[List[Dict[str, Any]]]
    ) -> str:
        """Format extraction fields for the prompt - now empty since they are in the DB prompt"""
        return ""
    
    def build_response_schema(
        self,
        criteria: List[Dict[str, Any]],
        extraction_fields: Optional[List[Dict[str, Any]]] = None,
        slot_hints_schema: Optional[Dict[str, Any]] = None,
        response_schema_override: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Build JSON schema for structured LLM response.
        
        This schema is used to validate the LLM response and ensure
        it contains all expected fields.
        
        Args:
            criteria: List of criteria from lead_scoring_criteria
            extraction_fields: Optional list of fields to extract
        
        Returns:
            JSON schema dict for the response
        """
        if isinstance(response_schema_override, dict) and response_schema_override:
            schema = dict(response_schema_override)
            schema.setdefault("type", "object")
            return schema

        extraction_properties = {}
        if extraction_fields:
            for field in extraction_fields:
                key = field.get("key")
                field_type = field.get("type", "string")
                description = field.get("description", "")
                
                if key:
                    extraction_properties[key] = {
                        "type": field_type if field_type in ["string", "number", "boolean", "integer"] else "string",
                        "description": description,
                        "nullable": True
                    }

        score_properties: Dict[str, Any] = {}
        required_scores: List[str] = []
        for criterion in criteria or []:
            criterion_key = str(criterion.get("criterion_key") or "").strip()
            if not criterion_key:
                continue
            min_score = float(criterion.get("min_score", 0))
            max_score = float(criterion.get("max_score", 10))
            score_properties[criterion_key] = {
                "type": "number",
                "minimum": min_score,
                "maximum": max_score,
            }
            required_scores.append(criterion_key)

        slot_hints_object_schema = slot_hints_schema if isinstance(slot_hints_schema, dict) else {
            "type": "object",
        }
        scores_schema: Dict[str, Any] = {
            "type": "object",
            "properties": score_properties,
        }
        if required_scores:
            scores_schema["required"] = required_scores
        
        properties = {
            "reasoning": {
                "type": "string",
                "description": "Brief explanation of the scoring decision"
            },
            "scores": scores_schema,
            "extracted_data": {
                "type": "object",
                "properties": extraction_properties,
                "description": "Extracted data from conversation",
```
### `services/inference-stack-v2/inference-core-v2/app/repositories/scoring_repository.py`

```
import logging
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger("inference-core-v2.repositories")


class ScoringRepository:
    """Repository for scoring v2 database operations - uses raw SQL"""
    
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_conversation_messages(
        self,
        conversation_id: UUID,
        client_id: UUID,
        max_messages: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Returns tenant-scoped conversation messages for LLM context.
        """
        query = text("""
            SELECT lc.messages
            FROM lead_conversations lc
            JOIN lead_leads ll ON ll.id = lc.lead_id
            WHERE lc.conversation_id = :conversation_id
              AND ll.client_id = :client_id
            LIMIT 1
        """)
        result = await self.session.execute(
            query,
            {
                "conversation_id": str(conversation_id),
                "client_id": str(client_id),
            },
        )
        row = result.mappings().first()
        if not row:
            return []

        messages = row.get("messages") or []
        if isinstance(messages, str):
            try:
                messages = json.loads(messages)
            except Exception:
                logger.warning("Invalid JSON in lead_conversations.messages for %s", conversation_id)
                return []

        if not isinstance(messages, list):
            return []

        if max_messages <= 0:
            return []
        return messages[-max_messages:]

    async def get_latest_lead_messages(
        self,
        lead_id: UUID,
        max_messages: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Fallback: returns latest conversation messages by lead when conversation lookup misses.
        """
        query = text("""
            SELECT lc.messages
            FROM lead_conversations lc
            WHERE lc.lead_id = :lead_id
            ORDER BY lc.updated_at DESC NULLS LAST, lc.created_at DESC
            LIMIT 1
        """)
        result = await self.session.execute(query, {"lead_id": str(lead_id)})
        row = result.mappings().first()
        if not row:
            return []

        messages = row.get("messages") or []
        if isinstance(messages, str):
            try:
                messages = json.loads(messages)
            except Exception:
                logger.warning("Invalid JSON in lead_conversations.messages for lead %s", lead_id)
                return []

        if not isinstance(messages, list):
            return []

        if max_messages <= 0:
            return []
        return messages[-max_messages:]

    async def get_conversation_metrics(
        self,
        conversation_id: UUID,
        client_id: UUID,
    ) -> Optional[Dict[str, Any]]:
        """
        Returns tenant-scoped metrics for a conversation.
        """
        query = text("""
            SELECT
                lc.lead_id,
                lc.total_messages,
                lc.bot_messages,
                lc.lead_messages,
                lc.last_message_at
            FROM lead_conversations lc
            JOIN lead_leads ll ON ll.id = lc.lead_id
            WHERE lc.conversation_id = :conversation_id
              AND ll.client_id = :client_id
            LIMIT 1
        """)
        result = await self.session.execute(
            query,
            {
                "conversation_id": str(conversation_id),
                "client_id": str(client_id),
            },
        )
        row = result.mappings().first()
        if not row:
            return None
        return {
            "lead_id": str(row.get("lead_id")) if row.get("lead_id") else None,
            "total_messages": row.get("total_messages", 0),
            "bot_messages": row.get("bot_messages", 0),
            "lead_messages": row.get("lead_messages", 0),
            "last_message_at": row.get("last_message_at").isoformat() if row.get("last_message_at") else None,
        }

    async def get_lead_snapshot(
        self,
        lead_id: UUID,
        client_id: UUID,
    ) -> Optional[Dict[str, Any]]:
        """
        Returns tenant-scoped lead snapshot for structured RAG context.
        """
        query = text("""
            SELECT
                id,
                full_name,
                email,
                phone,
                source_id,
                current_scorecard_id,
                created_at
            FROM lead_leads
            WHERE id = :lead_id
              AND client_id = :client_id
            LIMIT 1
        """)
        result = await self.session.execute(
            query,
            {
                "lead_id": str(lead_id),
                "client_id": str(client_id),
            },
        )
        row = result.mappings().first()
        if not row:
            return None
        return {
            "id": str(row.get("id")),
            "full_name": row.get("full_name"),
            "email": row.get("email"),
            "phone": row.get("phone"),
            "source_id": row.get("source_id"),
            "current_scorecard_id": str(row.get("current_scorecard_id")) if row.get("current_scorecard_id") else None,
            "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
        }

    async def delete_conversations_by_client(self, client_id: UUID) -> int:
        """
        Deletes conversation rows for a tenant and returns deleted count.
        """
        stmt = text("""
            DELETE FROM lead_conversations lc
            USING lead_leads ll
            WHERE lc.lead_id = ll.id
              AND ll.client_id = :client_id
        """)
        result = await self.session.execute(stmt, {"client_id": str(client_id)})
        await self.session.commit()
        return result.rowcount or 0

    async def get_or_create_conversation(
        self,
        lead_id: UUID,
        conversation_id: UUID,
        platform: str = "webchat"
    ) -> Dict[str, Any]:
        """Get or create a conversation"""
        # Try to find existing conversation
        query = text("""
            SELECT id, lead_id, platform, conversation_id, messages, total_messages, context_snapshot
            FROM lead_conversations 
            WHERE lead_id = :lead_id 
              AND conversation_id = :conversation_id
            LIMIT 1
        """)
        result = await self.session.execute(query, {
            "lead_id": str(lead_id),
            "conversation_id": str(conversation_id)
        })
        row = result.mappings().first()
        
        if row:
            return dict(row)
        
        # Create new conversation
        insert_query = text("""
            INSERT INTO lead_conversations (lead_id, platform, conversation_id, messages, total_messages, bot_messages, lead_messages, context_snapshot)
            VALUES (:lead_id, :platform, :conversation_id, '[]'::jsonb, 0, 0, 0, '{}'::jsonb)
            RETURNING id, lead_id, platform, conversation_id, messages, total_messages, context_snapshot
        """)
```
### `services/web/chat-web-renderer/backend/app/core/inference_bridge.py`

```
import os
import httpx
import logging
from typing import Dict, Any

# Logger config
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("inference_bridge")


class InferenceClient:
    """
    El 'Cable' que conecta el Bridge con el Cerebro de IA (Inference Core).
    Se encarga de enviar el payload con metadatos y recibir la respuesta plana.
    Opera exclusivamente con Inference Core V2.
    """

    def __init__(self):
        self.timeout = int(os.getenv("INFERENCE_TIMEOUT", 60))
        self.connect_timeout = float(os.getenv("INFERENCE_CONNECT_TIMEOUT", 5))
        self.default_client_id = os.getenv("DEFAULT_CLIENT_ID", "")
        self.base_url = os.getenv("INFERENCE_V2_URL", "http://inference-core-v2:8000") + "/api/v2"
        logger.info(f"🔌 InferenceClient conectado a Inference Core V2: {self.base_url} (Timeout: {self.timeout}s)")

    async def chat(self, user_query: str, session: Dict[str, Any]) -> Dict[str, Any]:
        """
        Envía un mensaje al Core AI.
        
        :param user_query: El texto que escribió el usuario.
        :param session: Diccionario con metadatos de la sesión (conversation_id, lead_id, etc.)
        """
        return await self._chat_v2(user_query, session)

    async def _chat_v2(self, user_query: str, session: Dict[str, Any]) -> Dict[str, Any]:
        """
        Envía un mensaje al Inference Core V2.
        """
        url = f"{self.base_url}/chat"
        
        user_metadata = {
            "lead_id": session.get("lead_id"),
            "brand_project": session.get("brand_project"),
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
            "conversationId": session.get("conversation_id"),
            "userMetadata": user_metadata if user_metadata else None
        }
        payload = {k: v for k, v in payload.items() if v is not None}

        try:
            timeout = httpx.Timeout(timeout=self.timeout, connect=self.connect_timeout)
            async with httpx.AsyncClient(timeout=timeout) as client:
                logger.info(f"📤 Enviando mensaje al Core V2: {user_query[:50]}...")
                response = await client.post(url, json=payload)
                response.raise_for_status()
                
                data = response.json()
                logger.info("📥 Respuesta recibida del Core V2.")
                return self._normalize_v2_response(data)

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Error HTTP del Core V2: {e.response.status_code} - {e.response.text}")
            raise ValueError(f"Error del servidor de IA: {e.response.status_code}")

        except httpx.TimeoutException as e:
            logger.error(f"❌ Timeout con Core V2 ({self.timeout}s): {repr(e)}")
            raise TimeoutError("El servicio de IA tardó demasiado en responder.")

        except httpx.RequestError as e:
            logger.error(f"❌ Error de conexión con el Core V2: {repr(e)}")
            raise ConnectionError("No se pudo conectar con el cerebro de IA V2.")

        except Exception as e:
            logger.error(f"❌ Error inesperado en el Bridge V2: {str(e)}")
            raise

    def _normalize_v2_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normaliza la respuesta de V2 al formato esperado por el transformer.
        """
        normalized = {
            "answer": data.get("answer", ""),
            "sources": data.get("sources", []),
            "components": data.get("components", []),
            "intent": data.get("intent"),
            "conversation_id": str(data.get("conversationId", data.get("conversation_id", ""))),
        }
        
        if "propertyTurn" in data or "property_turn" in data:
            normalized["property_turn"] = data.get("property_turn") or data.get("propertyTurn")
        
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
        
        return normalized
```

## ETL + Storage (R2/Staging)

### `services/etl-docs/main.py`

```
import logging
import os
import uuid
from uuid import UUID

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from redis import Redis
from rq import Queue
from rq.job import Job

from src.ETL_DOCS.worker_task import process_document_task
from src.shared.file_manager import FileManager
from src.shared.memory_reset import reset_client_memory
from src.shared.vector_store import VectorStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ETL Docs API", version="1.0.0")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
DOCS_QUEUE = os.getenv("DOCS_QUEUE_NAME", "docs")

redis_conn = Redis.from_url(REDIS_URL)
queue = Queue(DOCS_QUEUE, connection=redis_conn)


@app.get("/")
def root():
    return {"status": "ETL Docs API Running"}


@app.post("/documents/upload", status_code=202)
async def upload_document(
    file: UploadFile = File(...),
    client_id: str = Form(...),
    content_id: str | None = Form(None),
    access_level: str = Form("private"),
    category: str = Form("knowledge_base"),
):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only application/pdf is accepted")

    try:
        client_uuid = UUID(client_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid client_id UUID") from exc

    generated_content_id = content_id or f"doc_{uuid.uuid4()}"

    if FileManager.check_file_exists(client_uuid, file.filename):
        raise HTTPException(status_code=409, detail=f"File '{file.filename}' already exists")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    file_path = FileManager.save_upload(file_bytes, file.filename, client_uuid)

    vector_store = VectorStore()
    vector_store.register_document_in_db(
        client_id=client_uuid,
        filename=file.filename,
        storage_path=file_path,
        content_id=generated_content_id,
        access_level=access_level,
        category=category,
    )

    job = queue.enqueue(
        process_document_task,
        file_path,
        client_uuid,
        generated_content_id,
        file.filename,
        access_level,
        category,
        job_id=f"job_{generated_content_id}",
    )

    return {
        "status": "QUEUED",
        "job_id": job.id,
        "content_id": generated_content_id,
        "filename": file.filename,
        "queue_position": max(queue.count, 1),
    }


@app.get("/documents/list/{client_id}")
def list_documents(client_id: str):
    try:
        client_uuid = UUID(client_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid client_id UUID") from exc

    vector_store = VectorStore()
    docs = vector_store.list_documents(client_uuid)
    return {
        "status": "success",
        "client_id": client_id,
        "count": len(docs),
        "documents": docs,
    }


@app.get("/documents/jobs/{job_id}")
def get_job_status(job_id: str):
    try:
        job = Job.fetch(job_id, connection=redis_conn)
    except Exception:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "job_id": job.id,
        "status": job.get_status(refresh=True),
        "result": job.result if job.is_finished else None,
    }


@app.delete("/documents/{client_id}/{content_id}")
def delete_document(client_id: str, content_id: str):
    try:
        client_uuid = UUID(client_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid client_id UUID") from exc

    vector_store = VectorStore()
    filename = vector_store.delete_document(client_uuid, content_id)
    if filename:
        FileManager.delete_document(client_uuid, filename)
    reset_client_memory(str(client_uuid), reason="document_deleted")

    return {"status": "success", "content_id": content_id}


@app.delete("/documents/client/{client_id}")
def delete_client_documents(client_id: str):
    try:
        client_uuid = UUID(client_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid client_id UUID") from exc

    vector_store = VectorStore()
    vector_store.delete_client(client_uuid)
    FileManager.delete_client_folder(client_uuid)
    reset_client_memory(str(client_uuid), reason="client_knowledge_purged")
    return {"status": "success", "client_id": client_id}
```
### `services/etl-docs/src/shared/file_manager.py`

```

import os
import shutil
import logging
from pathlib import Path
from uuid import UUID

# Configuración básica de logging
logger = logging.getLogger(__name__)

# Definir la raíz del almacenamiento. 
# En producción Docker, /app/data/storage está montado al disco grande.
STORAGE_ROOT = Path(os.getenv("PATH_STORAGE", "/app/data/storage"))

class FileManager:
    """
    Gestor centralizado de archivos físicos en disco.
    Asegura que todos los archivos se guarden bajo la estructura:
    /app/data/storage/documents/{client_id}/{filename}
    """

    @staticmethod
    def _get_client_dir(client_id: UUID) -> Path:
        return STORAGE_ROOT / "documents" / str(client_id)

    @classmethod
    def check_file_exists(cls, client_id: UUID, filename: str) -> bool:
        """Verifica si un archivo ya existe en el directorio del cliente."""
        file_path = cls._get_client_dir(client_id) / filename
        return file_path.exists()

    @classmethod
    def save_upload(cls, file_bytes: bytes, filename: str, client_id: UUID) -> str:
        """
        Guarda un archivo subido en el directorio del cliente.
        Retorna la ruta absoluta del archivo guardado.
        """
        client_dir = cls._get_client_dir(client_id)
        
        # 1. Asegurar que existe el directorio
        try:
            client_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Error creando directorio {client_dir}: {e}")
            raise IOError(f"No se pudo crear directorio para cliente {client_id}")

        # 2. Ruta final
        file_path = client_dir / filename
        
        # 3. Escribir bytes
        try:
            with open(file_path, "wb") as f:
                f.write(file_bytes)
            logger.info(f"Archivo guardado: {file_path}")
            return str(file_path)
        except Exception as e:
            logger.error(f"Error escribiendo archivo {file_path}: {e}")
            raise IOError(f"Fallo al escribir archivo en disco")

    @classmethod
    def delete_document(cls, client_id: UUID, filename: str) -> bool:
        """
        Borra un archivo específico de un cliente.
        """
        file_path = cls._get_client_dir(client_id) / filename
        if file_path.exists():
            try:
                os.remove(file_path)
                logger.info(f"Archivo eliminado: {file_path}")
                return True
            except OSError as e:
                logger.error(f"Error borrando archivo {file_path}: {e}")
                return False
        else:
            logger.warning(f"Intento de borrar archivo inexistente: {file_path}")
            return False

    @classmethod
    def delete_client_folder(cls, client_id: UUID) -> bool:
        """
        Elimina recursivamente todo el directorio de un cliente.
        Usar con precaución (Baja de Cliente).
        """
        client_dir = cls._get_client_dir(client_id)
        if client_dir.exists():
            try:
                shutil.rmtree(client_dir)
                logger.info(f"Directorio de cliente eliminado completamente: {client_dir}")
                return True
            except OSError as e:
                logger.error(f"Error borrando directorio cliente {client_dir}: {e}")
                return False
        return True # Si no existe, "ya estaba borrado"

    @classmethod
    def list_files(cls, client_id: UUID) -> list[str]:
        """Listar archivos de un cliente"""
        client_dir = cls._get_client_dir(client_id)
        if not client_dir.exists():
            return []
        return [f.name for f in client_dir.iterdir() if f.is_file()]
```
### `services/etl-docs/src/shared/vector_store.py`

```

import os
import json
import logging
import hashlib
from typing import Optional, List, Dict, Any
import hashlib
from typing import Optional, List, Dict, Any
import uuid
from uuid import UUID

import psycopg2
from psycopg2.extras import Json
from google import genai
from google.genai import types
from dotenv import load_dotenv

from src.shared.schemas import CanonicalDocument

# Cargar configuración
load_dotenv()
logger = logging.getLogger(__name__)

# Configurar Google GenAI Client (nuevo SDK)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=GOOGLE_API_KEY)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/gemini-embedding-001")

# Configurar DB
DB_HOST = os.getenv("DB_HOST", "192.168.0.37")
DB_NAME = os.getenv("DB_NAME", "agentic") # Usamos la variable de entorno, default agentic
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")

class VectorStore:
    def __init__(self):
        self.conn = None
        self._connect()

    def _connect(self):
        """Establece conexión con la base de datos"""
        try:
            self.conn = psycopg2.connect(
                host=DB_HOST,
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASS
            )
            # Habilitar autocommit para operaciones simples
            self.conn.autocommit = True
        except Exception as e:
            logger.error(f"Error conectando a DB Semantic: {e}")
            raise

    def get_embedding(self, text: str) -> List[float]:
        """Genera embedding usando Google Gemini (SDK moderno)"""
        try:
            result = client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=text,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT"
                )
            )
            return result.embeddings[0].values
        except Exception as e:
            logger.error(f"Error generando embedding con Google AI: {e}")
            raise

    def calculate_hash(self, content: str) -> str:
        """Calcula SHA-256 del contenido de texto"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def register_document_in_db(self, client_id: UUID, filename: str, storage_path: str, content_id: str, access_level: str = 'shared', category: str = 'General'):
        """Crea el registro inicial en ai_knowledge_documents como PENDING."""
        if not self.conn or self.conn.closed: self._connect()
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO ai_knowledge_documents 
                (client_id, filename, storage_path, sync_status, content_hash, access_level, category, created_at)
                VALUES (%s, %s, %s, 'PENDING', %s, %s, %s, NOW())
            """, (str(client_id), filename, storage_path, content_id, access_level, category))

    def update_sync_status(self, client_id: UUID, content_id: str, status: str, error_message: str = None):
        """Actualiza el estado de sincronización y el hash final."""
        if not self.conn or self.conn.closed: self._connect()
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE ai_knowledge_documents 
                SET sync_status = %s, 
                    error_message = %s,
                    last_synced_at = NOW()
                WHERE client_id = %s AND content_hash = %s
            """, (status, error_message, str(client_id), content_id))

    def list_documents(self, client_id: UUID) -> List[Dict[str, Any]]:
        """Lista todos los documentos registrados para un cliente."""
        if not self.conn or self.conn.closed: self._connect()
        from psycopg2.extras import RealDictCursor
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, filename, sync_status, last_synced_at, created_at, content_hash as content_id, error_message, access_level, category
                FROM ai_knowledge_documents 
                WHERE client_id = %s
                ORDER BY created_at DESC
            """, (str(client_id),))
            return cur.fetchall()

    def upsert_document(self, doc: CanonicalDocument) -> bool:
        """
        Inserta o actualiza un documento en la tabla semantic_items.
        Lógica:
        1. Verifica hash existente para este content_id y client_id.
        2. Si el hash es igual -> SKIP (Idempotencia).
        3. Si cambió o es nuevo -> Generar Embedding -> UPSERT.
        """
        if not self.conn or self.conn.closed:
            self._connect()

        try:
            with self.conn.cursor() as cur:
                # 1. Verificar existencia y hash
                cur.execute("""
                    SELECT id, hash FROM ai_vectors 
                    WHERE client_id = %s AND content_id = %s
                """, (str(doc.metadata.client_id), doc.content_id))
                
                row = cur.fetchone()
                existing_id = row[0] if row else None
                existing_hash = row[1] if row else None
                # Calcular hash actual
                current_hash = self.calculate_hash(doc.body_content)
                
                # LOGIC CHECK: ¿Necesitamos actualizar?
                if existing_hash == current_hash:
                    logger.info(f"SKIP Upsert: El documento {doc.content_id} no ha cambiado.")
                    return True # Exitoso (porque ya estaba bien)

                logger.info(f"Procesando Upsert para {doc.content_id}...")
                
                # 2. Generar Embedding (Solo si es nuevo o cambió)
                embedding_vector = self.get_embedding(doc.body_content)

                # Asegurar que metadata sea JSON válido
                # Convertir modelo Pydantic a dict compatible con JSON (UUIDs a string)
                if hasattr(doc.metadata, "model_dump"):
                    meta_dict = doc.metadata.model_dump(mode='json')
                else:
                    meta_dict = doc.metadata
                meta_json = Json(meta_dict)

                # 3. UPSERT Manual (Evitar ON CONFLICT si falta índice compuesto)
                if existing_id:
                    # UPDATE Exitsente
                    sql = """
                        UPDATE ai_vectors 
                        SET body_content = %s,
                            title = %s,
                            metadata = %s,
                            hash = %s,
                            embedding = %s,
                            updated_at = NOW()
                        WHERE id = %s;
                    """
                    cur.execute(sql, (
                        doc.body_content,
                        doc.title,
                        meta_json,
                        current_hash,
                        embedding_vector,
                        existing_id
                    ))
                    logger.info(f"Update realizado para: {doc.content_id}")
                else:
                    # INSERT Nuevo
                    try:
                        sql = """
                            INSERT INTO ai_vectors 
                            (id, content_id, client_id, source, title, body_content, metadata, hash, embedding, updated_at, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW());
                        """
                        new_id = str(uuid.uuid4())
                        cur.execute(sql, (
                            new_id,
                            doc.content_id,
                            str(doc.metadata.client_id),
                            doc.source,
                            doc.title,
                            doc.body_content,
                            meta_json,
                            current_hash,
                            embedding_vector
                        ))
                        logger.info(f"Insert realizado para: {doc.content_id} (ID: {new_id})")
                    except psycopg2.errors.UniqueViolation as e:
                        # Si falla por hash key, significa que OTRO documento tiene exactamente el mismo contenido
                        # Esto es la validación DB de idempotencia. 
                        logger.warning(f"Hash duplicado detectado en DB para {doc.content_id}. El contenido ya existe bajo otro ID. {e}")
                        # En este modelo de negocio, decidimos: ¿Permitimos duplicados de contenido con diferente ID?
                        # Si la tabla tiene UNIQUE(hash), NO se permite.
                        # Retornamos True asumiendo que "ya está preservado el conocimiento".
                        self.conn.rollback() # Resetear transacción fallida
                        return True

                return True

        except Exception as e:
            logger.error(f"Error en BD durante upsert: {e}")
            self.conn.rollback() # Rollback manual si falla algo en un bloque no-autocommit implícito
            raise

    def delete_document(self, client_id: UUID, content_id: str) -> Optional[str]:
        """Borra un documento de ambas tablas y retorna el nombre del archivo para limpieza física."""
        if not self.conn or self.conn.closed:
            self._connect()
        
        filename = None
        with self.conn.cursor() as cur:
            # 0. Obtener el nombre del archivo antes de borrar el registro
            cur.execute("""
```
### `services/etl-docs/src/shared/memory_reset.py`

```
import logging
import os
from typing import Optional

import requests


logger = logging.getLogger(__name__)


def reset_client_memory(client_id: str, reason: Optional[str] = None) -> bool:
    """
    Best-effort call to reset downstream chat memory after knowledge mutations.
    Does not raise to avoid breaking ETL lifecycle operations.
    """
    reset_url = (os.getenv("MEMORY_RESET_URL") or "").strip().rstrip("/")
    if not reset_url:
        logger.info("MEMORY_RESET_URL not configured; skipping memory reset for client %s", client_id)
        return False

    payload = {"client_id": client_id}
    if reason:
        payload["reason"] = reason

    headers = {}
    token = (os.getenv("INTERNAL_API_TOKEN") or "").strip()
    if token:
        headers["X-Internal-Token"] = token

    timeout = float(os.getenv("MEMORY_RESET_TIMEOUT", "8"))
    try:
        response = requests.post(reset_url, json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()
        logger.info("Memory reset triggered for client %s", client_id)
        return True
    except Exception as exc:
        logger.warning("Memory reset failed for client %s: %s", client_id, exc)
        return False
```
### `services/etl-docs/src/ETL_DOCS/processor.py`

```

import logging
import os
import io
import hashlib
from uuid import UUID
from typing import Optional, Dict, Any

import pypdf
from pdf2image import convert_from_path
import pytesseract
from PIL import Image

from src.shared.schemas import CanonicalDocument, SourceType, IngestStatus
from src.shared.vector_store import VectorStore
from src.shared.file_manager import FileManager
from src.shared.memory_reset import reset_client_memory

logger = logging.getLogger(__name__)

class DocumentProcessor:
    """
    Orquestador del ETL de Documentos.
    Responsabilidades:
    1. Recibir path de archivo físico.
    2. Extraer texto (pypdf o OCR fallback).
    3. Construir CanonicalDocument.
    4. Delegar persistencia a VectorStore.
    """

    def __init__(self):
        self.vector_store = VectorStore()
        
    def _extract_text_from_pdf(self, file_path: str) -> str:
        """
        Intenta extracción rápida con pypdf. 
        Si retorna poco texto, asume imagen escaneada y usa OCR.
        """
        text = ""
        try:
            # 1. Intento Rápido (Texto seleccionable)
            reader = pypdf.PdfReader(file_path)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
            
            # Limpieza básica
            text = text.strip()

            # 2. Check de Calidad / OCR Fallback
            # Si hay muy poco texto (< 50 chars) para un PDF, probablemente sea imagen
            if len(text) < 50:
                logger.info(f"Texto insuficiente detectado ({len(text)} chars). Iniciando OCR para {file_path}...")
                text = self._ocr_pdf(file_path)
            
            return text

        except Exception as e:
            logger.error(f"Error parseando PDF {file_path}: {e}")
            raise ValueError(f"No se pudo leer el PDF: {e}")

    def _ocr_pdf(self, file_path: str) -> str:
        """Usa pdf2image + pytesseract para documentos escaneados"""
        text = ""
        try:
            # Convertir PDF a imágenes (una por página)
            images = convert_from_path(file_path)
            for i, image in enumerate(images):
                # Tesseract OCR
                page_text = pytesseract.image_to_string(image, lang='spa') # Prioridad Español
                text += page_text + "\n"
                logger.debug(f"OCR Página {i+1} completado")
            return text.strip()
        except Exception as e:
            logger.error(f"Fallo crítico en OCR: {e}")
            raise

    def process_document(self, 
                         file_path: str, 
                         client_id: UUID, 
                         content_id: str,
                         original_filename: str,
                         source: SourceType = SourceType.PDF_UPLOAD,
                         access_level: str = "private",
                         category: str = "knowledge_base") -> Dict[str, Any]:
        """
        Flujo principal de procesamiento con fragmentación por páginas.
        """
        logger.info(f"Iniciando procesamiento ETL para: {original_filename} ({content_id})")

        try:
            # 1. Extracción de Texto por páginas
            logger.info(f"Pasando a extracción de texto para {file_path}")
            reader = pypdf.PdfReader(file_path)
            pages_text = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text and len(text.strip()) > 10:
                    pages_text.append({
                        "text": text.strip(),
                        "page_number": i + 1
                    })
            
            logger.info(f"Texto extraído: {len(pages_text)} páginas con contenido.")

            # OCR Fallback si no hay texto extraído
            if not pages_text:
                logger.info(f"No se detectó texto seleccionable. Iniciando OCR para {file_path}...")
                full_ocr_text = self._ocr_pdf(file_path)
                pages_text.append({"text": full_ocr_text, "page_number": 1})

            if not pages_text:
                raise ValueError("El documento está vacío o no se pudo extraer texto legible.")

            # 2. Limpieza de fragmentos previos
            logger.info(f"Limpiando fragmentos previos para {content_id}")
            with self.vector_store.conn.cursor() as cur:
                cur.execute("DELETE FROM ai_vectors WHERE client_id = %s AND (content_id = %s OR content_id LIKE %s)", 
                            (str(client_id), content_id, f"{content_id}_part_%"))

            # 3. Procesamiento y Carga de Fragmentos
            total_chars = 0
            from src.shared.schemas import CanonicalMetadata
            
            for item in pages_text:
                chunk_id = f"{content_id}_part_{item['page_number']}"
                logger.info(f"Procesando fragmento: {chunk_id}")
                chunk_hash = self.vector_store.calculate_hash(item['text'])
                
                # Construir metadata con información del modelo de embeddings
                meta = CanonicalMetadata(
                    client_id=client_id,
                    category=category,
                    access_level=access_level,
                    url=None,
                    source_timestamp=None,
                    # Metadata extra para tracking de versiones
                    embedding_model=os.getenv("EMBEDDING_MODEL", "models/gemini-embedding-001"),
                    embedding_dimension=3072
                )
                
                doc = CanonicalDocument(
                    content_id=chunk_id,
                    source=source,
                    title=f"{original_filename} (Pág. {item['page_number']})",
                    body_content=item['text'],
                    hash=chunk_hash,
                    metadata=meta
                )
                
                self.vector_store.upsert_document(doc)
                total_chars += len(item['text'])

            # 4. Actualizar Registro Maestro
            logger.info(f"Actualizando estado a SYNCED para {content_id}")
            self.vector_store.update_sync_status(client_id, content_id, "SYNCED")
            reset_client_memory(str(client_id), reason="document_synced")

            logger.info(f"ETL Exitoso: {len(pages_text)} fragmentos creados para {content_id}")
            
            return {
                "status": IngestStatus.SYNCED,
                "content_id": content_id,
                "chunks_processed": len(pages_text),
                "total_chars": total_chars
            }

        except Exception as e:
            logger.error(f"ETL Fallido para {content_id}: {e}")
            try:
                self.vector_store.update_sync_status(client_id, content_id, "FAILED", str(e))
            except:
                pass
            return {
                "status": IngestStatus.FAILED,
                "error": str(e)
            }
```
### `services/etl-docs/src/ETL_DOCS/worker_task.py`

```

import logging
from uuid import UUID
from src.ETL_DOCS.processor import DocumentProcessor

# Configuración de log dedicada al Worker
logger = logging.getLogger("worker")

def process_document_task(file_path: str, client_id: UUID, content_id: str, original_filename: str, access_level: str = "private", category: str = "knowledge_base"):
    """
    Tarea ejecutable por RQ Worker.
    Es un wrapper simple alrededor del Processor, pero esencial para que RQ pueda
    serializar la llamada (pickle).
    """
    logger.info(f"👷 [WORKER] Iniciando tarea para: {content_id} (Access Level: {access_level}, Category: {category})")
    try:
        # Instanciar procesador fresco para cada tarea (Thread-safe)
        processor = DocumentProcessor()
        
        result = processor.process_document(
            file_path=file_path,
            client_id=client_id,
            content_id=content_id,
            original_filename=original_filename,
            access_level=access_level,
            category=category
        )
        
        logger.info(f"✅ [WORKER] Tarea completada: {result}")
        return result
        
    except Exception as e:
        logger.error(f"❌ [WORKER] Tarea fallida para {content_id}: {e}")
        # Re-lanzar para que RQ marque el job como Failed
        raise e
```

## Pruebas y Diagnóstico

```text

```
### `tests/README.md`

```
# Repository-Level Tests

Cross-service and stack-wide checks live here.

## Layout
- `tests/system/`: end-to-end tests across multiple services.
- `tests/smoke-stack/`: full-stack smoke scripts.
- `tests/sandbox/realtor/`: manual simulators/benchmarks for realtor v2.
- `tests/sandbox/dentist/`: manual simulators/benchmarks for dentist v2.
- `tests/sandbox/*.py`: legacy wrappers kept for backward compatibility.
- `tests/fixtures-shared/`: reusable fixtures for multiple services.
- `tests/scripts/`: helper runners/utilities.

## Notes
- Service-local tests must remain inside each service.
- Root-level tests are only for cross-service/system/sandbox use cases.
```

## Deuda Técnica Detectable (heurística)

```text
services/etl-processor (deprecated placeholder)
services/legacy-ETL_DOCS (legacy duplicate path)
services/web/datasyncsa (sitio estático fuera de SUID)
services/web/tests (UI de pruebas manuales)
services/web/admin-console/docs + themes (assets plantilla)
```
