# Inference Core v3 Blueprint

Ultima actualizacion: `2026-03-07`

Este documento define el blueprint exacto para `inference-core-v3`.

Objetivo:

- convertir el core en un agente formal sobre grafo,
- centralizar la inteligencia en un solo runtime,
- hacer crecer tools sin volver a degradar la arquitectura,
- coordinar de forma coherente respuestas de:
  - RAG,
  - SQL,
  - vectores,
  - memoria conversacional,
  - integraciones externas,
- mantener respuestas naturales,
- y preservar control operativo, seguridad y multi-tenant.

## 1. Decisión arquitectónica

`inference-core-v3` debe construirse sobre `LangGraph`.

Razón:

- el sistema ya no es un chat simple;
- es un agente multi-tool, multi-flujo y multi-vertical a nivel de plataforma, con memoria y side-effects;
- hacerlo seguir creciendo en un orquestador artesanal volverá a degradarlo.

`LangGraph` aquí no se introduce como moda.

Se introduce para formalizar:

- el grafo de ejecución,
- el estado del turno,
- la coordinación entre planner, tools y synthesis,
- los checkpoints,
- la trazabilidad,
- y la extensibilidad de tools.

## 2. Principios no negociables

- Una sola autoridad del turno: `inference-core-v3`.
- Los bridges y renderers no piensan.
- Toda decisión de intent, tool usage y continuidad la toma el agente.
- Los tools no redactan copy conversacional.
- Los tools ejecutan y devuelven facts.
- La respuesta final visible al usuario se sintetiza en el agente.
- Toda conversación persistida debe coincidir con la respuesta final mostrada.
- Toda operación de datos debe estar aislada por `client_id`.
- No heurística hardcodeada para negocio, intent, ubicación o continuidad.
- Structured output obligatorio para planner/router/tool plans.
- El vertical no se decide por LLM; se resuelve determinísticamente desde `client_id`.

## 3. Topología objetivo

### Servicios

- `chat-web-renderer`
  - canal web y render SDUI
  - no lógica de negocio

- `generic-bridge-v2`
  - adapter fino para integraciones genéricas
  - no lógica de negocio

- `property-bridge-v2`
  - adapter fino para integraciones legacy de realtor
  - no lógica de negocio

- `semantic-adapter-v2`
  - tool service de retrieval semántico/vectorial

- `inference-core-v3`
  - agente soberano
  - runtime de grafo
  - prompt registry consumer
  - tool orchestrator
  - state manager del turno
  - persistence coordinator

### Regla de ownership

- `chat-web-renderer` transporta y renderiza.
- `semantic-adapter-v2` recupera.
- `executors` ejecutan.
- `inference-core-v3` decide.

## 4. Capas internas de v3

`inference-core-v3` debe tener estas capas internas:

1. `graph_runtime`
   - define nodos, edges, checkpoints y policies

2. `state_models`
   - define el estado tipado del turno

3. `prompt_runtime`
   - resuelve prompts por tenant, vertical y propósito

4. `tool_registry`
   - monta el registry efectivo de tools para el tenant/vertical activos

5. `executors`
   - SQL, retrieval, calendar, email, MCP, etc.

6. `synthesis`
   - convierte facts en respuesta natural final

7. `persistence`
   - conversación, snapshot, lead, scorecard, jobs

8. `observability`
   - trace por nodo, tool calls, latencias, errores, decisiones

## 5. Estado canónico del agente

El estado del grafo debe ser tipado y explícito.

Base sugerida:

