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

## Guardrail Conversacional Realtor

- Bateria intensiva canonica: `tests/sandbox/realtor/realtor_v3_regression_battery.py`
- Uso:
  - validar regresiones conductuales del vertical realtor en `inference-core-v3`
  - cubrir contratos de `search`, `refine`, `inventory`, `price_range`, referencias a cards, memoria de busqueda, RAG post-busqueda y captura progresiva de lead
- Regla operativa:
  - si se toca la logica conversacional/realtor de `services/inference-stack-v2/inference-core-v3/**`, no basta con unit tests; esta bateria debe correrse como validacion end-to-end
- Salida:
  - imprime escenarios con `issues`
  - puede guardar JSON en `/tmp/realtor_v3_battery.json`

## 4. ENTIDADES CRÍTICAS (DB)

- Tenancy/seguridad: `lead_clients`, `auth_users`, `auth_roles`, `auth_client_user`
- Leads/conversación: `lead_leads`, `lead_conversations`, `lead_statuses`, `lead_sources`
- Scoring v2: `lead_scorecards`, `lead_score_items`, `lead_scoring_models`, `lead_scoring_criteria`, `lead_scoring_bands`, `lead_scoring_prompts`
- RAG/documentos: `ai_knowledge_documents`, `ai_vectors`
