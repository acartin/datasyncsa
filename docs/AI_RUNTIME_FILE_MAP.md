# AI Runtime File Map

Mapa operativo del stack conversacional activo.

## Runtime

`services/ai_runtime/`

- `main.py`
- `api.py`
- `config/tenant_loader.py`
- `config/prompt_composer.py`
- `domain/contracts.py`
- `domain/state.py`
- `graph/registry.py`
- `graph/_shared/**`
- `graph/generic/**`
- `graph/realtor/**`
- `rag/agency/repository.py`
- `rag/documents/repository.py`
- `runtime/bootstrap.py`
- `runtime/service.py`
- `runtime/settings.py`
- `workers/lead_worker.py`

## Data layer compartida

`services/data/`

- `cache/session_store.py`
- `cache/lead_store.py`
- `cache/tenant_cache.py`
- `repositories/base.py`
- `repositories/tenant_repository.py`
- `repositories/conversation_repository.py`
- `repositories/property_repository.py`
- `repositories/agent_repository.py`

## Bridges

`services/bridges/`

- `generic-bridge/main.py`
- `property-bridge/main.py`
- `_shared/` reservado para tipos o utilidades comunes

## Canales consumidores

- `services/web/chat-web-renderer/backend/app/core/inference_bridge.py`
- `services/web/chat-web-renderer/backend/app/core/memory_reset.py`
- `services/web/chat-web-renderer/backend/app/main.py`

## Boundaries

- Conversacion y decision: `ai-runtime`
- Adaptacion de contratos/canal: `bridges` y `chat-web-renderer`
- Scoring asincrono: `scoring-core`
- Ingesta documental y reseteo best-effort: `etl-docs`