```python
from typing import Any, Dict, List, Literal, Optional
from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    trace_id: str
    started_at_utc: str

    client_id: str
    vertical_slug: str
    channel: str
    channel_user_id: Optional[str]

    conversation_id: str
    lead_id: Optional[str]

    user_text: str
    user_metadata: Dict[str, Any]
    filters: Dict[str, Any]

    history: List[Dict[str, Any]]
    lead_snapshot: Dict[str, Any]
    conversation_snapshot: Dict[str, Any]

    conversation_extraction_result: Dict[str, Any]
    realtor_search_state: Dict[str, Any]

    prompt_bundle: Dict[str, str]
    policy_bundle: Dict[str, Any]
    vertical_graph_id: str
    effective_tool_registry: Dict[str, Any]

    route_mode: Literal["answer_only", "tool_required", "clarify", "handoff"]
    active_subflow: Literal["generic_answer", "generic_rag", "realtor_search", "workflow", "unknown"]
    intent: str

    planner_output: Dict[str, Any]
    tool_plan: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]
    execution_facts: Dict[str, Any]

    answer_text: str
    answer_components: List[Dict[str, Any]]

    scoring_action: Dict[str, Any]
    side_effects: List[Dict[str, Any]]

    final_status: Literal["completed", "clarification", "degraded", "failed"]
    errors: List[Dict[str, Any]]
```

## 6. Memory model

### Persistencia canónica por concern

- `lead_conversations.messages`
  - conversación final real

- `lead_conversations.context_snapshot`
  - estado vivo del turno/conversación

- `lead_scorecards.extraction_result`
  - histórico de extracción/scoring

- `lead_leads`
  - datos operativos de lead ya existentes

### Estado conversacional mínimo obligatorio

Dentro de `context_snapshot`:

```json
{
  "conversation_extraction_result": {
    "common": {},
    "vertical": {}
  },
  "realtor_search_state": {},
  "last_agent_route": {},
  "last_tool_results": {}
}
```

### Regla de memoria

- `common`
  - usa exactamente las llaves `extracted_*` del prompt del vertical

- `vertical`
  - guarda estado operativo específico del vertical

No introducir un segundo esquema semántico paralelo.

## 7. Nodos exactos del grafo

## 7.1 Root graph

Orden exacto:

1. `hydrate_request`
2. `load_tenant_runtime`
3. `load_conversation_state`
4. `merge_live_memory`
5. `route_turn`
6. `dispatch_vertical_subflow`
7. `synthesize_final_answer`
8. `persist_final_turn`
9. `enqueue_side_effects`
10. `return_response`

## 7.2 Nodo: `hydrate_request`

Responsabilidad:

- validar request,
- asignar `trace_id`,
- garantizar `conversation_id`,
- normalizar metadata de canal,
- poblar estado inicial.

No usa LLM.

## 7.3 Nodo: `load_tenant_runtime`

Responsabilidad:

- resolver tenant,
- resolver vertical,
- resolver prompts activos,
- resolver policies/feature flags,
- montar el `effective_tool_registry` para ese tenant,
- seleccionar el `vertical_graph_id`,
- resolver modelo y configuraciones de output.

Fuentes:

- `lead_clients`
- `lead_ai_prompts`
- `lead_scoring_prompts`
- cache Redis

No usa LLM.

### Cache de runtime

`load_tenant_runtime` debe cachear agresivamente en Redis un bundle completo por `client_id`.

Ese bundle debe incluir:

- `vertical_slug`
- `vertical_graph_id`
- `prompt_bundle`
- `policy_bundle`
- `effective_tool_registry`
- metadata del modelo

Regla:

- no hay invalidación automática por runtime;
- la invalidación es administrativa y explícita cuando cambian prompts, flags o configuración del tenant.

## 7.4 Nodo: `load_conversation_state`

Responsabilidad:

- cargar historial reciente,
- cargar `context_snapshot`,
- cargar `lead_snapshot`,
- cargar counters y datos operativos necesarios.

No usa LLM.

## 7.5 Nodo: `merge_live_memory`

Responsabilidad:

- consolidar en memoria:
  - `conversation_extraction_result`
  - `realtor_search_state`
  - datos confirmados del lead
- aplicar merge monotónico:
  - no pisar con vacíos,
  - no inventar,
  - preservar hechos confirmados.

No usa LLM.

## 7.6 Nodo: `route_turn`

Responsabilidad:

- decidir, dentro del vertical ya resuelto para el tenant:
  - `route_mode`
  - `intent`
  - `active_subflow`
- decidir si hace falta:
  - tool
  - aclaración
  - respuesta directa

Sí usa LLM.

Contrato obligatorio:

