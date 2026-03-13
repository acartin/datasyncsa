# AI Context Pack

- Generated UTC: `2026-03-13T03:59:07Z`
- Repo root: `/srv/datasyncsa`
- Git branch: `main`
- Git commit: `9f44094`
- Policy: High-signal only; assets/binarios excluidos.

## Contexto Maestro

- Fuente principal: `.agent/BRAIN_MAP.md`
### `.agent/BRAIN_MAP.md`

```
# BRAIN_MAP

- Generated UTC: `2026-03-13T03:59:07Z`
- Repo root: `/srv/datasyncsa`
- Git branch: `main`
- Git commit: `9f44094`

## 1. MAPA DE INTENCIONES (DIRECTORIO)

| Carpeta | Responsabilidad Técnica | Importancia (1-5) |
|---|---|---:|
| `docker-compose.yml` | Orquestación de servicios (DB, Redis, APIs, bridges, UI, ETL). | 5 |
| `services/agent-core` | Autoridad conversacional LangGraph (planner, gate, tools, synthesizer, persistencia). | 5 |
| `services/scoring-core` | Dominio de scoring asíncrono desacoplado del runtime conversacional. | 5 |
| `services/web/chat-web-renderer` | Canal web y renderer SDUI del chat. | 5 |
| `services/generic-bridge-v2` | Wrapper de integración genérica hacia `agent-core`. | 4 |
| `services/property-bridge-v2` | Wrapper del vertical realtor hacia `agent-core`. | 4 |
| `services/inference-stack-v2/semantic-adapter-v2` | Recuperación semántica v2 (RAG retriever). | 5 |
| `services/inference-stack-v2/inference-core-v2` | Compatibilidad legacy de scoring/APIs históricas (no autoridad principal de chat). | 3 |
| `services/web/admin-console` | BFF FastAPI + renderer SDUI para consola operativa multi-tenant. | 5 |
| `services/etl-docs` | Ingesta documental, colas RQ y vectorización. | 5 |
| `schemas` | Contratos canónicos compartidos entre servicios. | 4 |
| `tests` | Pruebas de integración y sistema cross-service. | 4 |
| `volumes/r2_storage` | Storage documental montado (Cloudflare R2 vía rclone). | 5 |
| `volumes/staging` | Buffer de staging para pipelines ETL. | 4 |
| `services/inference-stack-v2/inference-core-v3` | Código legado archivado; fuera del camino operativo principal. | 1 |
| `services/etl-processor` | Servicio deprecado (no usar para features nuevas). | 1 |
| `services/legacy-ETL_DOCS` | Código ETL legacy/deprecado. | 1 |

## 2. ARQUITECTURA CORE (SDUI/SUID)

- Backend soberano: frontend renderiza contratos SDUI, no decide negocio.
- Multi-tenant estricto: toda consulta operativa debe tener scope por `client_id`.
- Contratos UI validados con Pydantic y consistentes con renderer.

## 3. ENTRY POINTS PRINCIPALES

- `services/agent-core/main.py`
- `services/scoring-core/main.py`
- `services/web/admin-console/backend/app/main.py`
- `services/web/chat-web-renderer/backend/app/main.py`
- `services/inference-stack-v2/semantic-adapter-v2/main.py`
- `services/inference-stack-v2/inference-core-v2/main.py`
- `services/etl-docs/main.py`

## Referencia Canónica

- Índice arquitectónico: `docs/AGENT_CORE_INDEX.md`
- Arquitectura runtime: `docs/AGENT_CORE_ARCHITECTURE.md`
- Frontera de scoring: `docs/SCORING_CORE_BOUNDARY.md`

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

  # Agent Core (LangGraph conversational runtime)
  agent-core:
    build:
      context: ./services/agent-core
      dockerfile: Dockerfile
    container_name: ${ENV_PREFIX}-backend-agent-core
    restart: always
    command:
      - uvicorn
      - main:app
      - --host
      - 0.0.0.0
      - --port
      - "8000"
      - --workers
      - ${AGENT_CORE_WEB_CONCURRENCY:-1}
    ports:
      - "${AGENT_CORE_PORT:-8096}:8000"
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
      - RAG_RETRIEVER_V2_URL=http://semantic-adapter-v2:8000
      - RAG_RETRIEVER_V2_SEARCH_PATH=/api/v2/search
      - RAG_RETRIEVER_V2_TIMEOUT_SECS=${RAG_RETRIEVER_V2_TIMEOUT_SECS:-10}
      - SCORING_BG_ENABLED=${SCORING_BG_ENABLED:-true}
      - AGENT_CORE_API=${AGENT_CORE_API:-http://agent-core:8000}
      - SCORING_CORE_API=${SCORING_CORE_API:-http://scoring-core:8000}
      - SCORING_API_PREFIX=${SCORING_API_PREFIX:-/api/v1}
    volumes:
      - ./schemas:/app/schemas:ro
    depends_on:
      - postgres
      - redis
      - semantic-adapter-v2
      - scoring-core
    networks:
      - internal_network

  # Scoring Core API
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
      - AGENT_CORE_API=${AGENT_CORE_API:-http://agent-core:8000}
      - SCORING_CORE_API=${SCORING_CORE_API:-http://scoring-core:8000}
      - SCORING_API_PREFIX=${SCORING_API_PREFIX:-/api/v1}
    volumes:
      - ./schemas:/app/schemas:ro
    depends_on:
      - postgres
      - redis
    networks:
      - internal_network

  # Scoring Core Worker
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
      - AGENT_CORE_API=${AGENT_CORE_API:-http://agent-core:8000}
      - SCORING_CORE_API=${SCORING_CORE_API:-http://scoring-core:8000}
      - SCORING_API_PREFIX=${SCORING_API_PREFIX:-/api/v1}
    volumes:
      - ./schemas:/app/schemas:ro
    depends_on:
      - postgres
      - redis
      - scoring-core
    networks:
      - internal_network

  # Inference Core V2 async scoring worker (persistent jobs)
  inference-core-v2-worker:
    build:
      context: ./services/inference-stack-v2/inference-core-v2
      dockerfile: Dockerfile
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

# --- AGENT/SCORING SERVICE DISCOVERY ---
AGENT_CORE_API=http://agent-core:8000
AGENT_CORE_API_PREFIX=/api/v1
AGENT_CORE_RESET_URL=http://agent-core:8000/api/v1/internal/memory/reset
SCORING_CORE_API=http://scoring-core:8000
SCORING_API_PREFIX=/api/v1

# --- SCORING FEATURE FLAGS ---
SCORING_BG_ENABLED=true
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
AGENT_CORE_PORT=8096
SCORING_CORE_PORT=8097

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
### `docs/AGENT_CORE_INDEX.md`

```
# Agent Core Index (LangGraph Canonical)

Este índice reemplaza la documentación anterior de `AGENT_CORE`.

Estado actual:
- Arquitectura objetivo: `agent-core` con `LangGraph`.
- Alcance de esta fase: conversación y runtime del agente.
- Fuera de alcance en esta fase: refactor interno de `scoring`.

## Orden de lectura obligatorio

1. `docs/AGENT_CORE_EVAL_PROMPT.md`
2. `docs/AGENT_CORE_RULES.md`
3. `docs/AGENT_CORE_ARCHITECTURE.md`
4. `docs/AGENT_CORE_DIAGRAMS.md`
5. `docs/AGENT_CORE_API_CONTRACT.md`
6. `docs/AGENT_CORE_PROMPT_RUNTIME.md`
7. `docs/AGENT_CORE_FILE_MAP.md`
8. `docs/AGENT_CORE_IMPLEMENTATION_PLAN.md`
9. `docs/AGENT_CORE_PROMPT_SEQUENCE.md`
10. `docs/AGENT_CORE_PROMPT_STATUS.md`

## Objetivo

Construir un `agent-core` nuevo con orquestación `LangGraph`, contratos tipados y fronteras estrictas:
- lógica conversacional probabilística en LLMs
- ejecución de herramientas determinista
- control de riesgo determinista por `accept/reject`

## Regla de precedencia

Si hay contradicción:
1. Código ejecutable vigente.
2. `docs/AGENT_CORE_RULES.md`.
3. Resto de documentos `AGENT_CORE`.
```
### `docs/AGENT_CORE_ARCHITECTURE.md`

```
# Agent Core Architecture (Target)

## Resumen

`agent-core` será un servicio de conversación `LangGraph-first`.

Separa estrictamente:
- decisión conversacional (planner LLM)
- ejecución determinista (gate, tools, SQL translator, card renderer)
- redacción final (synthesizer LLM)

## Componentes

1. Input Normalizer
- Normaliza `tenant`, `channel`, `conversation_id`, `metadata`.
- Construye contexto operativo mínimo.

2. Planner LLM
- Entrada: historial + contexto + prompt de planner.
- Salida: `RouterDecision` tipado.
- No ejecuta herramientas.

3. Policy Gate
- Valida esquema, permisos tenant, tools permitidas, budget y confidence.
- Respuesta binaria `accept/reject`.

4. Tool Runtime
- Ejecuta tools permitidas en paralelo cuando aplique.
- Submódulos:
- `RAG` retriever
- `SQL translator` determinista
- `workflow executor` para side effects tipados

5. Card Renderer
- Convierte `ToolResult` a `CardModel`.
- No usa LLM.

6. Synthesizer LLM
- Entrada: `SynthesizerInput` (contexto resumido + tool results).
- Salida: `SynthesizerOutput`.
- No ve `RouterDecision`.

7. Answer Guardrail
- Verifica claims, evidencia y schema de salida.
- Respuesta binaria `accept/reject`.

8. Persistence
- Persiste envelope, decisión, tool results y trazas.
- Emite evento o enqueue hacia scoring (sin lógica de scoring local).

## Frontera con scoring

- `agent-core` solo invoca API de scoring para encolado y consulta de estado.
- No contiene motor, repositorios ni worker de scoring en su dominio.

## Modelo de errores

1. `goal=clarify`: respuesta de negocio válida.
2. `gate reject`: rechazo de seguridad/política.
3. `guardrail reject`: salida no confiable.
4. `tool failure`: degradación controlada según contrato.
```
### `docs/SCORING_CORE_BOUNDARY.md`

```
# Scoring Core Boundary

## Objetivo

Desacoplar scoring de `agent-core` sin tocar BD ni logica funcional de scoring.

## Regla central

`scoring-core` es duenio de:

- `lead_scoring_jobs`
- `lead_scorecards`
- `lead_score_items`
- `lead_scoring_models`
- `lead_scoring_criteria`
- `lead_scoring_bands`
- `lead_scoring_prompts`

## Lo que se conserva

- tablas actuales
- worker async actual
- `ScoringEngine`
- prompt builder/linter de scoring
- fallback conservador por criterio
- politica anti-stale por `generation`

## Lo que sale de `agent-core`

