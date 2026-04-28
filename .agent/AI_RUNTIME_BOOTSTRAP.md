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