- structured output
- schema estricto
- sin parseo de texto libre

Salida sugerida:

```json
{
  "route_mode": "tool_required",
  "intent": "PROPERTY_SEARCH",
  "active_subflow": "realtor_search",
  "reasoning": "El usuario quiere refinar una búsqueda inmobiliaria activa.",
  "requires_tools": true,
  "tool_plan": []
}
```

Regla:

- `route_turn` nunca decide el vertical;
- consume `vertical_slug`, `vertical_graph_id`, `policy_bundle` y `effective_tool_registry` ya resueltos.

## 7.7 Nodo: `dispatch_vertical_subflow`

Responsabilidad:

- entrar al subflow correcto dentro del grafo vertical ya seleccionado;
- no cambia de vertical;
- solo enruta a la rama correcta del turno.

Ejemplo:

- tenant realtor:
  - `realtor_search`
  - `generic_answer`
  - `generic_rag`
  - `workflow`

- tenant generic:
  - `generic_answer`
  - `generic_rag`
  - `workflow` si está habilitado

## 7.8 Subflow `generic_answer`

Nodos:

1. `generic_answer_plan`
2. `generic_answer_synthesis`

Uso típico:

- preguntas generales,
- memoria básica sin retrieval,
- respuestas directas sin tool.

## 7.9 Subflow `generic_rag`

Nodos:

1. `generic_rag_plan`
2. `generic_tool_dispatch`
3. `generic_answer_synthesis`

Uso típico:

- dudas informativas,
- respuestas con retrieval vectorial,
- coordinación de facts documentales.

## 7.10 Subflow `realtor_search`

Nodos:

1. `realtor_plan`
2. `realtor_tool_dispatch`
3. `realtor_answer_synthesis`

### Nodo: `realtor_plan`

Responsabilidad:

- decidir intent realtor
- decidir si va a SQL, a RAG o a aclaración
- construir `tool_plan`
- generar `search_summary`
- generar `filters` estructurados

Structured output obligatorio:

```json
{
  "intent": "PROPERTY_SEARCH",
  "mode": "sql",
  "search_summary": "casas en Heredia con dos habitaciones",
  "filters": {
    "desired_location": "Heredia",
    "property_type": "casa",
    "bedrooms_min": 2,
    "listing_intent": "buy"
  },
  "tool_plan": [
    {
      "tool": "realtor_sql_search",
      "arguments": {
        "sql": "SELECT ...",
        "search_summary": "casas en Heredia con dos habitaciones",
        "filters": {
          "desired_location": "Heredia",
          "property_type": "casa",
          "bedrooms_min": 2
        }
      }
    }
  ]
}
```

### Nodo: `realtor_tool_dispatch`

Responsabilidad:

- ejecutar tools del plan
- en paralelo cuando aplique
- consolidar `execution_facts`

No redacta copy.

### Nodo: `realtor_answer_synthesis`

Responsabilidad:

- usar:
  - `user_text`
  - `history`
  - `conversation_extraction_result`
  - `realtor_search_state`
  - `execution_facts`
- redactar la respuesta final natural

Structured output opcional:

- puede devolver solo texto final,
- o texto + metadata de UI si se desea,
- pero con schema validado.

## 7.11 Subflow `workflow`

Este subflow debe nacer desde v3 aunque algunas tools entren después.

No es un dominio autónomo.

Es una rama opcional dentro del vertical activo y solo existe si el tenant/vertical lo habilitan en políticas.

Nodos:

1. `workflow_plan`
2. `workflow_tool_dispatch`
3. `workflow_answer_synthesis`

Uso:

- agendar cita
- enviar correo
- seguimiento
- herramientas MCP

## 7.12 Nodo: `persist_final_turn`

Responsabilidad:

- guardar la respuesta final real,
- actualizar `context_snapshot`,
- actualizar memoria conversacional,
- actualizar lead cuando corresponda,
- dejar consistente lo mostrado al usuario.

Regla:

- una sola persistencia final por turno
- no guardar una respuesta preliminar distinta

## 7.13 Nodo: `enqueue_side_effects`

Responsabilidad:

