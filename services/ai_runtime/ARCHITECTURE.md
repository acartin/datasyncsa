# Datasyncsa AI Architecture

Documento de orientacion del runtime conversacional activo.

Precedencia si hay contradiccion:

1. codigo ejecutable vigente
2. `docs/AI_RUNTIME_PROMPT_RUNTIME.md` para carga/composicion de prompts
3. builders/routers del grafo y diagramas vivos en `services/ai_runtime/docs/graphs/`
4. este documento

## Objetivo

`services/ai_runtime` define el runtime conversacional multitenant activo de Datasyncsa AI con dos grafos LangGraph:

- `grafo_realtor`
- `grafo_basico`

El servicio es `multitenant-first`: ninguna operacion se ejecuta sin `client_id`, toda sesion se hidrata con `tenant_config`, y Redis/PostgreSQL se consultan con scope tenant desde la base del runtime.

## Principios Innegociables

1. `client_id` vive en el estado desde el primer turno.
2. El estado es acumulativo y se persiste por sesion.
3. Los prompts se componen en runtime como `stable_prefix + dynamic_context`.
   - `tone_prompt` del tenant es opcional
   - `analyze_turn`, `intent_detector` y `synthesis_prompt` son prompts locales por vertical
   - `lead_scoring_prompts` y `tone_prompt` siguen siendo configuracion externa
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
- `domain/ports.py`: puertos shared del runtime y contenedor `GraphDependencies`.
- `domain/policies.py`: hooks neutrales que cada vertical inyecta en `_shared`.
- `domain/vertical_adapters.py`: bundles de dependencias especificas por vertical.
- `config/tenant_loader.py`: carga y cache de tenant.
- `config/prompt_composer.py`: tone + vertical + context.
- `runtime/bootstrap.py`: wiring por defecto.
- `runtime/service.py`: bootstrap de sesion e invocacion del grafo.
- `runtime/turn_trace.py`: trazado por turno para nodos, routers y LLM.
- `verticals.py`: registro explicito de `VerticalSpec`, `state_model`, `graph_builder` y `policy`.
- `docs/graphs/**`: diagramas exportados del `grafo_basico` y `grafo_realtor`.
- `web/turn_trace/**`: consola web minima para inspeccionar trazas del runtime.
- `graph/_shared/**`: nodos, routers, prompts y tools comunes.
- `graph/_shared/nodes/mail_node.py`: implementacion compartida del handoff mail.
- `graph/generic/**`: builder y nodos del vertical reducido.
- `graph/healthcare/**`, `graph/legal/**`, `graph/insurance/**`: prompts semanticos propietarios por vertical.
- `graph/realtor/**`: builder, prompts y herramientas del vertical completo.
- `rag/**`: repositorios pgvector aislados por tenant.
- `workers/lead_worker.py`: worker fire-and-forget placeholder v1.

## Flujo de Entrada

### Entrada directa al runtime

1. El cliente de canal llama directo a `ai-runtime`.
2. Puede omitir `flow`; si lo hace, `ConversationRuntime` lo resuelve por vertical.
3. Si envía `flow=realtor_flow`, `GraphRegistry` exige `vertical=realtor`.
4. Si envía `flow=basic_flow`, `GraphRegistry` exige `vertical in {healthcare, legal, insurance}`.
5. Se hidrata o recupera sesion y se ejecuta `grafo_realtor` o `grafo_basico`.

## Estado Canonico

El estado esta modelado en `domain/state.py` y contiene:

- sesion: `session_id`, `conversation_id`, `user_id`, `client_id`, `vertical`, `flow`, `current_turn`
- prompts/config: `capabilities`, `tenant_config`
- referencias: `resolved_references`, `pending_clarification`, `clarification_attempts`
- cola: `intent_queue`, `active_intent`, `completed_intents`, `turn_outputs`
- lead: `lead_advisor`, `lead`, `escalacion`
- cita: `cita`
- salida: `final_response`
- realtor state model:
  - `search_filters`, `inventory`, `last_search_results`, `last_mentioned`
  - `active_comparison`, `focus_scope`, `search_attempts`
  - `cards_shown`, `cards_mode`, `render_mode`, `ui_payload`
  - `financial_context`

