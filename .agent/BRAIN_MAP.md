# BRAIN_MAP

- Generated UTC: `2026-02-27T21:45:51Z`
- Repo root: `/srv/datasyncsa`
- Git branch: `HETZNER-LOCAL-2026-02-28`
- Git commit: `9759548`

## 1. MAPA DE INTENCIONES (DIRECTORIO)

| Carpeta | Responsabilidad Técnica | Importancia (1-5) |
|---|---|---:|
| `docker-compose.yml` | Orquestación de servicios (DB, Redis, APIs, bridges, UI, ETL). | 5 |
| `services/web/admin-console` | BFF FastAPI + renderer SDUI para consola operativa multi-tenant. | 5 |
| `services/web/realtor-chat` | Bridge y widget chat SDUI inmobiliario. | 5 |
| `services/inference-stack-v2/inference-core-v2` | Motor v2 de chat/scoring por vertical/modelo/prompt. | 5 |
| `services/inference-stack-v2/semantic-adapter-v2` | Recuperación semántica v2 (RAG retriever). | 5 |
| `services/etl-docs` | Ingesta documental, colas RQ y vectorización. | 5 |
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
- `services/web/realtor-chat/backend/app/main.py`
- `services/inference-stack-v2/inference-core-v2/main.py`
- `services/inference-stack-v2/semantic-adapter-v2/main.py`
- `services/etl-docs/main.py`

## 4. ENTIDADES CRÍTICAS (DB)

- Tenancy/seguridad: `lead_clients`, `auth_users`, `auth_roles`, `auth_client_user`
- Leads/conversación: `lead_leads`, `lead_conversations`, `lead_statuses`, `lead_sources`
- Scoring v2: `lead_scorecards`, `lead_score_items`, `lead_scoring_models`, `lead_scoring_criteria`, `lead_scoring_bands`, `lead_scoring_prompts`
- RAG/documentos: `ai_knowledge_documents`, `ai_vectors`
