# BRAIN_MAP

- Generated UTC: `2026-04-01T20:09:03Z`
- Repo root: `/srv/datasyncsa`
- Git branch: `HETZNER-LOCAL-2026-03-31`
- Git commit: `5705281`

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
- `scoring-core` permanece separado y no debe absorber decisiones conversacionales.
- `chat-web-renderer` es consumidor/canal, no autoridad de negocio.
- Toda operacion conversacional debe mantener scope por `client_id`.

## 4. SERVICIOS DOCKER ACTIVOS

```text
postgres
redis
ai-runtime
chat-web-renderer-api
chat-web-renderer-ui
datasyncsa-web
portainer
admin-console-api
admin-console-web
etl-docs
etl-docs-worker
scoring-core
scoring-core-worker
test-ui
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