- disparar scoring async
- disparar email async si aplica
- disparar syncs no bloqueantes

No modifica la respuesta final ya cerrada.

## 8. Tool registry exacto

Los tools de v3 deben ser explícitos, tipados y registrables.

El registry efectivo no es global en runtime.

Debe construirse por tenant dentro de `load_tenant_runtime`, usando:

- `vertical_slug`
- políticas del tenant
- flags operativos
- permisos del vertical

Si existe un catálogo base de tools compartido, solo se usa como base de construcción.
Lo que el agente ve y puede invocar es el `effective_tool_registry` del tenant.

Interfaz sugerida:

```python
class ToolSpec(TypedDict):
    name: str
    verticals: list[str]
    enabled_by_default: bool
    input_schema: dict
    output_schema: dict
    timeout_ms: int
    idempotent: bool
    executor_ref: str
```

### Tools base de v3 para tenant realtor

1. `semantic_retrieval`
   - wrapper hacia `semantic-adapter-v2`

2. `realtor_sql_search`
   - ejecuta búsqueda de propiedades

3. `realtor_inventory_count`
   - cuenta inventario

4. `realtor_price_range`
   - min/max de precios

5. `conversation_memory_read`
   - lectura de snapshot útil

6. `lead_snapshot_read`
   - lectura de datos del lead

7. `scoring_enqueue`
   - side-effect no bloqueante

### Tools fase 2

8. `calendar_availability`
9. `calendar_create_event`
10. `email_prepare`
11. `email_send`
12. `mcp_call`
13. `knowledge_document_lookup`

Regla:

- un tenant realtor no ve tools de otros verticales salvo que su configuración lo permita explícitamente;
- un tenant generic no ve tools realtor salvo que su vertical los incluya;
- `workflow` tools existen solo si el vertical/policy del tenant los habilita.

## 9. Executors determinísticos

Los ejecutores viven debajo del tool registry.

No son agentes.

No redactan respuestas.

### Obligatorios en v3

- `RealtorTurnExecutor`
- `SemanticRetrievalExecutor`
- `ConversationMemoryExecutor`
- `LeadSnapshotExecutor`
- `CalendarExecutor`
- `EmailExecutor`
- `MCPExecutor`

### Regla de ejecutores

Pueden hardcodear:

- validación
- seguridad
- tenant scope
- timeouts
- transformación a facts
- componentes UI canónicos

No pueden hardcodear:

- copy
- intent
- continuidad
- priorización conversacional

## 10. Prompt runtime

`inference-core-v3` debe resolver prompts por propósito, no por mezcla informal.

Slugs sugeridos por propósito:

- `agent_router_system`
- `generic_planner_system`
- `generic_answer_synthesis`
- `realtor_planner_system`
- `realtor_answer_synthesis`
- `workflow_planner_system`
- `workflow_answer_synthesis`
- `email_generation_system`
- `calendar_confirmation_system`

### Regla de prompting

- prompts por tenant en BD
- fallback global solo si no existe override
- guardrails de seguridad añadidos por runtime
- structured output schema siempre que el nodo lo requiera

## 11. Coordinación de RAG, SQL y vectores

La coordinación correcta debe ser esta, dentro del vertical ya resuelto:

- el planner decide si necesita facts de:
  - SQL
  - vectores
  - ambos
- el dispatcher ejecuta
- la synthesis final combina results

Casos dentro del vertical:

1. `realtor_search`
   - SQL

2. `generic_rag`
   - retrieval vectorial

3. `hybrid`
   - SQL + vector retrieval
   - por ejemplo:
     - pregunta sobre proceso de compra mientras compara propiedades

4. `workflow`
   - memoria + calendar/email/MCP

## 12. Respuesta canónica

El contrato final del core debe seguir devolviendo:

- `answer`
- `components`
- `intent`
- `conversationId`
- `leadId`
- metadata operativa

Pero internamente el agente debe producir:

```json
{
  "answer_text": "...",
  "components": [],
  "final_status": "completed",
  "execution_facts": {},
  "side_effects": []
}
```

## 13. Observabilidad moderna