- resolver `scoring_model_id`
- resolver `lead_scoring_prompts`
- hacer `upsert` en `lead_scoring_jobs`
- exponer operaciones de scorecard/job
- conocer detalle del scorecard

## Contrato minimo entre servicios

`agent-core` solo debe emitir:

- `conversation_id`
- `lead_id`
- `client_id`

Opcional:

- metadata tecnica de canal

No debe emitir:

- `model_id`
- `prompt_id`
- prompt snapshot
- reglas de scoring

## Fuente de codigo actual

La base funcional a extraer viene de:

- `services/inference-stack-v2/inference-core-v2/app/services/scoring_engine.py`
- `services/inference-stack-v2/inference-core-v2/app/services/scoring_worker.py`
- `services/inference-stack-v2/inference-core-v2/app/services/scoring_job_service.py`
- `services/inference-stack-v2/inference-core-v2/app/repositories/scoring_repository.py`

## Beneficio

`agent-core` puede reescribirse o cambiar planner/synth/tools sin afectar scoring.
```
### `docs/OLD/SERVER_PROVISIONING.md`

```
# Server Provisioning Guide: DatasyncSA Infrastructure

This guide details the steps to configure a fresh Debian/Ubuntu server (Hetzner VPS or Local Machine) to host the DatasyncSA Docker stack with R2 storage integration.

## 1. Prerequisites
- **OS**: Debian 12 (Bookworm) or Ubuntu 22.04 LTS recommended.
- **User**: A non-root user with sudo privileges (e.g., `acartin`).
- **Cloudflare API**: Access Key ID and Secret Access Key for R2.

## 2. Docker Installation
Install the official Docker Engine and Compose plugin.

```bash
# Update and install dependencies
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg

# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add the repository
echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Enable for non-root user
sudo usermod -aG docker $USER
# LOGOUT AND LOGIN AGAIN FOR GROUPS TO UPDATE
```

## 3. Storage Configuration (R2 Mount)
We use `rclone` to mount the Cloudflare R2 bucket as a local file system. This allows legacy applications to interact with cloud storage as if it were a local disk, providing a zero-friction migration path.

### 3.1 Install & Configure Rclone
```bash
sudo apt-get install -y rclone fuse3

# Interactive Configuration
rclone config
# 1. New remote -> Name: "r2-remote" (Un nombre genérico para la conexión)
# 2. Type: "s3"
# 3. Provider: "Cloudflare"
# 4. Access Key ID: <YOUR_R2_ACCESS_KEY>
# 5. Secret Access Key: <YOUR_R2_SECRET_KEY>
# 6. Endpoint: https://<ACCOUNT_ID>.r2.cloudflarestorage.com
# 7. ACL: private
# 8. Finish and verify with: rclone lsd r2-remote:
```

### 3.2 Create Directory & Systemd Service
Create the mount point and the service to auto-mount on boot.

```bash
# Create mount points
sudo mkdir -p /srv/datasyncsa/volumes/r2_storage
sudo chown -R $USER:$USER /srv/datasyncsa/volumes/r2_storage
sudo mkdir -p /srv/datasyncsa/volumes/staging
sudo chown -R $USER:$USER /srv/datasyncsa/volumes/staging

# Create Service File
sudo nano /etc/systemd/system/rclone-mount.service
```

Paste the following configuration. Replace `datasync-dev` with the actual bucket name you want to mount (e.g., `datasync-dev` for Ryzen, `datasync-prod` for Hetzner).

```ini
[Unit]
Description=Rclone Mount for R2 Storage
After=network-online.target
Wants=network-online.target

[Service]
Type=notify
User=acartin
Group=acartin
# NOTA: r2-remote es la conexión, datasync-dev es el bucket
ExecStart=/usr/bin/rclone mount r2-remote:datasync-dev /srv/datasyncsa/volumes/r2_storage \
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

### 3.3 Enable Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now rclone-mount.service
# Check status
systemctl status rclone-mount.service
# Verify mount works
ls /srv/datasyncsa/volumes/r2_storage
```

## 4. Application Deployment
Clone the repo (or copy files) to `/srv/datasyncsa`.

