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
10. `services/ai_runtime/graph/registry.py`
Lectura adicional segun el caso:

- `services/data/repositories/base.py`
- `services/data/cache/session_store.py`
- `services/web/chat-web-renderer/backend/app/core/runtime_client.py`
- `services/web/chat-web-renderer/backend/app/core/memory_reset.py`

## Supuestos Operativos

- `ai-runtime` es la unica autoridad conversacional del compose actual
- `client_id` entra desde el primer turno y nunca se pierde
- `tenant_config` se hidrata al inicio de la sesion y se cachea
- el estado del grafo vive en Redis y se persiste por sesion
- el runtime selecciona `grafo_realtor` o `grafo_generico` segun vertical/flow
- `scoring-core` corre aparte y no debe bloquear decisiones de chat

## Restricciones de Cambio

- no mover logica de negocio desde `ai-runtime` hacia frontend o componentes legacy
- no reintroducir dependencias hacia componentes legacy como `services/legacy/agent-core` o `services/legacy/inference-stack-v2`
- no asumir heuristicas hardcodeadas para resolver intents, verticales o referencias
- si cambias naming o wiring Docker, tambien debes actualizar `.env.example` y `.agent/*`