Cada nodo debe loggear:

- `trace_id`
- `conversation_id`
- `client_id`
- `node_name`
- `duration_ms`
- `planner_json_valid`
- `tool_name`
- `tool_status`
- `vertical_slug`
- `active_subflow`
- `final_status`

Además:

- traces persistibles por turno
- soporte para inspección de tool plan y tool results
- errores estructurados por nodo

## 14. Rendimiento percibido

Objetivo:

- mantener o mejorar la latencia percibida frente a v2
- mejorar drásticamente la coherencia

Reglas:

- usar modelo barato para router/planner
- usar synthesis una sola vez cuando haga falta
- paralelizar tools cuando sea seguro
- evitar múltiples llamadas LLM innecesarias
- side-effects fuera del camino crítico

## 15. Estrategia de migración exacta

## Fase 0. Freeze de v2

- `v2` solo acepta bugfixes críticos
- no meter nuevas tools complejas en `ScoringOrchestrator`

## Fase 1. Skeleton de v3

- crear `services/inference-stack-v3/inference-core-v3`
- montar LangGraph
- definir `AgentState`
- definir `ToolSpec`
- crear endpoints `/api/v3/chat`

## Fase 2. Port de infraestructura reusable

Reusar desde v2:

- repositorios DB
- cache service
- prompt resolution
- `RealtorTurnExecutor`
- integración con `semantic-adapter-v2`
- scoring job service

## Fase 3. Root graph operativo

Implementar:

- `hydrate_request`
- `load_tenant_runtime`
- `load_conversation_state`
- `merge_live_memory`
- `route_turn`
- `dispatch_vertical_subflow`
- `persist_final_turn`

Sin tools complejas todavía.

## Fase 4. Port vertical realtor

Implementar subflows del vertical realtor:

- `realtor_plan`
- `realtor_tool_dispatch`
- `realtor_answer_synthesis`
- `generic_answer`
- `generic_rag`
- `workflow` si queda habilitado

Debe quedar feature-complete contra v2 antes de seguir.

## Fase 5. Port vertical generic

Implementar subflows del vertical generic:

- `generic_answer`
- `generic_rag_plan`
- `semantic_retrieval`
- `generic_answer_synthesis`

## Fase 6. Workflow tools

Agregar:

- calendar
- email
- MCP

como tools nuevas, no como ifs dentro del core.

## Fase 7. Canary y cutover

- bridges apuntan primero a `v2` por default
- activar `v3` por tenant o canal de prueba
- comparar:
  - latencia
  - coherencia
  - errores de tool call
  - necesidad de aclaraciones

## Fase 8. Decomission parcial de v2

Cuando `v3` absorba generic + realtor:

- `v2` queda en mantenimiento
- se retira lógica de orquestación duplicada

## 16. Criterios de aceptación

`inference-core-v3` estará listo cuando:

1. un solo agente decida todo el turno
2. ningún bridge reinterprete la respuesta
3. SQL, RAG y vectores puedan convivir en un mismo turno de forma coherente
4. agregar una nueva tool no requiera reescribir el orquestador central
5. la memoria conversacional viva sea consistente
6. la conversación persistida coincida exactamente con lo que vio el usuario
7. planner y synthesis usen structured output donde corresponda
8. la observabilidad permita entender por qué el agente hizo lo que hizo
9. el vertical se resuelva determinísticamente desde `client_id`, nunca por LLM

## 17. Anti-patrones prohibidos en v3

- volver a meter lógica de negocio en bridges
- tools que redactan copy
- parseo libre de JSON del LLM cuando exista structured output
- dos fuentes de verdad para memoria conversacional
- heurística hardcodeada para intent o continuidad
- side-effects bloqueando la respuesta principal
- persistir una respuesta distinta a la mostrada

## 18. Resumen ejecutivo

La arquitectura v3 correcta es:

- `LangGraph` para orquestación
- estado tipado
- tools tipadas
- ejecutores determinísticos
- synthesis final centralizada
- persistencia única por turno
- bridges tontos

La inteligencia vive en un solo lugar.
Todo lo demás ejecuta o transporta.