Importante:

- `_shared` no debe leer directamente campos realtor-only para interpretar turnos.
- Los nodos shared consumen hooks neutrales de `VerticalPolicy` y trabajan con snapshots como:
  - `search_context`
  - `visible_reference_ids`
  - `visible_reference_items`
  - `reference_candidates`
  - `focused_entity`
- El formato serializado del estado realtor no cambia: los campos realtor siguen viviendo en `RealtorGraphState`, pero su semantica ya no debe estar cableada dentro de `_shared`.

## Seams por Vertical

La extension multi-vertical del runtime hoy se hace por tres costuras explicitas:

1. `VerticalSpec` en `verticals.py`
   - registra `state_model`, `graph_builder`, `policy`, `turn_frame_builder`, `required_fields` y `scoring_criteria`
2. `VerticalPolicy` en `domain/policies.py`
   - expone hooks neutrales para:
     - snapshots de contexto de busqueda
     - referencias visibles y candidatos de referencia
     - entidad enfocada
     - quick actions
     - journey y lead capture progresivo
     - coerciones/turn policies del vertical
3. `VerticalAdapters` en `domain/vertical_adapters.py`
   - `GraphDependencies` conserva solo puertos shared
   - los adapters verticales se resuelven por slug con `dependencies.get_adapters(vertical)`
   - `RealtorAdapters` encapsula hoy `property_repository`

Guardrail:

- un vertical nuevo no debe requerir editar nodos shared para introducir semantica de dominio.
- si un comportamiento depende del vertical, debe entrar por `VerticalPolicy`, `VerticalAdapters` o por un nodo propio del vertical.

## LangGraph Control Loops

Los diagramas renderizados del estado actual del runtime viven en `services/ai_runtime/docs/graphs/` y se regeneran desde `services/ai_runtime/scripts/export_graph_diagrams.py`.

Esta seccion resume la topologia comun. La fuente exacta de edges y routers vive en:

- `services/ai_runtime/graph/generic/graph.py`
- `services/ai_runtime/graph/realtor/graph.py`
- `services/ai_runtime/graph/_shared/routers/common.py`
- `services/ai_runtime/graph/realtor/routers/routes.py`

## Turn Trace

Para desarrollo, `ai-runtime` registra una traza JSON por turno en `/app/log/turn-traces` y expone una consola en `/api/v1/debug/turn-trace/`.

Cada turno registra:

- inicio y cierre del turno
- entrada y salida de cada nodo
- decisiones de routers
- prompts y respuestas del puerto LLM
- resumen del estado antes y despues de cada paso

### Shared flow

`START -> analyze_turn`

Routers compartidos:

- `after_analyze_turn`
  - `ask_clarification`
  - `collect_lead_data`
  - `capture_memory_entities`
- `after_capture_memory`
  - `memory_lookup`
  - `route_next_intent`
  - `lead_advisor`
  - `synthesize`
- `after_memory_lookup`
  - `route_next_intent`
  - `lead_advisor`
  - `synthesize`
  - `end`
- `after_check_queue`
  - `route_next_intent`
  - `lead_advisor`

### Clarification loop

- entrada: referencia ambigua o dato faltante
- una sola pregunta por turno
- maximo 3 intentos
- al llegar al limite, pasa a `collect_lead_data`

### Intent queue

- `analyze_turn` interpreta el turno y devuelve `turn_analysis` con `intent_plan` inicial
- si el mensaje trae una quick action, `_shared` delega en `VerticalPolicy.handle_quick_action(...)`
- codigo deterministico normaliza referencias y alimenta `intent_queue`
- `route_next_intent` elige el siguiente intent ejecutable
- cada nodo de capacidad cierra explicitamente `running -> done`
- `check_queue` decide si quedan intents pendientes

