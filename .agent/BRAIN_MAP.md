# BRAIN_MAP

- Generated UTC: `2026-03-26T22:01:10Z`
- Repo root: `/srv/datasyncsa`
- Git branch: `HETZNER-LOCAL-2026-03-25`
- Git commit: `95e3ef6`

## 1. MAPA DE INTENCIONES (STACK ACTUAL)

| Carpeta | Responsabilidad Tecnica | Importancia (1-5) |
|---|---|---:|
| `docker-compose.yml` | Orquestacion oficial del stack local. | 5 |
| `services/ai_runtime` | Runtime conversacional LangGraph multitenant; autoridad principal de chat. | 5 |
| `services/bridges/generic-bridge` | Adapter fino para verticales no realtor hacia `ai-runtime`. | 4 |
| `services/bridges/property-bridge` | Adapter fino del vertical realtor hacia `ai-runtime`. | 4 |
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
| `services/agent-core` | Legacy; no es el cerebro activo del compose actual. |
| `services/inference-stack-v2` | Legacy archivado o compatibilidad historica. |
| `services/etl-processor` | Deprecado. |
| `services/ai-agents` | Exploracion; no participa en el runtime operativo. |

## 3. ARQUITECTURA CORE

- `ai-runtime` resuelve tenant, vertical, bridge y estado de sesion.
- `property-bridge` solo aplica a vertical `realtor`.
- `generic-bridge` aplica a `healthcare` y `legal`.
- `scoring-core` permanece separado y no debe absorber decisiones conversacionales.
- `chat-web-renderer` es consumidor/canal, no autoridad de negocio.
- Toda operacion conversacional debe mantener scope por `client_id`.

## 4. SERVICIOS DOCKER ACTIVOS

```text
datasyncsa-web
redis
postgres
ai-runtime
generic-bridge
portainer
admin-console-api
admin-console-web
chat-web-renderer-api
etl-docs-worker
property-bridge
scoring-core
test-ui
etl-docs
scoring-core-worker
chat-web-renderer-ui
```

## 5. ENTRY POINTS PRINCIPALES

- `services/ai_runtime/main.py`
- `services/scoring-core/main.py`
- `services/bridges/generic-bridge/main.py`
- `services/bridges/property-bridge/main.py`
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
