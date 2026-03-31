# Datasyncsa AI Architecture

## Objetivo

`services/ai_runtime` define el runtime conversacional multitenant nuevo de Datasyncsa AI con dos grafos LangGraph:

- `grafo_realtor`
- `grafo_basico`

El servicio es `multitenant-first`: ninguna operacion se ejecuta sin `client_id`, toda sesion se hidrata con `tenant_config`, y Redis/PostgreSQL se consultan con scope tenant desde la base del runtime.

## Principios Innegociables

1. `client_id` vive en el estado desde el primer turno.
2. El estado es acumulativo y se persiste por sesion.
3. Prompts se componen en runtime con tres capas:
   - `tone_prompt` del tenant
   - prompt base del vertical
   - contexto del turno
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
- `domain/ports.py`: puertos abstractos para LLM, Redis, PG, RAG, mail y workers.
- `config/tenant_loader.py`: carga y cache de tenant.
- `config/prompt_composer.py`: tone + vertical + context.
- `runtime/bootstrap.py`: wiring por defecto.
- `runtime/service.py`: bootstrap de sesion e invocacion del grafo.
- `runtime/turn_trace.py`: trazado por turno para nodos, routers y LLM.
- `docs/graphs/**`: diagramas exportados del `grafo_basico` y `grafo_realtor`.
- `web/turn_trace/**`: consola web minima para inspeccionar trazas del runtime.
- `graph/_shared/**`: nodos, routers, prompts y tools comunes.
- `graph/generic/**`: builder y nodos del vertical reducido.
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
- realtor only:
  - `search_filters`, `inventory`, `last_search_results`, `last_mentioned`
  - `active_comparison`, `focus_scope`, `search_attempts`
  - `cards_shown`, `cards_mode`, `render_mode`, `ui_payload`
  - `financial_context`

## LangGraph Control Loops

Los diagramas renderizados del estado actual del runtime viven en `services/ai_runtime/docs/graphs/` y se regeneran desde `services/ai_runtime/scripts/export_graph_diagrams.py`.

## Turn Trace

Para desarrollo, `ai-runtime` registra una traza JSON por turno en `/app/log/turn-traces` y expone una consola en `/api/v1/debug/turn-trace/`.

Cada turno registra:

- inicio y cierre del turno
- entrada y salida de cada nodo
- decisiones de routers
- prompts y respuestas del puerto LLM
- resumen del estado antes y despues de cada paso

### Shared flow

`START -> resolve_references -> classify_intent -> route_next_intent`

Routers compartidos:

- `after_resolve_references`
  - `ask_clarification`
  - `collect_lead_data`
  - `classify_intent`
- `after_classify_intent`
  - `route_next_intent`
  - `lead_advisor`
- `after_check_queue`
  - `route_next_intent`
  - `lead_advisor`

### Clarification loop

- entrada: referencia ambigua o dato faltante
- una sola pregunta por turno
- maximo 3 intentos
- al llegar al limite, pasa a `collect_lead_data`

### Intent queue

- `classify_intent` genera hasta 4 intents
- `route_next_intent` elige el siguiente intent ejecutable
- cada nodo de capacidad cierra explicitamente `running -> done`
- `check_queue` decide si quedan intents pendientes

### Realtor enrich/reanalyze loop

- `search`
- si `0 resultados` y `attempts < 3` -> `search` otra vez con filtros relajados
- si `0 < resultados < 4` -> `render_mode=text`
- si `>= 4` -> `render_cards`

## Separacion de Responsabilidades

### LLM

- `resolve_references`: clasifica tipo de referencia
- `classify_intent`: detecta intenciones
- `route_next_intent`: solo condiciones lazy
- `synthesize`: respuesta final
- `compare_properties`: solo redaccion
- `llm_recommend`: solo redaccion
- `text_to_sql`: traduccion controlada a SQL
- `collect_lead_data` y `collect_appointment_data`: extraccion conversacional

### Codigo deterministico

- resolver referencias a IDs
- filtrar capabilities por tenant
- manejar la cola y dependencias
- reglas `lead_advisor`
- `render_cards`
- `financial_calc`
- `assign_agent`
- aislamiento `client_id` en Redis y PostgreSQL

## Prompt Runtime

`prompt_composer.compose(node_type, tenant_config, vertical, context)` aplica:

1. `tone_prompt` del tenant
2. prompt del vertical o prompt base segun `node_type`
3. contexto JSON serializado del turno

Prompts incluidos:

- base:
  - `reference_classifier_prompt.py`
  - `intent_detector_prompt.py`
  - `lazy_condition_evaluator_prompt.py`
  - `clarification_prompt.py`
  - `lead_data_collector_prompt.py`
- vertical:
  - `vertical/realtor/{plan,synthesis}_prompt.py`
  - `vertical/healthcare/{plan,synthesis}_prompt.py`
  - `vertical/legal/{plan,synthesis}_prompt.py`
- realtor:
  - `text_to_sql_prompt.py`
  - `comparison_synthesizer_prompt.py`
  - `recommendation_prompt.py`
  - `appointment_data_collector_prompt.py`

## Persistencia y Caches

### Redis

- `SessionStore`: estado del grafo
- `LeadStore`: scores y campos extraidos
- `TenantCache`: config y agentes

### PostgreSQL

- `TenantRepository`: config editable por tenant
- `ConversationRepository`: historial entre sesiones
- `PropertyRepository`: consulta de inventario realtor
- `AgentRepository`: asignacion de agentes
- `AgencyRAGRepository`: FAQ por tenant
- `DocumentsRAGRepository`: documentos por tenant

## Lead Worker

`workers/lead_worker.py` deja el contrato v1 para:

- scorear `apertura`, `intencion`, `urgencia`, `match`, `solvencia`
- extraer campos conversacionales
- actualizar Redis sin bloquear el turno principal

El dispatcher actual en `runtime/bootstrap.py` es placeholder. El contrato ya esta listo para migrarlo a RQ, Celery o un bus interno despues.

## Fases de Implementacion

### Fase 1

Lista en este scaffold:

- contratos
- estado
- `tenant_loader`
- `prompt_composer`
- bootstrap FastAPI
- stores/repositorios

### Fase 2

Lista en este scaffold:

- `grafo_basico`
- nodos compartidos
- `rag_agencia`
- `captura_lead`
- `agendar`

### Fase 3

Lista en este scaffold:

- `grafo_realtor`
- `search`
- `render_cards`
- `financial_calc`
- `rag_agencia`
- `rag_docs`

### Fase 4

Lista en este scaffold:

- comparacion
- recomendacion
- agendamiento
- `lead_advisor`
- `mensajear` placeholder
- cierre explicito de intents en cola

### Fase 5

Preparado para la siguiente iteracion:

- conectar proveedor LLM real en `runtime/llm.py`
- conectar embeddings reales para RAG
- reemplazar dispatcher inline por cola asincrona
- persistencia final Redis -> PostgreSQL al cierre
- historial anaforico mas rico con snapshots de propiedades