```bash
# 1. Copy config
cp .env.example .env
nano .env # Edit secrets like DB_PASSWORD, R2_KEYS

# 2. Deploy Stack
docker compose up -d --build
```
```

## Topología Técnica (directorios clave)

```text
docs
docs/Manuales
docs/OLD
schemas
schemas/__pycache__
schemas/agent_core
schemas/agent_core/contracts
schemas/agent_core/runtime
schemas/scoring_core
schemas/scoring_core/contracts
services
services/agent-core
services/agent-core/__pycache__
services/agent-core/app
services/agent-core/app/__pycache__
services/agent-core/app/api
services/agent-core/app/core
services/agent-core/app/graph
services/agent-core/app/models
services/agent-core/app/planners
services/agent-core/app/renderers
services/agent-core/app/repositories
services/agent-core/app/runtime
services/agent-core/app/services
services/agent-core/app/synthesizers
services/agent-core/app/tools
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
services/inference-stack-v2/inference-core-v3
services/inference-stack-v2/inference-core-v3/__pycache__
services/inference-stack-v2/inference-core-v3/app
services/inference-stack-v2/inference-core-v3/tests
services/inference-stack-v2/semantic-adapter-v2
services/inference-stack-v2/semantic-adapter-v2/app
services/property-bridge-v2
services/property-bridge-v2/__pycache__
services/scoring-core
services/scoring-core/app
services/scoring-core/app/api
services/scoring-core/app/core
services/scoring-core/app/models
services/scoring-core/app/repositories
services/scoring-core/app/services
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
services/generic-bridge-v2/main.py:34:app = FastAPI(
services/generic-bridge-v2/main.py:292:if __name__ == "__main__":
services/generic-bridge-v2/main.py:298:    uvicorn.run(
services/etl-processor/main.py:3:app = FastAPI()
services/agent-core/main.py:5:app = FastAPI(title="agent-core")
services/agent-core/main.py:6:app.include_router(api_router)
services/property-bridge-v2/main.py:35:app = FastAPI(
services/property-bridge-v2/main.py:353:if __name__ == "__main__":
services/property-bridge-v2/main.py:359:    uvicorn.run(
services/web/chat-web-renderer/backend/tests/smoke/test_smoke_web_proxy.py:57:if __name__ == "__main__":
services/web/chat-web-renderer/backend/tests/smoke/test_smoke_bridge.py:36:if __name__ == "__main__":
services/web/chat-web-renderer/backend/app/main.py:13:app = FastAPI(title="Chat Web Renderer")
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
services/inference-stack-v2/inference-core-v3/main.py:44:app = FastAPI(
services/inference-stack-v2/inference-core-v3/main.py:59:app.include_router(chat_v3_router, prefix=settings.api_prefix, tags=["chat-v3"])
services/inference-stack-v2/inference-core-v3/main.py:72:if __name__ == "__main__":
services/inference-stack-v2/inference-core-v3/main.py:73:    uvicorn.run(
services/inference-stack-v2/semantic-adapter-v2/main.py:21:app = FastAPI(
services/inference-stack-v2/semantic-adapter-v2/main.py:46:app.include_router(router, prefix="/api/v2")
services/inference-stack-v2/semantic-adapter-v2/main.py:52:if __name__ == "__main__":
services/inference-stack-v2/semantic-adapter-v2/main.py:54:    uvicorn.run(app, host="0.0.0.0", port=8000)
services/etl-docs/tests/smoke/test_smoke_etl_docs.py:42:if __name__ == "__main__":
services/etl-docs/main.py:19:app = FastAPI(title="ETL Docs API", version="1.0.0")
services/scoring-core/worker.py:17:if __name__ == "__main__":
services/scoring-core/main.py:4:app = FastAPI(title="scoring-core")
```

## Rutas API Detectadas

```text
services/agent-core/app/api/chat.py:140:@router.get("/health")
services/agent-core/app/api/chat.py:145:@router.post("/chat", response_model=ChatResponse)
services/agent-core/app/api/chat.py:188:@router.post("/internal/memory/reset", response_model=InternalMemoryResetResponse)
services/inference-stack-v2/inference-core-v2/app/api/chat_v2.py:35:@router.post("/chat", response_model=ChatV2Response)
services/inference-stack-v2/inference-core-v2/app/api/chat_v2.py:77:@router.get("/leads/{lead_id}/scorecards/latest", response_model=ScorecardResponse)
services/inference-stack-v2/inference-core-v2/app/api/chat_v2.py:99:@router.get("/leads/{lead_id}/scorecards/{scorecard_id}", response_model=ScorecardResponse)
services/inference-stack-v2/inference-core-v2/app/api/chat_v2.py:126:@router.get("/scoring/jobs/{job_id}", response_model=ScoringJobResponse)
services/inference-stack-v2/inference-core-v2/app/api/chat_v2.py:145:@router.get("/scoring/ops/summary", response_model=ScoringOpsSummaryResponse)
services/inference-stack-v2/inference-core-v2/app/api/chat_v2.py:163:@router.get("/scoring/models/active", response_model=ActiveModelResponse)
services/inference-stack-v2/inference-core-v2/app/api/chat_v2.py:210:@router.post("/cache/invalidate")
services/inference-stack-v2/inference-core-v2/app/api/chat_v2.py:241:@router.get("/health")
services/inference-stack-v2/inference-core-v2/app/api/chat_v2.py:261:@router.post("/internal/memory/reset", response_model=InternalMemoryResetResponse)
services/web/chat-web-renderer/backend/app/api/external.py:56:@router.post(
services/web/chat-web-renderer/backend/app/api/external.py:267:@router.get("/health")
services/inference-stack-v2/inference-core-v3/app/api/chat_v3.py:32:@router.post("/chat", response_model=ChatV3Response)
services/inference-stack-v2/inference-core-v3/app/api/chat_v3.py:51:@router.get("/health")
services/inference-stack-v2/inference-core-v3/app/api/chat_v3.py:61:@router.post("/cache/invalidate", response_model=CacheInvalidateResponse)
services/inference-stack-v2/inference-core-v3/app/api/chat_v3.py:83:@router.post("/internal/memory/reset", response_model=InternalMemoryResetResponse)
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
services/web/admin-console/backend/app/dashboards/manager_workspace/router.py:13:@router.get("/manager", response_model=ManagerDashboardSchema)
services/web/admin-console/backend/app/dashboards/seller_workspace/router.py:14:@router.get("/seller", response_model=ClientUserDashboardSchema)
services/web/admin-console/backend/app/dashboards/seller_workspace/router.py:52:@router.get("/leads/{lead_id}", response_model=ClientUserDashboardSchema)
services/web/admin-console/backend/app/dashboards/seller_workspace/router.py:60:@router.get("/leads_v2/{lead_id}", response_model=ClientUserDashboardSchema)
services/web/admin-console/backend/app/dashboards/base_dash/router.py:10:@router.get("/app-init", response_model=UIAppShell)
services/web/admin-console/backend/app/dashboards/base_dash/router.py:72:@router.get("/base", response_model=WebIAFirstResponse)
services/web/admin-console/backend/app/dashboards/base_dash/router.py:94:@router.get("/check-contract", response_model=WebIAFirstResponse)
```

## Contratos/Modelos Críticos

```text
services/agent-core/app/models/contracts.py:23:class RealtorSearchSlots(BaseModel):
services/agent-core/app/models/contracts.py:36:class RAGQuery(BaseModel):
services/agent-core/app/models/contracts.py:42:class WorkflowCall(BaseModel):
services/agent-core/app/models/contracts.py:53:class ToolCall(BaseModel):
services/agent-core/app/models/contracts.py:70:class RouterDecision(BaseModel):
services/agent-core/app/models/contracts.py:97:class GateResult(BaseModel):
services/agent-core/app/models/contracts.py:110:class RAGChunk(BaseModel):
services/agent-core/app/models/contracts.py:118:class RAGResult(BaseModel):
services/agent-core/app/models/contracts.py:123:class PropertyListing(BaseModel):
services/agent-core/app/models/contracts.py:138:class RealtorSQLResult(BaseModel):
services/agent-core/app/models/contracts.py:145:class WorkflowResult(BaseModel):
services/agent-core/app/models/contracts.py:151:class ToolResult(BaseModel):
services/agent-core/app/models/contracts.py:161:class PropertyCard(BaseModel):
services/agent-core/app/models/contracts.py:173:class SearchSummaryCard(BaseModel):
services/agent-core/app/models/contracts.py:180:class RAGSourceCard(BaseModel):
services/agent-core/app/models/contracts.py:191:class SynthesizerInput(BaseModel):
services/agent-core/app/models/contracts.py:198:class SynthesizerOutput(BaseModel):
services/agent-core/app/models/contracts.py:211:class GuardrailResult(BaseModel):
services/agent-core/app/models/contracts.py:222:class AnswerEnvelope(BaseModel):
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
services/web/chat-web-renderer/backend/app/schemas/ui.py:4:class BaseComponent(BaseModel):
services/web/chat-web-renderer/backend/app/schemas/ui.py:52:class BrandingConfig(BaseModel):
services/web/chat-web-renderer/backend/app/schemas/ui.py:77:class SDUIResponse(BaseModel):
services/web/chat-web-renderer/backend/app/schemas/chat.py:7:class InitRequest(BaseModel):
services/web/chat-web-renderer/backend/app/schemas/chat.py:17:class ChatRequest(BaseModel):
services/web/chat-web-renderer/backend/app/schemas/chat.py:50:class InternalMemoryResetRequest(BaseModel):
services/web/chat-web-renderer/backend/app/schemas/internal_chat.py:10:class InternalChatRequest(BaseModel):
services/web/chat-web-renderer/backend/app/schemas/internal_chat.py:45:class InternalChatResponse(BaseModel):
```

## Tablas/SQL Referenciadas (DB Map)

```text
services/agent-core/app/graph/nodes.py -> lead_id
services/agent-core/app/services/scoring_client.py -> lead_id
services/agent-core/app/services/scoring_client.py -> lead_id_required
services/agent-core/app/tools/sql_translator.py -> lead_properties
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
services/inference-stack-v2/inference-core-v2/app/services/realtor_turn_executor.py -> lead_leads
services/inference-stack-v2/inference-core-v2/app/services/realtor_turn_executor.py -> lead_properties
services/inference-stack-v2/inference-core-v2/app/services/realtor_turn_executor.py -> lead_property_images
services/inference-stack-v2/inference-core-v2/app/services/realtor_turn_executor.py -> lead_propierties
services/inference-stack-v2/inference-core-v2/app/services/scoring_job_service.py -> lead_id
services/inference-stack-v2/inference-core-v2/app/services/scoring_job_service.py -> lead_messages
services/inference-stack-v2/inference-core-v2/app/services/scoring_orchestrator.py -> lead_ai_prompts
services/inference-stack-v2/inference-core-v2/app/services/scoring_orchestrator.py -> lead_by_conversation_id
services/inference-stack-v2/inference-core-v2/app/services/scoring_orchestrator.py -> lead_current_scorecard
services/inference-stack-v2/inference-core-v2/app/services/scoring_orchestrator.py -> lead_from_extraction
services/inference-stack-v2/inference-core-v2/app/services/scoring_orchestrator.py -> lead_id
services/inference-stack-v2/inference-core-v2/app/services/scoring_orchestrator.py -> lead_messages
services/inference-stack-v2/inference-core-v2/app/services/scoring_orchestrator.py -> lead_profile
services/inference-stack-v2/inference-core-v2/app/services/scoring_orchestrator.py -> lead_profile_text
services/inference-stack-v2/inference-core-v2/app/services/scoring_orchestrator.py -> lead_properties
services/inference-stack-v2/inference-core-v2/app/services/scoring_orchestrator.py -> lead_snapshot
services/inference-stack-v2/inference-core-v2/app/services/scoring_worker.py -> lead_id
services/inference-stack-v2/inference-core-v2/app/services/scoring_worker.py -> lead_messages
services/inference-stack-v2/inference-core-v2/tests/integration/test_api_chat_v2.py -> lead_id
services/inference-stack-v2/inference-core-v2/tests/unit/test_hybrid_chat_context.py -> lead_profile
services/inference-stack-v2/inference-core-v2/tests/unit/test_hybrid_chat_context.py -> lead_snapshot
services/inference-stack-v2/inference-core-v2/tests/unit/test_realtor_turn_executor.py -> lead_properties
services/inference-stack-v2/inference-core-v2/tests/unit/test_scoring_job_service.py -> lead_id
services/inference-stack-v2/inference-core-v2/tests/unit/test_scoring_job_service.py -> lead_messages
services/inference-stack-v2/inference-core-v2/tests/unit/test_scoring_orchestrator.py -> lead_by_conversation_id
services/inference-stack-v2/inference-core-v2/tests/unit/test_scoring_orchestrator.py -> lead_current_scorecard
services/inference-stack-v2/inference-core-v2/tests/unit/test_scoring_orchestrator.py -> lead_from_extraction
services/inference-stack-v2/inference-core-v2/tests/unit/test_scoring_orchestrator.py -> lead_id
services/inference-stack-v2/inference-core-v2/tests/unit/test_scoring_orchestrator.py -> lead_messages
services/inference-stack-v2/inference-core-v2/tests/unit/test_scoring_orchestrator.py -> lead_properties
services/inference-stack-v2/inference-core-v2/tests/unit/test_scoring_worker_generation.py -> lead_id
services/inference-stack-v2/inference-core-v2/tests/unit/test_scoring_worker_generation.py -> lead_messages
services/inference-stack-v2/inference-core-v3/app/graph/builder.py -> lead_followup_planner
services/inference-stack-v2/inference-core-v3/app/graph/builder.py -> lead_followup_planner_node
services/inference-stack-v2/inference-core-v3/app/graph/builder.py -> lead_state
services/inference-stack-v2/inference-core-v3/app/graph/nodes.py -> lead_followup_planner
services/inference-stack-v2/inference-core-v3/app/graph/nodes.py -> lead_followup_planner_node
services/inference-stack-v2/inference-core-v3/app/graph/nodes.py -> lead_id
services/inference-stack-v2/inference-core-v3/app/graph/nodes.py -> lead_messages
services/inference-stack-v2/inference-core-v3/app/graph/nodes.py -> lead_name
services/inference-stack-v2/inference-core-v3/app/graph/nodes.py -> lead_progression_state
services/inference-stack-v2/inference-core-v3/app/graph/nodes.py -> lead_snapshot
services/inference-stack-v2/inference-core-v3/app/graph/nodes.py -> lead_snapshot_into_memory
services/inference-stack-v2/inference-core-v3/app/graph/nodes.py -> lead_state
services/inference-stack-v2/inference-core-v3/app/models/agent_state.py -> lead_id
services/inference-stack-v2/inference-core-v3/app/models/agent_state.py -> lead_progression_state
services/inference-stack-v2/inference-core-v3/app/models/agent_state.py -> lead_snapshot
services/inference-stack-v2/inference-core-v3/app/models/chat_v3.py -> lead_id
services/inference-stack-v2/inference-core-v3/app/repositories/vertical_runtime_repository.py -> ai_system_prompt
services/inference-stack-v2/inference-core-v3/app/repositories/vertical_runtime_repository.py -> ai_system_prompt_bundle
services/inference-stack-v2/inference-core-v3/app/repositories/vertical_runtime_repository.py -> ai_system_prompts
services/inference-stack-v2/inference-core-v3/app/repositories/vertical_runtime_repository.py -> lead_ai_prompts
services/inference-stack-v2/inference-core-v3/app/repositories/vertical_runtime_repository.py -> lead_by_conversation_id
services/inference-stack-v2/inference-core-v3/app/repositories/vertical_runtime_repository.py -> lead_client_verticals
services/inference-stack-v2/inference-core-v3/app/repositories/vertical_runtime_repository.py -> lead_clients
services/inference-stack-v2/inference-core-v3/app/repositories/vertical_runtime_repository.py -> lead_conversations
services/inference-stack-v2/inference-core-v3/app/repositories/vertical_runtime_repository.py -> lead_id
services/inference-stack-v2/inference-core-v3/app/repositories/vertical_runtime_repository.py -> lead_leads
services/inference-stack-v2/inference-core-v3/app/repositories/vertical_runtime_repository.py -> lead_messages
services/inference-stack-v2/inference-core-v3/app/repositories/vertical_runtime_repository.py -> lead_scoring_jobs
services/inference-stack-v2/inference-core-v3/app/repositories/vertical_runtime_repository.py -> lead_scoring_models
services/inference-stack-v2/inference-core-v3/app/repositories/vertical_runtime_repository.py -> lead_scoring_prompts
services/inference-stack-v2/inference-core-v3/app/repositories/vertical_runtime_repository.py -> lead_snapshot
services/inference-stack-v2/inference-core-v3/app/services/answer_synthesizer.py -> lead_progression_state
services/inference-stack-v2/inference-core-v3/app/services/lead_followup_planner.py -> lead_followup_planner
services/inference-stack-v2/inference-core-v3/app/services/lead_followup_planner.py -> lead_progression_state
services/inference-stack-v2/inference-core-v3/app/services/orchestrator.py -> lead_id
services/inference-stack-v2/inference-core-v3/app/services/realtor_query_compiler.py -> lead_properties
services/inference-stack-v2/inference-core-v3/app/services/realtor_search_executor.py -> lead_leads
services/inference-stack-v2/inference-core-v3/app/services/realtor_search_executor.py -> lead_properties
services/inference-stack-v2/inference-core-v3/app/services/realtor_search_executor.py -> lead_property_images
services/inference-stack-v2/inference-core-v3/app/services/realtor_search_executor.py -> lead_propierties
services/inference-stack-v2/inference-core-v3/app/services/tenant_runtime.py -> ai_system_prompt_bundle
services/inference-stack-v2/inference-core-v3/app/services/tenant_runtime.py -> ai_system_prompts
services/inference-stack-v2/inference-core-v3/app/services/tenant_runtime.py -> lead_ai_prompts
services/inference-stack-v2/inference-core-v3/app/services/tenant_runtime.py -> lead_followup_planner
services/inference-stack-v2/inference-core-v3/app/services/tenant_runtime.py -> lead_properties
services/inference-stack-v2/inference-core-v3/app/services/tenant_runtime.py -> lead_snapshot_read
services/inference-stack-v2/inference-core-v3/app/services/turn_planning.py -> lead_progression_state
services/inference-stack-v2/inference-core-v3/tests/unit/test_lead_followup_planner.py -> lead_followup_planner
services/inference-stack-v2/inference-core-v3/tests/unit/test_lead_followup_planner.py -> lead_followup_planner_blocks_capture_before_any_cards_are_shown
services/inference-stack-v2/inference-core-v3/tests/unit/test_lead_followup_planner.py -> lead_followup_planner_blocks_capture_when_turn_is_empty
services/inference-stack-v2/inference-core-v3/tests/unit/test_lead_followup_planner.py -> lead_followup_planner_does_not_force_name_capture_on_first_cards
services/inference-stack-v2/inference-core-v3/tests/unit/test_lead_followup_planner.py -> lead_followup_planner_enforces_two_turn_cooldown_between_capture_attempts
services/inference-stack-v2/inference-core-v3/tests/unit/test_lead_followup_planner.py -> lead_followup_planner_keeps_model_question_on_first_card_turn
services/inference-stack-v2/inference-core-v3/tests/unit/test_lead_followup_planner.py -> lead_followup_planner_payload_marks_first_cards_shown_now
services/inference-stack-v2/inference-core-v3/tests/unit/test_lead_followup_planner.py -> lead_followup_planner_reapplies_capture_name_after_first_cards_turn
services/inference-stack-v2/inference-core-v3/tests/unit/test_lead_followup_planner.py -> lead_followup_planner_updates_memory_and_marks_asked_field
services/inference-stack-v2/inference-core-v3/tests/unit/test_lead_followup_planner.py -> lead_progression_state
services/inference-stack-v2/inference-core-v3/tests/unit/test_nodes.py -> lead_followup_planner
services/inference-stack-v2/inference-core-v3/tests/unit/test_nodes.py -> lead_name
services/inference-stack-v2/inference-core-v3/tests/unit/test_nodes.py -> lead_name_is_not_treated_as_real_name
services/inference-stack-v2/inference-core-v3/tests/unit/test_nodes.py -> lead_progression_state
services/inference-stack-v2/inference-core-v3/tests/unit/test_nodes.py -> lead_snapshot
services/inference-stack-v2/inference-core-v3/tests/unit/test_nodes.py -> lead_state
services/inference-stack-v2/inference-core-v3/tests/unit/test_nodes.py -> lead_state_merges_lead_snapshot_into_memory
services/inference-stack-v2/inference-core-v3/tests/unit/test_realtor_query_compiler.py -> lead_properties
services/inference-stack-v2/inference-core-v3/tests/unit/test_realtor_search_executor.py -> lead_properties
services/inference-stack-v2/inference-core-v3/tests/unit/test_response_contracts_loader.py -> lead_followup_planner
services/inference-stack-v2/inference-core-v3/tests/unit/test_tenant_runtime.py -> ai_system_prompt_bundle
services/inference-stack-v2/inference-core-v3/tests/unit/test_tenant_runtime.py -> lead_followup_planner
services/inference-stack-v2/inference-core-v3/tests/unit/test_turn_planning.py -> lead_progression_state
services/inference-stack-v2/inference-core-v3/tests/unit/test_vertical_runtime_repository.py -> lead_by_conversation_id
services/inference-stack-v2/inference-core-v3/tests/unit/test_vertical_runtime_repository.py -> lead_id
services/inference-stack-v2/inference-core-v3/tests/unit/test_vertical_runtime_repository.py -> lead_reuses_existing_conversation_lead
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
    public_url: Optional[str] = None
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
                public_url=prop_data.get("public_url"),
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
                el.publicUrl = config.public_url;
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
import logging
import time
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import httpx
from app.schemas.chat import InitRequest, InternalMemoryResetRequest
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
    inference_base = os.getenv(
        "AGENT_CORE_API",
        os.getenv("INFERENCE_API_URL", os.getenv("INFERENCE_V2_URL", "http://agent-core:8000")),
    ).rstrip("/")
    inference_prefix = os.getenv(
        "AGENT_CORE_API_PREFIX",
        os.getenv("INFERENCE_API_PREFIX", os.getenv("INFERENCE_V2_API_PREFIX", "/api/v1")),
    )
    inference_url = f"{inference_base}{inference_prefix}/health"
    retriever_url = os.getenv("RAG_RETRIEVER_V2_URL", "http://semantic-adapter-v2:8000").rstrip("/") + "/api/v2/health"

    result = {
        "status": "operational",
        "service": "chat-web-renderer-api",
        "dependencies": {
            "inference_core": {"ok": False, "url": inference_url},
            "semantic_adapter_v2": {"ok": False, "url": retriever_url},
        },
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        for name, url in (
            ("inference_core", inference_url),
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
    metadata = dict(req.metadata or {})
    trace_id = str(metadata.get("debug_trace_id") or "")
    incoming_conversation_id = str(req.conversation_id) if req.conversation_id else None
    request_started = time.perf_counter()

    session_data = await session_manager.get_session_multichannel(
        client_id=client_id,
        channel=channel,
        channel_user_id=channel_user_id,
    )
    
    session_context = {
        "client_id": client_id,
        "conversation_id": incoming_conversation_id or session_data.get("conversation_id"),
        "lead_id": session_data.get("lead_id"),
        "brand_project": req.brand_project or session_data.get("brand_project"),
        "channel": channel,
        "channel_user_id": channel_user_id,
    }
    
    if metadata:
        session_context.update(metadata)

    logger.info(
        "CHAT_RENDERER_INBOUND trace_id=%s client_id=%s channel=%s channel_user_id=%s incoming_conversation_id=%s "
        "session_conversation_id=%s resolved_conversation_id=%s frontend_runtime_conversation_id=%s "
        "frontend_stored_conversation_id=%s frontend_had_stored_conversation_id=%s "
        "frontend_runtime_channel_user_id=%s frontend_stored_channel_user_id=%s "
        "frontend_had_stored_channel_user_id=%s frontend_had_frontend_state=%s frontend_had_window_state=%s "
        "frontend_message_seq=%s frontend_page_load_id=%s landing_page_url=%s referrer_url=%s",
        trace_id or "-",
        client_id,
        channel,
        channel_user_id,
        incoming_conversation_id or "-",
        session_data.get("conversation_id") or "-",
        session_context.get("conversation_id") or "-",
        metadata.get("frontend_runtime_conversation_id") or "-",
        metadata.get("frontend_stored_conversation_id") or "-",
        metadata.get("frontend_had_stored_conversation_id"),
        metadata.get("frontend_runtime_channel_user_id") or "-",
        metadata.get("frontend_stored_channel_user_id") or "-",
        metadata.get("frontend_had_stored_channel_user_id"),
        metadata.get("frontend_had_frontend_state"),
        metadata.get("frontend_had_window_state"),
        metadata.get("frontend_message_seq"),
        metadata.get("frontend_page_load_id") or "-",
        metadata.get("landing_page_url") or "-",
        metadata.get("referrer_url") or "-",
    )
    
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

        logger.info(
            "CHAT_RENDERER_OUTBOUND trace_id=%s client_id=%s channel=%s channel_user_id=%s incoming_conversation_id=%s "
            "resolved_conversation_id=%s outgoing_conversation_id=%s conversation_reused=%s "
            "session_fallback_used=%s components_count=%s answer_chars=%s latency_ms=%.1f",
            trace_id or "-",
            client_id,
            channel,
            channel_user_id,
            incoming_conversation_id or "-",
            session_context.get("conversation_id") or "-",
            new_conversation_id or "-",
            bool(incoming_conversation_id and str(incoming_conversation_id) == str(new_conversation_id)),
            bool((not incoming_conversation_id) and session_data.get("conversation_id")),
            len(ai_response.get("components") or []),
            len((ai_response.get("answer") or "").strip()),
            (time.perf_counter() - request_started) * 1000.0,
        )
        
        vertical = await vertical_router.resolve_vertical_for_client_async(client_id)
        policy_handler = await vertical_router.get_handler_async(client_id, channel)
        if not policy_handler:
            raise HTTPException(status_code=500, detail="No renderer policy available for resolved vertical/channel")
        
        ai_text = ai_response.get("answer")
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

### `services/agent-core/app/graph/workflow.py`

```
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.models.contracts import GoalType
from app.graph.nodes import (
    answer_guardrail,
    clarify_response,
    execute_tools,
    normalize_input,
    persist,
    plan_turn,
    policy_gate,
    synthesize,
)
from app.graph.state import AgentCoreState


def _route_after_policy_gate(state: AgentCoreState) -> str:
    gate = state.get("gate_result")
    decision = state.get("router_decision")

    if gate is None or not getattr(gate, "accepted", False):
        return "persist"
    if decision is not None and decision.goal == GoalType.clarify:
        return "clarify_response"
    return "execute_tools"


def _route_after_guardrail(state: AgentCoreState) -> str:
    guardrail = state.get("guardrail_result")
    if guardrail is None or not getattr(guardrail, "accepted", False):
        return "persist"
    return "persist"


def build_agent_graph():
    graph = StateGraph(AgentCoreState)

    graph.add_node("normalize_input", normalize_input)
    graph.add_node("plan_turn", plan_turn)
    graph.add_node("policy_gate", policy_gate)
    graph.add_node("clarify_response", clarify_response)
    graph.add_node("execute_tools", execute_tools)
    graph.add_node("synthesize", synthesize)
    graph.add_node("answer_guardrail", answer_guardrail)
    graph.add_node("persist", persist)

    graph.add_edge(START, "normalize_input")
    graph.add_edge("normalize_input", "plan_turn")
    graph.add_edge("plan_turn", "policy_gate")

    graph.add_conditional_edges(
        "policy_gate",
        _route_after_policy_gate,
        {
            "clarify_response": "clarify_response",
            "execute_tools": "execute_tools",
            "persist": "persist",
        },
    )

    graph.add_edge("clarify_response", "persist")
    graph.add_edge("execute_tools", "synthesize")
    graph.add_edge("synthesize", "answer_guardrail")
    graph.add_conditional_edges(
        "answer_guardrail",
        _route_after_guardrail,
        {
            "persist": "persist",
        },
    )

    graph.add_edge("persist", END)

    return graph.compile()


agent_graph = build_agent_graph()
```
### `services/agent-core/app/graph/nodes.py`

```
from __future__ import annotations

import time
import uuid
from typing import Any

from app.core.config import settings
from app.models.contracts import (
    AnswerEnvelope,
    GoalType,
    GuardrailRejectCode,
    GuardrailResult,
    GateResult,
    GateRejectCode,
    ResponseMode,
    RouterDecision,
    SynthesizerOutput,
    ToolResult,
)
from app.planners.planner_service import planner_service
from app.renderers.card_renderer import card_renderer
from app.repositories.persistence import runtime_repository
from app.runtime.answer_guardrail import run_answer_guardrail
from app.runtime.policy_gate import run_policy_gate
from app.services.scoring_client import scoring_client
from app.tools.executor import tool_executor
from app.synthesizers.synthesizer_service import synthesizer_service
from app.graph.state import AgentCoreState


def _timing(state: AgentCoreState, node_name: str, started: float) -> dict[str, Any]:
    elapsed = (time.perf_counter() - started) * 1000.0
    timings = dict(state.get("node_timings_ms", {}))
    timings[node_name] = timings.get(node_name, 0.0) + elapsed
    return {"node_timings_ms": timings}


def normalize_input(state: AgentCoreState) -> dict[str, Any]:
    started = time.perf_counter()
    raw = state.get("raw_input", {})
    if not isinstance(raw, dict):
        raw = {}

    conversation_id = str(
        raw.get("conversationId")
        or raw.get("conversation_id")
        or uuid.uuid4()
    )
    tenant_id = raw.get("tenant_id") or raw.get("clientId") or raw.get("client_id")
    channel = raw.get("channel") or "web_html"
    vertical = str(raw.get("vertical") or "generic").strip() or "generic"

    normalized_input = {
        "conversation_summary": str(raw.get("queryText") or raw.get("text") or "").strip(),
        "vertical": vertical,
        "conversation_state": raw.get("conversation_state") or {},
        "last_user_turn": str(raw.get("queryText") or raw.get("text") or ""),
    }

    return {
        **_timing(state, "normalize_input", started),
        "normalized_input": normalized_input,
        "tenant_id": str(tenant_id) if tenant_id else None,
        "channel": str(channel),
        "conversation_id": conversation_id,
        "errors": [],
    }


async def plan_turn(state: AgentCoreState) -> dict[str, Any]:
    started = time.perf_counter()
    raw_input = state.get("raw_input") or {}
    normalized = state.get("normalized_input") or {}
    history = state.get("raw_input", {}).get("history", [])
    if not isinstance(history, list):
        history = []

    try:
        decision = await planner_service.run(
            raw_input=raw_input,
            normalized_input=normalized,
            history=history,
        )
        return {
            **_timing(state, "plan_turn", started),
            "router_decision": decision,
        }
    except Exception as exc:
        decision = RouterDecision(
            goal=GoalType.clarify,
            confidence=0.0,
            tool_calls=[],
            missing_slots=["planner_output_invalid"],
            clarify_message="No pude decidir el siguiente paso. Por favor formula la consulta de nuevo.",
            response_mode=ResponseMode.text_only,
        )
        return {
            **_timing(state, "plan_turn", started),
            "router_decision": decision,
            "errors": [str(exc)],
        }


def policy_gate(state: AgentCoreState) -> dict[str, Any]:
    started = time.perf_counter()
    decision = state.get("router_decision")
    if not isinstance(decision, RouterDecision):
        return {
            **_timing(state, "policy_gate", started),
            "gate_result": GateResult(
                accepted=False,
                reject_code=GateRejectCode.schema_invalid,
            ),
            "errors": ["invalid_router_decision"],
        }

    tenant_id = str(state.get("tenant_id")) if state.get("tenant_id") else "default"
    vertical = str((state.get("normalized_input") or {}).get("vertical", "generic"))
    gate = run_policy_gate(
        decision=decision,
        tenant_id=tenant_id,
        vertical=vertical,
    )
    return {
        **_timing(state, "policy_gate", started),
        "gate_result": gate,
    }


def clarify_response(state: AgentCoreState) -> dict[str, Any]:
    started = time.perf_counter()
    raw_input = state.get("raw_input") or {}
    decision = state.get("router_decision")
    goal = decision.goal if decision else GoalType.clarify
    message = (
        decision.clarify_message
        if decision and decision.clarify_message
        else "Necesito más contexto para continuar."
    )
    envelope = AnswerEnvelope(
        conversation_id=str(raw_input.get("conversationId") or raw_input.get("conversation_id") or state.get("conversation_id", "")),
        text=message,
        cards=[],
        response_mode=ResponseMode.text_only,
        evidence_ids=[],
        goal=goal,
        confidence=float(decision.confidence if decision else 0.0),
        clarify_message=message,
    )
    return {
        **_timing(state, "clarify_response", started),
        "answer_envelope": envelope,
    }


async def execute_tools(state: AgentCoreState) -> dict[str, Any]:
    started = time.perf_counter()
    raw_input = state.get("raw_input") or {}
    tenant_id = str(raw_input.get("tenant_id") or raw_input.get("clientId") or raw_input.get("client_id") or "default")
    decision = state.get("router_decision")
    if not decision:
        return {"tool_results": [], **_timing(state, "execute_tools", started)}
    calls = decision.tool_calls
    if not calls:
        return {"tool_results": [], **_timing(state, "execute_tools", started)}
    results: list[ToolResult] = await tool_executor.execute_all(tenant_id=tenant_id, calls=calls)
    return {"tool_results": results, **_timing(state, "execute_tools", started)}


async def synthesize(state: AgentCoreState) -> dict[str, Any]:
    started = time.perf_counter()
    raw_input = state.get("raw_input") or {}
    decision = state.get("router_decision")
    tool_results = state.get("tool_results") or []
    normalized = state.get("normalized_input") or {}
    if not isinstance(tool_results, list):
        tool_results = []

    if not isinstance(decision, RouterDecision):
        decision = RouterDecision(
            goal=GoalType.answer,
            confidence=0.0,
            tool_calls=[],
            missing_slots=[],
        )

    try:
        output = await synthesizer_service.run(
            tenant_id=str(raw_input.get("tenant_id") or raw_input.get("clientId") or raw_input.get("client_id") or "default"),
            raw_input=raw_input,
            tool_results=tool_results,
            response_mode=decision.response_mode,
            context_snapshot={
                "conversation_summary": normalized.get("conversation_summary", ""),
                "vertical": normalized.get("vertical", "generic"),
                "conversation_state": normalized.get("conversation_state", {}),
                "last_user_turn": normalized.get("last_user_turn", ""),
            },
        )
        return {
            **_timing(state, "synthesize", started),
            "synthesizer_output": output,
        }
    except Exception as exc:
        output = SynthesizerOutput(
            text="",
            evidence_ids=[],
            needs_cards=bool(tool_results),
        )
        return {
            **_timing(state, "synthesize", started),
            "synthesizer_output": output,
            "errors": [str(exc)],
        }


def answer_guardrail(state: AgentCoreState) -> dict[str, Any]:
    started = time.perf_counter()
    decision = state.get("router_decision")
    tool_results = state.get("tool_results") or []
```
### `services/agent-core/app/planners/planner_service.py`

```
from __future__ import annotations

from typing import Any, Dict

from pydantic import ValidationError

from app.core.config import settings
from app.core.llm_client import llm_service
from app.core.prompt_service import prompt_service
from app.models.contracts import RouterDecision


class PlannerService:
    async def run(
        self,
        *,
        raw_input: Dict[str, Any],
        normalized_input: Dict[str, Any],
        history: list[Dict[str, Any]],
    ) -> RouterDecision:
        tenant_id = str(raw_input.get("tenant_id") or raw_input.get("clientId") or "default").strip()
        vertical = str(raw_input.get("vertical") or normalized_input.get("vertical") or "generic").strip()
        channel = str(raw_input.get("channel") or "web_html").strip()

        prompts = prompt_service.resolve_prompts(
            tenant_id=tenant_id,
            vertical=vertical,
            channel=channel,
        )

        payload = {
            "query_text": raw_input.get("queryText") or raw_input.get("text") or "",
            "history": history[-10:],
            "normalized_input": normalized_input,
            "context_snapshot": {
                "conversation_summary": normalized_input.get("conversation_summary", ""),
                "vertical": vertical,
                "conversation_state": normalized_input.get("conversation_state", {}),
            },
            "tenant_id": tenant_id,
            "channel": channel,
            "contract": {
                "goal": "answer|clarify|rag|realtor_search|realtor_refine|workflow",
                "confidence": "float 0..1",
                "tool_calls": "optional tool calls",
                "missing_slots": "list",
                "clarify_message": "required when goal=clarify",
                "response_mode": "text_only|text_plus_cards",
            },
        }

        raw = await llm_service.generate_json(
            system_instruction=prompts.planner_system_prompt,
            payload=payload,
            temperature=0.1,
            max_output_tokens=settings.llm_max_output_tokens,
        )
        if isinstance(raw.get("RouterDecision"), dict):
            raw = raw["RouterDecision"]
        elif isinstance(raw.get("router_decision"), dict):
            raw = raw["router_decision"]

        try:
            return RouterDecision.model_validate(raw)
        except ValidationError as exc:
            raise ValueError(f"planner_output_invalid:{exc}") from exc


planner_service = PlannerService()
```
### `services/agent-core/app/synthesizers/synthesizer_service.py`

```
from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.core.llm_client import llm_service
from app.core.prompt_service import prompt_service
from app.models.contracts import (
    SynthesizerInput,
    SynthesizerOutput,
    ToolResult,
)


class SynthesizerService:
    async def run(
        self,
        *,
        tenant_id: str,
        raw_input: dict[str, Any],
        tool_results: list[ToolResult],
        response_mode: Any,
        context_snapshot: dict[str, Any],
    ) -> SynthesizerOutput:
        channel = str(raw_input.get("channel") or "web_html").strip()
        vertical = str(raw_input.get("vertical") or "generic").strip()
        tenant = str(tenant_id or raw_input.get("tenant_id") or "default").strip()

        prompts = prompt_service.resolve_prompts(
            tenant_id=tenant,
            vertical=vertical,
            channel=channel,
        )

        synth_input = SynthesizerInput(
            context_snapshot=str(context_snapshot),
            tool_results=tool_results,
            response_mode=response_mode,
            tenant_tone=str(raw_input.get("tenant_tone") or "formal"),
        )

        payload = synth_input.model_dump()
        raw = await llm_service.generate_json(
            system_instruction=prompts.synthesizer_system_prompt,
            payload=payload,
            temperature=0.2,
            max_output_tokens=settings.llm_max_output_tokens,
        )
        return SynthesizerOutput.model_validate(raw)


synthesizer_service = SynthesizerService()
```
### `services/agent-core/app/tools/executor.py`

```
from __future__ import annotations

import json
from typing import Any, Iterable

from sqlalchemy import create_engine, text

from app.core.config import settings
from app.models.contracts import (
    RealtorSearchSlots,
    RAGQuery,
    RAGResult,
    RealtorSQLResult,
    ToolCall,
    ToolName,
    ToolResult,
)
from app.tools.rag_client import rag_client
from app.tools.sql_translator import slots_to_sql
from app.tools.workflow_executor import workflow_executor


class ToolExecutor:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or settings.database_url

    async def execute(self, *, tenant_id: str, call: ToolCall) -> ToolResult:
        if call.tool_name == ToolName.rag:
            return await self._run_rag(tenant_id, call.rag)
        if call.tool_name == ToolName.realtor_sql:
            return await self._run_realtor_sql(tenant_id, call.realtor_slots)
        if call.tool_name == ToolName.workflow:
            return await self._run_workflow(tenant_id, call.workflow)
        return ToolResult(
            tool_name=call.tool_name,
            status="error",
            error_code="unsupported_tool",
            error="Unsupported tool",
        )

    async def execute_all(self, tenant_id: str, calls: list[ToolCall]) -> list[ToolResult]:
        results: list[ToolResult] = []
        for call in calls:
            results.append(await self.execute(tenant_id=tenant_id, call=call))
        return results

    async def _run_rag(self, tenant_id: str, payload: RAGQuery | None) -> ToolResult:
        if not payload:
            return ToolResult(
                tool_name=ToolName.rag,
                status="error",
                error="missing_rag_query",
                error_code="missing_payload",
            )
        try:
            result = await rag_client.search(tenant_id=tenant_id, query=payload)
            return ToolResult(tool_name=ToolName.rag, status="ok", rag=result)
        except Exception as exc:
            return ToolResult(
                tool_name=ToolName.rag,
                status="error",
                error_code="rag_tool_failed",
                error=str(exc),
            )

    async def _run_realtor_sql(self, tenant_id: str, payload: RealtorSearchSlots | None) -> ToolResult:
        if not payload:
            return ToolResult(
                tool_name=ToolName.realtor_sql,
                status="error",
                error="missing_realtor_slots",
                error_code="missing_payload",
            )
        try:
            sql, params = slots_to_sql.compile(tenant_id=tenant_id, slots=payload.model_dump())
            engine = create_engine(self.database_url, future=True)
            rows = []
            total = 0
            with engine.connect() as connection:
                rows_raw = connection.execute(text(sql), params).mappings().all()
                total = len(rows_raw)
                for row in rows_raw:
                    rows.append(self._normalize_row(dict(row)))
            result = RealtorSQLResult(
                listings=rows,
                total_found=total,
                sql_executed=sql,
                slots_used=payload,
            )
            return ToolResult(tool_name=ToolName.realtor_sql, status="ok", realtor=result)
        except Exception as exc:
            return ToolResult(
                tool_name=ToolName.realtor_sql,
                status="error",
                error_code="realtor_sql_failed",
                error=str(exc),
            )

    async def _run_workflow(self, tenant_id: str, payload: Any) -> ToolResult:
        if payload is None:
            return ToolResult(
                tool_name=ToolName.workflow,
                status="error",
                error="missing_workflow_payload",
                error_code="missing_payload",
            )
        try:
            workflow_result = await workflow_executor.execute(tenant_id=tenant_id, workflow=payload)
            return ToolResult(
                tool_name=ToolName.workflow,
                status="ok" if workflow_result.success else "error",
                error_code=None if workflow_result.success else "workflow_failed",
                workflow=workflow_result,
            )
        except Exception as exc:
            return ToolResult(
                tool_name=ToolName.workflow,
                status="error",
                error_code="workflow_execution_failed",
                error=str(exc),
            )

    def _normalize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        listing_id = str(row.get("listing_id") or row.get("id") or "")
        title = str(row.get("title") or "")
        city = str(row.get("city") or "")
        neighborhood = row.get("neighborhood")
        price = _coerce_int(row.get("price"))
        currency = str(row.get("currency") or "USD")
        rooms = _coerce_int(row.get("rooms"))
        area_m2 = _coerce_float(row.get("area_m2"))
        property_type = str(row.get("property_type") or "generic")
        raw_features = row.get("features_json") or row.get("features") or []
        raw_images = row.get("image_urls") or []
        listing_url = row.get("listing_url")

        return {
            "listing_id": listing_id,
            "title": title,
            "city": city,
            "neighborhood": neighborhood if neighborhood is not None else None,
            "price": price,
            "currency": currency,
            "rooms": rooms,
            "area_m2": area_m2,
            "property_type": property_type,
            "features": _parse_list(raw_features),
            "image_urls": _parse_list(raw_images),
            "listing_url": str(listing_url) if listing_url is not None else None,
        }


def _coerce_int(value: Any) -> int:
    try:
        if value is None:
            return 0
        if isinstance(value, bool):
            return int(value)
        return int(str(value).replace(",", "").strip())
    except Exception:
        return 0


def _coerce_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(str(value).replace(",", "").strip())
    except Exception:
        return None


def _parse_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed if str(item).strip()]
        except Exception:
            pass
    return []


tool_executor = ToolExecutor()
```
### `services/agent-core/app/tools/rag_client.py`

```
from __future__ import annotations

import uuid
from typing import Any

import httpx

from app.core.config import settings
from app.models.contracts import RAGQuery, RAGResult, RAGChunk


class RAGClient:
    async def search(self, tenant_id: str, query: RAGQuery) -> RAGResult:
        endpoint = settings.rag_retriever_url.rstrip("/") + settings.rag_retriever_search_path
        payload = {
            "query_text": query.query_text,
            "client_id": tenant_id,
            "filters": {"doc_type": query.filter_doc_type} if query.filter_doc_type else {},
            "top_k": query.top_k,
        }

        async with httpx.AsyncClient(timeout=settings.rag_retriever_timeout_secs) as client:
            response = await client.post(endpoint, json=payload)
            response.raise_for_status()
            data = response.json()

        chunks: list[RAGChunk] = []
        for row in data.get("results", []) or []:
            chunk_id = str(row.get("content_id") or uuid.uuid4())
            score = row.get("score", 0.0)
            chunks.append(
                RAGChunk(
                    chunk_id=chunk_id,
                    doc_id=str(row.get("content_id") or chunk_id),
                    content=str(row.get("body_content") or row.get("content") or ""),
                    score=float(score) if score is not None else 0.0,
                    source_url=str((row.get("metadata") or {}).get("source_url") or "") or None,
                )
            )

        return RAGResult(chunks=chunks, query_used=query.query_text)


rag_client = RAGClient()
```
### `services/agent-core/app/runtime/policy_gate.py`

```
from __future__ import annotations

from app.core.config import settings
from app.models.contracts import GateRejectCode, GateResult, GoalType, RouterDecision, ToolCall


_GOAL_TOOL_REQUIREMENTS = {
    GoalType.realtor_search: {"realtor_sql"},
    GoalType.realtor_refine: {"realtor_sql"},
    GoalType.rag: {"rag"},
    GoalType.workflow: {"workflow"},
    GoalType.answer: set(),
    GoalType.clarify: set(),
}

_VERTICAL_ALLOW = {
    "generic": {
        "goals": {GoalType.answer, GoalType.clarify, GoalType.rag, GoalType.workflow},
        "tools": {"rag", "workflow"},
    },
    "realtor": {
        "goals": {
            GoalType.clarify,
            GoalType.rag,
            GoalType.realtor_search,
            GoalType.realtor_refine,
            GoalType.workflow,
            GoalType.answer,
        },
        "tools": {"rag", "realtor_sql", "workflow"},
    },
}


def run_policy_gate(decision: RouterDecision, tenant_id: str | None, vertical: str) -> GateResult:
    if settings.allowed_tenants and tenant_id and tenant_id not in settings.allowed_tenants:
        return GateResult(accepted=False, reject_code=GateRejectCode.tenant_not_authorized)

    if decision.confidence < settings.policy_min_confidence:
        return GateResult(accepted=False, reject_code=GateRejectCode.confidence_too_low)

    if len(decision.tool_calls) > settings.policy_max_tool_calls:
        return GateResult(accepted=False, reject_code=GateRejectCode.tool_not_permitted)

    vertical_key = vertical.lower() if vertical else "generic"
    policy = _VERTICAL_ALLOW.get(vertical_key, _VERTICAL_ALLOW["generic"])

    if decision.goal not in policy["goals"]:
        return GateResult(accepted=False, reject_code=GateRejectCode.tool_not_permitted)

    for tool_call in decision.tool_calls:
        if tool_call.tool_name not in policy["tools"]:
            return GateResult(accepted=False, reject_code=GateRejectCode.tool_not_permitted)

    required = _GOAL_TOOL_REQUIREMENTS.get(decision.goal, set())
    used = {call.tool_name.value for call in decision.tool_calls}
    if required and not required.issubset(used):
        return GateResult(accepted=False, reject_code=GateRejectCode.missing_required_slots)

    if (
        not settings.policy_allow_side_effects
        and any(call.tool_name.value == "workflow" for call in decision.tool_calls)
    ):
        return GateResult(accepted=False, reject_code=GateRejectCode.side_effects_blocked)

    if decision.goal == GoalType.clarify and decision.tool_calls:
        return GateResult(accepted=False, reject_code=GateRejectCode.schema_invalid)

    return GateResult(accepted=True)
```
### `services/agent-core/app/runtime/answer_guardrail.py`

```
from __future__ import annotations

from app.models.contracts import (
    GuardrailRejectCode,
    GuardrailResult,
    GoalType,
    RAGChunk,
    RealtorSQLResult,
    SynthesizerOutput,
    ToolResult,
)


def _tool_result_ids(tool_results: list[ToolResult]) -> set[str]:
    ids: set[str] = set()
    for tr in tool_results:
        if tr.rag:
            for chunk in tr.rag.chunks:
                if chunk.chunk_id:
                    ids.add(chunk.chunk_id)
        if tr.realtor:
            for listing in tr.realtor.listings:
                if listing.listing_id:
                    ids.add(listing.listing_id)
            if tr.realtor.sql_executed:
                ids.add(tr.realtor.sql_executed)
        if tr.workflow and tr.workflow.success and tr.workflow.output:
            ids.add(tr.workflow.workflow_name)
    return ids


def run_answer_guardrail(
    *,
    goal: GoalType,
    synthesizer_output: SynthesizerOutput | None,
    tool_results: list[ToolResult],
) -> GuardrailResult:
    if goal == GoalType.clarify:
        return GuardrailResult(accepted=True)

    if not synthesizer_output:
        return GuardrailResult(accepted=False, reject_code=GuardrailRejectCode.schema_violation)

    if not synthesizer_output.text.strip():
        return GuardrailResult(accepted=False, reject_code=GuardrailRejectCode.claim_without_source)

    valid_ids = _tool_result_ids(tool_results)
    claimed_ids = [i for i in synthesizer_output.evidence_ids if i]
    if claimed_ids and not all(item in valid_ids for item in claimed_ids):
        return GuardrailResult(accepted=False, reject_code=GuardrailRejectCode.hallucinated_listing_id)

    if tool_results and not claimed_ids and goal in {GoalType.rag, GoalType.realtor_search, GoalType.realtor_refine, GoalType.workflow}:
        return GuardrailResult(accepted=False, reject_code=GuardrailRejectCode.no_evidence_cited)

    if tool_results:
        if any(tr.status != "ok" and tr.error for tr in tool_results):
            if not claimed_ids:
                return GuardrailResult(accepted=False, reject_code=GuardrailRejectCode.claim_without_source)

    return GuardrailResult(accepted=True)
```
### `services/agent-core/app/services/scoring_client.py`

```
from __future__ import annotations

import uuid
from dataclasses import dataclass

import httpx

from app.core.config import settings


@dataclass(frozen=True)
class ScoreJob:
    id: str
    status: str
    scheduled_for: str | None = None


class ScoringClient:
    def __init__(self) -> None:
        self.base_url = settings.scoring_core_api.rstrip("/")
        self.prefix = settings.scoring_api_prefix.rstrip("/")

    async def enqueue(self, *, client_id: str, lead_id: str | None, conversation_id: str, channel: str) -> ScoreJob:
        if not settings.scoring_enabled:
            return ScoreJob(id=str(uuid.uuid4()), status="disabled")
        if not lead_id:
            raise RuntimeError("lead_id_required")

        endpoint = f"{self.base_url}{self.prefix}/scoring/jobs/enqueue"
        payload = {
            "client_id": str(client_id),
            "lead_id": str(lead_id),
            "conversation_id": str(conversation_id),
            "channel": str(channel),
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(endpoint, json=payload)
            response.raise_for_status()
            data = response.json()
        return ScoreJob(
            id=str(data.get("id") or uuid.uuid4()),
            status=str(data.get("status") or "queued"),
            scheduled_for=data.get("scheduled_for"),
        )

    async def latest_scorecard(self, *, client_id: str, lead_id: str) -> dict:
        endpoint = f"{self.base_url}{self.prefix}/leads/{lead_id}/scorecards/latest?client_id={client_id}"
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(endpoint)
            if response.status_code == 404:
                return {}
            response.raise_for_status()
            return response.json()


scoring_client = ScoringClient()
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
    Opera contra el runtime activo del inference core.
    """

    def __init__(self):
        self.timeout = int(os.getenv("INFERENCE_TIMEOUT", 60))
        self.connect_timeout = float(os.getenv("INFERENCE_CONNECT_TIMEOUT", 5))
        self.default_client_id = os.getenv("DEFAULT_CLIENT_ID", "")
        inference_url = os.getenv(
            "AGENT_CORE_API",
            os.getenv("INFERENCE_API_URL", os.getenv("INFERENCE_V2_URL", "http://agent-core:8000")),
        )
        api_prefix = os.getenv(
            "AGENT_CORE_API_PREFIX",
            os.getenv("INFERENCE_API_PREFIX", os.getenv("INFERENCE_V2_API_PREFIX", "/api/v1")),
        )
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
                logger.info(
                    "📤 Enviando mensaje al Core: trace_id=%s client_id=%s conversation_id=%s channel=%s channel_user_id=%s text=%s",
                    trace_id,
                    session.get("client_id"),
                    session.get("conversation_id"),
                    session.get("channel"),
                    session.get("channel_user_id"),
                    user_query[:50],
                )
                response = await client.post(url, json=payload)
                response.raise_for_status()
                
                data = response.json()
                logger.info(
                    "📥 Respuesta recibida del Core: trace_id=%s conversation_id=%s answer_chars=%s components=%s",
                    trace_id,
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
            logger.error(f"❌ Error inesperado en el bridge: {str(e)}")
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
### `services/generic-bridge-v2/main.py`

```
"""
Generic Bridge V2
Adapts generic chat requests to the active inference-core API
"""
import asyncio
import logging
import time
from typing import Dict, Any, Optional
from uuid import UUID
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, ConfigDict, AliasChoices
from pydantic.alias_generators import to_camel
import httpx
import os


# Configuration
INFERENCE_API_URL = os.getenv(
    "AGENT_CORE_API",
    os.getenv("INFERENCE_API_URL", os.getenv("INFERENCE_V2_URL", "http://agent-core:8000")),
)
INFERENCE_API_PREFIX = os.getenv(
    "AGENT_CORE_API_PREFIX",
    os.getenv("INFERENCE_API_PREFIX", os.getenv("INFERENCE_V2_API_PREFIX", "/api/v1")),
)
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("generic-bridge-v2")

# FastAPI app
app = FastAPI(
    title="Generic Bridge V2",
    description="Adapts generic chat requests to the active inference core",
    version="2.0.0"
)


class GenericChatRequest(BaseModel):
    """Generic chat request contract"""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )

    query_text: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        validation_alias=AliasChoices("query_text", "queryText", "text"),
    )
    client_id: UUID = Field(
        ...,
        description="Tenant/client identifier",
        validation_alias=AliasChoices("client_id", "clientId", "cliente_id", "clienteId"),
    )
    business_domain: Optional[str] = Field(None, description="Optional business domain")
    conversation_id: Optional[UUID] = Field(None, description="Existing conversation ID")
    user_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class GenericChatResponse(BaseModel):
    """Generic chat response contract"""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    answer: str
    conversation_id: UUID
    lead_id: Optional[UUID] = None
    scorecard_id: Optional[UUID] = None
    scoring_status: Optional[str] = None
    scoring_job_id: Optional[UUID] = None
    scoring_eta: Optional[str] = None
    score_total: Optional[float] = None
    priority_label: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    service: str
    inference_status: str


class AsyncHTTPClient:
    """Async HTTP client with retry logic"""
    
    def __init__(self):
        self.client = None
        self.base_url = f"{INFERENCE_API_URL}{INFERENCE_API_PREFIX}"
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()
    
    async def post_with_retry(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        retries: int = MAX_RETRIES
    ) -> httpx.Response:
        """POST request with retry logic"""
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(retries):
            try:
                logger.debug(f"Attempt {attempt + 1}/{retries}: POST {url}")
                response = await self.client.post(url, json=payload)
                
                if response.status_code < 500 or attempt == retries - 1:
                    return response
                
                logger.warning(f"Attempt {attempt + 1} failed: {response.status_code}")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                if attempt == retries - 1:
                    raise
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(2 ** attempt)
        
        raise httpx.RequestError("Max retries exceeded")


def _pick(payload: Dict[str, Any], *keys: str):
    for key in keys:
        if key in payload:
            return payload[key]
    return None


@app.post("/chat", response_model=GenericChatResponse)
async def chat_endpoint(request: GenericChatRequest):
    """
    Generic chat endpoint that forwards to the active inference core
    
    Required:
    - query_text: User's question/message
    - client_id: Tenant/client identifier
    
    Optional:
    - business_domain: Additional granularity for model resolution
    - conversation_id: Continue existing conversation
    """
    start_time = time.time()
    
    try:
        request_payload = {
            "queryText": request.query_text,
            "clientId": str(request.client_id),
            "businessDomain": request.business_domain,
            "conversationId": str(request.conversation_id) if request.conversation_id else None,
            "userMetadata": request.user_metadata,
            "filters": request.filters
        }
        
        # Forward to inference core
        async with AsyncHTTPClient() as http_client:
            response = await http_client.post_with_retry("/chat", request_payload)
            
            if response.status_code == 400:
                error_data = response.json()
                raise HTTPException(status_code=400, detail=error_data.get("detail", "Bad request"))
            
            if response.status_code == 404:
                error_data = response.json()
                raise HTTPException(status_code=404, detail=error_data.get("detail", "Not found"))
            
            if response.status_code >= 500:
                logger.error(f"Inference core error: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=503,
                    detail="Scoring service temporarily unavailable"
                )
            
            if response.status_code != 200:
                logger.error(f"Unexpected response: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=502,
                    detail=f"Bad gateway: {response.status_code}"
                )
            
            # Parse core response
            core_response = response.json()
            
            # Build generic response
            generic_response = GenericChatResponse(
                answer=core_response["answer"],
                conversation_id=UUID(_pick(core_response, "conversationId", "conversation_id")),
                metadata={
                    "source": "agent-core",
                    "processing_time_ms": int((time.time() - start_time) * 1000)
                }
            )

            generic_response.scoring_status = _pick(core_response, "scoringStatus", "scoring_status")
            generic_response.scoring_eta = _pick(core_response, "scoringEta", "scoring_eta")
            scoring_job_id = _pick(core_response, "scoringJobId", "scoring_job_id")
            if scoring_job_id:
                try:
                    generic_response.scoring_job_id = UUID(str(scoring_job_id))
                except ValueError:
                    logger.warning("Invalid scoring_job_id in core response: %s", scoring_job_id)
            
            # Add scoring data if available
            if core_response.get("scorecard"):
                scorecard = core_response["scorecard"]
                scorecard_id = _pick(core_response, "scorecardId", "scorecard_id")
```
### `services/property-bridge-v2/main.py`

```
"""
Property Bridge V2
Adapts property-specific chat requests to the active inference-core API
Maintains compatibility with existing property integrations
"""
import asyncio
import logging
import time
from typing import Dict, Any, Optional
from uuid import UUID
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, ConfigDict, AliasChoices
from pydantic.alias_generators import to_camel
import httpx
import os


# Configuration
INFERENCE_API_URL = os.getenv(
    "AGENT_CORE_API",
    os.getenv("INFERENCE_API_URL", os.getenv("INFERENCE_V2_URL", "http://agent-core:8000")),
)
INFERENCE_API_PREFIX = os.getenv(
    "AGENT_CORE_API_PREFIX",
    os.getenv("INFERENCE_API_PREFIX", os.getenv("INFERENCE_V2_API_PREFIX", "/api/v1")),
)
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("property-bridge-v2")

# FastAPI app
app = FastAPI(
    title="Property Bridge V2",
    description="Adapts property chat requests to the active inference core",
    version="2.0.0"
)


class PropertyChatRequest(BaseModel):
    """Property chat request (compatible with existing contract)"""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore"
    )
    
    query_text: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        validation_alias=AliasChoices("query_text", "queryText", "text"),
    )
    client_id: UUID = Field(
        ...,
        description="Tenant/client identifier",
        validation_alias=AliasChoices("client_id", "clientId", "cliente_id", "clienteId"),
    )
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    conversation_id: Optional[UUID] = Field(None)
    user_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class SourceDocument(BaseModel):
    """Source document for backward compatibility"""
    content_id: str
    title: Optional[str] = None
    body_content: str
    score: float
    metadata: Dict[str, Any]


class LeadScoringResult(BaseModel):
    """Legacy scoring result for backward compatibility"""
    score_engagement: int = Field(0)
    score_finance: int = Field(0)
    score_timeline: int = Field(0)
    score_match: int = Field(0)
    score_info: int = Field(0)
    reasoning: str = Field("")
    
    # Extracted fields
    extracted_name: Optional[str] = None
    extracted_email: Optional[str] = None
    extracted_phone: Optional[str] = None
    extracted_income: Optional[float] = None
    extracted_debts: Optional[float] = None
    extracted_currency_id: Optional[str] = None
    extracted_contact_pref_id: Optional[str] = None


class PropertyChatResponse(BaseModel):
    """Property chat response (compatible with existing contract)"""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    answer: str
    sources: list[SourceDocument] = Field(default_factory=list)
    conversation_id: UUID
    lead_scoring: Optional[LeadScoringResult] = None
    scoring_status: Optional[str] = None
    scoring_job_id: Optional[UUID] = None
    scoring_eta: Optional[str] = None


class AsyncHTTPClient:
    """Async HTTP client for the active inference core"""
    
    def __init__(self):
        self.client = None
        self.base_url = f"{INFERENCE_API_URL}{INFERENCE_API_PREFIX}"
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()
    
    async def post_with_retry(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        retries: int = MAX_RETRIES
    ) -> httpx.Response:
        """POST request with retry logic"""
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(retries):
            try:
                logger.debug(f"Attempt {attempt + 1}/{retries}: POST {url}")
                response = await self.client.post(url, json=payload)
                
                if response.status_code < 500 or attempt == retries - 1:
                    return response
                
                logger.warning(f"Attempt {attempt + 1} failed: {response.status_code}")
                await asyncio.sleep(2 ** attempt)
                
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                if attempt == retries - 1:
                    raise
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(2 ** attempt)
        
        raise httpx.RequestError("Max retries exceeded")
    
def map_v2_scorecard_to_legacy(scorecard: Dict[str, Any]) -> LeadScoringResult:
    """
    Map v2 scorecard to legacy scoring format
    
    This is a simplified mapping for backward compatibility.
    In production, would need business logic to map criteria to legacy pillars.
    """
    if not scorecard:
        return LeadScoringResult(
            score_engagement=0,
            score_finance=0,
            score_timeline=0,
            score_match=0,
            score_info=0,
            reasoning="No scoring available",
        )
    
    # Extract scores from v2 score items
    engagement_score = 0
    finance_score = 0
    timeline_score = 0
    match_score = 0
    info_score = 0
    
    score_items = scorecard.get("score_items") or scorecard.get("scoreItems") or []
    for item in score_items:
        criterion = item.get("criterion_key", "")
        score = item.get("score", 0)
        
        # Map v2 criteria to legacy pillars (simplified)
        if "intent" in criterion or "urgency" in criterion:
            engagement_score = int(score * 3)  # Scale to legacy range
        elif "finance" in criterion or "budget" in criterion:
            finance_score = int(score * 3)
        elif "timeline" in criterion or "timeframe" in criterion:
            timeline_score = int(score * 2)
        elif "match" in criterion or "fit" in criterion:
            match_score = int(score * 1.5)
        elif "data" in criterion or "quality" in criterion:
            info_score = int(score * 0.5)
    
    # Ensure scores are within legacy ranges
    engagement_score = max(-20, min(30, engagement_score))
    finance_score = max(-10, min(30, finance_score))
    timeline_score = max(0, min(20, timeline_score))
    match_score = max(0, min(15, match_score))
    info_score = max(-3, min(5, info_score))
    
    return LeadScoringResult(
        score_engagement=engagement_score,
        score_finance=finance_score,
        score_timeline=timeline_score,
        score_match=match_score,
        score_info=info_score,
        reasoning=scorecard.get("reasoning", "Scoring calculated with v2 model"),
        # Note: Extracted fields would come from score_items extracted_data
    )


@app.post("/chat", response_model=PropertyChatResponse)
async def chat_endpoint(request: PropertyChatRequest):
    """
    Property chat endpoint with backward compatibility
    
    Forwards to the active inference core
    Maps scorecards to legacy format for frontend compatibility
    """
    start_time = time.time()
```
### `services/inference-stack-v2/inference-core-v2/app/api/chat_v2.py`

```
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.models.chat_v2 import (
    ChatV2Request,
    ChatV2Response,
    ScoringJobResponse,
    ScoringOpsSummaryResponse,
    ScorecardResponse,
    ActiveModelResponse,
    InternalMemoryResetRequest,
    InternalMemoryResetResponse,
)
from app.services.scoring_orchestrator import ScoringOrchestrator
from app.dependencies.database import get_db_session
from app.services.cache_service import cache_service
from app.core.config import settings
import logging


router = APIRouter()
logger = logging.getLogger("inference-core-v2.api")


def _assert_internal_token(request: Request):
    expected = (settings.internal_api_token or "").strip()
    if not expected:
        return
    provided = (request.headers.get("X-Internal-Token") or "").strip()
    if provided != expected:
        raise HTTPException(status_code=401, detail="Invalid internal token")


@router.post("/chat", response_model=ChatV2Response)
async def chat_v2_endpoint(
    request: ChatV2Request,
    db_session: AsyncSession = Depends(get_db_session)
):
    """
    Principal endpoint para interactuar con el bot v2.
    
    Realiza búsqueda semántica, genera respuesta con LLM y scoring configurable.
    
    Requerido:
    - client_id: Tenant para resolver vertical y modelo de scoring
    
    """
    try:
        # Initialize orchestrator
        orchestrator = ScoringOrchestrator(db_session)
        
        # Process chat with scoring
        response = await orchestrator.process_chat(request)
        
        return response
        
    except ValueError as e:
        error = str(e)
        logger.warning(f"Validation error in /api/v2/chat: {error}")
        if error == "CLIENT_NOT_FOUND":
            raise HTTPException(status_code=404, detail=error)
        if error in ("TENANT_VERTICAL_NOT_CONFIGURED", "TENANT_SCORING_MODEL_NOT_CONFIGURED"):
            raise HTTPException(status_code=422, detail=error)
        if error.startswith("NO_ACTIVE_VERTICAL_SCORING_MODEL"):
            raise HTTPException(status_code=404, detail=error)
        if error.startswith("LLM_ENGINE_NOT_AVAILABLE"):
            raise HTTPException(status_code=503, detail=error)
        raise HTTPException(status_code=400, detail=error)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled error in /api/v2/chat")
        raise HTTPException(status_code=500, detail="Internal inference error")


@router.get("/leads/{lead_id}/scorecards/latest", response_model=ScorecardResponse)
async def get_latest_scorecard(
    lead_id: UUID,
    db_session: AsyncSession = Depends(get_db_session)
):
    """Get the latest scorecard for a lead"""
    try:
        orchestrator = ScoringOrchestrator(db_session)
        scorecard = await orchestrator.get_latest_scorecard_response(lead_id)
        
        if not scorecard:
            raise HTTPException(status_code=404, detail="No scorecards found for this lead")
        
        return scorecard
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting latest scorecard for lead {lead_id}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/leads/{lead_id}/scorecards/{scorecard_id}", response_model=ScorecardResponse)
async def get_scorecard(
    lead_id: UUID,
    scorecard_id: UUID,
    db_session: AsyncSession = Depends(get_db_session)
):
    """Get specific scorecard for a lead"""
    try:
        orchestrator = ScoringOrchestrator(db_session)
        scorecard = await orchestrator.get_scorecard_response(scorecard_id)
        
        if not scorecard:
            raise HTTPException(status_code=404, detail="Scorecard not found")
        
        # Verify scorecard belongs to lead
        if UUID(scorecard["lead_id"]) != lead_id:
            raise HTTPException(status_code=404, detail="Scorecard not found for this lead")
        
        return scorecard
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting scorecard {scorecard_id} for lead {lead_id}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/scoring/jobs/{job_id}", response_model=ScoringJobResponse)
async def get_scoring_job(
    job_id: UUID,
    db_session: AsyncSession = Depends(get_db_session),
):
    """Get async scoring job status."""
    try:
        orchestrator = ScoringOrchestrator(db_session)
        job = await orchestrator.get_scoring_job_response(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Scoring job not found")
        return job
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error getting scoring job %s", job_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/scoring/ops/summary", response_model=ScoringOpsSummaryResponse)
async def get_scoring_ops_summary(
    request: Request,
    window_minutes: int = Query(60, ge=5, le=1440, description="Rolling window for rate/p95 metrics"),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Internal endpoint with scoring queue/SLO metrics."""
    _assert_internal_token(request)
    try:
        orchestrator = ScoringOrchestrator(db_session)
        return await orchestrator.get_scoring_ops_summary(window_minutes=window_minutes)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error getting scoring ops summary")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/scoring/models/active", response_model=ActiveModelResponse)
async def get_active_scoring_model(
    client_id: UUID = Query(..., description="Tenant/client identifier"),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Get active scoring model configuration for tenant scope"""
    try:
        orchestrator = ScoringOrchestrator(db_session)
        vertical_ctx = await orchestrator.resolve_vertical_for_client(client_id)
        vertical_id = int(vertical_ctx["vertical_id"])
        scoring_model_id = vertical_ctx.get("scoring_model_id")
        model_data = await orchestrator.get_active_scoring_model(
            client_id=client_id,
            vertical_id=vertical_id,
            scoring_model_id=scoring_model_id,
        )
        
        if not model_data:
            raise HTTPException(
                status_code=404,
                detail=(
                    "No active scoring model found for "
                    f"vertical_id={vertical_id}, scoring_model_id={scoring_model_id}"
                ),
            )
        
        return ActiveModelResponse(
            model_id=UUID(model_data["id"]),
            model_version=model_data["version"],
            prompt_version=model_data["prompt_version"],
            criteria=model_data["criteria"]
        )
        
    except ValueError as e:
        error = str(e)
        if error == "CLIENT_NOT_FOUND":
            raise HTTPException(status_code=404, detail=error)
        if error in ("TENANT_VERTICAL_NOT_CONFIGURED", "TENANT_SCORING_MODEL_NOT_CONFIGURED"):
            raise HTTPException(status_code=422, detail=error)
        raise HTTPException(status_code=400, detail=error)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting active scoring model")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/cache/invalidate")
async def invalidate_cache(
    client_id: UUID = None,
):
    """Invalidate cache entries (internal use)"""
    try:
        if client_id:
            active_ok = await cache_service.invalidate_active_model(client_id=client_id)
            prompts_ok = await cache_service.invalidate_client_prompts(client_id=client_id)
            if active_ok or prompts_ok:
                return {"status": "success", "message": "Cache invalidated"}
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
services/inference-stack-v2/inference-core-v3 (legacy archivado, fuera de ruta principal)
services/etl-processor (deprecated placeholder)
services/legacy-ETL_DOCS (legacy duplicate path)
services/web/datasyncsa (sitio estático fuera de SUID)
services/web/tests (UI de pruebas manuales)
services/web/admin-console/docs + themes (assets plantilla)
```