### Realtor enrich/reanalyze loop

- `search`
- si `0 resultados` y `search_attempts < 3` -> `search` otra vez
- si `0 resultados` y `search_attempts >= 3` -> `lead_advisor`
- si hay resultados -> `render_cards` -> `check_queue`
- `render_mode` y `cards_mode` se deciden downstream, no en el router

## Separacion de Responsabilidades

### LLM

- `analyze_turn`: interpreta el turno; es responsabilidad semantica del vertical
- `route_next_intent`: solo condiciones lazy
- `capture_memory_entities`: extrae memoria canonica del turno
- `lead_advisor`: scoring y estrategia de captura
- `synthesize`: respuesta final
- `compare_properties`: solo redaccion
- `llm_recommend`: solo redaccion
- `text_to_sql`: traduccion controlada a SQL
- `collect_lead_data` y `collect_appointment_data`: extraccion conversacional

### Codigo deterministico

- resolver referencias a IDs
- filtrar capabilities por tenant
- manejar la cola y dependencias
- delegar semantica vertical via `VerticalPolicy` cuando `_shared` necesita contexto de dominio
- reglas `lead_advisor`
- `render_cards`
- `financial_calc`
- `assign_agent`
- `mail_node` compartido para handoff appointment confirmation
- aislamiento `client_id` en Redis y PostgreSQL

## Prompt Runtime

`prompt_composer.compose(node_type, tenant_config, vertical, context)` compone:

1. `tone_prompt` del tenant
2. prompt del vertical o prompt base segun `node_type`
3. contexto JSON serializado del turno

El detalle canonico de carga, tablas, fallbacks y ownership vive en `docs/AI_RUNTIME_PROMPT_RUNTIME.md`.

Resumen minimo:

- `analyze_turn`, `intent_detector` y `synthesis_prompt` se resuelven por vertical desde codigo local
- `_shared/prompts` solo debe contener prompts tecnicos neutrales
- `tone_prompt` se carga por tenant desde `lead_ai_prompts`
- `lead_scoring_evaluator` usa el `scoring_profile` cargado en `TenantConfig`

Guardrail:

- Los prompts semanticos de negocio no deben vivir en `graph/_shared/prompts`.
- `analyze_turn` e `intent_detector` son `vertical-owned`.
- `shared` solo puede contener prompts tecnicos neutrales.

## Persistencia y Caches

### Redis

- `SessionStore`: estado del grafo
- `LeadStore`: scores y campos extraidos
- `TenantCache`: config y agentes

### PostgreSQL

- `TenantRepository`: config editable por tenant
- `ConversationRepository`: historial entre sesiones
- `PropertyRepository`: consulta de inventario realtor, expuesta via `RealtorAdapters`
- `AgentRepository`: asignacion de agentes
- `AgencyRAGRepository`: FAQ por tenant
- `DocumentsRAGRepository`: documentos por tenant

## Dependencias y Wiring

`runtime/bootstrap.py` construye un solo `GraphDependencies` con:

- puertos shared: LLM, stores, tenant/cache, repos de conversacion/agentes, RAG, mailer, worker dispatcher, trace store
- `vertical_adapters` por slug:
  - `realtor -> RealtorAdapters(property_repository=...)`
  - `healthcare/legal/insurance -> adapters placeholder vacios`

Esto permite bootear verticales generic sin requerir dependencias realtor-only.

## Lead Worker

`workers/lead_worker.py` deja el contrato v1 para:

- scorear `apertura`, `intencion`, `urgencia`, `match`, `solvencia`
- extraer campos conversacionales
- actualizar Redis sin bloquear el turno principal

El dispatcher actual en `runtime/bootstrap.py` es placeholder. El contrato ya esta listo para migrarlo a RQ, Celery o un bus interno despues.
